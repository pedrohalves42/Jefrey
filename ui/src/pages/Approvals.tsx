import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, mapHttpError, getToken } from "@/lib/api"

type Approval = { id: string; tool?: string; status?: string; risk?: string; user_id?: string; created_at?: string; reason?: string; [k: string]: unknown }

function riskVariant(r?: string) {
  const v = (r || "").toLowerCase()
  if (v === "low") return "secondary" as const
  if (v === "medium") return "outline" as const
  if (v === "high" || v === "critical") return "destructive" as const
  return "secondary" as const
}

export default function Approvals() {
  const [items, setItems] = useState<Approval[]>([])
  const [filter, setFilter] = useState("pending")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [acting, setActing] = useState<string | null>(null)

  async function load() {
    if (!getToken()) { setItems([]); setError("Sem token — cole seu Bearer em Settings para ver Approvals (Axiom #1 fail-closed, CIPHER-031). Nenhum request enviado."); setLoading(false); return; }
    setLoading(true); setError(null)
    try {
      const res = await apiFetch(`/approvals?status=${filter}`)
      if (!res.ok) throw new Error(mapHttpError(res.status) + " â€” " + (await res.text()).slice(0, 400))
      const data = await res.json().catch(() => ({}))
      const arr: Approval[] = data.items || data.approvals || data.results || (Array.isArray(data) ? data : [])
      setItems(arr)
      if (arr.length === 0) setError("Nenhum approval com status " + filter + " (CIPHER-032 HITL).")
    } catch (e) {
      setItems([])
      setError(e instanceof Error ? e.message : String(e))
    } finally { setLoading(false) }
  }

  async function decide(id: string, decision: "approved" | "rejected") {
    if (!getToken()) { setError("Sem token — defina Bearer em Settings antes de decidir."); return; }
    setActing(id + decision); setError(null)
    try {
      const res = await apiFetch(`/approvals/${id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      })
      if (!res.ok) throw new Error(mapHttpError(res.status) + " â€” " + (await res.text()).slice(0, 400))
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setActing(null) }
  }

  useEffect(() => { if (getToken()) load(); else { setItems([]); setError("Sem token — cole seu Bearer em Settings para ver Approvals (Axiom #1 fail-closed). Nenhum request enviado."); } }, [filter])
  useEffect(() => {
    if (!getToken()) return;
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [filter])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Approvals HITL <Badge variant="secondary">CIPHER-032</Badge>
            <Badge variant="outline">{filter}</Badge>
          </CardTitle>
          <p className="text-sm text-muted-foreground">GET /approvals + POST /approvals/:id/decision â€” so admin aprova (RBAC 403 se guest). Polling 15s.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <select className="rounded-md border px-2 py-2 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="pending">pending</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="all">all</option>
            </select>
            <Button variant="outline" onClick={load} disabled={loading}>{loading ? "Carregandoâ€¦" : "Atualizar"}</Button>
          </div>
          {error && <div className="rounded-md border bg-muted p-3 text-sm">{error}</div>}
          <div className="space-y-2">
            {items.map((it) => (
              <div key={String(it.id)} className="rounded-md border p-3 text-sm bg-card">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <Badge variant="outline" className="font-mono">{String(it.id).slice(0, 12)}</Badge>
                  {it.tool && <Badge variant="secondary">{String(it.tool)}</Badge>}
                  {it.status && <Badge variant="outline">{String(it.status)}</Badge>}
                  {it.risk && <Badge variant={riskVariant(String(it.risk))}>{String(it.risk)}</Badge>}
                  {it.user_id && <span className="text-xs text-muted-foreground">user {String(it.user_id).slice(0, 8)}</span>}
                </div>
                {it.reason && <div className="text-sm mb-2">{String(it.reason)}</div>}
                <pre className="text-xs bg-muted p-2 rounded overflow-auto">{JSON.stringify(it, null, 2).slice(0, 600)}</pre>
                {filter === "pending" && (
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" onClick={() => decide(String(it.id), "approved")} disabled={!!acting}>
                      {acting === String(it.id) + "approved" ? "Aprovandoâ€¦" : "Approve"}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => decide(String(it.id), "rejected")} disabled={!!acting}>
                      {acting === String(it.id) + "rejected" ? "Rejeitandoâ€¦" : "Reject"}
                    </Button>
                  </div>
                )}
              </div>
            ))}
            {!loading && items.length === 0 && !error && <p className="text-sm text-muted-foreground">Sem itens.</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}


