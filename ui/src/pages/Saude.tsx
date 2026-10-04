import { useQuery } from "@tanstack/react-query"
import { useStatus } from "@/lib/status"
import { authedFetch } from "@/lib/session"
import { formatDuration, formatSeconds, histogramQuantile, parsePrometheus, sum, type Metrics } from "@/lib/metrics"

async function fetchMetrics(): Promise<Metrics> {
  const r = await authedFetch("/metrics", { cache: "no-store" })
  if (!r.ok) throw new Error(String(r.status))
  return parsePrometheus(await r.text())
}

function Card({ title, value, hint }: { title: string; value: string; hint?: string }) {
  const empty = value === "sem dados"
  return (
    <div className="jf-panel p-4">
      <div className="text-xs uppercase tracking-wide text-white/45">{title}</div>
      <div className={`mt-1 text-2xl font-semibold ${empty ? "text-white/35" : "text-white"}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-white/40">{hint}</div>}
    </div>
  )
}

const num = (n: number | undefined) => (n === undefined ? "sem dados" : String(Math.round(n)))

/** Tudo aqui vem de /api/status e /metrics. Sem dado = "sem dados"; nunca um numero inventado. */
export default function Saude() {
  const status = useStatus()
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: fetchMetrics, refetchInterval: 15_000 })
  const m = metrics.data

  return (
    <section aria-labelledby="sd-t" className="space-y-4">
      <h2 id="sd-t" className="text-lg font-semibold text-white">
        Saúde do sistema
      </h2>

      <div className="jf-panel p-4">
        <h3 className="mb-2 text-sm font-medium text-white/80">Serviços</h3>
        {status.data && status.data.reachable ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {status.data.services.map(s => (
              <li key={s.id} className="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2 text-sm">
                <span className="text-white/80">{s.label}</span>
                <span className={s.state === "ok" ? "text-emerald-300" : "text-red-300"}>{s.state === "ok" ? "ok" : "fora do ar"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-red-300">Sem conexão com o servidor do Jefrey.</p>
        )}
      </div>

      {metrics.isError && <p className="text-sm text-amber-300">Não consegui ler as métricas agora.</p>}
      {m && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card title="No ar há" value={formatDuration(sum(m, "jefrey_uptime_seconds"))} />
          <Card title="Resposta do modelo (mediana)" value={formatSeconds(histogramQuantile(m, "jefrey_llm_latency_seconds", 0.5))} hint="desde que o servidor iniciou" />
          <Card title="Resposta do modelo (p95)" value={formatSeconds(histogramQuantile(m, "jefrey_llm_latency_seconds", 0.95))} hint="95% das respostas são mais rápidas que isso" />
          <Card title="Tokens gerados" value={num(sum(m, "jefrey_llm_tokens_total"))} />
          <Card title="Aprovações criadas" value={num(sum(m, "jefrey_approvals_created_total"))} />
          <Card title="Ações bloqueadas" value={num(sum(m, "jefrey_tools_blocked_total"))} hint="barradas pelas regras de segurança" />
        </div>
      )}
    </section>
  )
}
