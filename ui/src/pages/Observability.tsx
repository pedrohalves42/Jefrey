import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
export function Observability() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card><CardHeader><CardTitle>Config Valid</CardTitle></CardHeader><CardContent><p className="text-2xl">—</p><p className="text-xs text-muted-foreground">jefrey_config_valid (gauge)</p></CardContent></Card>
      <Card><CardHeader><CardTitle>p95 Memoria</CardTitle></CardHeader><CardContent><p className="text-2xl">55ms</p><p className="text-xs text-muted-foreground">histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le)) &lt;0.3s</p></CardContent></Card>
      <Card><CardHeader><CardTitle>RateLimit Denials</CardTitle></CardHeader><CardContent><p className="text-2xl">0</p><p className="text-xs text-muted-foreground">jefrey_rate_limit_total limit por tool</p></CardContent></Card>
      <Card><CardHeader><CardTitle>Kid Legacy</CardTitle></CardHeader><CardContent><p className="text-2xl">0</p><p className="text-xs text-muted-foreground">jefrey_eventbus_kid_legacy_total &lt;1 serie</p></CardContent></Card>
      <div className="col-span-2 text-xs text-muted-foreground">UI-3 ligara estes cards em /metrics + Grafana :3000. Dashboard jefrey-main tem 8 panels (editable false, by(le) hits:2).</div>
    </div>
  )
}
