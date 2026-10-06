import { useEffect, useRef, useState } from "react"
import { change, getInterests, money, points, saveInterests, type Interests, type NewsItem, type Quote, type TodayData } from "@/lib/today"

/** Numero que "corre" ate o valor novo e pisca verde/vermelho quando muda (a pagina parece viva, nao uma foto). */
export function Count({ value, fmt }: { value: number; fmt: (v: number) => string }) {
  const [shown, setShown] = useState(value)
  const [flash, setFlash] = useState<"" | "up" | "down">("")
  const prev = useRef(value)
  useEffect(() => {
    const from = prev.current
    if (from === value) return
    setFlash(value > from ? "up" : "down")
    const t0 = performance.now()
    let raf = 0
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / 700)
      setShown(from + (value - from) * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    prev.current = value
    const off = window.setTimeout(() => setFlash(""), 1500)
    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(off)
    }
  }, [value])
  return <span className={`rounded px-1 ${flash === "up" ? "jf-flash-up" : flash === "down" ? "jf-flash-down" : ""}`}>{fmt(shown)}</span>
}

/** Relogio e data ao vivo + "atualizado ha N min" que conta sozinho. */
export function LiveHeader({ name, generatedAt, onRefresh, busy }: { name?: string; generatedAt: string; onRefresh: () => void; busy: boolean }) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const h = now.getHours()
  const hello = h < 5 ? "Boa madrugada" : h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite"
  const date = now.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })
  const at = generatedAt ? new Date(generatedAt) : null
  const mins = at && !Number.isNaN(at.getTime()) ? Math.max(0, Math.floor((now.getTime() - at.getTime()) / 60000)) : null
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-base text-cyan-200">{hello}{name ? `, ${name}` : ""}!</p>
        <p className="font-mono text-5xl font-semibold tabular-nums tracking-wide text-white">{now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</p>
        <p className="text-base capitalize text-white/60">{date}</p>
      </div>
      <button type="button" onClick={onRefresh} disabled={busy} className="jf-focus jf-chip flex items-center gap-2 rounded-full border border-white/20 bg-black/30 px-4 py-2 text-sm text-white/80" aria-label="Atualizar agora">
        <span className={busy ? "inline-block animate-spin" : "inline-block"} aria-hidden="true">⟳</span>
        {busy ? "Atualizando…" : mins === null ? "Atualizar" : mins < 1 ? "Atualizado agora" : `Atualizado há ${mins} min`}
      </button>
    </div>
  )
}

/** Faixa de cotacoes que corre devagar (para ao passar o mouse). */
export function Ticker({ d }: { d: TodayData }) {
  const m = d.sections.market
  const items: { label: string; q?: Quote; fmt: (v: number) => string }[] = [
    { label: "Ibovespa", q: m.ibov, fmt: points }, { label: "Dólar", q: m.usd, fmt: money }, { label: "Euro", q: m.eur, fmt: money }, { label: "Bitcoin", q: m.btc, fmt: money },
  ]
  const shown = items.filter(i => i.q)
  if (!shown.length) return null
  const row = shown.map(i => {
    const c = change(i.q!.pct)
    const tone = c.tone === "up" ? "text-emerald-300" : c.tone === "down" ? "text-red-300" : "text-white/50"
    return (
      <span key={i.label} className="flex items-baseline gap-2 whitespace-nowrap px-6 text-base">
        <span className="text-white/60">{i.label}</span>
        <span className="text-white"><Count value={i.q!.value} fmt={i.fmt} /></span>
        <span className={tone}>{c.text}</span>
      </span>
    )
  })
  return (
    <div className="jf-panel overflow-hidden py-2.5" aria-label="Cotações" role="group">
      <div className="jf-ticker">
        <div className="flex">{row}</div>
        <div className="flex" aria-hidden="true">{row}</div>
      </div>
    </div>
  )
}

/** Escolha dos assuntos: marcar/desmarcar salva na hora. */
function InterestPicker({ onChanged }: { onChanged: () => void }) {
  const [it, setIt] = useState<Interests | null>(null)
  useEffect(() => {
    void getInterests().then(r => setIt(r.data))
  }, [])
  if (!it) return null
  async function toggle(id: string) {
    if (!it) return
    const on = it.selected.includes(id)
    if (!on && it.selected.length >= it.max) return
    const next = on ? it.selected.filter(x => x !== id) : [...it.selected, id]
    setIt({ ...it, selected: next })
    await saveInterests(next)
    onChanged()
  }
  return (
    <div>
      <p className="text-sm text-white/60">Escolha até {it.max} assuntos. O Jefrey só traz notícias do que você marcar.</p>
      {(it.suggested?.length ?? 0) > 0 && (
        <p className="mt-2 text-sm text-cyan-100">
          Pelo que aprendi de você, talvez goste de:{" "}
          {it.suggested!.slice(0, 4).map(id => {
            const o = it.options.find(x => x.id === id)
            return o ? (
              <button key={id} type="button" onClick={() => void toggle(id)} className="jf-focus mr-2 underline underline-offset-2 hover:text-white">+ {o.label}</button>
            ) : null
          })}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        {it.options.map(o => {
          const on = it.selected.includes(o.id)
          const full = !on && it.selected.length >= it.max
          return (
            <button key={o.id} type="button" aria-pressed={on} disabled={full} onClick={() => void toggle(o.id)}
              className={`jf-focus jf-chip rounded-full border px-3 py-1.5 text-sm ${on ? "border-cyan-300/70 bg-cyan-400/20 text-white" : "border-white/20 bg-black/30 text-white/75"} ${full ? "opacity-40" : ""}`}>
              {on ? "✓ " : ""}{o.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** "Para voce": a manchete em destaque troca sozinha (8 s, com barrinha); a lista ao lado mostra as proximas. */
export function ForYou({ items, status, onChanged }: { items: NewsItem[]; status: string; onChanged: () => void }) {
  const [i, setI] = useState(0)
  const [paused, setPaused] = useState(false)
  const [editing, setEditing] = useState(status === "sem_interesses")
  useEffect(() => {
    if (paused || items.length < 2) return
    const id = window.setTimeout(() => setI(x => (x + 1) % items.length), 8000)
    return () => window.clearTimeout(id)
  }, [i, paused, items.length])
  useEffect(() => {
    if (i >= items.length) setI(0)
  }, [items.length, i])
  const cur = items[i]
  return (
    <section className="jf-panel jf-rise p-5 md:col-span-2" aria-label="Para você" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium text-white">Para você</h2>
        <button type="button" onClick={() => setEditing(v => !v)} className="jf-focus text-sm text-cyan-200 underline underline-offset-2">{editing ? "Fechar" : "Escolher meus assuntos"}</button>
      </div>
      {editing && <div className="mt-3"><InterestPicker onChanged={onChanged} /></div>}
      {!editing && status === "sem_interesses" && <p className="mt-3 text-base text-white/70">Marque os assuntos que te interessam e eu trago só isso.</p>}
      {!editing && status === "erro" && <p className="mt-3 text-base text-white/60">Não consegui buscar agora. Tento de novo daqui a pouco.</p>}
      {cur && (
        <div className="mt-4 grid gap-4 md:grid-cols-[1.4fr_1fr]">
          <div key={cur.link} className="jf-fade">
            {cur.topic && <span className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs font-medium text-cyan-100">{cur.topic}</span>}
            <a href={cur.link} target="_blank" rel="noopener noreferrer" className="jf-focus mt-3 block text-2xl font-semibold leading-snug text-white hover:underline">{cur.title}</a>
            {items.length > 1 && !paused && <div className="mt-4 h-1 overflow-hidden rounded bg-white/10"><div key={`${cur.link}-${i}`} className="jf-progress h-full bg-cyan-300/70" /></div>}
          </div>
          <ul className="space-y-1.5" aria-label="Próximas">
            {items.map((n, k) => (
              <li key={n.link}>
                <button type="button" onClick={() => setI(k)} aria-current={k === i} className={`jf-focus w-full rounded-lg px-3 py-2 text-left text-sm leading-snug ${k === i ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5"}`}>
                  {n.topic && <span className="mr-2 text-xs text-cyan-200/80">{n.topic}</span>}{n.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
