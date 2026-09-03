import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
export function Settings() {
  return (
    <Card><CardHeader><CardTitle>Settings — 7 pecas + links</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
      <div className="grid md:grid-cols-2 gap-2">
        <div className="border rounded p-2"><b>API</b> :8000 /health /docs</div>
        <div className="border rounded p-2"><b>MCP</b> :8001 streamable-http</div>
        <div className="border rounded p-2"><b>Postgres+pgvector</b> :5432</div>
        <div className="border rounded p-2"><b>Redis</b> :6379 Streams + DLQ</div>
        <div className="border rounded p-2"><b>Prometheus</b> :9090 6 alerts</div>
        <div className="border rounded p-2"><b>Grafana</b> :3000 jefrey-main 8 panels</div>
        <div className="border rounded p-2"><b>n8n</b> :5678 event router</div>
        <div className="border rounded p-2"><b>UI</b> :5173 dev / :8000 prod (static)</div>
      </div>
      <p className="text-xs text-muted-foreground">JEFREY_ENV dev|prod — validate_for_production() fail-closed 8 envs ?required. Sem user_id em labelnames (Livro4 cap5 cardinality &lt;800 series).</p>
    </CardContent></Card>
  )
}
