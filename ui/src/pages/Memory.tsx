import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
export function Memory() {
  const curl = `curl -X POST http://localhost:8000/memory/search -H "Content-Type: application/json" -d '{"query":"teste","user_id":"demo"}'`
  return (
    <Card><CardHeader><CardTitle>Memoria — busca vetorial (pgvector HNSW m16 ef64)</CardTitle></CardHeader><CardContent>
      <p className="text-sm text-muted-foreground">UI-2 entregara busca /memory com p50 48ms p95 55ms + 6 camadas (episodic/semantic/procedural ...). Por enquanto use <code>/docs</code> para testar POST /memory/search.</p>
      <div className="mt-3 p-3 border rounded bg-muted/30 text-xs">{curl}</div>
    </CardContent></Card>
  )
}
