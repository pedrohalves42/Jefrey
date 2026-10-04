import { useState } from "react"
import { authedFetch } from "@/lib/session"

type Hit = { id?: string; content: string; similarity?: number }

export default function Memoria() {
  const [query, setQuery] = useState("")
  const [hits, setHits] = useState<Hit[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [note, setNote] = useState("")
  const [title, setTitle] = useState("")
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function search(e?: React.FormEvent) {
    e?.preventDefault()
    const q = query.trim()
    if (!q || searching) return
    setSearching(true)
    setMsg(null)
    try {
      const r = await authedFetch(`/memory/search?${new URLSearchParams({ q, limit: "8" })}`)
      if (!r.ok) throw new Error(String(r.status))
      const j = await r.json()
      setHits(Array.isArray(j.memories) ? j.memories : [])
    } catch {
      setHits(null)
      setMsg({ ok: false, text: "Não consegui buscar agora. Verifique se o Jefrey está rodando." })
    } finally {
      setSearching(false)
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    const content = note.trim()
    if (!content || saving) return
    setSaving(true)
    setMsg(null)
    try {
      const r = await authedFetch("/memory/add", {
        method: "POST",
        body: JSON.stringify({ content, title: title.trim() || undefined }),
      })
      if (!r.ok) throw new Error(String(r.status))
      setNote("")
      setTitle("")
      setMsg({ ok: true, text: "Guardado. O Jefrey vai lembrar disso." })
    } catch {
      setMsg({ ok: false, text: "Não consegui guardar. Tente de novo." })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto h-full max-w-3xl space-y-4 overflow-y-auto pb-4">
      <header>
        <h1 className="text-2xl font-semibold text-white">Memória</h1>
        <p className="text-sm text-white/55">O que o Jefrey guarda sobre você. Fica só no seu computador e é separado por usuário.</p>
      </header>

      <section className="jf-panel p-4" aria-labelledby="m-add">
        <h2 id="m-add" className="mb-2 font-medium text-white">
          Guardar algo
        </h2>
        <form onSubmit={save} className="space-y-2">
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Título (opcional)"
            aria-label="Título"
            maxLength={120}
            className="jf-focus w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            rows={3}
            placeholder="Ex.: Meu café favorito é sem açúcar."
            aria-label="O que guardar"
            className="jf-focus w-full resize-y rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
          <button type="submit" disabled={!note.trim() || saving} className="jf-btn jf-focus px-4 py-1.5 text-sm">
            {saving ? "Guardando…" : "Guardar"}
          </button>
        </form>
      </section>

      <section className="jf-panel p-4" aria-labelledby="m-find">
        <h2 id="m-find" className="mb-2 font-medium text-white">
          Buscar na memória
        </h2>
        <form onSubmit={search} className="flex gap-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Pergunte como numa conversa: qual é o meu café favorito?"
            aria-label="Buscar na memória"
            className="jf-focus min-w-0 flex-1 rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
          <button type="submit" disabled={!query.trim() || searching} className="jf-btn jf-focus px-4 py-1.5 text-sm">
            {searching ? "Buscando…" : "Buscar"}
          </button>
        </form>

        {hits && hits.length === 0 && (
          <p className="mt-3 text-sm text-white/60">
            Nada parecido encontrado. A busca entende o sentido, então prefira frases completas a palavras soltas.
          </p>
        )}
        {hits && hits.length > 0 && (
          <ul className="mt-3 space-y-2">
            {hits.map((h, i) => (
              <li key={h.id ?? i} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <p className="whitespace-pre-wrap break-words text-white/90">{h.content}</p>
                {typeof h.similarity === "number" && (
                  <p className="mt-1 text-xs text-white/40">parecido com a sua busca: {Math.round(h.similarity * 100)}%</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {msg && (
        <p role="status" className={`text-sm ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>
          {msg.text}
        </p>
      )}
    </div>
  )
}
