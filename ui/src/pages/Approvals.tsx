import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
export function Approvals() {
  return (
    <Card><CardHeader><CardTitle>Approvals — HITL queue</CardTitle></CardHeader><CardContent>
      <p className="text-sm text-muted-foreground">UI-3 entregara fila pending/approved/rejected via /approvals (Starlette sub-app + Bearer). Por enquanto use <code>/approvals</code> direto ou <code>/docs</code>.</p>
      <div className="mt-3 p-3 border rounded bg-muted/30 text-xs">GET http://localhost:8000/approvals/pending — requer Authorization: Bearer &lt;token&gt; (JWKS RS256 kid v1/v2)</div>
    </CardContent></Card>
  )
}
