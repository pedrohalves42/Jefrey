import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { apiMessage, deleteUserSource, getUserSources, learnMessage, learnRequest, type UserSource } from "@/lib/studies"
import { correctFact, correctionError, forgetAll, forgetFact, getLearned, groupFacts, setLearning, type Fact } from "@/lib/learning"

const card = "jf-panel p-5"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white"

/** Fontes e links: a pessoa indica sites para o Jefrey pesquisar sobre os assuntos. */
function Links() {
  const [url, setUrl] = useState("")
  const [topic, setTopic] = useState("")
  const [list, setList] = useState<UserSource[]>([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  async function load() {
    setList((await getUserSources()).data?.sources ?? [])
  }
  useEffect(() => {
    void load()
  }, [])
  async function go(run: boolean) {
    if (!url.trim()) {
      setMsg({ ok: false, text: "Cole o link de um site." })
      return
    }
    setBusy(true)
    setMsg(run ? { ok: true, text: "Lendo o site e estudando… pode levar um minuto." } : null)
    const r = await learnRequest({ url: url.trim(), topic: topic.trim(), run })
    setBusy(false)
    if (r.ok && r.data) {
      setMsg(learnMessage(r.data))
      setUrl("")
      setTopic("")
      await load()
    } else setMsg({ ok: false, text: apiMessage(r, "Não consegui agora. Tente de novo.") })
  }
  const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/35"
  return (
    <section className={card} aria-labelledby="l-links">
      <h2 id="l-links" className="text-xl font-medium text-white">Fontes e links para eu pesquisar</h2>
      <p className="mt-1 text-base text-white/70">Cole o endereço de um site de que você gosta. Eu leio, estudo e uso nas respostas, citando a fonte.</p>
      <label className="mt-3 block text-base text-white/85">
        Link
        <input className={`${field} mt-1`} value={url} inputMode="url" maxLength={600} placeholder="https://…" onChange={e => setUrl(e.target.value)} />
      </label>
      <label className="mt-3 block text-base text-white/85">
        Sobre qual assunto? (opcional)
        <input className={`${field} mt-1`} value={topic} maxLength={80} placeholder="Ex.: orquídeas" onChange={e => setTopic(e.target.value)} />
      </label>
      <div className="mt-3 flex flex-wrap gap-3">
        <button type="button" onClick={() => void go(true)} disabled={busy} className="jf-btn jf-focus px-5 py-3 text-base">{busy ? "Estudando…" : "Pesquisar agora"}</button>
        <button type="button" onClick={() => void go(false)} disabled={busy} className="jf-focus rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">Só guardar o link</button>
        <Link to="/aprender" className="jf-focus rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">Pedir outra coisa</Link>
      </div>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-3 text-base ${msg.ok ? "text-emerald-100" : "text-red-200"}`}>{msg.text}</p>}
      {list.length > 0 && (
        <ul className="mt-4 space-y-2">
          {list.map(s => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 p-3 text-base text-white/85">
              <span className="min-w-0 break-all">{s.title}</span>
              <button type="button" onClick={() => void deleteUserSource(s.id).then(load)} className="jf-focus rounded-lg border border-red-300/40 px-3 py-1.5 text-sm text-red-100 hover:bg-red-400/10">Apagar</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Aprendi() {
  const [facts, setFacts] = useState<Fact[]>([])
  const [enabled, setEnabled] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [confirmAll, setConfirmAll] = useState(false)

  async function load() {
    const r = await getLearned()
    if (r.data) {
      setFacts(r.data.facts)
      setEnabled(r.data.enabled)
    }
    setLoaded(true)
  }
  useEffect(() => {
    void load()
  }, [])

  async function toggle() {
    const next = !enabled
    const r = await setLearning(next)
    if (r.ok) {
      setEnabled(next)
      setMsg({ ok: true, text: next ? "Pronto. O Jefrey volta a aprender com as nossas conversas." : "Pronto. O Jefrey não vai mais guardar nada novo sobre você." })
    } else setMsg({ ok: false, text: "Não consegui mudar isso agora. Tente de novo." })
  }

  async function save(f: Fact) {
    const r = await correctFact(f.id, draft.trim())
    if (r.ok) {
      setEditing(null)
      setMsg({ ok: true, text: "Corrigido." })
    } else {
      setMsg({ ok: false, text: correctionError(r.status) })
      if (r.status === 404) setEditing(null)
    }
    await load()
  }

  async function forget(f: Fact) {
    const r = await forgetFact(f.id)
    setMsg(r.ok ? { ok: true, text: "Esquecido. Isso foi apagado de verdade." } : { ok: false, text: "Não consegui apagar agora. Tente de novo." })
    await load()
  }

  async function wipe() {
    const r = await forgetAll()
    setConfirmAll(false)
    setMsg(r.ok ? { ok: true, text: "Pronto. O Jefrey esqueceu tudo o que tinha aprendido sobre você." } : { ok: false, text: "Não consegui apagar agora. Tente de novo." })
    await load()
  }

  const groups = groupFacts(facts)
  const intro = "Aqui está o que eu aprendi sobre você nas nossas conversas. Você pode corrigir, esquecer o que quiser, ou pedir para eu parar de aprender."
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">O que aprendi</h1>
        <p className="mt-1 text-base text-white/70">{intro}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <ListenButton text={intro} />
          <button type="button" onClick={() => void toggle()} aria-pressed={enabled} className="jf-btn jf-focus px-5 py-3 text-base">
            {enabled ? "Parar de aprender" : "Voltar a aprender"}
          </button>
        </div>
        <p className="mt-2 text-sm text-white/55">
          Nunca guardo senhas, números de documentos nem de cartões. Tudo fica só neste computador.
        </p>
      </header>

      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>
          {msg.text}
        </p>
      )}

      <Links />

      {loaded && groups.length === 0 && (
        <section className={card}>
          <p className="text-base text-white/80">
            {enabled ? "Ainda não aprendi nada sobre você. Conte um pouco: onde você mora, do que gosta, como se chama a sua família." : "O aprendizado está desligado."}
          </p>
        </section>
      )}

      {groups.map(g => (
        <section key={g.kind} className={card} aria-labelledby={`g-${g.kind}`}>
          <h2 id={`g-${g.kind}`} className="text-xl font-medium text-white">{g.label}</h2>
          <ul className="mt-3 space-y-3">
            {g.items.map(f => (
              <li key={f.id} className="rounded-lg border border-white/10 p-3">
                {editing === f.id ? (
                  <div>
                    <input className={field} value={draft} maxLength={200} onChange={e => setDraft(e.target.value)} aria-label="Corrigir" />
                    <div className="mt-2 flex gap-2">
                      <button type="button" onClick={() => void save(f)} disabled={draft.trim().length < 3} className="jf-btn jf-focus px-4 py-2 text-base">
                        Salvar
                      </button>
                      <button type="button" onClick={() => setEditing(null)} className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5">
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-base text-white/90">
                      {f.text}
                      {f.sensitive && <span className="ml-2 rounded-full bg-amber-400/15 px-2 py-0.5 text-xs text-amber-200">Delicado</span>}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(f.id)
                          setDraft(f.text)
                          setMsg(null)
                        }}
                        className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5"
                      >
                        Corrigir
                      </button>
                      <button type="button" onClick={() => void forget(f)} className="jf-focus rounded-lg border border-red-300/40 px-4 py-2 text-base text-red-100 hover:bg-red-400/10">
                        Esquecer
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {facts.length > 0 && (
        <section className={card}>
          {confirmAll ? (
            <div>
              <p className="text-base text-white/85">Tem certeza? Eu vou esquecer tudo o que aprendi sobre você. Isso não dá para desfazer.</p>
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => void wipe()} className="jf-focus rounded-lg border border-red-300/50 px-5 py-3 text-base text-red-100 hover:bg-red-400/10">
                  Sim, esquecer tudo
                </button>
                <button type="button" onClick={() => setConfirmAll(false)} className="jf-btn jf-focus px-5 py-3 text-base">
                  Não, manter
                </button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirmAll(true)} className="jf-focus rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">
              Esquecer tudo
            </button>
          )}
        </section>
      )}
    </div>
  )
}
