import { useEffect, useState } from "react"
import { isDesktop } from "@/lib/shell"
import { useSearchParams } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { disconnectGoogle, getGoogle, saveGoogleCredentials, googleReturnMessage, SERVICE_LABEL, startGoogle, type GoogleService, type GoogleStatus } from "@/lib/connections"
import AlexaTab from "@/components/AlexaTab"
import WaCompose from "@/components/WaCompose"
import Cerebros from "@/components/Cerebros"
import {
  MODE_LABEL, minutesLeft, sortChats, waForgetAll, waOpenFolder, waPairing, waRevoke, waSetMode, waSetPaused, waStatus, WA_PRIVACY_NOTE, WA_RISK_NOTE,
  type WaChat, type WaMode, type WaStatus,
} from "@/lib/wa"

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

/** Configuracao unica do app Google: cola o ID e a chave do Google Cloud (quem entrega o Jefrey pode deixar isso pronto). */
function GoogleSetup({ onDone }: { onDone: () => void }) {
  const [id, setId] = useState("")
  const [secret, setSecret] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState("")
  async function save() {
    setBusy(true)
    setErr("")
    const r = await saveGoogleCredentials(id, secret)
    setBusy(false)
    if (r.ok) {
      setSecret("")
      onDone()
    } else setErr(((r.data as { detail?: unknown } | null)?.detail as string) || "Não consegui guardar agora. Tente de novo.")
  }
  const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/30"
  return (
    <div className="mt-4 rounded-xl border border-amber-300/30 p-4">
      <p className="text-base text-amber-100">Falta uma configuração, feita uma vez só. Quem te entregou o Jefrey pode deixar pronta; se for você, siga o guia <b>docs/GOOGLE.md</b>, crie o acesso no Google Cloud (tipo “Aplicativo para computador”) e cole abaixo.</p>
      <label className="mt-3 block text-base text-white/85">ID do cliente
        <input className={`${field} mt-1`} value={id} onChange={e => setId(e.target.value)} placeholder="123456-abc.apps.googleusercontent.com" autoComplete="off" spellCheck={false} />
      </label>
      <label className="mt-3 block text-base text-white/85">Chave secreta
        <input className={`${field} mt-1`} type="password" value={secret} onChange={e => setSecret(e.target.value)} autoComplete="off" spellCheck={false} />
      </label>
      {err && <p role="alert" className="mt-2 text-base text-red-200">{err}</p>}
      <button type="button" onClick={() => void save()} disabled={busy || !id.trim() || !secret.trim()} className={`${big} mt-3`}>{busy ? "Guardando…" : "Guardar"}</button>
    </div>
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
    } else if (isDesktop()) {
      setMsg({ ok: true, text: "Abri o Google no seu navegador. Entre na sua conta, aceite e volte aqui: eu aviso quando conectar." })
      void waitConnected()
    }
  }

  /** No app o login acontece no navegador; aqui a tela espera (ate 4 min) o Google ficar conectado. */
  async function waitConnected() {
    for (let i = 0; i < 80; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const s = (await getGoogle()).data
      if (s?.connected) {
        setSt(s)
        setBusy(false)
        setMsg({ ok: true, text: "Pronto! O Google foi conectado. Agora o Jefrey pode ver a sua agenda e ajudar com o seu e-mail." })
        return
      }
    }
    setBusy(false)
    setMsg({ ok: false, text: "Não vi a conexão terminar. Se o Google mostrou algum erro no navegador, me conte; senão, aperte o botão de novo." })
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
          {st?.diagnosis && !st.diagnosis.ok && st.configured && (
            <p role="alert" className="mt-3 break-words text-base text-amber-200">{st.diagnosis.advice}</p>
          )}
          {st?.configured && st.redirect_uri && (
            <p className="mt-3 break-all text-sm text-white/50">Se o Google disser “redirect_uri_mismatch”, cadastre este endereço no Google Cloud: <code className="text-white/80">{st.redirect_uri}</code></p>
          )}
          <Note msg={msg} />
          {st && !st.configured && <GoogleSetup onDone={() => void load()} />}
          {st?.configured && (
            <details key={msg && !msg.ok ? "aberto" : "fechado"} open={!!msg && !msg.ok} className="mt-3 rounded-xl border border-white/10 p-3">
              <summary className="cursor-pointer text-base text-white/85">Trocar o ID e a chave do Google</summary>
              <GoogleSetup onDone={() => void load()} />
            </details>
          )}
        </>
      )}
      {st?.connected && <Note msg={msg} />}
    </section>
  )
}

const STATUS_LABEL: Record<string, string> = { sent: "enviada", rejected: "você não quis enviar", expired: "venceu", failed: "não consegui enviar", approved: "esperando para enviar" }

function WhatsApp() {
  const [st, setSt] = useState<WaStatus | null>(null)
  const [code, setCode] = useState<{ code: string; at: number; ttl: number } | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [msg, setMsg] = useState<Msg>(null)
  const [confirmWipe, setConfirmWipe] = useState(false)

  async function load() {
    const r = await waStatus()
    if (r.data) setSt(r.data)
  }
  useEffect(() => {
    void load()
    const t = window.setInterval(() => {
      void load()
      setNow(Date.now())
    }, 5000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (!code) return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [code])

  const paired = (st?.devices.length ?? 0) > 0
  const left = code ? minutesLeft(code.ttl, (now - code.at) / 1000) : 0

  async function makeCode() {
    const r = await waPairing()
    if (r.data) setCode({ code: r.data.code, at: Date.now(), ttl: r.data.expires_in })
    else setMsg({ ok: false, text: "Não consegui gerar o código agora. Tente de novo." })
  }
  async function openFolder() {
    const r = await waOpenFolder()
    setMsg(r.ok ? { ok: true, text: `Abri a pasta da extensão${r.data?.path ? ` (${r.data.path})` : ""}. Se não abrir, procure por ela em Documentos > Jefrey. Siga os passos abaixo.` } : { ok: false, text: "Não consegui abrir a pasta. Peça ajuda a quem instalou o Jefrey." })
  }
  async function mode(c: WaChat, m: WaMode) {
    const r = await waSetMode(c.id, m)
    if (!r.ok) setMsg({ ok: false, text: "Não consegui mudar isso agora." })
    await load()
  }
  async function pause(p: boolean) {
    await waSetPaused(p)
    setMsg({ ok: true, text: p ? "Pausado. O Jefrey não vai ler nem responder nada no WhatsApp." : "Continuando. O Jefrey volta a atender as conversas liberadas." })
    await load()
  }
  async function wipe() {
    await waForgetAll()
    setConfirmWipe(false)
    setCode(null)
    setMsg({ ok: true, text: "Pronto. Apaguei as conversas, as mensagens guardadas e desconectei o WhatsApp." })
    await load()
  }

  const btn = "jf-focus rounded-lg border px-4 py-2 text-base"
  return (
    <section className={card} aria-labelledby="c-wa">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="c-wa" className="text-xl font-medium text-white">WhatsApp</h2>
        <Badge on={paired && !st?.paused} yes="Conectado" no={paired ? "Em pausa" : "Ainda não conectado"} />
      </div>
      <p className="mt-2 text-base text-white/70">
        O Jefrey lê e responde, no WhatsApp do computador (web.whatsapp.com), só as conversas que você liberar. Quando for dinheiro, dados pessoais, compromisso ou
        algo delicado, ele pergunta a você antes.
      </p>
      <p className="mt-2 text-sm text-amber-100/90">{WA_RISK_NOTE}</p>
      <p className="mt-2 text-sm text-white/60">{WA_PRIVACY_NOTE}</p>

      {!paired && (
        <div className="mt-4 rounded-xl border border-white/10 p-4">
          <ol className="list-decimal space-y-2 pl-6 text-base text-white/85">
            <li>Aperte o botão para abrir a pasta da extensão do Chrome.</li>
            <li>No Chrome, digite <b>chrome://extensions</b> no endereço, ligue o <b>Modo do desenvolvedor</b> e clique em <b>Carregar sem compactação</b>. Escolha a pasta que abriu.</li>
            <li>Aperte o botão abaixo para gerar um código, clique no ícone do Jefrey no Chrome e digite o código.</li>
          </ol>
          <div className="mt-3 flex flex-wrap gap-3">
            <button type="button" onClick={() => void openFolder()} className={`${btn} border-white/25 text-white/85 hover:bg-white/5`}>Abrir a pasta da extensão</button>
            <button type="button" onClick={() => void makeCode()} className={big}>Gerar código</button>
          </div>
          {code && (
            <p className="mt-4 text-center" aria-live="polite">
              <span className="block text-sm text-white/60">Digite este código na extensão ({left > 0 ? `vale por ${left} min` : "venceu, gere outro"}):</span>
              <span className="mt-1 block text-4xl font-semibold tracking-[0.4em] text-white">{code.code}</span>
            </p>
          )}
        </div>
      )}

      {paired && st && (
        <>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={() => void pause(!st.paused)} className={st.paused ? big : `${btn} border-amber-300/50 text-amber-100 hover:bg-amber-400/10`}>
              {st.paused ? "Continuar" : "Pausar tudo"}
            </button>
          </div>

          <h3 className="mt-5 text-lg font-medium text-white">Conversas</h3>
          {st.chats.length === 0 && <p className="mt-1 text-base text-white/70">Ainda não vi nenhuma conversa. Abra o WhatsApp Web no Chrome e clique em uma conversa.</p>}
          <ul className="mt-2 space-y-3">
            {sortChats(st.chats).map(c => (
              <li key={c.id} className="rounded-lg border border-white/10 p-3">
                <p className="text-lg text-white">{c.display} <span className="text-sm text-white/55">· {MODE_LABEL[c.mode]}</span></p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(["ask", "auto", "off"] as WaMode[]).map(m => (
                    <button
                      key={m}
                      type="button"
                      aria-pressed={c.mode === m}
                      onClick={() => void mode(c, m)}
                      className={`${btn} ${c.mode === m ? "border-cyan-300 bg-cyan-400/10 text-white" : "border-white/25 text-white/85 hover:bg-white/5"}`}
                    >
                      {m === "ask" ? "Perguntar antes" : m === "auto" ? "Responder sozinho" : "Ignorar"}
                    </button>
                  ))}
                </div>
                {c.mode !== "off" && <WaCompose chat={c} onQueued={() => void load()} />}
              </li>
            ))}
          </ul>

          {st.recent.length > 0 && (
            <>
              <h3 className="mt-5 text-lg font-medium text-white">Últimas respostas</h3>
              <ul className="mt-2 space-y-1 text-base text-white/80">
                {st.recent.slice(0, 5).map(d => (
                  <li key={d.id}>{d.chat}: <span className="text-white/60">{d.reply ? `"${d.reply}"` : "(sem resposta)"} · {STATUS_LABEL[d.status] ?? d.status}</span></li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-5 flex flex-wrap gap-3">
            {st.devices.map(d => (
              <button key={d.id} type="button" onClick={() => void waRevoke(d.id).then(load)} className={`${btn} border-white/25 text-white/85 hover:bg-white/5`}>
                Desconectar {d.label}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="mt-4">
        {confirmWipe ? (
          <div>
            <p className="text-base text-white/85">Apagar tudo do WhatsApp (conversas liberadas, mensagens guardadas e a conexão)? Não dá para desfazer.</p>
            <div className="mt-2 flex gap-2">
              <button type="button" onClick={() => void wipe()} className={`${btn} border-red-300/50 text-red-100 hover:bg-red-400/10`}>Sim, apagar</button>
              <button type="button" onClick={() => setConfirmWipe(false)} className={`${btn} border-white/25 text-white/85`}>Não</button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirmWipe(true)} className="jf-focus text-sm text-white/55 underline hover:text-white/80">Apagar tudo do WhatsApp</button>
        )}
      </div>
      <Note msg={msg} />
    </section>
  )
}

const TABS = [
  { id: "cerebros", label: "Cérebros" },
  { id: "google", label: "Google" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "alexa", label: "Alexa" },
] as const
type TabId = (typeof TABS)[number]["id"]

function pickTab(params: URLSearchParams): TabId {
  const a = params.get("aba") ?? (params.get("google") ? "google" : "")
  return (TABS.find(t => t.id === a)?.id ?? "cerebros") as TabId
}

export default function Conexoes() {
  const [params, setParams] = useSearchParams()
  const [tab, setTab] = useState<TabId>(() => pickTab(params))
  function choose(id: TabId) {
    setTab(id)
    if (params.get("aba")) setParams({ aba: id }, { replace: true })
  }
  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Conexões</h1>
        <p className="mt-1 text-base text-white/65">Ligue o Jefrey às suas contas. É só apertar o botão, entrar na sua conta e voltar.</p>
      </header>
      <div role="tablist" aria-label="Conexões" className="mt-4 flex flex-wrap gap-2 border-b border-white/10 pb-3">
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`painel-${t.id}`}
            onClick={() => choose(t.id)}
            className={`jf-focus rounded-lg border px-5 py-2.5 text-base ${tab === t.id ? "border-cyan-300 bg-cyan-400/10 text-white" : "border-white/20 text-white/75 hover:bg-white/5"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`painel-${tab}`} aria-labelledby={`tab-${tab}`} className="mt-4">
        {tab === "cerebros" && <Cerebros />}
        {tab === "google" && <Google />}
        {tab === "whatsapp" && <WhatsApp />}
        {tab === "alexa" && <AlexaTab />}
      </div>
    </div>
  )
}
