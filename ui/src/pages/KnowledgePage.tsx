import { useState, useEffect, ChangeEvent, FormEvent } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiFetch, getUserId, mapHttpError } from "@/lib/api"
import { Loader2, Search, Plus, Edit2, Trash2, Tag, FileText, X } from "lucide-react"
import { cn } from "@/lib/utils"

type Note = {
  id: string
  content: string
  metadata?: Record<string, unknown>
  score?: number
  created_at?: string
}

type NoteForm = {
  title: string
  content: string
  tags: string
  source: "user" | "web" | "conversation" | "email" | "document"
  related_people: string
  related_projects: string
}

function NoteCard({ note, onEdit, onDelete }: { note: Note; onEdit: (n: Note) => void; onDelete: (id: string) => void }) {
  const meta = note.metadata || {}
  const title = String(meta.title || "Sem título")
  const tags = Array.isArray(meta.tags) ? meta.tags : []
  return (
    <div className={cn("rounded-md border p-3 bg-card hover:border-cyan-500/20 transition-colors")}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium truncate">{title}</span>
            {typeof note.score === "number" && <Badge variant="secondary">score {note.score.toFixed(3)}</Badge>}
            {note.created_at && <span className="text-xs text-muted-foreground">{note.created_at.slice(0, 19)}</span>}
          </div>
          <div className="whitespace-pre-wrap break-words text-sm line-clamp-3">{note.content.slice(0, 400)}</div>
          {tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {tags.slice(0, 5).map((t) => (
                <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={() => onEdit(note)} title="Editar" aria-label="Editar nota">
            <Edit2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => { if (window.confirm(`Excluir "${title}"?`)) onDelete(note.id) }} title="Excluir" aria-label="Excluir nota">
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<"search" | "recent" | "create">("search")
  const [query, setQuery] = useState("")
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editingNote, setEditingNote] = useState<Note | null>(null)
  const [form, setForm] = useState<NoteForm>({
    title: "",
    content: "",
    tags: "",
    source: "user",
    related_people: "",
    related_projects: "",
  })

  async function callMcpTool(toolName: string, payload: Record<string, unknown>) {
    const res = await apiFetch(`/mcp/tools/${toolName}`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const body = await res.text().catch(() => "")
      throw new Error(mapHttpError(res.status) + (body ? " - " + body.slice(0, 400) : ""))
    }
    return res.json()
  }

  function normalizeResults(results: unknown[]): Note[] {
    return results.map((r: unknown) => {
      if (typeof r === "string") return { id: crypto.randomUUID(), content: r }
      const o = r as Record<string, unknown>
      return {
        id: String(o.id || o.memory_id || crypto.randomUUID()),
        content: String(o.content || o.text || o.memory || JSON.stringify(o).slice(0, 500)),
        score: typeof o.score === "number" ? o.score : undefined,
        metadata: (o.metadata as Record<string, unknown>) || undefined,
        created_at: String(o.created_at || o.createdAt || ""),
      }
    })
  }

  async function searchNotes() {
    const q = query.trim()
    if (!q || loading) return
    setError(null)
    setLoading(true)
    try {
      const data = await callMcpTool("search_notes", { query: q, top_k: 10 })
      const results: unknown[] = data.results || data.hits || data.memories || data.items || []
      const norm = normalizeResults(results)
      setNotes(norm)
      if (norm.length === 0) setError("Nenhum resultado — tente outro termo.")
    } catch (e) {
      setNotes([])
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function listNotes() {
    setError(null)
    setLoading(true)
    try {
      const data = await callMcpTool("list_notes", { limit: 20 })
      const results: unknown[] = data.results || data.hits || data.memories || data.items || []
      const norm = normalizeResults(results)
      setNotes(norm)
    } catch (e) {
      setNotes([])
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function createNote() {
    if (!form.title.trim() || !form.content.trim() || loading) return
    setError(null)
    setLoading(true)
    try {
      const tagsArray = form.tags.split(",").map(s => s.trim()).filter(Boolean)
      await callMcpTool("save_note", {
        title: form.title,
        content: form.content,
        tags: tagsArray,
        source: form.source,
        related_people: form.related_people.split(",").map(s => s.trim()).filter(Boolean),
        related_projects: form.related_projects.split(",").map(s => s.trim()).filter(Boolean),
      })
      setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" })
      await searchNotes()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function updateNote() {
    if (!editingNote || !form.title.trim() || !form.content.trim() || loading) return
    setError(null)
    setLoading(true)
    try {
      const tagsArray = form.tags.split(",").map(s => s.trim()).filter(Boolean)
      await callMcpTool("update_note", {
        note_id: editingNote.id,
        title: form.title,
        content: form.content,
        tags: tagsArray,
      })
      setEditingNote(null)
      setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" })
      await searchNotes()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function deleteNote(id: string) {
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      await callMcpTool("delete_note", { note_id: id })
      await searchNotes()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleEdit(note: Note) {
    const meta = note.metadata || {}
    setForm({
      title: String(meta.title || ""),
      content: note.content,
      tags: Array.isArray(meta.tags) ? meta.tags.join(", ") : "",
      source: (meta.source as NoteForm["source"]) || "user",
      related_people: Array.isArray(meta.related_people) ? meta.related_people.join(", ") : "",
      related_projects: Array.isArray(meta.related_projects) ? meta.related_projects.join(", ") : "",
    })
    setEditingNote(note)
    setActiveTab("create")
  }

  function resetForm() {
    setEditingNote(null)
    setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" })
  }

  return (
    <div className="space-y-4">
      <Card className="glass-strong border-cyan-500/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 flex-wrap">
            <FileText className="h-5 w-5 text-cyan-400" />
            Conhecimento Pessoal
            <Badge variant="secondary">Jefrey Notes</Badge>
            <Badge variant="outline">Axiom #2 isolado</Badge>
            <span className="ml-auto text-xs text-muted-foreground font-mono">user: {getUserId()}</span>
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            CRUD completo de notas com busca semântica (pgvector HNSW m16 ef64) — isolamento multi-tenant por user_id.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Tabs value={activeTab} onValueChange={(v: string) => setActiveTab(v as "search" | "recent" | "create")} className="w-full">
            <TabsList className="grid w-full grid-cols-3 bg-muted">
              <TabsTrigger value="search"><Search className="mr-2 h-4 w-4" /> Buscar</TabsTrigger>
              <TabsTrigger value="recent"><FileText className="mr-2 h-4 w-4" /> Recentes</TabsTrigger>
              <TabsTrigger value="create"><Plus className="mr-2 h-4 w-4" /> Criar</TabsTrigger>
            </TabsList>

            {/* TAB BUSCAR */}
            <TabsContent value="search" className="space-y-3">
              <div className="flex gap-2 flex-wrap">
                <Input
                  placeholder="Busca semântica… ex: 'reunião projeto alfa'"
                  value={query}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") searchNotes(); }}
                  aria-label="query busca notas"
                  className="flex-1 min-w-[220px]"
                />
                <Button onClick={searchNotes} disabled={loading || !query.trim()}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Buscar"}
                </Button>
              </div>
              {error && <div className="text-sm text-destructive bg-destructive/10 p-2 rounded">{error}</div>}
              <div className="space-y-2">
                {notes.map((n, i) => (
                  <NoteCard key={i} note={n} onEdit={handleEdit} onDelete={deleteNote} />
                ))}
                {!loading && notes.length === 0 && !error && (
                  <p className="text-sm text-muted-foreground">Digite um termo e clique Buscar.</p>
                )}
              </div>
            </TabsContent>

            {/* TAB RECENTES */}
            <TabsContent value="recent" className="space-y-3">
              <Button variant="outline" onClick={listNotes} disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : "Carregar recentes"}
              </Button>
              <div className="space-y-2">
                {notes.map((n, i) => (
                  <NoteCard key={i} note={n} onEdit={handleEdit} onDelete={deleteNote} />
                ))}
                {!loading && notes.length === 0 && !error && (
                  <p className="text-sm text-muted-foreground">Clique em Carregar recentes para ver suas notas.</p>
                )}
              </div>
            </TabsContent>

            {/* TAB CRIAR / EDITAR */}
            <TabsContent value="create" className="space-y-3">
              <form onSubmit={(e: FormEvent) => { e.preventDefault(); editingNote ? updateNote() : createNote(); }} className="space-y-3 max-w-2xl">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{editingNote ? "Editar nota" : "Nova nota"}</CardTitle>
                  {editingNote && (
                    <Button type="button" variant="ghost" size="icon" onClick={resetForm} aria-label="Cancelar edição">
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="title">Título</Label>
                    <Input
                      id="title"
                      value={form.title}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, title: e.target.value })}
                      placeholder="Título da nota"
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="source">Origem</Label>
                    <Select value={form.source} onValueChange={(v: string) => setForm({ ...form, source: v as NoteForm["source"] })}>
                      <SelectTrigger id="source"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">Pessoal</SelectItem>
                        <SelectItem value="web">Web</SelectItem>
                        <SelectItem value="conversation">Conversa</SelectItem>
                        <SelectItem value="email">Email</SelectItem>
                        <SelectItem value="document">Documento</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="tags">Tags (separadas por vírgula)</Label>
                  <Input
                    id="tags"
                    value={form.tags}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, tags: e.target.value })}
                    placeholder="ex: projeto, reuniao, importante"
                  />
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="related_people">Pessoas relacionadas</Label>
                    <Input
                      id="related_people"
                      value={form.related_people}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, related_people: e.target.value })}
                      placeholder="João, Maria"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="related_projects">Projetos relacionados</Label>
                    <Input
                      id="related_projects"
                      value={form.related_projects}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, related_projects: e.target.value })}
                      placeholder="Projeto Alfa, Beta"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="content">Conteúdo</Label>
                  <Textarea
                    id="content"
                    value={form.content}
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setForm({ ...form, content: e.target.value })}
                    rows={8}
                    placeholder="Escreva sua nota aqui…"
                    required
                  />
                </div>
                <Button type="submit" disabled={loading || !form.title.trim() || !form.content.trim()}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : ""}
                  {editingNote ? "Atualizar" : "Salvar nota"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}