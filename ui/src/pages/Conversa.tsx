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
import { plainText } from "@/lib/utils"
import { haltComputer } from "@/lib/halt"
import QuickActions from "@/components/QuickActions"
import LearnedToast from "@/components/LearnedToast"
import TodayPopup from "@/components/TodayPopup"
import NewsPopup from "@/components/NewsPopup"
import DayStrip from "@/components/DayStrip"
import AvatarPicker from "@/components/AvatarPicker"
import { LivePanel } from "@/components/hud/LivePanel"
import { getToday, spokenSummary } from "@/lib/today"
import { useVoicePulse } from "@/hooks/useVoicePulse"
import { SentenceBuffer } from "@/lib/voice/sentences"
import { isDesktop, publishOrb } from "@/lib/shell"
import { authedFetch, ensureSession } from "@/lib/session"
import {
  newThread, saveActiveId, saveThreads, streamChat, titleFrom, uid,
  type Message, type Thread, type ToolStep,
} from "@/lib/chat"
import { initThreads, readFlag, writeFlag } from "@/lib/conversaState"
import MessageList from "@/components/conversa/MessageList"
import ThreadList from "@/components/conversa/ThreadList"
import ApprovalDialog from "@/components/conversa/ApprovalDialog"
import HistoryDrawer from "@/components/conversa/HistoryDrawer"
import OptionsMenu from "@/components/conversa/OptionsMenu"
import Composer from "@/components/conversa/Composer"

const SUGGESTIONS = [
  "Me ajude a organizar meu dia",
  "Me lembra de beber água daqui a 30 minutos",
  "Quais são meus lembretes?",
  "O que você consegue fazer por mim?",
]

/** Ferramentas que respondem na hora: nao precisam do "um instante". */
const FAST_TOOLS = new Set(["current_time", "calculator", "list_reminders"])

export default function Conversa() {
  const init = useMemo(initThreads, [])
  const [threads, setThreads] = useState<Thread[]>(init.threads)
  const [activeId, setActiveId] = useState(init.active)
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [gotToken, setGotToken] = useState(false)
  const [pendingApproval, setPendingApproval] = useState<{ id: string | null; label?: string; detail?: string } | undefined>(undefined)
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

  // o orbe (outra janela do app) copia o estado do cerebro; so quando muda, e com o nivel arredondado
  const orbLevel = Math.round((speaker.speaking ? Math.max(micLevel, voiceLvl, 0.25) : micLevel) * 10) / 10
  useEffect(() => {
    if (isDesktop()) publishOrb({ state: brainState, level: orbLevel })
  }, [brainState, orbLevel])

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
    let acked = false // ja falou o "um instante" nesta resposta?
    let gotAnyToken = false
    const result = await streamChat(
      text,
      tid,
      {
        onToken: chunk => {
          gotAnyToken = true
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
        onToolStart: (tool, label, risk) => {
          if (!acked && !gotAnyToken && voiceReplyRef.current && risk !== "high" && !FAST_TOOLS.has(tool)) {
            acked = true
            speaker.say("Um instante, já vejo isso.")
          }
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m =>
              m.id === aiMsg.id ? { ...m, tools: [...(m.tools ?? []), { tool, label, risk, state: "running" } as ToolStep] } : m,
            ),
          }))
        },
        onApprovalRequired: (id, tool, label, detail) => {
          setPendingApproval({ id, label, detail })
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

  const messageList = <MessageList messages={active.messages} streaming={streaming} />

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* lista de conversas (so fora do modo Facil) */}
      <ThreadList
        threads={threads}
        activeId={activeId}
        streaming={streaming}
        visible={!easy && showList}
        onNew={startNew}
        onPick={id => { setActiveId(id); setShowList(false); setPendingApproval(undefined) }}
        onRemove={removeThread}
      />

      {/* palco: o avatar ocupa quase toda a tela e as opcoes ficam pequenas por cima */}
      <section className="jf-stage relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl" aria-label="Conversa com o Jefrey">
        <div className="relative min-h-0 basis-[80%] grow-0 shrink" onPointerMove={onTilt} onPointerLeave={offTilt}>
        <div ref={stageRef} className="jf-stage-core absolute inset-0 will-change-transform">
          <div ref={tiltRef} className="jf-tilt h-full w-full cursor-pointer" role="button" tabIndex={0} aria-label="Toque no avatar para falar com o Jefrey" onClick={() => void toggleVoiceMode()} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); void toggleVoiceMode() } }}>
          <BrainStage state={brainState} level={speaker.speaking ? Math.max(micLevel, voiceLvl, 0.25) : micLevel} note={streaming || listeningNow ? null : note} className="h-full w-full" />
        </div>
        </div>

        {/* topo: relogio, estado e atalhos */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between p-3">
          <button type="button" onClick={() => setShowList(v => !v)} className={`jf-focus pointer-events-auto rounded-md border border-white/15 bg-black/40 px-2.5 py-1 text-xs text-white/75 md:hidden ${easy ? "hidden" : ""}`}>Conversas</button>
          <button type="button" onClick={() => setTodayOpen(true)} className="jf-focus jf-chip pointer-events-auto ml-auto mr-3 rounded-full border border-white/20 bg-black/40 px-3 py-1 text-xs text-white/85">☀️ Hoje</button>
          <span className="jf-serif text-lg tabular-nums text-[hsl(var(--hue)_55%_78%)] opacity-90">
            {clock.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        {hud && <HudOverlay messages={active.messages} activity={activity} />}
        {hud && <LivePanel />}

        {/* painel lateral: resumo do dia e saudacao ficam pequenos no canto, o cerebro continua inteiro */}
        <aside className="pointer-events-none absolute bottom-2 right-3 z-20 hidden w-64 flex-col gap-2 lg:flex" aria-label="Resumo">
          <div className="pointer-events-auto"><BriefingCard /></div>
          {empty && (
            <div className="pointer-events-auto jf-glass rounded-xl px-3 py-2">
              <h2 className="text-sm font-semibold text-white">{greeting(clock.getHours(), myName)}</h2>
              <p className="text-xs text-white/55">{myName ? "O que vamos resolver agora?" : "Eu sou o Jefrey. Como posso te chamar?"}</p>
            </div>
          )}
          {empty && <div className="pointer-events-auto"><DayStrip onOpen={() => setTodayOpen(true)} /></div>}
        </aside>

        <NewsPopup />
        {todayOpen && <TodayPopup name={myName ?? undefined} onClose={() => setTodayOpen(false)} />}

        {/* aprovacao de acao de risco */}
        {pendingApproval !== undefined && <ApprovalDialog label={pendingApproval.label} detail={pendingApproval.detail} onDecide={d => void decide(d)} />}

        </div>

        {/* doca: legenda, atalhos, voz, texto e opcoes (fora do cerebro, nunca por cima dele) */}
        <div className="relative z-30 flex min-h-[8.75rem] basis-[20%] grow shrink-0 flex-col border-t border-white/[0.07] bg-[hsl(24_14%_5%/0.7)] px-4 py-2">
          {/* parte que rola: atalhos, resposta e avisos. A caixa de digitar fica sempre embaixo, visivel. */}
          <div className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col items-center justify-end gap-1.5 overflow-y-auto pb-1">
          <div className="w-full max-w-lg lg:hidden"><BriefingCard /></div>
          <LearnedToast streaming={streaming} />
          {(empty || !caption) && <QuickActions onAsk={t => void send(t)} onSummary={() => void speakSummary()} busy={summaryBusy} />}

          {!empty && (caption || streaming) && (
            <div className="jf-glass relative max-w-2xl rounded-xl px-4 py-1.5 text-center" aria-live="polite">
              {lastUser && <p className="truncate text-xs text-white/45">Você: {lastUser.content}</p>}
              {streaming && !caption ? (
                <span className="jf-typing" aria-label="Jefrey está pensando"><span /><span /><span /></span>
              ) : (
                <p className={`text-[15px] leading-snug ${lastAi?.error ? "text-red-200" : "text-white/95"} line-clamp-2`}>{plainText(caption)}</p>
              )}
              {lastAi?.recall && lastAi.recall.length > 0 && <p className="mt-1 line-clamp-1 text-xs text-white/55"><span className="jf-accent">Lembrei:</span> {lastAi.recall.map(r => r.text).join(" · ")}</p>}
              {caption.length > 220 && <button type="button" onClick={() => setDrawer(true)} className="jf-focus mt-1 text-xs text-[hsl(var(--hue)_80%_75%)] underline">ver tudo</button>}
            </div>
          )}

          {lastIsError && !streaming && (
            <button type="button" onClick={retry} className="jf-btn jf-focus px-3 py-1 text-sm">Tentar de novo</button>
          )}

          </div>
          <div className="mx-auto flex w-full shrink-0 flex-col items-center gap-1.5">
          <Wave level={micLevel} speaking={speaker.speaking} className={`max-w-md opacity-80 ${speaker.speaking || micLevel > 0.02 ? "" : "hidden"}`} />

          <div className="flex w-full max-w-4xl items-end gap-2">
          {listener.supported && (
            <div className="flex shrink-0 flex-col items-center gap-1 pb-1">
              <button
                type="button"
                onClick={() => void toggleVoiceMode()}
                disabled={voiceReady.preparing}
                aria-pressed={view.tone === "listening" || view.tone === "hearing"}
                className={`jf-btn jf-focus flex min-h-[2.5rem] items-center justify-center gap-2 rounded-full px-4 py-1 text-sm font-medium ${view.tone === "hearing" || view.tone === "speaking" ? "ring-2 ring-white/50" : ""}`}
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM6 11a6 6 0 0012 0M12 17v4" />
                </svg>
                <span aria-live="polite" className="hidden xl:inline">{view.label}</span>
              </button>
            </div>
          )}
          <div className="min-w-0 flex-1">
          <Composer
            menuOpen={opts}
            onToggleMenu={() => setOpts(v => !v)}
            menu={
              <OptionsMenu
                speaker={speaker}
                listenerSupported={listener.supported}
                voiceReply={voiceReply}
                onVoiceReply={on => { setVoiceReplyState(on); writeFlag("jefrey_voice_reply", on) }}
                continuous={continuous}
                onContinuous={on => { setContinuousState(on); writeFlag("jefrey_voice_continuous", on) }}
                wakeOn={wakeOn}
                onToggleWake={() => void toggleWake()}
                hud={hud}
                onHud={on => { setHud(on); writeFlag("jefrey_hud", on) }}
              />
            }
            showThreadsButton={!easy}
            threadsOpen={showList}
            onToggleThreads={() => setShowList(v => !v)}
            onOpenHistory={() => setDrawer(true)}
            taRef={taRef}
            input={input}
            onInput={setInput}
            onKey={onKey}
            streaming={streaming}
            onStop={stop}
            onSend={() => void send()}
          />
          </div>
          </div>
          {listener.supported && view.hint && <p className="text-xs text-white/60">{view.hint}</p>}
          {listener.supported && unclear && view.tone === "listening" && <p role="status" className="text-sm text-amber-200">Não entendi. Pode repetir, devagar?</p>}
          {listener.supported && voiceReady.error && <p role="alert" className="text-center text-sm text-red-200">{voiceReady.error}</p>}
          {listener.error && <p role="alert" className="text-center text-xs text-red-300">{listener.error}</p>}
        </div>
        </div>

        {/* gaveta do historico */}
        {drawer && <HistoryDrawer empty={empty} onClose={() => setDrawer(false)} endRef={endRef}>{messageList}</HistoryDrawer>}
      </section>
    </div>
  )
}
