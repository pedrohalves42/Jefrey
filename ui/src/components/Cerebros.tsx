import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import ListenButton from "@/components/ListenButton"
import { apiDetail, connectBrain, disconnectBrain, getBrains, makePrimary, roleOf, routingSummary, steps, type BrainCard, type BrainsState } from "@/lib/brains"
import { KEY_COST_NOTE } from "@/lib/keyGuide"
import { startOpenRouter } from "@/lib/llm"

const big = "jf-btn jf-focus px-5 py-3 text-base"
const soft = "jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/30"

type Msg = { ok: boolean; text: string } | null

function Role({ role }: { role: "principal" | "reserva" | null }) {
  if (!role) return <span className="rounded-full bg-white/10 px-3 py-1 text-sm text-white/60">Não conectado</span>
  return (
    <span className={`rounded-full px-3 py-1 text-sm ${role === "principal" ? "bg-emerald-400/15 text-emerald-200" : "bg-cyan-400/15 text-cyan-100"}`}>
      {role === "principal" ? "Principal" : "Reserva"}
    </span>
  )
}

function KeyFlow({ card, onDone, onMsg }: { card: BrainCard; onDone: (s: BrainsState) => void; onMsg: (m: Msg) => void }) {
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  async function go() {
    setBusy(true)
    onMsg(null)
    const r = await connectBrain(card.id, key)
    setBusy(false)
    if (r.ok && r.data) {
      setKey("")
      onMsg({ ok: true, text: `${card.name} conectado!` })
      onDone(r.data)
    } else onMsg({ ok: false, text: apiDetail(r, "Não consegui conectar agora. Tente de novo.") })
  }
  const text = `${steps(card.name).join(" ")} ${KEY_COST_NOTE}`
  return (
    <div className="mt-3 rounded-xl border border-white/10 p-4">
      <ol className="list-decimal space-y-2 pl-6 text-base text-white/85">
        {steps(card.name).map(s => <li key={s}>{s}</li>)}
      </ol>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <a href={card.key_url} target="_blank" rel="noopener noreferrer" className={`${big} inline-block`}>Abrir o site do {card.name}</a>
        <ListenButton text={text} />
      </div>
      <p className="mt-3 text-sm text-white/60">{KEY_COST_NOTE}</p>
      <label className="mt-3 block text-base text-white/85">
        Cole aqui o código que você copiou
        <input className={`${field} mt-1`} type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} />
      </label>
      <button type="button" onClick={() => void go()} disabled={busy} className={`${big} mt-3`}>{busy ? "Testando…" : "Conectar"}</button>
    </div>
  )
}

/** Cerebros do Jefrey: varios ao mesmo tempo; se um falhar, o proximo assume sozinho. */
export default function Cerebros() {
  const qc = useQueryClient()
  const [st, setSt] = useState<BrainsState | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)

  useEffect(() => {
    void getBrains().then(r => setSt(r.data))
  }, [])

  const names = Object.fromEntries((st?.catalog ?? []).map(c => [c.id, c.name]))
  const summary = routingSummary(st, names)

  function done(s: BrainsState) {
    setSt(s)
    setOpen(null)
    void qc.invalidateQueries({ queryKey: ["llm-config"] })
  }

  async function oneClick(c: BrainCard) {
    setBusy(c.id)
    setMsg(null)
    const err = await startOpenRouter()
    if (err) {
      setMsg({ ok: false, text: err })
      setBusy(null)
    }
  }

  async function local(c: BrainCard) {
    setBusy(c.id)
    setMsg(null)
    const r = await connectBrain(c.id)
    setBusy(null)
    if (r.ok && r.data) {
      setMsg({ ok: true, text: "Pronto: o Jefrey vai pensar neste computador." })
      done(r.data)
    } else setMsg({ ok: false, text: apiDetail(r, "Não consegui usar o modelo deste computador. Veja como preparar em “Bem-vindo”.") })
  }

  async function primary(c: BrainCard) {
    const r = await makePrimary(c.id)
    if (r.ok && r.data) {
      setMsg({ ok: true, text: `Agora o Jefrey pensa primeiro com ${c.name}.` })
      done(r.data)
    } else setMsg({ ok: false, text: apiDetail(r, "Não consegui mudar agora.") })
  }

  async function remove(c: BrainCard) {
    const r = await disconnectBrain(c.id)
    if (r.ok && r.data) {
      setMsg({ ok: true, text: `${c.name} desconectado. A chave foi apagada deste computador.` })
      done(r.data)
    } else setMsg({ ok: false, text: apiDetail(r, "Não consegui desconectar agora.") })
  }

  const intro = `Os cérebros fazem o Jefrey pensar e responder. Você pode conectar vários: ${summary}`
  return (
    <section className="jf-panel p-5" aria-labelledby="c-ia">
      <h2 id="c-ia" className="text-xl font-medium text-white">Cérebros do Jefrey</h2>
      <p className="mt-2 text-base text-white/75">{summary}</p>
      <p className="mt-1 text-sm text-white/55">Você paga direto ao serviço, só pelo que usar. O Jefrey nunca vê a sua senha.</p>
      <div className="mt-2"><ListenButton text={intro} /></div>
      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`mt-3 rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>{msg.text}</p>
      )}

      <ul className="mt-4 space-y-3">
        {(st?.catalog ?? []).map(c => {
          const role = roleOf(st, c.id)
          return (
            <li key={c.id} className={`rounded-xl border p-4 ${c.recommended && !role ? "border-cyan-400/40" : "border-white/10"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-lg text-white">{c.name}{c.recommended && !role && <span className="ml-2 text-sm text-cyan-300">recomendado</span>}</p>
                <Role role={role} />
              </div>
              <p className="mt-1 text-base text-white/65">{c.tagline}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {role ? (
                  <>
                    {role === "reserva" && <button type="button" onClick={() => void primary(c)} className={soft}>Usar como principal</button>}
                    {c.kind !== "local" && <button type="button" onClick={() => setOpen(open === c.id ? null : c.id)} className={soft}>Trocar o código</button>}
                    <button type="button" onClick={() => void remove(c)} className="jf-focus rounded-lg border border-red-300/40 px-4 py-2 text-base text-red-100 hover:bg-red-400/10">Desconectar</button>
                  </>
                ) : c.kind === "oneclick" ? (
                  <>
                    <button type="button" onClick={() => void oneClick(c)} disabled={busy !== null} className={big}>{busy === c.id ? "Abrindo o site…" : "Conectar com 1 clique"}</button>
                    <button type="button" onClick={() => setOpen(open === c.id ? null : c.id)} className={soft}>Já tenho um código</button>
                  </>
                ) : c.kind === "local" ? (
                  <>
                    <button type="button" onClick={() => void local(c)} disabled={busy !== null} className={big}>{busy === c.id ? "Preparando…" : "Usar neste computador"}</button>
                    <Link to="/bem-vindo" className={soft}>Como preparar</Link>
                  </>
                ) : (
                  <button type="button" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id} className={big}>
                    {open === c.id ? "Fechar" : "Conectar"}
                  </button>
                )}
              </div>
              {open === c.id && <KeyFlow card={c} onDone={done} onMsg={setMsg} />}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
