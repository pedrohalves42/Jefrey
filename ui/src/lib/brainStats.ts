import { authedFetch } from "@/lib/session"

export type RawStat = { n: number; ok: number; median: number | null }
export type StatRow = { model: string; n: number; failPct: number; median: number | null }
export const MIN_CALLS = 5 // igual ao servidor: abaixo disso a ordem ainda nao muda pelo desempenho

/** As chaves vem como "provedor|modelo|endereco"; a tela mostra pelo modelo. Mais rapido primeiro; sem medida, por ultimo. */
export function toRows(brains: Record<string, RawStat>): StatRow[] {
  return Object.entries(brains)
    .map(([key, s]) => ({ model: key.split("|")[1] ?? key, n: s.n, failPct: s.n ? Math.round(((s.n - s.ok) / s.n) * 100) : 0, median: s.median }))
    .sort((a, b) => (a.median ?? Infinity) - (b.median ?? Infinity))
}

export function statLine(r: StatRow): string {
  if (r.n < MIN_CALLS) return `${r.n} ${r.n === 1 ? "uso" : "usos"}: ainda medindo (preciso de ${MIN_CALLS})`
  const t = r.median === null ? "sem resposta" : `${r.median.toFixed(1).replace(".", ",")} s`
  return `${r.n} usos · ${r.failPct}% de falhas · responde em ${t}`
}

export async function getBrainStats(role = "conversa"): Promise<StatRow[]> {
  try {
    const r = await authedFetch(`/brains/metrics?role=${encodeURIComponent(role)}`)
    return r.ok ? toRows(((await r.json()) as { brains?: Record<string, RawStat> }).brains ?? {}) : []
  } catch {
    return []
  }
}
