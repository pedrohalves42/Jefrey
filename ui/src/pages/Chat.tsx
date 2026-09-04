import { useState, useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, getUserId, getThreadId, setThreadId, getToken, mapHttpError, ensureDevToken } from "@/lib/api"
import { VoiceButton } from "@/components/VoiceButton"
import { ConnectionHub } from "@/components/ConnectionHub"

type Msg = { role: "user" | "assistant"; content: string }

function renderMarkdown(text: string) {
  // lightweight markdown: **bold**, `code`, ```code```, - list, [link](url)
  const esc = (s: string) => s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  let html = esc(text)
  // code blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-black/20 rounded p-2 overflow-x-auto text-xs font-mono"><code>$1</code></pre>')
  // inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-black/10 px-1 py-0.5 rounded text-xs font-mono">$1</code>')
  // bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer" class="underline text-cyan-600">$1</a>')
  // line breaks
  html = html.replace(/\n/g, '<br/>')
  return html
}

export default function Chat() {
  const [input, setInput] = useState("")
  const [llmOk,setLlmOk] = useState<boolean|null>(null)
  useEffect(()=>{ fetch("/health").then(r=>setLlmOk(r.ok)).catch(()=>setLlmOk(false)); },[])
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Ola! Sou o Jefrey â€” 1 programa, 7 pecas. Digite sua mensagem. (thread demo-1)" },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [threadId, setThreadIdState] = useState(getThreadId())
  const [hasToken, setHasToken] = useState<boolean>(() => !!getToken())
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setThreadId(threadId); }, [threadId])
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, loading])
  useEffect(() => {
    if (!getToken()) {
      ensureDevToken().then((t) => setHasToken(!!t))
    }
  }, [])

  async function ensureAndRetry(sendFn: () => Promise<void>) {
    const tok = await ensureDevToken()
    if (tok) {
      setHasToken(true)
      setError(null)
      await sendFn()
    } else {
      setError("Nao foi possivel liberar acesso automaticamente. Va em Settings > Obter token dev.")
    }
  }

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
      if (res.status === 401) {
        const body = await res.text()
        throw new Error("401 " + body.slice(0,200))
      }
      if (!res.ok) {
        const body = await res.text()
        throw new Error(mapHttpError(res.status) + (body ? " â€” " + body.slice(0, 300) : ""))
      }
      const data = await res.json().catch(() => ({}))
      const reply: string = data.response || data.message || data.output || data.content || JSON.stringify(data).slice(0, 800) || "(sem resposta)"
      setMsgs((m) => [...m, { role: "assistant", content: reply }])
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.includes("401") || msg.includes("Nao autenticado")) {
        setError("Sessao expirou â€” clique para liberar acesso (1s).")
      } else {
        setError(msg)
      }
      setMsgs((m) => [...m, { role: "assistant", content: "Sem conexao com API :8000 ou erro acima. Verifique Settings/token e docker 7/7." }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {llmOk===false && <div className="text-amber-400 text-xs p-2 mb-2 border border-amber-500/30 rounded bg-amber-500/10">LLM offline â€” modo mock (inicie Ollama: ollama serve & ollama pull qwen2:0.5b)</div>}
      <Card className="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Chat <Badge variant="secondary">thread {threadId}</Badge>
            {hasToken ? <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30">Pronto</Badge> : <Badge variant="secondary">conectando...</Badge>}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            POST /chat com Bearer + user_id (<span className="font-mono">{getUserId()}</span>) â€” Axiom #2 isolamento. {hasToken ? "Pronto para enviar." : "Liberando acesso automaticamente..."}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm glass"
              placeholder="user_id em Settings â€” thread_id editavel"
              value={threadId}
              onChange={(e) => setThreadIdState(e.target.value)}
              aria-label="thread_id"
            />
            <Badge variant="outline">{getUserId()}</Badge>
          </div>
          <div ref={listRef} className="h-[52vh] overflow-y-auto rounded-md border p-3 space-y-2 glass" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${m.role === "user" ? "bg-primary text-primary-foreground" : "glass border"}`}>
                  <span className="font-medium mr-1">{m.role === "user" ? "Voce:" : "Jefrey:"}</span>
                  <span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                </div>
              </div>
            ))}
            {loading && <div className="text-sm text-muted-foreground animate-pulse flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" /> Jefrey pensandoâ€¦</div>}
          </div>
          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm">
              <span>{error}</span>
              {(error.includes("401") || error.includes("Liberar") || error.includes("Sessao")) && (
                <Button size="sm" className="ml-2" onClick={() => ensureAndRetry(send)}>Liberar acesso (1s)</Button>
              )}
              {(error.includes("401") || error.includes("Nao autenticado")) && (
                <Link to="/settings" className="ml-2 underline font-medium">Ir para Settings â†’</Link>
              )}
            </div>
          )}
          <div className="flex gap-2 items-center">
            <VoiceButton onTranscript={(txt)=> setInput(txt)} onReply={(reply)=> setMsgs((m)=> [...m, { role: "assistant", content: reply }])} />
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm glass"
              placeholder="Digite sua mensagem e pressione Enter (ou use o microfone)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
              aria-label="mensagem"
            />
            <Button onClick={send} disabled={loading || !input.trim()}>{loading ? "Enviandoâ€¦" : "Enviar"}</Button>
          </div>
      <ConnectionHub onResult={(r)=> setMsgs(m=>[...m, { role: "assistant", content: `[${r.kind}] ${r.text}` }])} />
          {!hasToken && (
            <p className="text-xs text-muted-foreground">
              Conectando automaticamenteâ€¦ Se falhar, <Link to="/settings" className="underline">Settings â†’ Obter token dev</Link> (ja esta pronto, este e so avancado).
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
