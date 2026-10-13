/** Nivel real da voz (0 a 1) para o avatar pulsar com o volume de verdade. */

let source: (() => number) | null = null

export function setLevelSource(fn: (() => number) | null): void {
  source = fn
}

export function hasLevelSource(): boolean {
  return source !== null
}

/** 0 quando nao ha audio medido (voz do navegador: ai o pulso usa as palavras). */
export function currentLevel(): number {
  try {
    return source ? Math.max(0, Math.min(1, source())) : 0
  } catch {
    return 0
  }
}

/** RMS de uma janela de amostras do AnalyserNode (bytes 0..255 centrados em 128), ja suavizado para 0..1. */
export function rmsLevel(samples: ArrayLike<number>): number {
  if (!samples.length) return 0
  let sum = 0
  for (let i = 0; i < samples.length; i++) {
    const v = (samples[i] - 128) / 128
    sum += v * v
  }
  return Math.min(1, Math.sqrt(sum / samples.length) * 3) // a fala fica em ~0.1..0.3 de RMS: ganho para ocupar a faixa util
}

export type LevelMeter = { level(): number; stop(): void }

/** Mede o volume de um <audio> com WebAudio. Se o navegador nao permitir, devolve um medidor que sempre diz 0 (o pulso segue pelas palavras). */
export function createLevelMeter(audio: HTMLMediaElement): LevelMeter {
  try {
    const Ctx = (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext }).AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return { level: () => 0, stop: () => undefined }
    const ctx = new Ctx()
    const src = ctx.createMediaElementSource(audio)
    const an = ctx.createAnalyser()
    an.fftSize = 512
    src.connect(an)
    an.connect(ctx.destination)
    const buf = new Uint8Array(an.fftSize)
    return {
      level: () => {
        an.getByteTimeDomainData(buf)
        return rmsLevel(buf)
      },
      stop: () => {
        void ctx.close().catch(() => undefined)
      },
    }
  } catch {
    return { level: () => 0, stop: () => undefined }
  }
}
