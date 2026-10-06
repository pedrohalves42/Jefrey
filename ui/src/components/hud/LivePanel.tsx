import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { change, getTodayCached, money, points, type Quote, type TodayData } from "@/lib/today"

function Row({ label, q, fmt }: { label: string; q?: Quote; fmt: (v: number) => string }) {
  if (!q) return null
  const c = change(q.pct)
  return (
    <li className="flex justify-between text-[11px] text-white/70">
      <span>{label}</span>
      <span className="text-white">{fmt(q.value)} <span className={c.tone === "up" ? "text-emerald-300" : c.tone === "down" ? "text-red-300" : "text-white/50"}>{c.text}</span></span>
    </li>
  )
}

/** Paineis do HUD com informacao UTIL e viva (tempo, bolsa, proximo compromisso), no lugar de status tecnico. So aparece em telas largas. */
export function LivePanel() {
  const [d, setD] = useState<TodayData | null>(null)
  useEffect(() => {
    let alive = true
    const load = () => void getTodayCached().then(r => alive && r.data && setD(r.data))
    load()
    const id = window.setInterval(load, 10 * 60 * 1000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])
  if (!d) return null
  const s = d.sections
  const next = s.agenda.items[0]
  return (
    <>
      <section className="jf-hudpanel jf-glass absolute left-3 top-14 z-10 hidden w-56 xl:block" aria-label="Agora">
        <h3 className="mb-2 text-[10px] uppercase tracking-[0.28em] text-[hsl(var(--hue)_80%_72%)]">Agora</h3>
        {s.weather.status === "ok" ? <p className="mb-2 text-xs leading-snug text-white/90">{s.weather.summary}</p> : s.weather.status === "falta_regiao" ? <p className="mb-2 text-xs text-white/60"><Link className="underline" to="/hoje">Escolha sua cidade</Link> para ver o tempo.</p> : null}
        <ul className="space-y-1">
          <Row label="Dólar" q={s.market.usd} fmt={money} />
          <Row label="Ibovespa" q={s.market.ibov} fmt={points} />
        </ul>
      </section>
      <section className="jf-hudpanel jf-glass absolute right-3 top-14 z-10 hidden w-56 xl:block" aria-label="Próximo">
        <h3 className="mb-2 text-[10px] uppercase tracking-[0.28em] text-[hsl(var(--hue)_80%_72%)]">Próximo</h3>
        {next ? <p className="text-xs text-white/90">{next.time && <span className="text-white/60">{next.time} · </span>}{next.title}</p>
          : s.reminders.items[0] ? <p className="text-xs text-white/90">🔔 {s.reminders.items[0].text} <span className="text-white/50">({s.reminders.items[0].due_label})</span></p>
          : <p className="text-xs text-white/55">Nada marcado por enquanto.</p>}
        {s.news.items[0] && <a href={s.news.items[0].link} target="_blank" rel="noopener noreferrer" className="jf-focus mt-2 block text-[11px] leading-snug text-white/65 underline-offset-2 hover:underline">📰 {s.news.items[0].title}</a>}
      </section>
    </>
  )
}
