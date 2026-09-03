import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

type Health = { status: string; version?: string; checks?: Record<string,string> }

export function HealthBadge() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: async (): Promise<Health> => {
      const r = await fetch("/health")
      if (!r.ok) throw new Error("health fail")
      return r.json()
    },
    refetchInterval: 10000
  })
  const ok = !isError && !isLoading && data?.status === "ok"
  return (
    <Card className="w-full">
      <CardContent className="p-3 flex items-center gap-3">
        <Badge variant={ok ? "success" : isLoading ? "secondary" : "destructive"}>{isLoading ? "checking..." : ok ? "7/7 healthy" : "offline"}</Badge>
        <span className="text-sm text-muted-foreground">{data?.version ? `v${data.version}` : ""} {data?.status ?? ""}</span>
        <span className="ml-auto text-xs text-muted-foreground">API :8000 | MCP :8001 | Grafana :3000 | Prometheus :9090 | n8n :5678</span>
      </CardContent>
    </Card>
  )
}
