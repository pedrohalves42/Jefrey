import { useEffect, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { change, getToday, money, points, saveRegion, spokenSummary, UFS, type NewsItem, type Quote, type TodayData } from "@/lib/today"
import { getProfile } from "@/lib/llm"

const card = "jf-panel p-5"
const h2 = "text-lg font-medium text-white"

function Card({ title, children, status }: { title: string; children: ReactNode; status?: string }) {
  return (
    <section className={card} aria-label={title}>
      <h2 className={h2}>{title}</h2>
      {status === "erro" ? <p className="mt-2 text-base text-white/60">Não consegui buscar agora. Tento de novo daqui a pouco.</p> : children}
    </section>
  )
}

function News({ items }: { items: NewsItem[] }) {
  if (!items.length) return <p className="mt-2 text-base text-white/60">Nada por enquanto.</p>
  return (
    <ul className="mt-2 space-y-2">
      {items.map(n => (
        <li key={n.link}>
          <a href={n.link} target="_blank" rel="noopener noreferrer" className="jf-focus text-base text-white/90 underline-offset-2 hover:underline">{n.title}</a>
        </li>
      ))}
    </ul>
  )
}

function Q({ label, q, fmt }: { label: string; q?: Quote; fmt: (v: number) => string }) {
  if (!q) return null
  const c = change(q.pct)
  return (
    <li className="flex items-baseline justify-between gap-3 text-base">
      <span className="text-white/70">{label}</span>
      <span className="text-white">{fmt(q.value)} <span className={c.tone === "up" ? "text-emerald-300" : c.tone === "down" ? "text-red-300" : "text-white/50"}>{c.text}</span></span>
    </li>
  )
}

function RegionForm({ onSaved }: { onSaved: () => void }) {
  const [city, setCity] = useState("")
  const [uf, setUf] = useState("SP")
  const [err, setErr] = useState("")
  async function save() {
    setErr("")
    const r = await saveRegion(city, uf)
    if (r.ok) onSaved()
    else setErr(((r.data as { detail?: unknown } | null)?.detail as string) || "Não consegui guardar agora.")
  }
  return (
    <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void save() }}>
      <label className="text-base text-white/85">Sua cidade
        <input className="mt-1 block rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white" value={city} onChange={e => setCity(e.target.value)} placeholder="Ex.: São Paulo" />
      </label>
      <label className="text-base text-white/85">Estado
        <select className="mt-1 block rounded-lg border border-white/15 bg-black/60 px-3 py-3 text-base text-white" value={uf} onChange={e => setUf(e.target.value)}>
          {UFS.map(u => <option key={u} value={u}>{u}</option>)}
        </select>
      </label>
      <button type="submit" disabled={!city.trim()} className="jf-btn jf-focus px-5 py-3 text-base">Guardar</button>
      {err && <p role="alert" className="w-full text-base text-red-200">{err}</p>}
    </form>
  )
}

/** "Hoje": o que importa agora (clima, agenda, lembretes, notícias, bolsa e a sua região), em vez de um painel técnico. */
export default function Hoje() {
  const [d, setD] = useState<TodayData | null>(null)
  const [failed, setFailed] = useState(false)
  const [name, setName] = useState<string | undefined>()

  async function load() {
    const r = await getToday()
    if (r.data) {
      setD(r.data)
      setFailed(false)
    } else setFailed(true)
  }
  useEffect(() => {
    void load()
    void getProfile().then(r => setName(r.data?.display_name ?? undefined))
    const id = window.setInterval(() => void load(), 15 * 60 * 1000)
    return () => window.clearInterval(id)
  }, [])

  const s = d?.sections
  return (
    <div className="mx-auto h-full max-w-5xl space-y-4 overflow-y-auto pb-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Hoje</h1>
          <p className="text-base text-white/60">O que importa agora, num lugar só.</p>
        </div>
        {d && <ListenButton text={spokenSummary(d, name)} />}
      </header>

      {failed && !d && <p role="alert" className="text-base text-red-200">Não consegui montar o painel agora. Verifique a internet.</p>}
      {!d && !failed && <p className="text-base text-white/60">Buscando as novidades…</p>}

      {s && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Tempo" status={s.weather.status}>
            {s.weather.status === "falta_regiao" ? (
              <>
                <p className="mt-2 text-base text-white/75">Diga onde você mora para eu mostrar o tempo e as notícias da sua região.</p>
                <RegionForm onSaved={() => void load()} />
              </>
            ) : (
              <p className="mt-2 text-base text-white/90"><span className="text-white/60">{s.weather.place}. </span>{s.weather.summary}</p>
            )}
          </Card>

          <Card title="Sua agenda e lembretes" status={s.agenda.status === "erro" && s.reminders.status === "erro" ? "erro" : undefined}>
            {s.agenda.status === "desconectado" && <p className="mt-2 text-base text-white/60">Para ver sua agenda do Google, <Link className="underline" to="/conexoes?aba=google">conecte o Google</Link>.</p>}
            {s.agenda.items.length > 0 && (
              <ul className="mt-2 space-y-1">{s.agenda.items.map((e, i) => <li key={i} className="text-base text-white/90">{e.time && <span className="text-white/60">{e.time} · </span>}{e.title}</li>)}</ul>
            )}
            {s.agenda.status === "ok" && s.agenda.items.length === 0 && <p className="mt-2 text-base text-white/60">Nenhum compromisso hoje.</p>}
            {s.reminders.items.length > 0 && (
              <ul className="mt-3 space-y-1">{s.reminders.items.map((r, i) => <li key={i} className="text-base text-white/90">🔔 {r.text} <span className="text-white/50">({r.due_label})</span></li>)}</ul>
            )}
            {s.reminders.items.length === 0 && s.agenda.status !== "desconectado" && <p className="mt-2 text-base text-white/50">Sem lembretes pendentes.</p>}
          </Card>

          <Card title="Bolsa e câmbio" status={s.market.status}>
            <ul className="mt-2 space-y-1.5">
              <Q label="Ibovespa" q={s.market.ibov} fmt={points} />
              <Q label="Dólar" q={s.market.usd} fmt={money} />
              <Q label="Euro" q={s.market.eur} fmt={money} />
              <Q label="Bitcoin" q={s.market.btc} fmt={money} />
            </ul>
            {s.market.status === "parcial" && <p className="mt-2 text-sm text-white/50">Alguns valores não chegaram agora.</p>}
          </Card>

          <Card title={d?.region.city ? `Perto de você (${d.region.city})` : "Perto de você"} status={s.region.status}>
            {s.region.status === "falta_regiao" ? <p className="mt-2 text-base text-white/60">Escolha sua cidade no cartão “Tempo”.</p> : <News items={s.region.items} />}
          </Card>

          <Card title="Principais notícias" status={s.news.status}><News items={s.news.items} /></Card>
          <Card title="Economia" status={s.economy.status}><News items={s.economy.items} /></Card>
        </div>
      )}
      {d && <p className="text-sm text-white/40">Atualizado às {d.generated_at.slice(11, 16)}. Notícias do g1; câmbio e bolsa de fontes públicas. Nada seu é enviado para essas fontes, só o nome da cidade para o tempo.</p>}
    </div>
  )
}
