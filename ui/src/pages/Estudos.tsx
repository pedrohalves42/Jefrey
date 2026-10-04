import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import {
  addTopic, apiMessage, BUDGET_CHOICES, budgetPercent, deleteTopic, getGuide, getStudies, hourLabel, lastStudied, levelDots, parseGuide, putPrefs,
  runStudy, safeHref, setTopicStatus, sourceLabel, suggestTopics, usd, type Guide, type Overview, type Topic,
} from "@/lib/studies"

const card = "jf-panel p-5"
const btn = "jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5"
const field = "rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white"
const HOURS = Array.from({ length: 24 }, (_, i) => i)

type Msg = { ok: boolean; text: string } | null

function GuideView({ g, onClose }: { g: Guide; onClose: () => void }) {
  const blocks = parseGuide(g.body)
  return (
    <section className={`${card} border border-cyan-400/30`} aria-label={`Guia: ${g.title}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold text-white">{g.title}</h2>
          <p className="text-sm text-white/60">Nível: {g.level_label}</p>
        </div>
        <div className="flex gap-2">
          <ListenButton text={`${g.title}. ${blocks.map(b => b.text).join(" ")}`} />
          <button type="button" onClick={onClose} className={btn}>Fechar</button>
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {blocks.map((b, i) =>
          b.type === "h" ? <h3 key={i} className="pt-2 text-lg font-medium text-white">{b.text}</h3>
          : <p key={i} className={`text-base text-white/85 ${b.type === "li" ? "pl-3" : ""}`}>{b.text}</p>,
        )}
      </div>
      {g.sources.length > 0 && (
        <div className="mt-4 border-t border-white/10 pt-3">
          <h3 className="text-lg font-medium text-white">De onde tirei isso</h3>
          <ul className="mt-2 space-y-1 text-base text-white/80">
            {g.sources.map((s, i) => {
              const href = safeHref(s.url)
              return (
                <li key={i}>
                  {href ? <a className="underline" href={href} target="_blank" rel="noopener noreferrer">{s.title || href}</a> : s.title}
                  <span className="text-white/50"> · lido em {s.date}</span>
                </li>
              )
            })}
          </ul>
          <p className="mt-2 text-sm text-white/55">Confira as fontes antes de decidir algo importante. Eu posso errar.</p>
        </div>
      )}
    </section>
  )
}

export default function Estudos() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [title, setTitle] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [guide, setGuide] = useState<Guide | null>(null)

  async function load() {
    const r = await getStudies()
    if (r.data) setOv(r.data)
  }
  useEffect(() => {
    void load()
  }, [])

  async function add() {
    if (title.trim().length < 3) return
    const r = await addTopic(title.trim())
    if (r.ok) {
      setTitle("")
      setMsg({ ok: true, text: "Anotado. Eu estudo esse assunto quando você estiver longe do computador." })
    } else setMsg({ ok: false, text: apiMessage(r) })
    await load()
  }

  async function suggest() {
    const r = await suggestTopics()
    const n = r.data?.added.length ?? 0
    setMsg(r.ok ? { ok: true, text: n ? `Escolhi ${n} assunto${n > 1 ? "s" : ""} pelo que sei de você.` : "Ainda não achei assuntos novos. Converse mais comigo!" } : { ok: false, text: apiMessage(r) })
    await load()
  }

  async function study(t: Topic) {
    setBusy(t.id)
    setMsg({ ok: true, text: `Estudando "${t.title}"… isso pode levar um minuto.` })
    const r = await runStudy(t.id)
    setBusy(null)
    if (r.ok && r.data) {
      setGuide(r.data)
      setMsg({ ok: true, text: "Terminei! O guia está logo abaixo." })
    } else setMsg({ ok: false, text: apiMessage(r, "Não consegui estudar agora. Tente de novo mais tarde.") })
    await load()
  }

  async function open(t: Topic) {
    const r = await getGuide(t.id)
    if (r.ok && r.data) setGuide(r.data)
    else setMsg({ ok: false, text: apiMessage(r, "Ainda não estudei esse assunto.") })
  }

  async function toggle(t: Topic) {
    const r = await setTopicStatus(t.id, t.status === "active" ? "paused" : "active")
    if (!r.ok) setMsg({ ok: false, text: apiMessage(r) })
    await load()
  }

  async function remove(t: Topic) {
    await deleteTopic(t.id)
    if (guide && guide.title && ov?.topics.find(x => x.id === t.id)) setGuide(null)
    await load()
  }

  async function prefs(p: Parameters<typeof putPrefs>[0]) {
    const r = await putPrefs(p)
    if (!r.ok) setMsg({ ok: false, text: apiMessage(r) })
    await load()
  }

  const intro = "Quando você está longe do computador, eu estudo sozinho os assuntos que combinam com você e escrevo guias práticos, com as fontes. Você escolhe o que eu estudo e quanto posso gastar."
  const p = ov?.prefs
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Estudos</h1>
        <p className="mt-1 text-base text-white/70">{intro}</p>
        <div className="mt-3"><ListenButton text={intro} /></div>
      </header>

      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>
          {msg.text}
        </p>
      )}

      {ov && !ov.cloud_ready && (
        <section className={`${card} border border-amber-400/40`}>
          <p className="text-base text-amber-100">
            Para estudar bem eu preciso estar ligado à inteligência na nuvem. <Link className="underline" to="/conexoes">Ligar agora</Link>.
          </p>
        </section>
      )}

      {guide && <GuideView g={guide} onClose={() => setGuide(null)} />}

      <section className={card} aria-labelledby="e-add">
        <h2 id="e-add" className="text-xl font-medium text-white">Incluir um assunto</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input className={`${field} min-w-0 flex-1`} value={title} maxLength={80} placeholder="Ex.: cuidar de orquídeas" aria-label="Assunto" onChange={e => setTitle(e.target.value)} onKeyDown={e => e.key === "Enter" && void add()} />
          <button type="button" onClick={() => void add()} disabled={title.trim().length < 3} className="jf-btn jf-focus px-5 py-3 text-base">Incluir</button>
        </div>
        <button type="button" onClick={() => void suggest()} className={`${btn} mt-3`}>Escolher pelo que sei de você</button>
      </section>

      <section className={card} aria-labelledby="e-list">
        <h2 id="e-list" className="text-xl font-medium text-white">O que estou estudando</h2>
        {ov && ov.topics.length === 0 && <p className="mt-2 text-base text-white/70">Ainda nenhum assunto. Inclua um acima ou peça para eu escolher.</p>}
        <ul className="mt-3 space-y-3">
          {ov?.topics.map(t => (
            <li key={t.id} className="rounded-lg border border-white/10 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-lg text-white">{t.title}</p>
                <span className="flex items-center gap-1" role="img" aria-label={`Nível ${t.level_label}`}>
                  {levelDots(t.level).map((on, i) => <span key={i} className={`h-3 w-3 rounded-full ${on ? "bg-cyan-300" : "bg-white/15"}`} />)}
                </span>
              </div>
              <p className="text-sm text-white/60">
                {t.level_label} · {sourceLabel(t.source)} · {lastStudied(t.last_studied_at)}{t.status === "paused" ? " · em pausa" : ""}
              </p>
              {t.last_error && <p className="mt-1 text-sm text-amber-200">{t.last_error}</p>}
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => void study(t)} disabled={busy !== null} className="jf-btn jf-focus px-4 py-2 text-base">
                  {busy === t.id ? "Estudando…" : "Estudar agora"}
                </button>
                {t.guides > 0 && <button type="button" onClick={() => void open(t)} className={btn}>Ver o guia</button>}
                <button type="button" onClick={() => void toggle(t)} className={btn}>{t.status === "active" ? "Pausar" : "Retomar"}</button>
                <button type="button" onClick={() => void remove(t)} className="jf-focus rounded-lg border border-red-300/40 px-4 py-2 text-base text-red-100 hover:bg-red-400/10">Apagar</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {p && ov && (
        <section className={card} aria-labelledby="e-prefs">
          <h2 id="e-prefs" className="text-xl font-medium text-white">Quanto posso gastar</h2>
          <p className="mt-1 text-base text-white/70">Os estudos usam a inteligência da nuvem, que cobra por uso. Eu paro quando chegar no limite do dia.</p>
          <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-white/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={budgetPercent(ov.spent_today, p.budget_usd)}>
            <div className="h-full bg-cyan-400" style={{ width: `${budgetPercent(ov.spent_today, p.budget_usd)}%` }} />
          </div>
          <p className="mt-1 text-sm text-white/60">Hoje: {usd(ov.spent_today)} de {usd(p.budget_usd)}</p>
          <div className="mt-3 flex flex-wrap gap-4">
            <label className="text-base text-white/85">
              Limite por dia
              <select className={`${field} ml-2`} value={p.budget_usd} onChange={e => void prefs({ budget_usd: Number(e.target.value) })}>
                {[...new Set([...BUDGET_CHOICES, p.budget_usd])].sort((a, b) => a - b).map(v => <option key={v} value={v}>{usd(v)}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-base text-white/85">
              <input type="checkbox" className="h-5 w-5" checked={p.enabled} onChange={e => void prefs({ enabled: e.target.checked })} />
              Estudar sozinho
            </label>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-base text-white/85">
            Não estudar entre
            <select className={field} aria-label="Início do silêncio" value={p.quiet_start} onChange={e => void prefs({ quiet_start: Number(e.target.value) })}>
              {HOURS.map(h => <option key={h} value={h}>{hourLabel(h)}</option>)}
            </select>
            e
            <select className={field} aria-label="Fim do silêncio" value={p.quiet_end} onChange={e => void prefs({ quiet_end: Number(e.target.value) })}>
              {HOURS.map(h => <option key={h} value={h}>{hourLabel(h)}</option>)}
            </select>
          </div>
        </section>
      )}
    </div>
  )
}
