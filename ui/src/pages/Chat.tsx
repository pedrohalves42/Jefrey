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
  const esc = (s: string) => s.replace(/&/g,"&").replace(/</g,"<").replace(/>/g,">")
  let html = esc(text)
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-black/30 rounded p-2 overflow-x-auto text-xs font-mono border border-cyan-500/20"><code>$1</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="bg-cyan-500/10 px-1 py-0.5 rounded text-xs font-mono border border-cyan-500/20">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-cyan-300">$1</strong>')
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer" class="underline text-cyan-400 hover:text-cyan-300">$1</a>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

export default function Chat() {
  const [input, setInput] = useState("")
  const [llmOk,setLlmOk] = useState<boolean|null>(null)
  useEffect(()=>{ fetch("/health").then(r=>setLlmOk(r.ok)).catch(()=>setLlmOk(false)); },[])
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Good evening, Sir. Jefrey online Ã¢â‚¬â€ 7/7 systems nominal. How may I assist you? (diga 'oi' ou clique no microfone)" },
  ])
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [threadId, setThreadIdState] = useState(getThreadId())
  const [hasToken, setHasToken] = useState<boolean>(() => !!getToken())
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setThreadId(threadId); }, [threadId])
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, loading, polling])
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

  function setHud(s: string){ try{ (window as any).__setHudState?.(s) }catch{} }
  async function pollStatus(tid: string): Promise<string> {
    setPolling(true)
    try {
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500))
        try {
          const r = await apiFetch(`/chat/status/${encodeURIComponent(tid)}`)
          if (!r.ok) continue
          const j: any = await r.json().catch(() => ({}))
          if (j.status === "complete") return j.response || j.message || j.output || JSON.stringify(j).slice(0, 2000) || "(sem resposta)"
          if (j.status === "error") throw new Error(j.error || "erro no agente")
          if (j.status === "pending_approval") return j.message || `Aprovacao pendente ${j.approval_id} â€” vÃ¢ em Approvals`
          if (j.status === "idle") continue
        } catch {}
      }
      throw new Error("Timeout 60s â€” Sir, o reator ainda esta aquecendo (qwen2.5:0.5b frio). Tente novamente.")
    } finally {
      setPolling(false)
    }
  }

  async function send() {
    setHud("thinking")
    const text = input.trim()
    if (!text || loading) return
    setError(null)
    const userMsg: Msg = { role: "user", content: text }
    setMsgs((m) => [...m, userMsg])
    setInput("")
    setLoading(true)
    // placeholder para streaming token-por-token (typewriter) com lip-sync realtime
    const placeholderIdx = msgs.length + 1
    let streamed = ""
    let didStream = false
    let streamDone = false
    let lastUpdateTime = 0
    const updateInterval = 20 // Update every 20ms for smoother typewriter
    // helper para atualizar placeholder com timing control e lip-sync
    function upsertPlaceholder(chunk: string, force: boolean = false){
      const now = Date.now()
      if(!didStream || force || now - lastUpdateTime > updateInterval){
        if(!didStream){
          didStream = true
          setMsgs((m) => [...m, { role: "assistant" as const, content: "" }])
        }
        streamed += chunk
        setMsgs((m) => m.map((msg,i) => i === placeholderIdx ? { ...msg, content: streamed } : msg))
        lastUpdateTime = now
        // Lip-sync: update hud speaking state based on stream activity
        setHud("speaking")
        // Reset idle after a brief pause of no new tokens
        clearTimeout(upsertPlaceholder.idleTimer)
        upsertPlaceholder.idleTimer = setTimeout(()=>{
          if(didStream && !streamDone){
            setHud("idle")
          }
        }, 1500 - streamed.length * 20) // Faster idle for longer messages
      }
    }
    function finalizeStream(){
      if(didStream && !streamDone){
        streamDone = true
        setHud("speaking")
        setTimeout(()=> setHud("idle"), Math.max(1000, streamed.length * 30))
      }
    }
    // Cleanup idle timer on component unmount
    useEffect(()=>{clearTimeout(upsertPlaceholder.idleTimer)}, [])

    try {
      // Tenta SSE /chat/stream primeiro (DIFF4.1)
      const headers: Record<string,string> = { "Content-Type":"application/json" }
      try{
        const tok = localStorage.getItem("jefrey_token"); if(tok) headers["Authorization"] = `Bearer ${tok}`
        const uid = localStorage.getItem("jefrey_user_id") || "demo"; headers["X-User-Id"] = uid
      }catch{}
      let sseOk = false
      try{
        const r = await fetch("/chat/stream", {
          method: "POST",
          headers,
          body: JSON.stringify({ message: text, thread_id: threadId }),
        })
        if(r.ok && r.body && (r.headers.get("content-type")||"").includes("text/event-stream")){
          const reader = (r.body as ReadableStream<Uint8Array>).getReader()
          const decoder = new TextDecoder()
          let buf = ""
          let sawDone = false
          while(true){
            const {done, value} = await reader.read()
            if(done) break
            buf += decoder.decode(value, {stream:true})
            const lines = buf.split("\n")
            buf = lines.pop() || ""
            for(const line of lines){
              const t = line.trim()
              if(!t.startsWith("data:")) continue
              const dataStr = t.slice(5).trim()
              if(!dataStr) continue
              try{
                const evt = JSON.parse(dataStr)
                if(evt.type === "token" && evt.content){
                  upsertPlaceholder(evt.content)
                  sseOk = true
                } else if(evt.type === "done"){
                  sawDone = true
                } else if(evt.type === "pending_approval"){
                  const msg = evt.message || `Aprovacao pendente ${evt.approval_id || threadId}`
                  if(!didStream) setMsgs((m)=> [...m, { role:"assistant", content: msg }])
                  else setMsgs((m)=> m.map((x,i)=> i===placeholderIdx ? {...x, content: msg} : x))
                  sawDone = true; sseOk = true
                } else if(evt.type === "error"){
                  throw new Error(evt.message || "stream error")
                }
              }catch(e){
                const m2 = e instanceof Error ? e.message : String(e)
                if(m2.includes("stream error")) throw e
              }
            }
            if(sawDone) break
          }
          if(sawDone || sseOk) sseOk = true
        }
      }catch(e){
        // falha de stream -> fallback classico
        console.warn("SSE falhou, fallback classico", e)
      }
      if(sseOk){
        finalizeStream()
        if(!didStream){
          // stream retornou done sem tokens (ex: HITL) -> ja tratado
        }
        return
      }
      // fallback classico /chat
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
        throw new Error(mapHttpError(res.status) + (body ? " - " + body.slice(0, 300) : ""))
      }
      const data: any = await res.json().catch(() => ({}))
      let reply: string
      if (data.status === "complete") {
        reply = data.response || data.message || data.output || data.content || JSON.stringify(data).slice(0, 800) || "(sem resposta)"
      } else if (data.status === "running") {
        reply = await pollStatus(threadId)
      } else if (data.status === "pending_approval") {
        reply = data.message || `Aprovacao pendente ${data.approval_id}`
      } else {
        reply = data.response || data.message || data.output || data.content || JSON.stringify(data).slice(0, 800) || "(sem resposta)"
        if (!reply || reply.includes("Execucao longa")) reply = await pollStatus(threadId)
      }
      if(didStream){
        setMsgs((m) => m.map((msg,i) => i===placeholderIdx ? {...msg, content: reply} : msg))
      } else {
        setMsgs((m) => [...m, { role: "assistant", content: reply }])
      }
      setHud("speaking"); setTimeout(()=> setHud("idle"), Math.min(4000, reply.length*40))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.includes("401") || msg.includes("Nao autenticado")) {
        setError("Sessao expirou â€” clique para liberar acesso (1s).")
      } else {
        setError(msg)
      }
      setHud("idle");
      if(didStream){
        setMsgs((m) => m.map((x,i)=> i===placeholderIdx ? {...x, content: "Sir, erro: " + msg + " â€” verifique docker 7/7 e tente novamente." + (streamed ? "\n\n(parcial: "+streamed.slice(0,600)+")" : "")} : x))
      } else {
        setMsgs((m) => [...m, { role: "assistant", content: "Sir, erro: " + msg + " â€” verifique docker 7/7 e tente novamente." }])
      }
    } finally {
      setLoading(false)
      setPolling(false)
    }
  }

  return (
    <div className="space-y-4">
      {llmOk===false && <div className="text-amber-400 text-xs p-2 mb-2 border border-amber-500/30 rounded bg-amber-500/10">LLM offline â€” modo mock (inicie Ollama: ollama serve & ollama pull qwen2.5:0.5b)</div>}
      <Card className="glass border-cyan-500/20">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-cyan-100">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
            Jefrey <span className="text-xs font-normal text-cyan-400/70">Stark-mode â€” Jefrey capabilities</span>
            <Badge variant="secondary" className="ml-2 font-mono text-[10px]">thread {threadId}</Badge>
            {hasToken ? <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30">ONLINE</Badge> : <Badge variant="secondary" className="animate-pulse">conectando...</Badge>}
          </CardTitle>
          <p className="text-xs text-cyan-200/50 font-mono">
            Sir, sistemas em Stark Lab â€” Bearer + user_id <span className="font-mono text-cyan-300">{getUserId()}</span> â€” Axiom #2 isolamento. {hasToken ? "Pronto, Sir." : "Liberando acesso automaticamente..."}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-cyan-500/20 bg-black/20 px-3 py-2 text-sm text-cyan-100 placeholder:text-cyan-200/30 focus:border-cyan-400/50 focus:outline-none"
              placeholder="thread_id (edite se quiser isolar conversa)"
              value={threadId}
              onChange={(e) => setThreadIdState(e.target.value)}
              aria-label="thread_id"
            />
            <Badge variant="outline" className="border-cyan-500/30 text-cyan-300">{getUserId()}</Badge>
          </div>
          <div ref={listRef} className="h-[52vh] overflow-y-auto rounded-md border border-cyan-500/10 bg-black/30 p-3 space-y-3 backdrop-blur" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[82%] rounded-lg px-3 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "bg-cyan-600 text-white shadow-[0_0_12px_rgba(6,182,212,0.3)]" : "bg-white/5 border border-cyan-500/15 text-cyan-50 backdrop-blur"}`}>
                  <span className={`font-mono text-[10px] tracking-widest mr-2 ${m.role === "user" ? "text-cyan-100" : "text-cyan-400"}`}>{m.role === "user" ? "SIR:" : "JEFREY:"}</span>
                  <span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                </div>
              </div>
            ))}
            {(loading || polling) && (
              <div className="flex items-center gap-3 text-sm text-cyan-300/80 font-mono">
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="animate-pulse">{polling ? "Jefrey sintetizando, Sir..." : "Jefrey pensando..."}</span>
                <span className="flex gap-1 ml-2">
                  <span className="h-1 w-6 bg-cyan-400/60 rounded animate-pulse" style={{animationDelay:"0ms"}} />
                  <span className="h-1 w-8 bg-cyan-400/40 rounded animate-pulse" style={{animationDelay:"150ms"}} />
                  <span className="h-1 w-4 bg-cyan-400/60 rounded animate-pulse" style={{animationDelay:"300ms"}} />
                </span>
              </div>
            )}
          </div>
          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <span>{error}</span>
              {(error.includes("401") || error.includes("Liberar") || error.includes("Sessao")) && (
                <Button size="sm" className="ml-2 bg-cyan-600 hover:bg-cyan-700" onClick={() => ensureAndRetry(send)}>Liberar acesso (1s)</Button>
              )} 
              {(error.includes("401") || error.includes("Nao autenticado")) && (
                <Link to="/settings" className="ml-2 underline font-medium">Ir para Settings</Link>
              )}
            </div>
          )}
          <div className="flex gap-2 items-center">
            <VoiceButton onTranscript={(txt)=> setInput(txt)} onReply={(reply)=> setMsgs((m)=> [...m, { role: "assistant", content: reply }])} />
            <input
              className="flex-1 rounded-md border border-cyan-500/20 bg-black/20 px-3 py-2.5 text-sm text-cyan-100 placeholder:text-cyan-200/40 focus:border-cyan-400/50 focus:outline-none"
              placeholder="Fale com Jefrey, Sir... (Enter para enviar)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
              aria-label="mensagem"
              disabled={loading}
            />
            <Button onClick={send} disabled={loading || !input.trim()} className="bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_12px_rgba(6,182,212,0.4)] min-w-[88px]">
              {loading ? (polling ? "Aguardando..." : "Enviando...") : "Enviar"}
            </Button>
          </div>
          <ConnectionHub onResult={(r)=> setMsgs(m=>[...m, { role: "assistant", content: `[${r.kind}] ${r.text}` }])} />
          {!hasToken && (
            <p className="text-xs text-cyan-200/40 font-mono">
              Conectando automaticamente, Sir... Se falhar, <Link to="/settings" className="underline text-cyan-400">Settings Obter token dev</Link>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
