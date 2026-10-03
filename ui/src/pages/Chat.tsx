import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, getUserId, getThreadId, setThreadId, getToken, ensureDevToken } from "@/lib/api"

type Msg = { role: "user" | "assistant"; content: string }

export default function Chat() {
  const [input, setInput] = useState("")
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Olá! Sou o Jefrey. Como posso ajudar?" },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [threadId, setThreadIdState] = useState(getThreadId())
  const [hasToken, setHasToken] = useState<boolean>(() => !!getToken())

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    
    const userMsg: Msg = { role: "user", content: text }
    setMsgs((m) => [...m, userMsg])
    setInput("")
    setLoading(true)
    setError(null)

    try {
      const res = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, thread_id: threadId, user_id: getUserId() }),
      })
      
      if (!res.ok) {
        const body = await res.text()
        throw new Error(`Erro ${res.status}: ${body}`)
      }
      
      const data: any = await res.json()
      
      // Se retornou "running", fazer polling do status
      if (data.status === "running") {
        await pollForResponse(threadId)
      } else {
        const reply = data.response || data.message || data.output || "Sem resposta"
        const assistantMsg: Msg = { role: "assistant", content: reply }
        setMsgs((m) => [...m, assistantMsg])
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      const errorMsg: Msg = { role: "assistant", content: `Erro: ${msg}` }
      setMsgs((m) => [...m, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const pollForResponse = async (tid: string) => {
    const maxAttempts = 30 // 30 segundos max
    const interval = 1000 // 1 segundo
    
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(resolve => setTimeout(resolve, interval))
      
      try {
        const res = await apiFetch(`/chat/status/${tid}`)
        if (!res.ok) continue
        
        const data: any = await res.json()
        
        if (data.status === "complete" && data.response) {
          const assistantMsg: Msg = { role: "assistant", content: data.response }
          setMsgs((m) => [...m, assistantMsg])
          return
        }
        
        if (data.status === "error") {
          const errorMsg: Msg = { role: "assistant", content: `Erro: ${data.error || "Erro desconhecido"}` }
          setMsgs((m) => [...m, errorMsg])
          return
        }
      } catch (e) {
        console.error("Polling error:", e)
      }
    }
    
    // Timeout
    const timeoutMsg: Msg = { role: "assistant", content: "A resposta demorou muito. Tente novamente." }
    setMsgs((m) => [...m, timeoutMsg])
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleGetToken = async () => {
    const tok = await ensureDevToken()
    if (tok) {
      setHasToken(true)
      setError(null)
    } else {
      setError("Falha ao obter token")
    }
  }

  return (
    <div className="space-y-4 p-4">
      <Card className="border border-cyan-500/20 bg-white">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-cyan-900">
            Jefrey - Chat
            <Badge variant="outline" className="ml-2">{threadId}</Badge>
            {hasToken ? <Badge className="bg-green-500 text-white">Online</Badge> : <Badge className="bg-yellow-500 text-white">Conectando...</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="h-[50vh] overflow-y-auto rounded-md border border-gray-300 p-3 space-y-3 bg-gray-50">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${m.role === "user" ? "bg-cyan-600 text-white" : "bg-gray-200 text-gray-900"}`}>
                  <span className="font-bold text-xs mr-2">{m.role === "user" ? "Você:" : "Jefrey:"}</span>
                  <span>{m.content}</span>
                </div>
              </div>
            ))}
            {loading && <div className="text-gray-500">Jefrey pensando...</div>}
          </div>
          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              <span>{error}</span>
              <Button size="sm" className="ml-2 bg-cyan-600 text-white" onClick={handleGetToken}>Obter Token</Button>
            </div>
          )}
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="Digite sua mensagem..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={loading}
            />
            <Button onClick={handleSend} disabled={loading || !input.trim()} className="bg-cyan-600 text-white">
              {loading ? "Enviando..." : "Enviar"}
            </Button>
          </div>
          {!hasToken && (
            <p className="text-xs text-gray-500">
              Conectando automaticamente... <button onClick={handleGetToken} className="underline text-cyan-600">Obter token</button>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
