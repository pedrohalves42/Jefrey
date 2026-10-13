import { useEffect, useState } from "react"
import { dayStrip, getTodayCached } from "@/lib/today"

/** Uma linha com o essencial do dia (tempo, proximo compromisso, dolar) no lugar do cumprimento generico. Toque abre o painel Hoje. */
export default function DayStrip({ onOpen }: { onOpen: () => void }) {
  const [parts, setParts] = useState<string[]>([])
  useEffect(() => {
    let alive = true
    void getTodayCached().then(r => alive && r.data && setParts(dayStrip(r.data)))
    return () => {
      alive = false
    }
  }, [])
  if (!parts.length) return null
  return (
    <button type="button" onClick={onOpen} className="jf-focus jf-chip flex max-w-full flex-wrap items-center justify-center gap-x-4 gap-y-1 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-white/90" aria-label="Abrir o resumo do dia">
      {parts.map(p => <span key={p}>{p}</span>)}
      <span className="text-xs text-white/50">ver tudo ›</span>
    </button>
  )
}
