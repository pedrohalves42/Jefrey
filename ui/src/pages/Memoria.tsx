import { useCallback, useEffect, useState } from "react"
import { authedFetch } from "@/lib/session"

type Hit = { id?: string; content: string; similarity?: number; metadata?: { title?: string; timestamp?: string } }

function when(ts?: string): string {
  if (!ts) return ""
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
}

export default function Memoria() {
  const [query, setQuery] = useState("")
  const [hits, setHits] = useState<Hit[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [note, setNote] = useState("")
  const [title, setTitle] = useState("")
  const [saving, setSaving] = useState(false)
  const [recent, setRecent] = useState<Hit[] | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const loadRecent = useCallback(async () => {
    try {
      const r = await authedFetch("/memory/recent?limit=50")
      if (!r.ok) throw new Error(String(r.status))
      const j = await r.json()
      setRecent(Array.isArray(j.memories) ? j.memories : [])
    } catch {
      setRecent(null)
      setMsg({ ok: false, text: "Não consegui carregar suas memórias. Verifique se o Jefrey está rodando." })
    }
  }, [])

  useEffect(() => {
    void loadRecent()
  }, [loadRecent])

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
      await loadRecent()
    } catch {
      setMsg({ ok: false, text: "Não consegui guardar. Tente de novo." })
    } finally {
      setSaving(false)
    }
  }

  async function forget(id: string) {
    setMsg(null)
    try {
      const r = await authedFetch(`/memory/${id}`, { method: "DELETE" })
      if (!r.ok && r.status !== 404) throw new Error(String(r.status))
      setConfirming(null)
      setRecent(prev => (prev ? prev.filter(m => m.id !== id) : prev))
      setHits(prev => (prev ? prev.filter(m => m.id !== id) : prev))
      setMsg({ ok: true, text: "Esquecido de vez." })
    } catch {
      setMsg({ ok: false, text: "Não consegui apagar. Tente de novo." })
    }
  }

  function Item({ m }: { m: Hit }) {
    return (
      <li className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
        {m.metadata?.title && <p className="font-medium text-white">{m.metadata.title}</p>}
        <p className="whitespace-pre-wrap break-words text-white/85">{m.content}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-white/40">
          {typeof m.similarity === "number" && <span>parecido com a sua busca: {Math.round(m.similarity * 100)}%</span>}
          {when(m.metadata?.timestamp) && <span>{when(m.metadata?.timestamp)}</span>}
          {m.id &&
            (confirming === m.id ? (
              <span className="flex items-center gap-2">
                <span className="text-amber-200">Apagar de vez?</span>
                <button type="button" onClick={() => void forget(m.id as string)} className="jf-focus rounded border border-red-400/40 px-2 py-0.5 text-red-200 hover:bg-red-400/10">
                  Sim, esquecer
                </button>
                <button type="button" onClick={() => setConfirming(null)} className="jf-focus rounded border border-white/15 px-2 py-0.5 hover:bg-white/5">
                  Cancelar
                </button>
              </span>
            ) : (
              <button type="button" onClick={() => setConfirming(m.id as string)} aria-label="Esquecer esta memória" className="jf-focus rounded px-1 hover:text-red-300">
                Esquecer
              </button>
            ))}
        </div>
      </li>
    )
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
        {hits && hits.length === 0 && <p className="mt-3 text-sm text-white/60">Nada parecido encontrado. A busca entende o sentido: tente descrever com outras palavras.</p>}
        {hits && hits.length > 0 && (
          <ul className="mt-3 space-y-2">
            {hits.map((h, i) => (
              <Item key={h.id ?? i} m={h} />
            ))}
          </ul>
        )}
      </section>

      <section className="jf-panel p-4" aria-labelledby="m-recent">
        <h2 id="m-recent" className="mb-2 font-medium text-white">
          Tudo que está guardado {recent ? <span className="text-sm font-normal text-white/40">({recent.length})</span> : null}
        </h2>
        {recent === null ? (
          <p className="text-sm text-white/50">Carregando…</p>
        ) : recent.length === 0 ? (
          <p className="text-sm text-white/60">Ainda não há nada guardado. Peça ao Jefrey no chat ("guarde uma nota…") ou use o campo acima.</p>
        ) : (
          <ul className="space-y-2">
            {recent.map(m => (
              <Item key={m.id} m={m} />
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
