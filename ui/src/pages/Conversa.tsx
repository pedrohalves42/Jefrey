import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { BrainStage, type BrainState } from "@/components/brain/BrainStage"
import { MessageText } from "@/components/MessageText"
import { useSpeaker } from "@/hooks/useSpeaker"
import { greeting } from "@/lib/greeting"
import { getProfile } from "@/lib/llm"
import { useListener } from "@/hooks/useListener"
import { useVoiceReady } from "@/hooks/useVoiceReady"
import { useWakeSignal } from "@/hooks/useWakeSignal"
import { voiceView } from "@/lib/voiceMode"
import { useEasy } from "@/lib/easy"
import { useActivity } from "@/hooks/useActivity"
import { ambientLabel } from "@/lib/briefing"
import BriefingCard from "@/components/BriefingCard"
import { HudOverlay, Wave } from "@/components/hud/JarvisHud"
import { haltComputer } from "@/lib/halt"
import QuickActions from "@/components/QuickActions"
import LearnedToast from "@/components/LearnedToast"
import TodayPopup from "@/components/TodayPopup"
import DayStrip from "@/components/DayStrip"
import AvatarPicker from "@/components/AvatarPicker"
import { LivePanel } from "@/components/hud/LivePanel"
import { getToday, spokenSummary } from "@/lib/today"
import { useVoicePulse } from "@/hooks/useVoicePulse"
import { SentenceBuffer } from "@/lib/voice/sentences"
import { authedFetch, ensureSession } from "@/lib/session"
import {
  loadActiveId, loadThreads, newThread, saveActiveId, saveThreads, streamChat, titleFrom, uid,
  type Message, type Thread, type ToolStep,
} from "@/lib/chat"

const SUGGESTIONS = [
  "Me ajude a organizar meu dia",
  "Me lembra de beber água daqui a 30 minutos",
  "Quais são meus lembretes?",
  "O que você consegue fazer por mim?",
]

/** Preferencia salva; sem escolha ainda, usa o padrao (voz ligada: o caminho principal e falar e ouvir). */
function readFlag(key: string, fallback = true): boolean {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v === "1"
  } catch {
    return fallback
  }
}

function writeFlag(key: string, on: boolean): void {
  try {
    localStorage.setItem(key, on ? "1" : "0")
  } catch {
    /* sem armazenamento: vale so nesta sessao */
  }
}

function initThreads(): { threads: Thread[]; active: string } {
  const threads = loadThreads()
  const saved = loadActiveId()
  if (threads.length === 0) {
    const t = newThread()
    return { threads: [t], active: t.id }
  }
  return { threads, active: threads.some(t => t.id === saved) ? (saved as string) : (threads[0] as Thread).id }
}

export default function Conversa() {
  const init = useMemo(initThreads, [])
  const [threads, setThreads] = useState<Thread[]>(init.threads)
  const [activeId, setActiveId] = useState(init.active)
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [gotToken, setGotToken] = useState(false)
  const [pendingApproval, setPendingApproval] = useState<{ id: string | null; label?: string } | undefined>(undefined)
  const [showList, setShowList] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // ---- voz ----
  const [voiceReply, setVoiceReplyState] = useState(() => readFlag("jefrey_voice_reply"))
  const [continuous, setContinuousState] = useState(() => readFlag("jefrey_voice_continuous"))
  const [micOn, setMicOn] = useState(false)
  const [micLevel, setMicLevel] = useState(0)
  const speaker = useSpeaker()
  const voiceReady = useVoiceReady()
  const [easy] = useEasy()
  const [unclear, setUnclear] = useState(false)
  const [myName, setMyName] = useState<string | null>(null)
  const [clock, setClock] = useState(() => new Date())
  useEffect(() => {
    void getProfile().then(r => setMyName(r.data?.display_name ?? null))
    const t = window.setInterval(() => setClock(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  const voiceReplyRef = useRef(voiceReply)
  voiceReplyRef.current = voiceReply
  const continuousRef = useRef(continuous)
  continuousRef.current = continuous
  const sendRef = useRef<(t?: string) => Promise<void>>(async () => {})
  const listener = useListener({
    onTranscript: t => {
      setUnclear(false)
      if (!continuousRef.current) setMicOn(false)
      void sendRef.current(t)
    },
    onUnclear: () => setUnclear(true),
    onSpeechStart: () => {
      setUnclear(false)
      speaker.cancel() // falar por cima interrompe o Jefrey
    },
    onLevel: setMicLevel,
  })
  const listeningNow = listener.state === "listening" || listener.state === "hearing"
  // ---- chamar pelo nome ("Jefrey, ...") e pelo atalho do Windows (Ctrl+Alt+J) ----
  const [hud, setHud] = useState(() => readFlag("jefrey_hud", true))
  const [drawer, setDrawer] = useState(false)
  const [voiceLvl, setVoiceLvl] = useState(0)
  const [summaryBusy, setSummaryBusy] = useState(false)
  const [todayOpen, setTodayOpen] = useState(false)
  useEffect(() => {
    // 1a vez do dia: mostra o resumo por cima da conversa (uma vez so por dia; a pessoa fecha com Esc ou "Fechar")
    try {
      const day = new Date().toISOString().slice(0, 10)
      if (localStorage.getItem("jefrey_today_seen") !== day) {
        localStorage.setItem("jefrey_today_seen", day)
        const id = window.setTimeout(() => setTodayOpen(true), 1500)
        return () => window.clearTimeout(id)
      }
    } catch {
      /* sem armazenamento: nao abre sozinho */
    }
  }, [])
  const tiltRef = useRef<HTMLDivElement | null>(null)
  const [opts, setOpts] = useState(false)
  const stageRef = useRef<HTMLDivElement>(null)
  const [wakeOn, setWakeOn] = useState(() => readFlag("jefrey_wake", false))
  const startVoiceRef = useRef<(first?: string) => Promise<void>>(async () => {})
  const wakeListener = useListener({
    endpoint: "/stt/wake",
    onTranscript: () => {},
    onResult: j => {
      if (j.wake === true) void startVoiceRef.current(typeof j.rest === "string" ? j.rest.trim() : "")
    },
  })
  useWakeSignal(() => {
    if (!micOn && listener.state === "idle") void startVoiceRef.current()
  })
  const endRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  const active = threads.find(t => t.id === activeId) ?? (threads[0] as Thread)

  useEffect(() => {
    void ensureSession()
  }, [])
  useEffect(() => saveThreads(threads), [threads])
  useEffect(() => saveActiveId(activeId), [activeId])
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [active.messages, streaming])

  const updateThread = useCallback((id: string, fn: (t: Thread) => Thread) => {
    setThreads(prev => prev.map(t => (t.id === id ? fn(t) : t)))
  }, [])

  const activity = useActivity()
  const note = ambientLabel(activity)
  useVoicePulse(stageRef, speaker.speaking, setVoiceLvl)
  const brainState: BrainState = pendingApproval !== undefined
    ? "approval"
    : speaker.speaking
      ? "responding"
    : streaming
      ? gotToken ? "responding" : "thinking"
      : listeningNow ? "listening" : note ? "thinking" : "idle"

  async function send(textArg?: string) {
    const text = (textArg ?? input).trim()
    if (!text || streaming) return
    const tid = active.id
    const userMsg: Message = { id: uid(), role: "user", content: text, at: Date.now() }
    const aiMsg: Message = { id: uid(), role: "assistant", content: "", at: Date.now() }
    updateThread(tid, t => ({
      ...t,
      title: t.messages.length === 0 ? titleFrom(text) : t.title,
      updated: Date.now(),
      messages: [...t.messages, userMsg, aiMsg],
    }))
    setInput("")
    setStreaming(true)
    setGotToken(false)
    setPendingApproval(undefined)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const sb = new SentenceBuffer()
    const result = await streamChat(
      text,
      tid,
      {
        onToken: chunk => {
          setGotToken(true)
          if (voiceReplyRef.current) sb.push(chunk).forEach(speaker.say)
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m => (m.id === aiMsg.id ? { ...m, content: m.content + chunk } : m)),
          }))
        },
        onPendingApproval: id => setPendingApproval({ id: id ?? null }),
        onRecall: items =>
          updateThread(tid, t => ({ ...t, messages: t.messages.map(m => (m.id === aiMsg.id ? { ...m, recall: items } : m)) })),
        onToolStart: (tool, label, risk) =>
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m =>
              m.id === aiMsg.id ? { ...m, tools: [...(m.tools ?? []), { tool, label, risk, state: "running" } as ToolStep] } : m,
            ),
          })),
        onApprovalRequired: (id, tool, label) => {
          setPendingApproval({ id, label })
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m =>
              m.id === aiMsg.id
                ? { ...m, tools: (m.tools ?? []).map(x => (x.tool === tool && x.state === "running" ? { ...x, state: "waiting" as const } : x)) }
                : m,
            ),
          }))
        },
        onToolEnd: (tool, ok, summary) => {
          setPendingApproval(undefined)
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m => {
              if (m.id !== aiMsg.id) return m
              const tools = [...(m.tools ?? [])]
              for (let i = tools.length - 1; i >= 0; i--) {
                const x = tools[i] as ToolStep
                if (x.tool === tool && (x.state === "running" || x.state === "waiting")) {
                  tools[i] = { ...x, state: ok ? "ok" : "failed", summary }
                  break
                }
              }
              return { ...m, tools }
            }),
          }))
        },
      },
      ctrl.signal,
    )
    setStreaming(false)
    abortRef.current = null
    if (voiceReplyRef.current) sb.flush().forEach(speaker.say)
    if (!result.ok) {
      updateThread(tid, t => ({
        ...t,
        messages: t.messages.map(m =>
          m.id === aiMsg.id ? { ...m, content: m.content ? `${m.content}\n\n(${result.error})` : (result.error as string), error: !m.content } : m,
        ),
      }))
    }
    taRef.current?.focus()
  }

  sendRef.current = send

  // conversa continua: depois da resposta (e da fala), volta a ouvir sozinho
  useEffect(() => {
    if (micOn && continuous && !streaming && !speaker.speaking && listener.state === "idle") void listener.start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micOn, continuous, streaming, speaker.speaking, listener.state])

  // se o microfone falhar, o botao volta ao normal (a mensagem de erro continua visivel)
  useEffect(() => {
    if (listener.state === "error") setMicOn(false)
  }, [listener.state])

  /** O avatar acompanha o mouse (leve inclinacao): a tela responde a quem esta olhando. */
  function onTilt(e: React.PointerEvent<HTMLDivElement>) {
    const el = tiltRef.current
    if (!el) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width - 0.5) * 2
    const y = ((e.clientY - r.top) / r.height - 0.5) * 2
    el.style.transform = `perspective(900px) rotateY(${(x * 7).toFixed(2)}deg) rotateX(${(-y * 5).toFixed(2)}deg)`
  }
  function offTilt() {
    if (tiltRef.current) tiltRef.current.style.transform = ""
  }

  /** "Resumo do dia": fala o tempo, a agenda, os lembretes, o dolar e as manchetes, sem gastar o modelo de IA. */
  async function speakSummary() {
    setSummaryBusy(true)
    try {
      setTodayOpen(true)
      const r = await getToday()
      if (r.data) speaker.say(spokenSummary(r.data, myName ?? undefined))
      else speaker.say("Não consegui buscar o resumo agora. Verifique a internet.")
    } finally {
      setSummaryBusy(false)
    }
  }

  function stop() {
    abortRef.current?.abort()
    speaker.cancel()
    void haltComputer() // "Parar" tambem interrompe qualquer acao no computador (digitar, abrir, fechar...)
  }

  function toggleMic() {
    if (micOn || listener.state !== "idle") {
      setMicOn(false)
      listener.stop()
      return
    }
    speaker.cancel()
    setMicOn(true)
    void listener.start()
  }

  /** Liga a conversa por voz (usado pelo atalho e pela palavra "Jefrey"); `first` e o que a pessoa ja disse depois do nome. */
  async function startVoice(first?: string) {
    if (micOn) return
    wakeListener.stop()
    speaker.cancel()
    if (!(await voiceReady.ensure())) return
    setVoiceReplyState(true)
    writeFlag("jefrey_voice_reply", true)
    setContinuousState(true)
    writeFlag("jefrey_voice_continuous", true)
    setMicOn(true)
    if (first) void send(first)
    else void listener.start()
  }
  startVoiceRef.current = startVoice

  async function toggleWake() {
    const next = !wakeOn
    if (next && !(await voiceReady.ensure())) return
    setWakeOn(next)
    writeFlag("jefrey_wake", next)
    if (!next) wakeListener.stop()
  }

  // escuta so pelo nome enquanto nada mais esta acontecendo
  useEffect(() => {
    if (wakeOn && !micOn && !streaming && !speaker.speaking && listener.state === "idle" && wakeListener.state === "idle") void wakeListener.start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wakeOn, micOn, streaming, speaker.speaking, listener.state, wakeListener.state])
  useEffect(() => {
    if (micOn || streaming) wakeListener.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micOn, streaming])
  useEffect(() => {
    if (wakeListener.state === "error") setWakeOn(false)
  }, [wakeListener.state])

  /** Botao grande: liga (ou desliga) a conversa por voz inteira: ouvir, responder falando e ouvir de novo. */
  async function toggleVoiceMode() {
    if (speaker.speaking) {
      speaker.cancel() // tocar enquanto ele fala interrompe e ja passa a ouvir
    } else if (micOn || listener.state !== "idle") {
      setMicOn(false)
      listener.stop()
      return
    }
    setUnclear(false)
    if (!(await voiceReady.ensure())) return
    setVoiceReplyState(true)
    writeFlag("jefrey_voice_reply", true)
    setContinuousState(true)
    writeFlag("jefrey_voice_continuous", true)
    setMicOn(true)
    void listener.start()
  }

  const view = voiceView({ micOn, listener: listener.state, streaming, speaking: speaker.speaking, preparing: voiceReady.preparing })

  function retry() {
    const lastUser = [...active.messages].reverse().find(m => m.role === "user")
    if (!lastUser) return
    updateThread(active.id, t => {
      const copy = [...t.messages]
      while (copy.length && copy[copy.length - 1]!.role === "assistant" && copy[copy.length - 1]!.error) copy.pop()
      if (copy.length && copy[copy.length - 1]!.role === "user") copy.pop()
      return { ...t, messages: copy }
    })
    void send(lastUser.content)
  }

  function startNew() {
    if (streaming) return
    const t = newThread()
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
    setShowList(false)
    setPendingApproval(undefined)
  }

  function removeThread(id: string) {
    if (streaming) return
    setThreads(prev => {
      const rest = prev.filter(t => t.id !== id)
      if (rest.length === 0) {
        const t = newThread()
        setActiveId(t.id)
        return [t]
      }
      if (id === activeId) setActiveId((rest[0] as Thread).id)
      return rest
    })
  }

  async function decide(decision: "approved" | "rejected") {
    const pending = pendingApproval
    if (!pending?.id) {
      setPendingApproval(undefined)
      return
    }
    const r = await authedFetch(`/approvals/${pending.id}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision, decided_by: "usuario" }),
    })
    if (!r.ok) {
      updateThread(active.id, t => ({
        ...t,
        messages: [...t.messages, { id: uid(), role: "assistant", at: Date.now(), error: true,
          content: "Não consegui registrar sua decisão (pode ter expirado). Tente de novo." }],
      }))
    }
    if (!streaming) setPendingApproval(undefined) // com resposta em andamento, o servidor segue sozinho
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void send()
    }
  }

  const empty = active.messages.length === 0
  const lastIsError = active.messages.length > 0 && active.messages[active.messages.length - 1]!.error

  const lastAi = [...active.messages].reverse().find(m => m.role === "assistant")
  const lastUser = [...active.messages].reverse().find(m => m.role === "user")
  const caption = lastAi?.content ? lastAi.content.replace(/\s+/g, " ").trim() : ""

  const messageList = (
    <ul className="space-y-3 py-2">
      {active.messages.map((m, idx) => {
        const isLast = idx === active.messages.length - 1
        const typing = streaming && isLast && m.role === "assistant" && !m.content && !(m.tools && m.tools.length)
        return (
          <li key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${m.role === "user" ? "jf-bubble-user" : m.error ? "jf-bubble-err" : "jf-bubble-ai"}`}>
              {typing ? (
                <span className="jf-typing" aria-label="Jefrey está pensando"><span /><span /><span /></span>
              ) : (
                <>
                  {m.tools && m.tools.length > 0 && (
                    <div className="mb-1.5 flex flex-wrap gap-1.5">
                      {m.tools.map((t, i) => (
                        <span
                          key={i}
                          title={t.summary || t.label}
                          className={`rounded-full border px-2 py-0.5 text-xs ${
                            t.state === "ok" ? "border-emerald-400/30 text-emerald-200"
                            : t.state === "failed" ? "border-red-400/30 text-red-200"
                            : t.state === "waiting" ? "border-amber-400/40 text-amber-200"
                            : "border-white/20 text-white/60"
                          }`}
                        >
                          {t.state === "ok" ? "✓ " : t.state === "failed" ? "✗ " : t.state === "waiting" ? "⏳ " : "… "}
                          {t.label}
                        </span>
                      ))}
                    </div>
                  )}
                  <MessageText text={m.content} />
                  {m.recall && m.recall.length > 0 && (
                    <p className="mt-2 border-t border-white/10 pt-2 text-sm text-white/65">
                      <span className="jf-accent">Lembrei de: </span>
                      {m.recall.map(r => r.text).join(" · ")}{" "}
                      <Link to="/aprendi" className="underline hover:text-white">ver tudo</Link>
                    </p>
                  )}
                </>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* lista de conversas (so fora do modo Facil) */}
      <aside
        className={`jf-panel absolute inset-y-0 left-0 z-20 w-72 shrink-0 flex-col p-3 ${easy || !showList ? "hidden" : "flex"}`}
        aria-label="Conversas"
      >
        <button type="button" onClick={startNew} disabled={streaming} className="jf-btn jf-focus mb-3 px-3 py-2 text-sm">+ Nova conversa</button>
        <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {threads.map(t => (
            <li key={t.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  if (!streaming) {
                    setActiveId(t.id)
                    setShowList(false)
                    setPendingApproval(undefined)
                  }
                }}
                aria-current={t.id === activeId}
                className={`jf-focus min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-left text-sm ${t.id === activeId ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5"}`}
              >
                {t.title}
              </button>
              <button type="button" onClick={() => removeThread(t.id)} aria-label={`Apagar conversa ${t.title}`} className="jf-focus rounded px-2 py-1 text-white/30 opacity-0 hover:text-red-300 group-hover:opacity-100 focus:opacity-100">×</button>
            </li>
          ))}
        </ul>
      </aside>

      {/* palco: o avatar ocupa quase toda a tela e as opcoes ficam pequenas por cima */}
      <section className="jf-stage relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl" aria-label="Conversa com o Jefrey">
        <div className="relative min-h-[52%] flex-1" onPointerMove={onTilt} onPointerLeave={offTilt}>
        <div ref={stageRef} className="jf-stage-core absolute inset-0 will-change-transform">
        <div className="jf-rings" aria-hidden="true" />
          <div ref={tiltRef} className="jf-tilt h-full w-full cursor-pointer" role="button" tabIndex={0} aria-label="Toque no avatar para falar com o Jefrey" onClick={() => void toggleVoiceMode()} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); void toggleVoiceMode() } }}>
          <BrainStage state={brainState} level={speaker.speaking ? Math.max(micLevel, voiceLvl, 0.25) : micLevel} note={streaming || listeningNow ? null : note} className="h-full w-full" />
        </div>
        </div>
        <span className="jf-corner jf-corner-tl" /><span className="jf-corner jf-corner-tr" /><span className="jf-corner jf-corner-bl" /><span className="jf-corner jf-corner-br" />

        {/* topo: relogio, estado e atalhos */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between p-3">
          <button type="button" onClick={() => setShowList(v => !v)} className={`jf-focus pointer-events-auto rounded-md border border-white/15 bg-black/40 px-2.5 py-1 text-xs text-white/75 md:hidden ${easy ? "hidden" : ""}`}>Conversas</button>
          <button type="button" onClick={() => setTodayOpen(true)} className="jf-focus jf-chip pointer-events-auto ml-auto mr-3 rounded-full border border-white/20 bg-black/40 px-3 py-1 text-xs text-white/85">☀️ Hoje</button>
          <span className="text-xs tabular-nums tracking-[0.3em] text-[hsl(var(--hue)_80%_75%)] opacity-80">
            {clock.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        {hud && <HudOverlay messages={active.messages} activity={activity} />}
        {hud && <LivePanel />}

        {todayOpen && <TodayPopup name={myName ?? undefined} onClose={() => setTodayOpen(false)} />}

        {/* aprovacao de acao de risco */}
        {pendingApproval !== undefined && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/55 p-4" role="alertdialog" aria-label="Aprovação necessária">
            <div className="jf-panel w-full max-w-md border-amber-400/40 bg-[#07141b] p-5">
              <p className="text-lg font-medium text-amber-200">Preciso da sua aprovação</p>
              <p className="mt-1 text-base text-white/75">
                {pendingApproval.label ? <>Ação: <b>{pendingApproval.label}</b>. </> : null}Pode ter efeitos reais. Você autoriza?
              </p>
              <div className="mt-4 flex gap-2">
                <button type="button" onClick={() => void decide("approved")} className="jf-btn jf-focus px-5 py-2.5 text-base">Aprovar</button>
                <button type="button" onClick={() => void decide("rejected")} className="jf-focus rounded-lg border border-white/20 px-5 py-2.5 text-base text-white/85 hover:bg-white/5">Negar</button>
              </div>
            </div>
          </div>
        )}

        </div>

        {/* doca: legenda, atalhos, voz, texto e opcoes (fora do cerebro, nunca por cima dele) */}
        <div className="relative z-30 flex max-h-[46%] shrink-0 flex-col items-center gap-3 overflow-y-auto border-t border-white/10 bg-black/50 px-4 pb-4 pt-4">
          <div className="w-full max-w-lg"><BriefingCard /></div>
          {empty && (
            <>
              <div className="max-w-xl text-center">
                <h2 className="text-lg font-semibold text-white">{greeting(clock.getHours(), myName)}</h2>
                <p className="text-sm text-white/60">{myName ? "O que vamos resolver agora?" : "Eu sou o Jefrey. Como posso te chamar?"}</p>
              </div>
              <DayStrip onOpen={() => setTodayOpen(true)} />
            </>
          )}
          <LearnedToast streaming={streaming} />
          <QuickActions onAsk={t => void send(t)} onSummary={() => void speakSummary()} busy={summaryBusy} />

          {!empty && (caption || streaming) && (
            <div className="jf-glass relative max-w-2xl rounded-xl px-4 py-2.5 text-center" aria-live="polite">
              {lastUser && <p className="mb-1 truncate text-xs text-white/45">Você: {lastUser.content}</p>}
              {streaming && !caption ? (
                <span className="jf-typing" aria-label="Jefrey está pensando"><span /><span /><span /></span>
              ) : (
                <p className={`text-[15px] leading-snug ${lastAi?.error ? "text-red-200" : "text-white/95"} line-clamp-4`}>{caption}</p>
              )}
              {lastAi?.recall && lastAi.recall.length > 0 && <p className="mt-1 text-xs text-white/55"><span className="jf-accent">Lembrei:</span> {lastAi.recall.map(r => r.text).join(" · ")}</p>}
              {caption.length > 220 && <button type="button" onClick={() => setDrawer(true)} className="jf-focus mt-1 text-xs text-[hsl(var(--hue)_80%_75%)] underline">ver tudo</button>}
            </div>
          )}

          {lastIsError && !streaming && (
            <button type="button" onClick={retry} className="jf-btn jf-focus px-3 py-1 text-sm">Tentar de novo</button>
          )}

          {listener.supported && (
            <div className="flex w-full flex-col items-center gap-1">
              <button
                type="button"
                onClick={() => void toggleVoiceMode()}
                disabled={voiceReady.preparing}
                aria-pressed={view.tone === "listening" || view.tone === "hearing"}
                className={`jf-btn jf-focus flex min-h-[3rem] items-center justify-center gap-2.5 rounded-full px-7 py-2 text-base font-medium ${view.tone === "hearing" || view.tone === "speaking" ? "ring-2 ring-white/50" : ""}`}
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM6 11a6 6 0 0012 0M12 17v4" />
                </svg>
                <span aria-live="polite">{view.label}</span>
              </button>
              {view.hint && <p className="text-xs text-white/60">{view.hint}</p>}
              {unclear && view.tone === "listening" && <p role="status" className="text-sm text-amber-200">Não entendi. Pode repetir, devagar?</p>}
              {voiceReady.error && <p role="alert" className="text-center text-sm text-red-200">{voiceReady.error}</p>}
            </div>
          )}
          <Wave level={micLevel} speaking={speaker.speaking} className="max-w-md opacity-80" />

          <div className="flex w-full max-w-2xl items-end gap-1.5">
            <div className="relative">
              <button type="button" onClick={() => setOpts(v => !v)} aria-expanded={opts} aria-label="Opções" className="jf-focus rounded-lg border border-white/20 bg-black/40 px-2.5 py-2 text-sm text-white/75 hover:bg-white/10">⚙</button>
              {opts && (
                <div className="jf-glass absolute bottom-11 left-0 z-40 w-64 space-y-2 rounded-xl p-3 text-sm text-white/80">
                  <AvatarPicker />
                  {speaker.supported && (
                    <label className="flex cursor-pointer items-center gap-2">
                      <input type="checkbox" checked={voiceReply} onChange={e => { setVoiceReplyState(e.target.checked); writeFlag("jefrey_voice_reply", e.target.checked); if (!e.target.checked) speaker.cancel() }} />
                      Falar as respostas
                    </label>
                  )}
                  {speaker.supported && (speaker.voices.length > 1 || speaker.cloudOk) && (
                    <label className="block text-xs text-white/60">
                      Voz
                      <select
                        value={speaker.voiceChoice ?? ""}
                        onChange={e => { speaker.setVoice(e.target.value || null); speaker.cancel(); speaker.say("Oi, essa é a minha voz.") }}
                        className="jf-focus mt-1 w-full rounded-lg border border-white/20 bg-black/60 px-2 py-1.5 text-sm text-white"
                      >
                        <option value="">Automática (a mais natural)</option>
                        {speaker.engines?.engines.filter(e => e.id !== "browser" && e.available).map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
                        {speaker.voices.map(v => <option key={v.uri} value={v.uri}>{v.name.replace(/^Microsoft /, "")}</option>)}
                      </select>
                    </label>
                  )}
                  {listener.supported && (
                    <label className="flex cursor-pointer items-center gap-2">
                      <input type="checkbox" checked={continuous} onChange={e => { setContinuousState(e.target.checked); writeFlag("jefrey_voice_continuous", e.target.checked) }} />
                      Conversa contínua
                    </label>
                  )}
                  {listener.supported && (
                    <label className="flex cursor-pointer items-center gap-2" title="O microfone fica ligado e eu só entendo o que você fala quando começa com 'Jefrey'. Nada é guardado nem enviado para a internet.">
                      <input type="checkbox" checked={wakeOn} onChange={() => void toggleWake()} />
                      Chamar pelo nome ("Jefrey, …")
                    </label>
                  )}
                  <label className="flex cursor-pointer items-center gap-2" title="Medidores e registro sobre o avatar (telas largas)">
                    <input type="checkbox" checked={hud} onChange={e => { setHud(e.target.checked); writeFlag("jefrey_hud", e.target.checked) }} />
                    Painel Jarvis
                  </label>
                </div>
              )}
            </div>
            {!easy && <button type="button" onClick={() => setShowList(v => !v)} aria-pressed={showList} aria-label="Minhas conversas" className="jf-focus rounded-lg border border-white/20 bg-black/40 px-2.5 py-2 text-sm text-white/75 hover:bg-white/10">Conversas</button>}
            <button type="button" onClick={() => setDrawer(true)} aria-label="Histórico da conversa" className="jf-focus rounded-lg border border-white/20 bg-black/40 px-2.5 py-2 text-sm text-white/75 hover:bg-white/10">Histórico</button>
            <textarea
              ref={taRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
              rows={1}
              maxLength={10000}
              placeholder="Ou escreva aqui…"
              aria-label="Mensagem para o Jefrey"
              className="jf-focus max-h-28 min-h-[38px] flex-1 resize-none rounded-lg border border-white/15 bg-black/45 px-3 py-2 text-sm outline-none placeholder:text-white/35"
              style={{ height: "auto" }}
              onInput={e => {
                const el = e.currentTarget
                el.style.height = "auto"
                el.style.height = Math.min(el.scrollHeight, 112) + "px"
              }}
            />
            {streaming ? (
              <button type="button" onClick={stop} className="jf-focus rounded-lg border border-white/25 bg-black/40 px-3 py-2 text-sm text-white/85 hover:bg-white/10">Parar</button>
            ) : (
              <button type="button" onClick={() => void send()} disabled={!input.trim()} className="jf-btn jf-focus px-3 py-2 text-sm">Enviar</button>
            )}
          </div>
          {listener.error && <p role="alert" className="text-center text-xs text-red-300">{listener.error}</p>}
        </div>

        {/* gaveta do historico */}
        {drawer && (
          <div className="absolute inset-y-0 right-0 z-50 flex w-[min(30rem,100%)] flex-col border-l border-white/10 bg-[#050d13]/95 backdrop-blur" role="dialog" aria-label="Histórico da conversa">
            <div className="flex items-center justify-between border-b border-white/10 p-3">
              <h2 className="text-lg font-medium text-white">Histórico</h2>
              <button type="button" onClick={() => setDrawer(false)} className="jf-focus rounded-lg border border-white/20 px-3 py-1.5 text-sm text-white/85 hover:bg-white/10">Fechar</button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-3" role="log" aria-live="polite" aria-label="Mensagens">
              {empty ? <p className="py-6 text-center text-base text-white/60">Ainda não conversamos. Toque no botão de voz e fale comigo.</p> : messageList}
              <div ref={endRef} />
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
