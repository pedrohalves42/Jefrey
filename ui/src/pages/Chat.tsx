import { useState, useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, getUserId, getThreadId, setThreadId, getToken, mapHttpError } from "@/lib/api"

type Msg = { role: "user" | "assistant"; content: string }

export default function Chat() {
  const [input, setInput] = useState("")
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Ola! Sou o Jefrey — 1 programa, 7 pecas. Digite sua mensagem. (thread demo-1)" },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [threadId, setThreadIdState] = useState(getThreadId())
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setThreadId(threadId); }, [threadId])
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, loading])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setError(null)
    const userMsg: Msg = { role: "user", content: text }
    setMsgs((m) => [...m, userMsg])
    setInput("")
    setLoading(true)
    try {
      const res = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, thread_id: threadId, user_id: getUserId() }),
      })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(mapHttpError(res.status) + (body ? " — " + body.slice(0, 300) : ""))
      }
      const data = await res.json().catch(() => ({}))
      // contrato: {response|message|output|content} — fail-closed: se vazio, mostra JSON
      const reply: string = data.response || data.message || data.output || data.content || JSON.stringify(data).slice(0, 800) || "(sem resposta)"
      setMsgs((m) => [...m, { role: "assistant", content: reply }])
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      // CIPHER-021: nunca silent except — exibe erro humano + CTA Settings se 401
      if (msg.includes("401") || msg.includes("Nao autenticado")) {
        setError(msg + " ")
      } else {
        setError(msg)
      }
      // fallback visual sem quebrar Axiom #1
      setMsgs((m) => [...m, { role: "assistant", content: "Sem conexao com API :8000 ou erro acima. Verifique Settings/token e docker 7/7." }])
    } finally {
      setLoading(false)
    }
  }

  const hasToken = !!getToken()

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Chat <Badge variant="secondary">thread {threadId}</Badge>
            {!hasToken && <Badge variant="destructive">sem token</Badge>}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            POST /chat com Bearer + user_id (<span className="font-mono">{getUserId()}</span>) — Axiom #2 isolamento. Sem token = 401 fail-closed.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              placeholder="user_id em Settings — thread_id editavel"
              value={threadId}
              onChange={(e) => setThreadIdState(e.target.value)}
              aria-label="thread_id"
            />
            <Badge variant="outline">{getUserId()}</Badge>
          </div>
          <div ref={listRef} className="h-[42vh] overflow-y-auto rounded-md border p-3 space-y-2 bg-muted/20" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-card border"}`}>
                  <span className="font-medium mr-1">{m.role === "user" ? "Voce:" : "Jefrey:"}</span>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && <div className="text-sm text-muted-foreground animate-pulse">Jefrey pensando…</div>}
          </div>
          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm">
              <span>{error}</span>
              {(error.includes("401") || error.includes("Nao autenticado")) && (
                <Link to="/settings" className="ml-2 underline font-medium">Ir para Settings →</Link>
              )}
            </div>
          )}
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              placeholder="Digite sua mensagem e pressione Enter"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
              aria-label="mensagem"
            />
            <Button onClick={send} disabled={loading || !input.trim()}>{loading ? "Enviando…" : "Enviar"}</Button>
          </div>
          {!hasToken && (
            <p className="text-xs text-muted-foreground">
              Dica: cole seu Bearer token em <Link to="/settings" className="underline">Settings</Link> para sair do 401. Em dev, use JEFREY_API__SECRET_KEY.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
