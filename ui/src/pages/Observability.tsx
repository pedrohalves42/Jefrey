import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from "recharts"

type MetricsParsed = { ts: number; p95?: number; errorRate?: number; denies?: number; legacy?: number }

function parseMetrics(text: string): Record<string, number> {
  const out: Record<string, number> = {}
  for (const line of text.split("\n")) {
    if (line.startsWith("#") || !line.trim()) continue
    const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*).*? ([0-9.+\-eE]+)$/)
    if (m) {
      const name = m[1]
      const val = Number(m[2])
      if (!isNaN(val)) out[name] = val
    }
  }
  return out
}

export default function Observability() {
  const [raw, setRaw] = useState("")
  const [parsed, setParsed] = useState<Record<string, number>>({})
  const [series, setSeries] = useState<MetricsParsed[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      const res = await fetch("/metrics", { headers: { Accept: "text/plain" } })
      if (!res.ok) throw new Error("HTTP " + res.status)
      const text = await res.text()
      setRaw(text.slice(0, 6000))
      const p = parseMetrics(text)
      setParsed(p)
      const point: MetricsParsed = {
        ts: Date.now(),
        p95: p["memory_latency_seconds"] ?? p["jefrey_memory_latency_p95"] ?? 0,
        errorRate: p["jefrey_api_errors_total"] ?? p["http_requests_total"] ?? 0,
        denies: p["jefrey_rate_limit_denials_total"] ?? 0,
        legacy: p["jefrey_kid_legacy_total"] ?? 0,
      }
      setSeries((s) => [...s.slice(-19), point])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setLoading(false) }
  }

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [])

  const cards = [
    { label: "API errors", value: parsed["jefrey_api_errors_total"] ?? parsed["http_requests_total"] ?? 0, hint: "jefrey_api_errors_total" },
    { label: "RateLimit denials", value: parsed["jefrey_rate_limit_denials_total"] ?? 0, hint: "CIPHER-026" },
    { label: "Kid legacy (v0)", value: parsed["jefrey_kid_legacy_total"] ?? 0, hint: "CIPHER-033 rotation" },
    { label: "Config valid", value: parsed["jefrey_config_valid"] ?? 1, hint: "Livro 4 cap10" },
  ]

  const chartData = series.map((p, i) => ({ name: String(i), legacy: p.legacy || 0, denies: p.denies || 0 }))

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <Card key={c.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{c.label}</CardTitle>
              <p className="text-xs text-muted-foreground">{c.hint}</p>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{String(c.value)}</div>
              <Badge variant={(c.value === 0 || (c.label.includes("valid") && c.value === 1)) ? "secondary" : "outline"} className="mt-1">
                {loading ? "loading..." : "live 15s"}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Observabilidade <Badge variant="secondary">/metrics</Badge>
            <Badge variant="outline">Livro 4 cap5 &lt;800 series sem user_id</Badge>
          </CardTitle>
          <p className="text-sm text-muted-foreground">Recharts polling 15s — 4 cards + serie legacy/denies. Grafana jefrey-main 8 panels editable false schema 39.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" hide />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="legacy" stroke="#8884d8" dot={false} name="kid legacy" />
                <Line type="monotone" dataKey="denies" stroke="#82ca9d" dot={false} name="denies" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cards.map((c) => ({ name: c.label.slice(0, 8), value: c.value }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={load} disabled={loading}>{loading ? "Carregando..." : "Atualizar /metrics"}</Button>
            <Button variant="secondary" onClick={() => window.open("http://localhost:3000", "_blank")}>Abrir Grafana :3000</Button>
          </div>
          {error && <div className="rounded-md border bg-destructive/10 p-3 text-sm">{error}</div>}
          <details className="text-xs">
            <summary className="cursor-pointer">Ver /metrics bruto (6000 chars)</summary>
            <pre className="mt-2 bg-muted p-3 rounded overflow-auto max-h-64">{raw || "(vazio — verifique /metrics, /metrics e public em auth_middleware)"}</pre>
          </details>
          <pre className="text-xs bg-muted p-2 rounded overflow-auto">{JSON.stringify(parsed, null, 2).slice(0, 1200) || "{}"}</pre>
        </CardContent>
      </Card>
    </div>
  )
}
