import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { apiFetch, getUserId } from "@/lib/api"
import { Brain, Search, Plus, Trash2, Tag } from "lucide-react"

type Memory = { id: string; content: string; score?: number; metadata?: Record<string, unknown>; type?: string; created_at?: string }

export default function MemoryStudio() {
  const [content, setContent] = useState("")
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [filteredMemories, setFilteredMemories] = useState<Memory[]>([])

  const handleAddMemory = async () => {
    const text = content.trim()
    if (!text || loading) return
    
    setLoading(true)
    try {
      const res = await apiFetch("/memory", {
        method: "POST",
        body: JSON.stringify({ content: text, user_id: getUserId() }),
      })
      
      if (!res.ok) throw new Error("Falha ao adicionar memória")
      
      const data: any = await res.json()
      setMemories((m) => [...m, data])
      setContent("")
    } catch (e) {
      console.error("Erro ao adicionar memória:", e)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setFilteredMemories(memories)
      return
    }
    
    setLoading(true)
    try {
      const res = await apiFetch(`/memory/search?query=${encodeURIComponent(searchQuery)}&user_id=${getUserId()}`)
      
      if (!res.ok) throw new Error("Falha ao buscar memórias")
      
      const data: any = await res.json()
      setFilteredMemories(data.results || [])
    } catch (e) {
      console.error("Erro ao buscar memórias:", e)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      const res = await apiFetch(`/memory/${id}`, {
        method: "DELETE",
        body: JSON.stringify({ user_id: getUserId() }),
      })
      
      if (!res.ok) throw new Error("Falha ao deletar memória")
      
      setMemories((m) => m.filter(mem => mem.id !== id))
      setFilteredMemories((m) => m.filter(mem => mem.id !== id))
    } catch (e) {
      console.error("Erro ao deletar memória:", e)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="glass border-cyan-500/20" glassStrong>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-cyan-100">
            <Brain className="w-5 h-5 text-cyan-400" />
            Memory Studio
            <Badge variant="glass" className="ml-2 font-mono text-[10px]">{memories.length} memórias</Badge>
          </CardTitle>
          <p className="text-xs text-cyan-200/50 font-mono">
            Sir, Memory Studio — memória semântica com busca e tags.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Add Memory */}
          <div className="space-y-2">
            <Textarea
              placeholder="Adicionar nova memória, Sir..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={3}
            />
            <div className="flex justify-end">
              <Button onClick={handleAddMemory} disabled={loading || !content.trim()} className="bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_12px_rgba(6,182,212,0.4)]">
                <Plus className="w-4 h-4 mr-2" />
                Adicionar Memória
              </Button>
            </div>
          </div>

          {/* Search */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyan-400/50" />
              <Input
                glass
                placeholder="Buscar memórias..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                onKeyDown={(e) => { if (e.key === "Enter") handleSearch() }}
              />
            </div>
            <Button variant="glass" onClick={handleSearch} disabled={loading}>
              Buscar
            </Button>
          </div>

          {/* Memories List */}
          <div className="h-[40vh] overflow-y-auto rounded-md border border-cyan-500/10 bg-black/30 p-3 space-y-3 backdrop-blur">
            {filteredMemories.length === 0 ? (
              <div className="text-center text-cyan-200/40 py-8">
                <Brain className="w-12 h-12 mx-auto mb-2 text-cyan-400/30" />
                <p className="text-sm">Nenhuma memória encontrada, Sir.</p>
              </div>
            ) : (
              filteredMemories.map((mem) => (
                <div key={mem.id} className="glass-subtle border border-cyan-500/15 rounded-lg p-3 backdrop-blur">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className="text-sm text-cyan-50 mb-2">{mem.content}</p>
                      <div className="flex items-center gap-2">
                        {mem.score && (
                          <Badge variant="glass" className="text-[10px]">
                            Score: {mem.score.toFixed(2)}
                          </Badge>
                        )}
                        {mem.type && (
                          <Badge variant="glass" className="text-[10px]">
                            <Tag className="w-3 h-3 mr-1" />
                            {mem.type}
                          </Badge>
                        )}
                        {mem.created_at && (
                          <span className="text-[10px] text-cyan-200/40">
                            {new Date(mem.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(mem.id)}
                      className="border-red-500/30 hover:bg-red-500/10 text-red-400"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="text-center text-cyan-300/80 font-mono">
                <span className="animate-pulse">Buscando memórias...</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
