import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { BrainStage, type BrainState } from "@/components/brain/BrainStage"
import { MessageText } from "@/components/MessageText"
import { authedFetch, ensureSession } from "@/lib/session"
import {
  loadActiveId, loadThreads, newThread, saveActiveId, saveThreads, streamChat, titleFrom, uid,
  type Message, type Thread,
} from "@/lib/chat"

const SUGGESTIONS = [
  "O que você consegue fazer por mim?",
  "Me ajude a organizar meu dia",
  "Explique o que é RAM em duas frases",
  "Guarde isto: meu café favorito é sem açúcar",
]

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
  const [pendingApproval, setPendingApproval] = useState<string | null | undefined>(undefined)
  const [showList, setShowList] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
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

  const brainState: BrainState = pendingApproval !== undefined
    ? "approval"
    : streaming
      ? gotToken ? "responding" : "thinking"
      : "idle"

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
    const result = await streamChat(
      text,
      tid,
      {
        onToken: chunk => {
          setGotToken(true)
          updateThread(tid, t => ({
            ...t,
            messages: t.messages.map(m => (m.id === aiMsg.id ? { ...m, content: m.content + chunk } : m)),
          }))
        },
        onPendingApproval: id => setPendingApproval(id ?? null),
      },
      ctrl.signal,
    )
    setStreaming(false)
    abortRef.current = null
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

  function stop() {
    abortRef.current?.abort()
  }

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
    if (!pendingApproval) {
      setPendingApproval(undefined)
      return
    }
    const r = await authedFetch(`/approvals/${pendingApproval}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision, decided_by: "usuario" }),
    })
    setPendingApproval(undefined)
    updateThread(active.id, t => ({
      ...t,
      messages: [
        ...t.messages,
        {
          id: uid(), role: "assistant", at: Date.now(), error: !r.ok,
          content: r.ok
            ? decision === "approved" ? "Aprovado. Envie a mensagem de novo para eu continuar." : "Negado. Não vou executar essa ação."
            : "Não consegui registrar sua decisão. Tente de novo.",
        },
      ],
    }))
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void send()
    }
  }

  const empty = active.messages.length === 0
  const lastIsError = active.messages.length > 0 && active.messages[active.messages.length - 1]!.error

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* lista de conversas */}
      <aside
        className={`jf-panel absolute inset-y-0 left-0 z-20 w-72 shrink-0 flex-col p-3 md:static md:flex ${showList ? "flex" : "hidden"}`}
        aria-label="Conversas"
      >
        <button type="button" onClick={startNew} disabled={streaming} className="jf-btn jf-focus mb-3 px-3 py-2 text-sm">
          + Nova conversa
        </button>
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
                className={`jf-focus min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-left text-sm ${
                  t.id === activeId ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5"
                }`}
              >
                {t.title}
              </button>
              <button
                type="button"
                onClick={() => removeThread(t.id)}
                aria-label={`Apagar conversa ${t.title}`}
                className="jf-focus rounded px-2 py-1 text-white/30 opacity-0 hover:text-red-300 group-hover:opacity-100 focus:opacity-100"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {/* conversa */}
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="mb-2 flex items-center gap-2 md:hidden">
          <button type="button" onClick={() => setShowList(v => !v)} className="jf-btn jf-focus px-3 py-1.5 text-sm">
            Conversas
          </button>
        </div>

        <BrainStage state={brainState} className={empty ? "h-[34vh] min-h-[200px]" : "h-[22vh] min-h-[130px]"} />

        <div className="min-h-0 flex-1 overflow-y-auto px-1" role="log" aria-live="polite" aria-label="Mensagens">
          {empty && (
            <div className="mx-auto mt-2 max-w-xl text-center">
              <h2 className="text-xl font-semibold text-white">Oi, eu sou o Jefrey.</h2>
              <p className="mt-1 text-sm text-white/60">Pergunte qualquer coisa. Roda no seu computador, e seus dados ficam com você.</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map(s => (
                  <button key={s} type="button" onClick={() => void send(s)} className="jf-btn jf-focus px-3 py-1.5 text-sm">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ul className="mx-auto max-w-3xl space-y-3 py-2">
            {active.messages.map((m, idx) => {
              const isLast = idx === active.messages.length - 1
              const typing = streaming && isLast && m.role === "assistant" && !m.content
              return (
                <li key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${
                      m.role === "user" ? "jf-bubble-user" : m.error ? "jf-bubble-err" : "jf-bubble-ai"
                    }`}
                  >
                    {typing ? (
                      <span className="jf-typing" aria-label="Jefrey está pensando">
                        <span />
                        <span />
                        <span />
                      </span>
                    ) : (
                      <MessageText text={m.content} />
                    )}
                  </div>
                </li>
              )
            })}
          </ul>

          {pendingApproval !== undefined && (
            <div className="jf-panel mx-auto my-3 max-w-xl border-amber-400/40 p-4" role="alertdialog" aria-label="Aprovação necessária">
              <p className="font-medium text-amber-200">Preciso da sua aprovação</p>
              <p className="mt-1 text-sm text-white/70">Esta ação pode ter efeitos reais. Você autoriza?</p>
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => void decide("approved")} className="jf-btn jf-focus px-4 py-1.5 text-sm">
                  Aprovar
                </button>
                <button type="button" onClick={() => void decide("rejected")} className="jf-focus rounded-lg border border-white/15 px-4 py-1.5 text-sm text-white/80 hover:bg-white/5">
                  Negar
                </button>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* campo de mensagem */}
        <div className="mx-auto w-full max-w-3xl pb-1 pt-2">
          {lastIsError && !streaming && (
            <button type="button" onClick={retry} className="jf-btn jf-focus mb-2 px-3 py-1 text-sm">
              Tentar de novo
            </button>
          )}
          <div className="jf-panel flex items-end gap-2 p-2">
            <textarea
              ref={taRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
              rows={1}
              maxLength={10000}
              placeholder="Escreva uma mensagem…"
              aria-label="Mensagem para o Jefrey"
              className="jf-focus max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-white/35"
              style={{ height: "auto" }}
              onInput={e => {
                const el = e.currentTarget
                el.style.height = "auto"
                el.style.height = Math.min(el.scrollHeight, 160) + "px"
              }}
            />
            {streaming ? (
              <button type="button" onClick={stop} className="jf-focus rounded-lg border border-white/20 px-4 py-2 text-sm text-white/85 hover:bg-white/5">
                Parar
              </button>
            ) : (
              <button type="button" onClick={() => void send()} disabled={!input.trim()} className="jf-btn jf-focus px-4 py-2 text-sm">
                Enviar
              </button>
            )}
          </div>
          <p className="mt-1 text-center text-[11px] text-white/30">Enter envia · Shift+Enter quebra a linha</p>
        </div>
      </section>
    </div>
  )
}
