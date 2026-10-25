import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { apiMessage, deleteUserSource, getStudies, getUserSources, learnMessage, learnRequest, looksLikeLink, type Overview, type UserSource } from "@/lib/studies"

const card = "jf-panel p-5"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/35"

/** Aprender por pedido, sem conversar: um assunto, um link ou um texto. */
export default function Aprender() {
  const [topic, setTopic] = useState("")
  const [url, setUrl] = useState("")
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [ov, setOv] = useState<Overview | null>(null)
  const [src, setSrc] = useState<UserSource[]>([])

  async function load() {
    const [a, b] = await Promise.all([getStudies(), getUserSources()])
    if (a.data) setOv(a.data)
    setSrc(b.data?.sources ?? [])
  }
  useEffect(() => {
    void load()
  }, [])

  async function go(run: boolean) {
    // quem colou um link no campo do assunto: manda como link
    let t = topic.trim()
    let u = url.trim()
    if (!u && looksLikeLink(t)) {
      u = t
      t = ""
    }
    if (!t && !u && text.trim().length < 20) {
      setMsg({ ok: false, text: "Diga o assunto, cole um link ou cole um texto (com pelo menos uma frase)." })
      return
    }
    setBusy(true)
    setMsg(run ? { ok: true, text: "Aprendendo… isso pode levar um minuto. Pode deixar esta tela aberta." } : null)
    const r = await learnRequest({ topic: t, url: u, text: text.trim(), run })
    setBusy(false)
    if (r.ok && r.data) {
      setMsg(learnMessage(r.data))
      setTopic("")
      setUrl("")
      setText("")
      await load()
    } else setMsg({ ok: false, text: apiMessage(r, "Não consegui agora. Tente de novo.") })
  }

  const intro = "Peça aqui para eu aprender algo, sem precisar conversar. Diga um assunto, cole um link de um site ou cole um texto. Eu leio, estudo e guardo."
  const topics = ov?.topics ?? []
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Aprender</h1>
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
            Para estudar de verdade eu preciso de um cérebro na nuvem. Você pode deixar o pedido anotado agora. <Link className="underline" to="/conexoes">Conectar um cérebro</Link>.
          </p>
        </section>
      )}

      <section className={card} aria-labelledby="a-pedir">
        <h2 id="a-pedir" className="text-xl font-medium text-white">O que você quer que eu aprenda?</h2>
        <label className="mt-3 block text-base text-white/85">
          Assunto
          <input className={`${field} mt-1`} value={topic} maxLength={80} placeholder="Ex.: cuidar de orquídeas" onChange={e => setTopic(e.target.value)} />
        </label>
        <label className="mt-3 block text-base text-white/85">
          Link de um site (opcional)
          <input className={`${field} mt-1`} value={url} maxLength={600} placeholder="https://…" inputMode="url" onChange={e => setUrl(e.target.value)} />
        </label>
        <label className="mt-3 block text-base text-white/85">
          Ou cole um texto para eu guardar (opcional)
          <textarea className={`${field} mt-1`} rows={4} value={text} maxLength={6000} placeholder="Cole aqui uma receita, uma anotação, um texto…" onChange={e => setText(e.target.value)} />
        </label>
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" onClick={() => void go(true)} disabled={busy} className="jf-btn jf-focus px-5 py-3 text-base">{busy ? "Aprendendo…" : "Aprender agora"}</button>
          <button type="button" onClick={() => void go(false)} disabled={busy} className="jf-focus rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">Só anotar para depois</button>
        </div>
        <p className="mt-3 text-sm text-white/55">Nunca guardo senhas, documentos nem cartões. Links só de sites públicos.</p>
      </section>

      <section className={card} aria-labelledby="a-lista">
        <h2 id="a-lista" className="text-xl font-medium text-white">Pedidos e fontes</h2>
        {topics.length === 0 && src.length === 0 && <p className="mt-2 text-base text-white/70">Ainda nenhum pedido.</p>}
        <ul className="mt-2 space-y-2">
          {topics.map(t => (
            <li key={t.id} className="rounded-lg border border-white/10 p-3 text-base text-white/85">
              {t.title} <span className="text-sm text-white/55">· {t.level_label}</span>
            </li>
          ))}
        </ul>
        {src.length > 0 && (
          <>
            <h3 className="mt-4 text-lg font-medium text-white">Links que você me deu</h3>
            <ul className="mt-2 space-y-2">
              {src.map(s => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 p-3 text-base text-white/85">
                  <span className="min-w-0 break-all">{s.title}</span>
                  <button type="button" onClick={() => void deleteUserSource(s.id).then(load)} className="jf-focus rounded-lg border border-red-300/40 px-3 py-1.5 text-sm text-red-100 hover:bg-red-400/10">Apagar</button>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="mt-3 text-sm text-white/60">Os guias prontos ficam em <Link className="underline" to="/estudos">Estudos</Link>.</p>
      </section>
    </div>
  )
}
