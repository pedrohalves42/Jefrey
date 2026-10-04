import { useCallback, useEffect, useState } from "react"
import { authedFetch } from "@/lib/session"

type Approval = {
  id: string
  tool_name?: string
  risk_level?: string
  reason?: string
  thread_id?: string
  created_at?: string
  expires_at?: string
}

const RISK: Record<string, { label: string; cls: string }> = {
  low: { label: "baixo", cls: "text-emerald-300" },
  medium: { label: "médio", cls: "text-amber-300" },
  high: { label: "alto", cls: "text-orange-300" },
  critical: { label: "crítico", cls: "text-red-300" },
}

function fmt(ts?: string): string {
  if (!ts) return ""
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("pt-BR")
}

export default function Aprovacoes() {
  const [items, setItems] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await authedFetch("/approvals/pending")
      if (!r.ok) throw new Error(String(r.status))
      const j = await r.json()
      setItems(Array.isArray(j.pending) ? j.pending : [])
      setError(null)
    } catch {
      setError("Não consegui carregar as aprovações. Verifique se o Jefrey está rodando.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const t = setInterval(() => void load(), 8000)
    return () => clearInterval(t)
  }, [load])

  async function decide(id: string, decision: "approved" | "rejected") {
    setBusy(id)
    try {
      const r = await authedFetch(`/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision, decided_by: "usuario" }),
      })
      if (!r.ok) setError("Não consegui registrar a decisão (talvez já tenha expirado).")
      await load()
    } finally {
      setBusy(null)
    }
  }

  return (
    <section aria-labelledby="ap-t" className="space-y-3">
      <div>
        <h2 id="ap-t" className="text-lg font-semibold text-white">
          Aprovações pendentes
        </h2>
        <p className="text-sm text-white/55">Quando o Jefrey vai fazer algo de risco, ele espera a sua decisão aqui antes de agir.</p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}
      {loading ? (
        <p className="text-sm text-white/50">Carregando…</p>
      ) : items.length === 0 ? (
        <p className="jf-panel p-4 text-sm text-white/60">Nada esperando por você.</p>
      ) : (
        <ul className="space-y-2">
          {items.map(a => {
            const risk = RISK[(a.risk_level || "").toLowerCase()]
            return (
              <li key={a.id} className="jf-panel p-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-medium text-white">{a.tool_name || "ação"}</span>
                  {risk && <span className={`text-xs ${risk.cls}`}>risco {risk.label}</span>}
                  <span className="text-xs text-white/40">{fmt(a.created_at)}</span>
                </div>
                {a.reason && <p className="mt-1 text-sm text-white/70">{a.reason}</p>}
                <div className="mt-3 flex gap-2">
                  <button type="button" disabled={busy === a.id} onClick={() => void decide(a.id, "approved")} className="jf-btn jf-focus px-4 py-1.5 text-sm">
                    Aprovar
                  </button>
                  <button
                    type="button"
                    disabled={busy === a.id}
                    onClick={() => void decide(a.id, "rejected")}
                    className="jf-focus rounded-lg border border-white/15 px-4 py-1.5 text-sm text-white/80 hover:bg-white/5"
                  >
                    Negar
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
