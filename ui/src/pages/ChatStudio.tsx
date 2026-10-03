import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { apiFetch, getUserId, getThreadId, setThreadId } from "@/lib/api"
import { getUploadHistory, addUploadHistory, clearUploadHistory, type UploadHistoryItem } from "@/lib/history"
import { Send, History, Upload, Clock, Search, X } from "lucide-react"

type Msg = { role: "user" | "assistant"; content: string; timestamp: string }

export default function ChatStudio() {
  const [input, setInput] = useState("")
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "Sir, Chat Studio online. Conversa com histórico de uploads e busca integrada.", timestamp: new Date().toISOString() },
  ])
  const [loading, setLoading] = useState(false)
  const [threadId, setThreadIdState] = useState(getThreadId())
  const [searchQuery, setSearchQuery] = useState("")
  const [filteredMsgs, setFilteredMsgs] = useState<Msg[]>(msgs)
  const [uploadHistory, setUploadHistory] = useState<UploadHistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(false)

  // Carregar upload history ao montar
  useEffect(() => {
    setUploadHistory(getUploadHistory())
  }, [])

  const handleSearch = () => {
    if (!searchQuery.trim()) {
      setFilteredMsgs(msgs)
      return
    }
    const filtered = msgs.filter(m => 
      m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.role.toLowerCase().includes(searchQuery.toLowerCase())
    )
    setFilteredMsgs(filtered)
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    
    const userMsg: Msg = { role: "user", content: text, timestamp: new Date().toISOString() }
    setMsgs((m) => [...m, userMsg])
    setInput("")
    setLoading(true)

    try {
      const res = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, thread_id: threadId, user_id: getUserId() }),
      })
      
      if (!res.ok) throw new Error("Falha ao enviar mensagem")
      
      const data: any = await res.json()
      const reply = data.response || data.message || data.output || "(sem resposta)"
      
      const assistantMsg: Msg = { role: "assistant", content: reply, timestamp: new Date().toISOString() }
      setMsgs((m) => [...m, assistantMsg])
    } catch (e) {
      const errorMsg: Msg = { role: "assistant", content: `Erro: ${e instanceof Error ? e.message : String(e)}`, timestamp: new Date().toISOString() }
      setMsgs((m) => [...m, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const clearHistory = () => {
    setMsgs([{ role: "assistant", content: "Histórico limpo, Sir.", timestamp: new Date().toISOString() }])
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    Array.from(files).forEach(file => {
      addUploadHistory({
        name: file.name,
        size: file.size,
        type: file.type,
      })
    })

    setUploadHistory(getUploadHistory())
  }

  return (
    <div className="space-y-4">
      <Card className="glass border-cyan-500/20" glassStrong>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-cyan-100">
              <Clock className="w-5 h-5 text-cyan-400" />
              Chat Studio
              <Badge variant="glass" className="ml-2 font-mono text-[10px]">thread {threadId}</Badge>
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowHistory(!showHistory)} className="border-cyan-500/30 hover:bg-cyan-500/10">
                <History className="w-4 h-4 mr-1" />
                Uploads ({uploadHistory.length})
              </Button>
              <Button variant="outline" size="sm" onClick={clearHistory} className="border-cyan-500/30 hover:bg-cyan-500/10">
                Limpar Chat
              </Button>
            </div>
          </div>
          <p className="text-xs text-cyan-200/50 font-mono">
            Sir, Chat Studio — conversa com histórico integrado, busca e upload.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload History Panel */}
          {showHistory && (
            <div className="glass-subtle border border-cyan-500/15 rounded-lg p-4 mb-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-cyan-100">Upload History</h3>
                <Button variant="outline" size="sm" onClick={() => { clearUploadHistory(); setUploadHistory([]) }} className="border-red-500/30 hover:bg-red-500/10 text-red-400">
                  <X className="w-4 h-4" />
                </Button>
              </div>
              {uploadHistory.length === 0 ? (
                <p className="text-xs text-cyan-200/40">Nenhum upload ainda, Sir.</p>
              ) : (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {uploadHistory.map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-xs text-cyan-200/60">
                      <span>{item.name}</span>
                      <span className="text-cyan-200/40">{(item.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Search Bar */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyan-400/50" />
              <Input
                glass
                placeholder="Buscar no histórico..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  handleSearch()
                }}
                className="pl-10"
              />
            </div>
            <Button variant="glass" size="sm" onClick={handleSearch}>
              Buscar
            </Button>
          </div>

          {/* Upload Area */}
          <div className="border-2 border-dashed border-cyan-500/30 rounded-lg p-6 text-center hover:border-cyan-500/50 transition-colors cursor-pointer relative">
            <input
              type="file"
              multiple
              onChange={handleFileUpload}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
            <Upload className="w-8 h-8 mx-auto mb-2 text-cyan-400/60" />
            <p className="text-sm text-cyan-200/60">Arraste arquivos aqui ou clique para upload</p>
            <p className="text-xs text-cyan-200/40 mt-1">Upload History: {uploadHistory.length} arquivos</p>
          </div>

          {/* Chat Messages */}
          <div className="h-[40vh] overflow-y-auto rounded-md border border-cyan-500/10 bg-black/30 p-3 space-y-3 backdrop-blur">
            {filteredMsgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[82%] rounded-lg px-3 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "bg-cyan-600 text-white shadow-[0_0_12px_rgba(6,182,212,0.3)]" : "glass-subtle border border-cyan-500/15 text-cyan-50 backdrop-blur"}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`font-mono text-[10px] tracking-widest ${m.role === "user" ? "text-cyan-100" : "text-cyan-400"}`}>
                      {m.role === "user" ? "SIR:" : "JEFREY:"}
                    </span>
                    <span className="text-[10px] text-cyan-200/40">
                      {new Date(m.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <span>{m.content}</span>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-3 text-sm text-cyan-300/80 font-mono">
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="animate-pulse">Jefrey pensando...</span>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="flex gap-2 items-center">
            <Input
              glass
              placeholder="Digite sua mensagem, Sir... (Enter para enviar)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSend() }}
              disabled={loading}
            />
            <Button onClick={handleSend} disabled={loading || !input.trim()} className="bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_12px_rgba(6,182,212,0.4)]">
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
