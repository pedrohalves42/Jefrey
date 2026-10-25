/** Lembrete falado que repete ate a pessoa dizer "ok" (REGRAS PURAS, sem relogio proprio). */

export const REPEAT_EVERY_MS = 5 * 60_000
export const MAX_SPOKEN = 3
export const QUIET_FROM = 22 // 22h as 8h: silencio
export const QUIET_TO = 8

export type NagState = { spoken: number; lastAt: number | null }

export function isQuietHour(hour: number): boolean {
  return hour >= QUIET_FROM || hour < QUIET_TO
}

/** Deve falar agora? Primeira vez assim que aparece; depois a cada 5 min, no maximo 3 vezes, nunca em horario de silencio. */
export function shouldSpeak(s: NagState, nowMs: number, hour: number): boolean {
  if (isQuietHour(hour) || s.spoken >= MAX_SPOKEN) return false
  return s.lastAt === null || nowMs - s.lastAt >= REPEAT_EVERY_MS
}

export function spokenText(text: string, attempt: number): string {
  return attempt === 0 ? `Lembrete: ${text}.` : `Só reforçando: ${text}. Quando quiser, diga ok ou toque em Ok.`
}
