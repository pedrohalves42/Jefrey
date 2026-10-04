/** Saudacao pelo horario. 5-11 bom dia, 12-17 boa tarde, resto boa noite. */
export function greeting(hour: number, name?: string | null): string {
  const h = Number.isFinite(hour) ? ((Math.floor(hour) % 24) + 24) % 24 : 12
  const base = h >= 5 && h < 12 ? "Bom dia" : h >= 12 && h < 18 ? "Boa tarde" : "Boa noite"
  const n = (name ?? "").trim()
  return n ? `${base}, ${n}.` : `${base}.`
}
