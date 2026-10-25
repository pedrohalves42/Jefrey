/**
 * Quem pode falar com o Jefrey pela voz. O microfone ouve o ambiente (TV, outras pessoas), entao so entra no chat:
 *  - a fala que COMECA chamando o Jefrey pelo nome ("Jefrey, ..."); ou
 *  - a fala logo depois de uma conversa com ele (janela curta, para responder sem repetir o nome).
 * O resto e descartado aqui, antes de chegar ao chat.
 */
export const WINDOW_MS = 45_000
const NAMES = ["jefrey", "jeffrey", "jefri", "jefre", "jeferi", "jefrei", "geferi", "jefery", "jeffri", "jeffery", "geffrey", "jefferi", "jefre"]
const LEAD = new Set(["oi", "ola", "e", "ai", "ei", "hey", "opa", "fala", "entao", "bom", "dia", "boa", "tarde", "noite", "eae", "ok", "olha", "escuta", "com", "licenca"])
const MAX_LEAD_WORDS = 3
const MIN_RATIO = 0.78

function plain(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

function ratio(a: string, b: string): number {
  if (a === b) return 1
  const m = a.length
  const n = b.length
  if (!m || !n) return 0
  let prev = Array.from({ length: n + 1 }, (_, j) => j)
  for (let i = 1; i <= m; i++) {
    const cur = [i]
    for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j]! + 1, cur[j - 1]! + 1, prev[j - 1]! + (a[i - 1] === b[j - 1] ? 0 : 1))
    prev = cur
  }
  return 1 - prev[n]! / Math.max(m, n)
}

/** O Whisper escreve o nome de varios jeitos ("Jeffrey", "Geferi", "Jéfri"): compara de forma aproximada. */
export function isName(word: string): boolean {
  const w = plain(word).replace(/[^a-z]/g, "")
  return w.length >= 4 && w.length <= 9 && NAMES.some(n => ratio(w, n) >= MIN_RATIO)
}

/** Dirigido ao Jefrey? O nome nas primeiras palavras (com ate 3 de "oi, bom dia, ei"), ou conversa aberta ha pouco. */
export function addressed(text: string, now: number, engagedAt: number): { ok: boolean; text: string } {
  const original = (text || "").trim()
  if (!original) return { ok: false, text: "" }
  const words = original.split(/\s+/)
  for (let i = 0; i <= Math.min(MAX_LEAD_WORDS, words.length - 1); i++) {
    if (i > 0 && !LEAD.has(plain(words[i - 1]!).replace(/[^a-z]/g, ""))) break
    if (isName(words[i]!)) {
      const rest = words.slice(i + 1).join(" ").replace(/^[\s,.;:!?-]+/, "").trim()
      return rest ? { ok: true, text: rest } : { ok: false, text: "" }
    }
  }
  if (engagedAt > 0 && now - engagedAt <= WINDOW_MS) return { ok: true, text: original }
  return { ok: false, text: "" }
}

/** Antes de gastar o Whisper: so transcreve o trecho que PODE ser para o Jefrey. Fora de uma conversa aberta, descarta o que e fraco
 *  (longe do microfone, como uma TV) ou longo demais (um programa falando). Nada do que foi descartado e enviado nem guardado. */
export const NEAR_FIELD_PEAK = 0.012 // so descarta o quase silencio: microfone de notebook costuma ter nivel baixo e a fala da pessoa NUNCA pode ser perdida aqui
export const MAX_UNADDRESSED_MS = 30_000
export const MIN_SEGMENT_MS = 250

export type Segment = { peak: number; durationMs: number }

export function worthTranscribing(seg: Segment, now: number, engagedAt: number): boolean {
  if (seg.durationMs < MIN_SEGMENT_MS) return false
  if (engagedAt > 0 && now - engagedAt <= WINDOW_MS) return true
  return seg.peak >= NEAR_FIELD_PEAK && seg.durationMs <= MAX_UNADDRESSED_MS
}
