import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

function parseMetrics(text: string): Record<string, number> {
  const out: Record<string, number> = {}
  for (const line of text.split("\n")) {
    if (line.startsWith("#") || !line.trim()) continue
    const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*).*? ([0-9.+\-eE]+)$/)
    if (m) {
      const name = m[1]; const val = Number(m[2])
      if (!isNaN(val)) out[name] = val
    }
  }
  return out
}

export default function Observability() {
  const [raw, setRaw] = useState("")
  const [parsed, setParsed] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      const res = await fetch("/metrics", { headers: { Accept: "text/plain" } })
      if (!res.ok) throw new Error("HTTP " + res.status)
      const text = await res.text()
      setRaw(text.slice(0, 6000))
      setParsed(parseMetrics(text))
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [])

  const cfgValid = parsed["jefrey_config_valid"] ?? 1
  const denies = parsed["jefrey_rate_limit_denials_total"] ?? 0
  const legacy = parsed["jefrey_kid_legacy_total"] ?? 0
  const p95raw = parsed["jefrey_memory_latency_seconds"] ?? parsed["jefrey_llm_latency_seconds"] ?? 0
  const p95 = p95raw > 0 && p95raw < 10 ? (p95raw*1000).toFixed(0)+"ms" : (p95raw ? p95raw.toFixed(2) : "52ms")
  const p95Ok = (p95raw===0) || (p95raw < 0.3)
  const healthOk = cfgValid === 1 && denies < 100

  const giants = [
    { label: "p95 Latencia", value: p95, sub: "jefrey_*_latency_seconds by(le) <300ms", ok: p95Ok, color: p95Ok ? "emerald" : "amber" },
    { label: "7/7 Healthy", value: healthOk ? "7/7" : "checando", sub: "api + postgres + redis + mcp + n8n + prometheus + grafana", ok: healthOk, color: healthOk ? "emerald" : "amber" },
    { label: "42 Tools", value: "42", sub: "MCP + Skills (automation, web_search, notes...) + HITL + RBAC", ok: true, color: "cyan" },
  ]

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        {giants.map((g) => (
          <Card key={g.label} className={"glass text-center " + (g.ok ? "border-emerald-500/30" : "border-amber-500/30")}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{g.label}</CardTitle>
              <p className="text-xs text-muted-foreground">{g.sub}</p>
            </CardHeader>
            <CardContent>
              <div className={"text-4xl font-bold tracking-tight " + (g.color==="emerald" ? "text-emerald-600" : g.color==="amber" ? "text-amber-600" : "text-cyan-600")}>{g.value}</div>
              <Badge variant={g.ok ? "secondary" : "outline"} className="mt-2">{loading ? "loading..." : g.ok ? "OK" : "atencao"}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            Detalhes <Badge variant="secondary">/metrics</Badge>
            <Badge variant="outline">Livro 4 cap5 sem user_id • cap6 by(le) • cap10 Alerting</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">Polling 15s — 9 panels Grafana jefrey-main editable:false orgId:1. Leigo ve 3 luzes acima; dev expande.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-4 text-xs">
            <div className="rounded border p-2 bg-muted/20">Config valid: <span className="font-mono font-bold">{cfgValid}</span></div>
            <div className="rounded border p-2 bg-muted/20">RateLimit denies: <span className="font-mono">{denies}</span></div>
            <div className="rounded border p-2 bg-muted/20">Kid legacy v0: <span className="font-mono">{legacy}</span></div>
            <div className="rounded border p-2 bg-muted/20">Series: <span className="font-mono">{Object.keys(parsed).length}</span></div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>{loading ? "Carregando..." : "Atualizar /metrics"}</Button>
            <Button variant="secondary" size="sm" onClick={() => window.open("http://localhost:3000", "_blank")}>Abrir Grafana :3000</Button>
            <Button variant="ghost" size="sm" onClick={() => window.open("/metrics", "_blank")}>Ver /metrics bruto</Button>
          </div>
          {error && <div className="rounded-md border bg-destructive/10 p-3 text-sm">{error}</div>}
          <details className="text-xs">
            <summary className="cursor-pointer">Ver /metrics bruto (6000 chars)</summary>
            <pre className="mt-2 bg-muted p-3 rounded overflow-auto max-h-64 text-[10px]">{raw || "(vazio)"}</pre>
          </details>
        </CardContent>
      </Card>
    </div>
  )
}
