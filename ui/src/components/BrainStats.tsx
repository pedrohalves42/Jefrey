import { useEffect, useState } from "react"
import { getBrainStats, statLine, type StatRow } from "@/lib/brainStats"

/** Como cada cerebro se saiu nos ultimos 7 dias. O Jefrey usa isto para decidir quem responde primeiro. */
export default function BrainStats() {
  const [rows, setRows] = useState<StatRow[] | null>(null)
  useEffect(() => {
    // a funcao com mais medidas (conversa ou ferramentas) mostra melhor como cada cerebro se comporta
    void Promise.all([getBrainStats("conversa"), getBrainStats("ferramentas")]).then(([a, b]) => setRows(a.length >= b.length ? a : b))
  }, [])
  if (!rows?.length) return null
  return (
    <section className="mt-4 rounded-xl border border-white/10 p-3" aria-label="Desempenho dos cérebros">
      <h3 className="text-base font-medium text-white">Como cada cérebro está se saindo</h3>
      <p className="text-sm text-white/55">Nos últimos 7 dias. Quem responde mais rápido e erra menos passa a ir primeiro.</p>
      <ul className="mt-2 space-y-1 text-sm text-white/80">
        {rows.map(r => (
          <li key={r.model}>
            <span className="font-medium text-white">{r.model}</span>: {statLine(r)}
          </li>
        ))}
      </ul>
    </section>
  )
}
