import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiFetch, getUserId, mapHttpError } from "@/lib/api";
import { Loader2, Search, Plus, Edit2, Trash2, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";
function NoteCard({ note, onEdit, onDelete }) {
    const meta = note.metadata || {};
    const title = String(meta.title || "Sem título");
    const tags = Array.isArray(meta.tags) ? meta.tags : [];
    return (_jsx("div", { className: cn("rounded-md border p-3 bg-card hover:border-cyan-500/20 transition-colors"), children: _jsxs("div", { className: "flex items-start justify-between gap-2", children: [_jsxs("div", { className: "flex-1 min-w-0", children: [_jsxs("div", { className: "flex items-center gap-2 mb-1 flex-wrap", children: [_jsx("span", { className: "font-medium truncate", children: title }), typeof note.score === "number" && _jsxs(Badge, { variant: "secondary", children: ["score ", note.score.toFixed(3)] }), note.created_at && _jsx("span", { className: "text-xs text-muted-foreground", children: note.created_at.slice(0, 19) })] }), _jsx("div", { className: "whitespace-pre-wrap break-words text-sm line-clamp-3", children: note.content.slice(0, 400) }), tags.length > 0 && (_jsx("div", { className: "mt-2 flex flex-wrap gap-1", children: tags.slice(0, 5).map((t) => (_jsx(Badge, { variant: "outline", className: "text-xs", children: t }, t))) }))] }), _jsxs("div", { className: "flex gap-1", children: [_jsx(Button, { variant: "ghost", size: "icon", onClick: () => onEdit(note), title: "Editar", "aria-label": "Editar nota", children: _jsx(Edit2, { className: "h-4 w-4" }) }), _jsx(Button, { variant: "ghost", size: "icon", onClick: () => { if (window.confirm(`Excluir "${title}"?`))
                                onDelete(note.id); }, title: "Excluir", "aria-label": "Excluir nota", children: _jsx(Trash2, { className: "h-4 w-4 text-destructive" }) })] })] }) }));
}
export default function KnowledgePage() {
    const [activeTab, setActiveTab] = useState("search");
    const [query, setQuery] = useState("");
    const [notes, setNotes] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [editingNote, setEditingNote] = useState(null);
    const [form, setForm] = useState({
        title: "",
        content: "",
        tags: "",
        source: "user",
        related_people: "",
        related_projects: "",
    });
    async function callMcpTool(toolName, payload) {
        const res = await apiFetch(`/mcp/tools/${toolName}`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const body = await res.text().catch(() => "");
            throw new Error(mapHttpError(res.status) + (body ? " - " + body.slice(0, 400) : ""));
        }
        return res.json();
    }
    function normalizeResults(results) {
        return results.map((r) => {
            if (typeof r === "string")
                return { id: crypto.randomUUID(), content: r };
            const o = r;
            return {
                id: String(o.id || o.memory_id || crypto.randomUUID()),
                content: String(o.content || o.text || o.memory || JSON.stringify(o).slice(0, 500)),
                score: typeof o.score === "number" ? o.score : undefined,
                metadata: o.metadata || undefined,
                created_at: String(o.created_at || o.createdAt || ""),
            };
        });
    }
    async function searchNotes() {
        const q = query.trim();
        if (!q || loading)
            return;
        setError(null);
        setLoading(true);
        try {
            const data = await callMcpTool("search_notes", { query: q, top_k: 10 });
            const results = data.results || data.hits || data.memories || data.items || [];
            const norm = normalizeResults(results);
            setNotes(norm);
            if (norm.length === 0)
                setError("Nenhum resultado — tente outro termo.");
        }
        catch (e) {
            setNotes([]);
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    async function listNotes() {
        setError(null);
        setLoading(true);
        try {
            const data = await callMcpTool("list_notes", { limit: 20 });
            const results = data.results || data.hits || data.memories || data.items || [];
            const norm = normalizeResults(results);
            setNotes(norm);
        }
        catch (e) {
            setNotes([]);
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    async function createNote() {
        if (!form.title.trim() || !form.content.trim() || loading)
            return;
        setError(null);
        setLoading(true);
        try {
            const tagsArray = form.tags.split(",").map(s => s.trim()).filter(Boolean);
            await callMcpTool("save_note", {
                title: form.title,
                content: form.content,
                tags: tagsArray,
                source: form.source,
                related_people: form.related_people.split(",").map(s => s.trim()).filter(Boolean),
                related_projects: form.related_projects.split(",").map(s => s.trim()).filter(Boolean),
            });
            setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" });
            await searchNotes();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    async function updateNote() {
        if (!editingNote || !form.title.trim() || !form.content.trim() || loading)
            return;
        setError(null);
        setLoading(true);
        try {
            const tagsArray = form.tags.split(",").map(s => s.trim()).filter(Boolean);
            await callMcpTool("update_note", {
                note_id: editingNote.id,
                title: form.title,
                content: form.content,
                tags: tagsArray,
            });
            setEditingNote(null);
            setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" });
            await searchNotes();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    async function deleteNote(id) {
        if (loading)
            return;
        setError(null);
        setLoading(true);
        try {
            await callMcpTool("delete_note", { note_id: id });
            await searchNotes();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    function handleEdit(note) {
        const meta = note.metadata || {};
        setForm({
            title: String(meta.title || ""),
            content: note.content,
            tags: Array.isArray(meta.tags) ? meta.tags.join(", ") : "",
            source: meta.source || "user",
            related_people: Array.isArray(meta.related_people) ? meta.related_people.join(", ") : "",
            related_projects: Array.isArray(meta.related_projects) ? meta.related_projects.join(", ") : "",
        });
        setEditingNote(note);
        setActiveTab("create");
    }
    function resetForm() {
        setEditingNote(null);
        setForm({ title: "", content: "", tags: "", source: "user", related_people: "", related_projects: "" });
    }
    return (_jsx("div", { className: "space-y-4", children: _jsxs(Card, { className: "glass-strong border-cyan-500/10", children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2 flex-wrap", children: [_jsx(FileText, { className: "h-5 w-5 text-cyan-400" }), "Conhecimento Pessoal", _jsx(Badge, { variant: "secondary", children: "Jefrey Notes" }), _jsx(Badge, { variant: "outline", children: "Axiom #2 isolado" }), _jsxs("span", { className: "ml-auto text-xs text-muted-foreground font-mono", children: ["user: ", getUserId()] })] }), _jsx("p", { className: "text-sm text-muted-foreground", children: "CRUD completo de notas com busca sem\u00E2ntica (pgvector HNSW m16 ef64) \u2014 isolamento multi-tenant por user_id." })] }), _jsx(CardContent, { className: "space-y-3", children: _jsxs(Tabs, { value: activeTab, onValueChange: (v) => setActiveTab(v), className: "w-full", children: [_jsxs(TabsList, { className: "grid w-full grid-cols-3 bg-muted", children: [_jsxs(TabsTrigger, { value: "search", children: [_jsx(Search, { className: "mr-2 h-4 w-4" }), " Buscar"] }), _jsxs(TabsTrigger, { value: "recent", children: [_jsx(FileText, { className: "mr-2 h-4 w-4" }), " Recentes"] }), _jsxs(TabsTrigger, { value: "create", children: [_jsx(Plus, { className: "mr-2 h-4 w-4" }), " Criar"] })] }), _jsxs(TabsContent, { value: "search", className: "space-y-3", children: [_jsxs("div", { className: "flex gap-2 flex-wrap", children: [_jsx(Input, { placeholder: "Busca sem\u00E2ntica\u2026 ex: 'reuni\u00E3o projeto alfa'", value: query, onChange: (e) => setQuery(e.target.value), onKeyDown: (e) => { if (e.key === "Enter")
                                                    searchNotes(); }, "aria-label": "query busca notas", className: "flex-1 min-w-[220px]" }), _jsx(Button, { onClick: searchNotes, disabled: loading || !query.trim(), children: loading ? _jsx(Loader2, { className: "h-4 w-4 animate-spin" }) : "Buscar" })] }), error && _jsx("div", { className: "text-sm text-destructive bg-destructive/10 p-2 rounded", children: error }), _jsxs("div", { className: "space-y-2", children: [notes.map((n, i) => (_jsx(NoteCard, { note: n, onEdit: handleEdit, onDelete: deleteNote }, i))), !loading && notes.length === 0 && !error && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Digite um termo e clique Buscar." }))] })] }), _jsxs(TabsContent, { value: "recent", className: "space-y-3", children: [_jsx(Button, { variant: "outline", onClick: listNotes, disabled: loading, children: loading ? _jsx(Loader2, { className: "h-4 w-4 animate-spin mr-2" }) : "Carregar recentes" }), _jsxs("div", { className: "space-y-2", children: [notes.map((n, i) => (_jsx(NoteCard, { note: n, onEdit: handleEdit, onDelete: deleteNote }, i))), !loading && notes.length === 0 && !error && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Clique em Carregar recentes para ver suas notas." }))] })] }), _jsx(TabsContent, { value: "create", className: "space-y-3", children: _jsxs("form", { onSubmit: (e) => { e.preventDefault(); editingNote ? updateNote() : createNote(); }, className: "space-y-3 max-w-2xl", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx(CardTitle, { className: "text-lg", children: editingNote ? "Editar nota" : "Nova nota" }), editingNote && (_jsx(Button, { type: "button", variant: "ghost", size: "icon", onClick: resetForm, "aria-label": "Cancelar edi\u00E7\u00E3o", children: _jsx(X, { className: "h-4 w-4" }) }))] }), _jsxs("div", { className: "grid gap-2 sm:grid-cols-2", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "title", children: "T\u00EDtulo" }), _jsx(Input, { id: "title", value: form.title, onChange: (e) => setForm({ ...form, title: e.target.value }), placeholder: "T\u00EDtulo da nota", required: true })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "source", children: "Origem" }), _jsxs(Select, { value: form.source, onValueChange: (v) => setForm({ ...form, source: v }), children: [_jsx(SelectTrigger, { id: "source", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "user", children: "Pessoal" }), _jsx(SelectItem, { value: "web", children: "Web" }), _jsx(SelectItem, { value: "conversation", children: "Conversa" }), _jsx(SelectItem, { value: "email", children: "Email" }), _jsx(SelectItem, { value: "document", children: "Documento" })] })] })] })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "tags", children: "Tags (separadas por v\u00EDrgula)" }), _jsx(Input, { id: "tags", value: form.tags, onChange: (e) => setForm({ ...form, tags: e.target.value }), placeholder: "ex: projeto, reuniao, importante" })] }), _jsxs("div", { className: "grid gap-2 sm:grid-cols-2", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "related_people", children: "Pessoas relacionadas" }), _jsx(Input, { id: "related_people", value: form.related_people, onChange: (e) => setForm({ ...form, related_people: e.target.value }), placeholder: "Jo\u00E3o, Maria" })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "related_projects", children: "Projetos relacionados" }), _jsx(Input, { id: "related_projects", value: form.related_projects, onChange: (e) => setForm({ ...form, related_projects: e.target.value }), placeholder: "Projeto Alfa, Beta" })] })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { htmlFor: "content", children: "Conte\u00FAdo" }), _jsx(Textarea, { id: "content", value: form.content, onChange: (e) => setForm({ ...form, content: e.target.value }), rows: 8, placeholder: "Escreva sua nota aqui\u2026", required: true })] }), _jsxs(Button, { type: "submit", disabled: loading || !form.title.trim() || !form.content.trim(), children: [loading ? _jsx(Loader2, { className: "h-4 w-4 animate-spin mr-2" }) : "", editingNote ? "Atualizar" : "Salvar nota"] })] }) })] }) })] }) }));
}
