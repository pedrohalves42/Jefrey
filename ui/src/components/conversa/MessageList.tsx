import { Link } from "react-router-dom"
import { MessageText } from "@/components/MessageText"
import type { Message } from "@/lib/chat"

const TOOL_TONE: Record<string, string> = {
  ok: "border-emerald-400/30 text-emerald-200",
  failed: "border-red-400/30 text-red-200",
  waiting: "border-amber-400/40 text-amber-200",
}
const TOOL_MARK: Record<string, string> = { ok: "✓ ", failed: "✗ ", waiting: "⏳ " }

/** Historico da conversa: balões, passos das ferramentas e "Lembrei de". So apresenta; nao guarda estado. */
export default function MessageList({ messages, streaming }: { messages: Message[]; streaming: boolean }) {
  return (
    <ul className="space-y-3 py-2">
      {messages.map((m, idx) => {
        const isLast = idx === messages.length - 1
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
                        <span key={i} title={t.summary || t.label} className={`rounded-full border px-2 py-0.5 text-xs ${TOOL_TONE[t.state] ?? "border-white/20 text-white/60"}`}>
                          {TOOL_MARK[t.state] ?? "… "}
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
}
