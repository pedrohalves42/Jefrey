import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import ListenButton from "@/components/ListenButton"
import { disconnectGoogle, getGoogle, googleReturnMessage, SERVICE_LABEL, startGoogle, type GoogleService, type GoogleStatus } from "@/lib/connections"
import { cleanKey, guideFor, KEY_COST_NOTE, KEY_GUIDES, keyProblem, type KeyProviderId } from "@/lib/keyGuide"
import { getConfig, getPresets, saveConfig, startOpenRouter, testConfig, testMessage, type LlmConfig, type Preset } from "@/lib/llm"

const card = "jf-panel p-5"
const big = "jf-btn jf-focus px-5 py-3 text-base"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/30"

type Msg = { ok: boolean; text: string } | null

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <p role={msg.ok ? "status" : "alert"} className={`mt-3 rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>
      {msg.text}
    </p>
  )
}

function Badge({ on, yes, no }: { on: boolean; yes: string; no: string }) {
  return (
    <span className={`rounded-full px-3 py-1 text-sm ${on ? "bg-emerald-400/15 text-emerald-200" : "bg-white/10 text-white/60"}`}>{on ? yes : no}</span>
  )
}

/** Passo a passo para colar a chave do Claude ou do ChatGPT, sem termos tecnicos. */
function KeySteps({ presets, onDone }: { presets: Preset[]; onDone: () => void }) {
  const [who, setWho] = useState<KeyProviderId | null>(null)
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)
  const guide = who ? guideFor(who) : undefined

  async function connect() {
    if (!who) return
    const problem = keyProblem(who, key)
    if (problem) {
      setMsg({ ok: false, text: problem })
      return
    }
    const preset = presets.find(p => p.id === who)
    if (!preset || !preset.models.length) {
      setMsg({ ok: false, text: "Não consegui preparar esse serviço agora. Tente de novo." })
      return
    }
    setBusy(true)
    setMsg(null)
    const saved = await saveConfig({ provider: preset.provider, model: preset.models[0], base_url: preset.base_url, api_key: cleanKey(key) })
    if (!saved.ok) {
      setMsg({ ok: false, text: "Não consegui guardar o código. Confira se copiou inteiro." })
      setBusy(false)
      return
    }
    setKey("")
    const t = testMessage(await testConfig())
    setMsg(t)
    setBusy(false)
    if (t.ok) onDone()
  }

  return (
    <div className="mt-4 rounded-xl border border-white/10 p-4">
      <p className="text-base text-white/85">Qual serviço você usa?</p>
      <div className="mt-2 flex flex-wrap gap-3">
        {KEY_GUIDES.map(g => (
          <button
            key={g.id}
            type="button"
            aria-pressed={who === g.id}
            onClick={() => {
              setWho(g.id)
              setMsg(null)
            }}
            className={`jf-focus rounded-lg border px-5 py-3 text-base ${who === g.id ? "border-cyan-300 bg-cyan-400/10 text-white" : "border-white/20 text-white/80 hover:bg-white/5"}`}
          >
            {g.name}
          </button>
        ))}
      </div>

      {guide && (
        <div className="mt-4">
          <ol className="list-decimal space-y-2 pl-6 text-base text-white/80">
            {guide.steps.map(s => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <a href={guide.url} target="_blank" rel="noopener noreferrer" className={`${big} inline-block`}>
              Abrir o site do {guide.name}
            </a>
            <ListenButton text={`${guide.steps.join(" ")} ${KEY_COST_NOTE}`} />
          </div>
          <p className="mt-3 text-sm text-white/60">{KEY_COST_NOTE}</p>
          <label className="mt-4 block text-base text-white/85">
            Cole aqui o código que você copiou
            <input
              className={`${field} mt-1`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={key}
              onChange={e => {
                setKey(e.target.value)
                setMsg(null)
              }}
              placeholder="começa com sk-"
            />
          </label>
          <button type="button" onClick={() => void connect()} disabled={busy} className={`${big} mt-3`}>
            {busy ? "Testando…" : "Conectar"}
          </button>
        </div>
      )}
      <Note msg={msg} />
    </div>
  )
}

function Assistente() {
  const qc = useQueryClient()
  const [cfg, setCfg] = useState<LlmConfig | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)

  async function load() {
    const [c, p] = await Promise.all([getConfig(), getPresets()])
    setCfg(c.data)
    setPresets(p.data?.presets ?? [])
  }
  useEffect(() => {
    void load()
  }, [])

  async function oneClick() {
    setBusy(true)
    setMsg(null)
    const err = await startOpenRouter()
    if (err) {
      setMsg({ ok: false, text: err })
      setBusy(false)
    }
  }

  const connected = !!cfg?.configured && !!cfg?.is_cloud && cfg.has_key
  const text =
    "A inteligência do Jefrey. Aperte o botão, o site abre, você entra na sua conta e volta. O Jefrey nunca vê a sua senha. " +
    "Você paga direto ao serviço, só pelo que usar."
  return (
    <section className={card} aria-labelledby="c-ia">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="c-ia" className="text-xl font-medium text-white">Inteligência do Jefrey</h2>
        <Badge on={connected} yes="Conectada" no="Ainda não conectada" />
      </div>
      <p className="mt-2 text-base text-white/70">
        É o que faz o Jefrey pensar e responder. Aperte o botão: o site abre, você entra na sua conta e volta sozinho. O Jefrey nunca vê a sua senha.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => void oneClick()} disabled={busy} className={big}>
          {busy ? "Abrindo o site…" : connected ? "Conectar de novo" : "Conectar com 1 clique"}
        </button>
        <ListenButton text={text} />
      </div>
      <p className="mt-3 text-sm text-white/55">Você paga direto ao serviço, só pelo que usar, e acompanha o gasto lá.</p>
      <Note msg={msg} />

      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open} className="jf-focus mt-4 text-base text-white/70 underline hover:text-white">
        {open ? "Fechar" : "Prefiro usar minha conta do Claude ou do ChatGPT"}
      </button>
      {open && (
        <KeySteps
          presets={presets}
          onDone={() => {
            void qc.invalidateQueries({ queryKey: ["llm-config"] })
            void load()
          }}
        />
      )}
    </section>
  )
}

function Google() {
  const [params, setParams] = useSearchParams()
  const [st, setSt] = useState<GoogleStatus | null>(null)
  const [pick, setPick] = useState<Record<GoogleService, boolean>>({ calendar: true, email: true, drive: false })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(googleReturnMessage(params.get("google")))

  async function load() {
    setSt((await getGoogle()).data)
  }
  useEffect(() => {
    void load()
    if (params.get("google")) setParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const chosen = (Object.keys(pick) as GoogleService[]).filter(k => pick[k])

  async function go() {
    if (!chosen.length) {
      setMsg({ ok: false, text: "Marque pelo menos uma coisa: Agenda ou E-mail." })
      return
    }
    setBusy(true)
    setMsg(null)
    const err = await startGoogle(chosen)
    if (err) {
      setMsg({ ok: false, text: err })
      setBusy(false)
    }
  }

  async function leave() {
    setBusy(true)
    await disconnectGoogle()
    setBusy(false)
    setMsg({ ok: true, text: "Desconectado. O Jefrey não vê mais o seu Google." })
    await load()
  }

  const listen = "Conta do Google. Aperte o botão, o site do Google abre, você entra na sua conta e escolhe o que o Jefrey pode ver. Depois volta sozinho."
  return (
    <section className={card} aria-labelledby="c-google">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="c-google" className="text-xl font-medium text-white">Conta do Google</h2>
        <Badge on={!!st?.connected} yes="Conectada" no="Ainda não conectada" />
      </div>
      <p className="mt-2 text-base text-white/70">Para o Jefrey ver a sua agenda e ajudar com o seu e-mail. Você escolhe o que ele pode ver.</p>

      {st?.connected ? (
        <>
          <p className="mt-3 text-base text-white/85">
            Conectado{st.email ? ` como ${st.email}` : ""}: {st.services.map(s => SERVICE_LABEL[s]).join(" e ")}.
          </p>
          <button type="button" onClick={() => void leave()} disabled={busy} className="jf-focus mt-3 rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">
            Desconectar
          </button>
        </>
      ) : (
        <>
          <fieldset className="mt-3">
            <legend className="text-base text-white/80">O que o Jefrey pode usar?</legend>
            <div className="mt-2 flex flex-wrap gap-4">
              {(["calendar", "email"] as GoogleService[]).map(k => (
                <label key={k} className="flex items-center gap-3 text-base text-white/85">
                  <input type="checkbox" className="h-5 w-5" checked={pick[k]} onChange={e => setPick(p => ({ ...p, [k]: e.target.checked }))} />
                  {SERVICE_LABEL[k]}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => void go()} disabled={busy} className={big}>
              {busy ? "Abrindo o Google…" : "Entrar com o Google"}
            </button>
            <ListenButton text={listen} />
          </div>
          {st && !st.configured && (
            <p className="mt-3 text-sm text-amber-200/90">
              Esta cópia do Jefrey ainda não foi liberada para o Google. Quando for, o botão acima funciona sozinho.
            </p>
          )}
        </>
      )}
      <Note msg={msg} />
    </section>
  )
}

function WhatsApp() {
  return (
    <section className={card} aria-labelledby="c-wa">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="c-wa" className="text-xl font-medium text-white">WhatsApp</h2>
        <Badge on={false} yes="" no="Em breve" />
      </div>
      <p className="mt-2 text-base text-white/70">
        Em breve o Jefrey vai poder ler e responder as suas conversas, só com as pessoas que você liberar e perguntando antes quando for algo delicado.
      </p>
    </section>
  )
}

export default function Conexoes() {
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Conexões</h1>
        <p className="mt-1 text-base text-white/65">Ligue o Jefrey às suas contas. É só apertar o botão, entrar na sua conta e voltar.</p>
      </header>
      <Assistente />
      <Google />
      <WhatsApp />
    </div>
  )
}
