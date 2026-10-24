/**
 * Quem pode falar com o Jefrey pela voz. O microfone ouve o ambiente (TV, outras pessoas), entao so entra no chat:
 *  - a fala que COMECA chamando o Jefrey pelo nome ("Jefrey, ..."); ou
 *  - a fala logo depois de uma conversa com ele (janela curta, para responder sem repetir o nome).
 * O resto e descartado aqui, antes de chegar ao chat.
 */
export const WINDOW_MS = 25_000
const WAKE = /^(?:oi|ola|e ai|hey|ei)?[\s,]*(?:jefrey|jefrei|jeffrey|jefri|jefre)\b[\s,!.?:-]*/i

function plain(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

export function addressed(text: string, now: number, engagedAt: number): { ok: boolean; text: string } {
  const original = (text || "").trim()
  if (!original) return { ok: false, text: "" }
  const m = plain(original).match(WAKE)
  if (m) {
    const rest = original.slice(m[0].length).trim()
    return rest ? { ok: true, text: rest } : { ok: false, text: "" }
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
