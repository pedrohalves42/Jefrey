import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
export function HealthBadge() {
    const { data, isError, isLoading } = useQuery({
        queryKey: ["health"],
        queryFn: async () => {
            const r = await fetch("/health");
            if (!r.ok)
                throw new Error("health fail");
            return r.json();
        },
        refetchInterval: 10000
    });
    const ok = !isError && !isLoading && data?.status === "ok";
    return (_jsx(Card, { className: "w-full", children: _jsxs(CardContent, { className: "p-3 flex items-center gap-3", children: [_jsx(Badge, { variant: ok ? "success" : isLoading ? "secondary" : "destructive", children: isLoading ? "checking..." : ok ? "7/7 healthy" : "offline" }), _jsxs("span", { className: "text-sm text-muted-foreground", children: [data?.version ? `v${data.version}` : "", " ", data?.status ?? ""] }), _jsx("span", { className: "ml-auto text-xs text-muted-foreground", children: "API :8000 | MCP :8001 | Grafana :3000 | Prometheus :9090 | n8n :5678" })] }) }));
}
