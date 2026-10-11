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
