import { useCallback, useEffect, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { change, getTodayCached, money, points, resetTodayCache, saveRegion, spokenSummary, UFS, type NewsItem, type Quote, type TodayData } from "@/lib/today"
import { getProfile } from "@/lib/llm"
import { Count, ForYou, LiveHeader, Ticker } from "@/components/TodayLive"

const h2 = "text-lg font-medium text-white"

function Card({ title, children, status, wide = false }: { title: string; children: ReactNode; status?: string; wide?: boolean }) {
  return (
    <section className={`jf-panel p-5 ${wide ? "md:col-span-2" : ""}`} aria-label={title}>
      <h2 className={h2}>{title}</h2>
      {status === "erro" ? <p className="mt-3 text-base text-white/60">Não consegui buscar agora. Tento de novo daqui a pouco.</p> : <div className="mt-3">{children}</div>}
    </section>
  )
}

function News({ items }: { items: NewsItem[] }) {
  if (!items.length) return <p className="text-base text-white/60">Nada por enquanto.</p>
  return (
    <ul className="space-y-3">
      {items.map(n => (
        <li key={n.link}>
          <a href={n.link} target="_blank" rel="noopener noreferrer" className="jf-focus text-base leading-snug text-white/90 underline-offset-2 hover:underline">{n.title}</a>
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
      <span className="text-white"><Count value={q.value} fmt={fmt} /> <span className={c.tone === "up" ? "text-emerald-300" : c.tone === "down" ? "text-red-300" : "text-white/50"}>{c.text}</span></span>
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

/** Busca o painel (com cache de 5 min) e atualiza sozinho a cada 15 min. */
export function useToday() {
  const [d, setD] = useState<TodayData | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const load = useCallback(async (force = false) => {
    if (force) resetTodayCache()
    setBusy(true)
    const r = await getTodayCached(force)
    if (r.data) {
      setD(r.data)
      setFailed(false)
    } else setFailed(true)
    setBusy(false)
  }, [])
  useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(true), 5 * 60 * 1000)
    const onVisible = () => {
      if (!document.hidden) void load(false) // volta para a janela: usa o cache de 5 min ou busca de novo
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      window.clearInterval(id)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [load])
  return { d, failed, busy, reload: () => load(true) }
}

/** Os cartoes do dia. Usado na pagina Hoje e no popup da tela principal. */
export function TodayCards({ d, reload, withForYou = false }: { d: TodayData; reload: () => void; withForYou?: boolean }) {
  const s = d.sections
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {withForYou && <ForYou items={s.foryou.items} status={s.foryou.status} onChanged={reload} />}
      <Card title="Tempo" status={s.weather.status}>
        {s.weather.status === "falta_regiao" ? (
          <>
            <p className="text-base text-white/75">Diga onde você mora para eu mostrar o tempo e as notícias da sua região.</p>
            <RegionForm onSaved={reload} />
          </>
        ) : (
          <p className="text-base leading-relaxed text-white/90"><span className="text-white/60">{s.weather.place}. </span>{s.weather.summary}</p>
        )}
      </Card>

      <Card title="Sua agenda e lembretes" status={s.agenda.status === "erro" && s.reminders.status === "erro" ? "erro" : undefined}>
        {s.agenda.status === "desconectado" && <p className="text-base text-white/60">Para ver sua agenda do Google, <Link className="underline" to="/conexoes?aba=google">conecte o Google</Link>.</p>}
        {s.agenda.items.length > 0 && (
          <ul className="space-y-1.5">{s.agenda.items.map((e, i) => <li key={i} className="text-base text-white/90">{e.time && <span className="text-white/60">{e.time} · </span>}{e.title}</li>)}</ul>
        )}
        {s.agenda.status === "ok" && s.agenda.items.length === 0 && <p className="text-base text-white/60">Nenhum compromisso hoje.</p>}
        {s.reminders.items.length > 0 && (
          <ul className="mt-3 space-y-1.5">{s.reminders.items.map((r, i) => <li key={i} className="text-base text-white/90">🔔 {r.text} <span className="text-white/50">({r.due_label})</span></li>)}</ul>
        )}
        {s.reminders.items.length === 0 && s.agenda.status !== "desconectado" && <p className="mt-2 text-base text-white/50">Sem lembretes pendentes.</p>}
      </Card>

      <Card title="Bolsa e câmbio" status={s.market.status}>
        <ul className="space-y-2">
          <Q label="Ibovespa" q={s.market.ibov} fmt={points} />
          <Q label="Dólar" q={s.market.usd} fmt={money} />
          <Q label="Euro" q={s.market.eur} fmt={money} />
          <Q label="Bitcoin" q={s.market.btc} fmt={money} />
        </ul>
        {s.market.status === "parcial" && <p className="mt-2 text-sm text-white/50">Alguns valores não chegaram agora.</p>}
      </Card>

      <Card title={d.region.city ? `Perto de você (${d.region.city})` : "Perto de você"} status={s.region.status}>
        {s.region.status === "falta_regiao" ? <p className="text-base text-white/60">Escolha sua cidade no cartão “Tempo”.</p> : <News items={s.region.items} />}
      </Card>

      <Card title="Principais notícias" status={s.news.status}><News items={s.news.items} /></Card>
      <Card title="Economia" status={s.economy.status}><News items={s.economy.items} /></Card>
    </div>
  )
}

export function TodayFooter({ d }: { d: TodayData }) {
  return <p className="text-sm text-white/40">Atualizado às {d.generated_at.slice(11, 16)}. Notícias do g1; câmbio e bolsa de fontes públicas. Nada seu é enviado para essas fontes, só o nome da cidade para o tempo.</p>
}

/** Pagina "Hoje". */
export default function Hoje() {
  const { d, failed, busy, reload } = useToday()
  const [name, setName] = useState<string | undefined>()
  useEffect(() => {
    void getProfile().then(r => setName(r.data?.display_name ?? undefined))
  }, [])
  return (
    <div className="mx-auto h-full max-w-5xl space-y-5 overflow-y-auto pb-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1"><LiveHeader name={name} generatedAt={d?.generated_at ?? ""} onRefresh={reload} busy={busy} /></div>
          {d && <ListenButton text={spokenSummary(d, name)} label="Ouvir o resumo" />}
        </div>
        {d && <Ticker d={d} />}
      </header>
      {failed && !d && <p role="alert" className="text-base text-red-200">Não consegui montar o painel agora. Verifique a internet.</p>}
      {!d && !failed && <p className="text-base text-white/60">Buscando as novidades…</p>}
      {d && <TodayCards d={d} reload={reload} withForYou />}
      {d && <TodayFooter d={d} />}
    </div>
  )
}
