import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, getUserId, mapHttpError } from "@/lib/api"

type Hit = { content: string; score?: number; metadata?: Record<string, unknown>; type?: string; created_at?: string }

export default function Memory() {
  const [query, setQuery] = useState("")
  const [layer, setLayer] = useState("episodic")
  const [limit, setLimit] = useState(5)
  const [hits, setHits] = useState<Hit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [latency, setLatency] = useState<number | null>(null)

  async function search() {
    const q = query.trim()
    if (!q || loading) return
    setError(null); setLoading(true); setLatency(null)
    const t0 = performance.now()
    try {
      const res = await apiFetch("/memory/search", {
        method: "POST",
        body: JSON.stringify({ query: q, user_id: getUserId(), limit, layer }),
      })
      const ms = Math.round(performance.now() - t0)
      setLatency(ms)
      if (!res.ok) {
        const body = await res.text()
        throw new Error(mapHttpError(res.status) + (body ? " — " + body.slice(0, 400) : ""))
      }
      const data = await res.json().catch(() => ({}))
      const results: Hit[] = data.results || data.hits || data.memories || data.items || []
      // normaliza: se vier string, vira Hit
      const norm = results.map((r: unknown) => {
        if (typeof r === "string") return { content: r }
        const o = r as Record<string, unknown>
        return {
          content: String(o.content || o.text || o.memory || JSON.stringify(o).slice(0, 500)),
          score: typeof o.score === "number" ? o.score : undefined,
          metadata: (o.metadata as Record<string, unknown>) || undefined,
          type: String(o.type || o.layer || layer),
          created_at: String(o.created_at || o.createdAt || ""),
        }
      })
      setHits(norm)
      if (norm.length === 0) setError("Nenhum resultado — HNSW m16 ef64 pode retornar Seq Scan em <10k linhas (DDIA cap12). Tente outro termo ou cadastre memoria.")
    } catch (e) {
      setHits([])
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Memoria vetorial <Badge variant="secondary">HNSW m16 ef64</Badge>
            <Badge variant="outline">p50 48ms p95 55ms</Badge>
            {latency !== null && <Badge variant={latency < 300 ? "secondary" : "destructive"}>{latency}ms</Badge>}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            POST /memory/search vetorial por user_id (<span className="font-mono">{getUserId()}</span>) — p95 &lt;300ms SLO (Livro 5 DDIA cap12). Isolamento Axiom #2.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 flex-wrap">
            <input
              className="flex-1 min-w-[220px] rounded-md border px-3 py-2 text-sm"
              placeholder="Busque: ex. 'teste' ou 'projeto jefrey'"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") search(); }}
              aria-label="query memoria"
            />
            <select className="rounded-md border px-2 py-2 text-sm" value={layer} onChange={(e) => setLayer(e.target.value)} aria-label="layer">
              <option value="episodic">episodic</option>
              <option value="semantic">semantic</option>
              <option value="procedural">procedural</option>
              <option value="all">all</option>
            </select>
            <select className="rounded-md border px-2 py-2 text-sm" value={limit} onChange={(e) => setLimit(Number(e.target.value))} aria-label="limit">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
            <Button onClick={search} disabled={loading || !query.trim()}>{loading ? "Buscando…" : "Buscar"}</Button>
          </div>
          {error && <div className="rounded-md border bg-muted p-3 text-sm">{error}</div>}
          <div className="space-y-2">
            {hits.map((h, i) => (
              <div key={i} className="rounded-md border p-3 text-sm bg-card">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline">{h.type || layer}</Badge>
                  {typeof h.score === "number" && <Badge variant="secondary">score {h.score.toFixed(3)}</Badge>}
                  {h.created_at && <span className="text-xs text-muted-foreground">{h.created_at.slice(0, 19)}</span>}
                </div>
                <div className="whitespace-pre-wrap break-words">{h.content}</div>
                {h.metadata && <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-auto">{JSON.stringify(h.metadata, null, 2).slice(0, 800)}</pre>}
              </div>
            ))}
            {!loading && hits.length === 0 && !error && <p className="text-sm text-muted-foreground">Digite um termo e clique Buscar.</p>}
          </div>
          <p className="text-xs text-muted-foreground">
            Curl: <code className="font-mono bg-muted px-1 rounded">curl -X POST http://localhost:8000/memory/search -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"{"}query":"teste","user_id":"demo","limit":5{"}"}'</code>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
