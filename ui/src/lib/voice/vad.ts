export type VadEvent = "speech_start" | "speech_end" | "timeout" | null

export type VadOptions = {
  /** nivel RMS minimo (0-1) considerado fala, antes de ajustar ao ruido de fundo */
  threshold?: number
  /** fala precisa durar isso (ms) para contar como inicio (ignora estalos) */
  minSpeechMs?: number
  /** silencio (ms) depois da fala que encerra a captura */
  endSilenceMs?: number
  /** limite de duracao de uma fala (ms) */
  maxSpeechMs?: number
  /** se ninguem falar nesse tempo (ms), desiste */
  maxWaitMs?: number
}

const DEFAULTS: Required<VadOptions> = {
  threshold: 0.02,
  minSpeechMs: 150,
  endSilenceMs: 1200,
  maxSpeechMs: 30_000,
  maxWaitMs: 8_000,
}

/**
 * Detector de inicio e fim de fala por energia (RMS), com ruido de fundo adaptativo e histerese.
 * Puro: recebe (rms, agora) e devolve o evento; nao depende de audio nem de relogio.
 */
export class Endpointer {
  private o: Required<VadOptions>
  private state: "waiting" | "speaking" | "done" = "waiting"
  private floor = 0.005 // ruido de fundo estimado
  private aboveSince: number | null = null
  private belowSince: number | null = null
  private startedAt: number | null = null
  private speechStart: number | null = null

  constructor(opts: VadOptions = {}) {
    this.o = { ...DEFAULTS, ...opts }
  }

  private limit(): number {
    return Math.max(this.o.threshold, this.floor * 3)
  }

  get finished(): boolean {
    return this.state === "done"
  }

  get speaking(): boolean {
    return this.state === "speaking"
  }

  update(rms: number, now: number): VadEvent {
    if (this.state === "done") return null
    if (this.startedAt === null) this.startedAt = now
    const level = Number.isFinite(rms) ? Math.max(0, rms) : 0
    const limit = this.limit()

    if (this.state === "waiting") {
      if (level >= limit) {
        this.aboveSince ??= now
        if (now - this.aboveSince >= this.o.minSpeechMs) {
          this.state = "speaking"
          this.speechStart = this.aboveSince
          this.belowSince = null
          return "speech_start"
        }
      } else {
        this.aboveSince = null
        this.floor = this.floor * 0.95 + level * 0.05 // acompanha o ruido ambiente
      }
      if (now - this.startedAt >= this.o.maxWaitMs) {
        this.state = "done"
        return "timeout"
      }
      return null
    }

    // falando: histerese (fim so abaixo de 60% do limite)
    if (level < limit * 0.6) {
      this.belowSince ??= now
      if (now - this.belowSince >= this.o.endSilenceMs) {
        this.state = "done"
        return "speech_end"
      }
    } else {
      this.belowSince = null
    }
    if (this.speechStart !== null && now - this.speechStart >= this.o.maxSpeechMs) {
      this.state = "done"
      return "speech_end"
    }
    return null
  }
}
