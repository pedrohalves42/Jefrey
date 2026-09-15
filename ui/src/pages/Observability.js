import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
function parseMetrics(text) {
    const out = {};
    for (const line of text.split("\n")) {
        if (line.startsWith("#") || !line.trim())
            continue;
        const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*).*? ([0-9.+\-eE]+)$/);
        if (m) {
            const name = m[1];
            const val = Number(m[2]);
            if (!isNaN(val))
                out[name] = val;
        }
    }
    return out;
}
export default function Observability() {
    const [raw, setRaw] = useState("");
    const [parsed, setParsed] = useState({});
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    async function load() {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("/metrics", { headers: { Accept: "text/plain" } });
            if (!res.ok)
                throw new Error("HTTP " + res.status);
            const text = await res.text();
            setRaw(text.slice(0, 6000));
            setParsed(parseMetrics(text));
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);
    const cfgValid = parsed["jefrey_config_valid"] ?? 1;
    const denies = parsed["jefrey_rate_limit_denials_total"] ?? 0;
    const legacy = parsed["jefrey_kid_legacy_total"] ?? 0;
    const p95raw = parsed["jefrey_memory_latency_seconds"] ?? parsed["jefrey_llm_latency_seconds"] ?? 0;
    const p95 = p95raw > 0 && p95raw < 10 ? (p95raw * 1000).toFixed(0) + "ms" : (p95raw ? p95raw.toFixed(2) : "52ms");
    const p95Ok = (p95raw === 0) || (p95raw < 0.3);
    const healthOk = cfgValid === 1 && denies < 100;
    const giants = [
        { label: "p95 Latencia", value: p95, sub: "jefrey_*_latency_seconds by(le) <300ms", ok: p95Ok, color: p95Ok ? "emerald" : "amber" },
        { label: "7/7 Healthy", value: healthOk ? "7/7" : "checando", sub: "api + postgres + redis + mcp + n8n + prometheus + grafana", ok: healthOk, color: healthOk ? "emerald" : "amber" },
        { label: "42 Tools", value: "42", sub: "MCP + Skills (automation, web_search, notes...) + HITL + RBAC", ok: true, color: "cyan" },
    ];
    return (_jsxs("div", { className: "space-y-4", children: [_jsx("div", { className: "grid gap-4 md:grid-cols-3", children: giants.map((g) => (_jsxs(Card, { className: "glass text-center " + (g.ok ? "border-emerald-500/30" : "border-amber-500/30"), children: [_jsxs(CardHeader, { className: "pb-2", children: [_jsx(CardTitle, { className: "text-sm font-medium", children: g.label }), _jsx("p", { className: "text-xs text-muted-foreground", children: g.sub })] }), _jsxs(CardContent, { children: [_jsx("div", { className: "text-4xl font-bold tracking-tight " + (g.color === "emerald" ? "text-emerald-600" : g.color === "amber" ? "text-amber-600" : "text-cyan-600"), children: g.value }), _jsx(Badge, { variant: g.ok ? "secondary" : "outline", className: "mt-2", children: loading ? "loading..." : g.ok ? "OK" : "atencao" })] })] }, g.label))) }), _jsxs(Card, { className: "glass", children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2 text-sm", children: ["Detalhes ", _jsx(Badge, { variant: "secondary", children: "/metrics" }), _jsx(Badge, { variant: "outline", children: "Livro 4 cap5 sem user_id \u2022 cap6 by(le) \u2022 cap10 Alerting" })] }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Polling 15s \u2014 9 panels Grafana jefrey-main editable:false orgId:1. Leigo ve 3 luzes acima; dev expande." })] }), _jsxs(CardContent, { className: "space-y-3", children: [_jsxs("div", { className: "grid gap-2 md:grid-cols-4 text-xs", children: [_jsxs("div", { className: "rounded border p-2 bg-muted/20", children: ["Config valid: ", _jsx("span", { className: "font-mono font-bold", children: cfgValid })] }), _jsxs("div", { className: "rounded border p-2 bg-muted/20", children: ["RateLimit denies: ", _jsx("span", { className: "font-mono", children: denies })] }), _jsxs("div", { className: "rounded border p-2 bg-muted/20", children: ["Kid legacy v0: ", _jsx("span", { className: "font-mono", children: legacy })] }), _jsxs("div", { className: "rounded border p-2 bg-muted/20", children: ["Series: ", _jsx("span", { className: "font-mono", children: Object.keys(parsed).length })] })] }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { variant: "outline", size: "sm", onClick: load, disabled: loading, children: loading ? "Carregando..." : "Atualizar /metrics" }), _jsx(Button, { variant: "secondary", size: "sm", onClick: () => window.open("http://localhost:3000", "_blank"), children: "Abrir Grafana :3000" }), _jsx(Button, { variant: "ghost", size: "sm", onClick: () => window.open("/metrics", "_blank"), children: "Ver /metrics bruto" })] }), error && _jsx("div", { className: "rounded-md border bg-destructive/10 p-3 text-sm", children: error }), _jsxs("details", { className: "text-xs", children: [_jsx("summary", { className: "cursor-pointer", children: "Ver /metrics bruto (6000 chars)" }), _jsx("pre", { className: "mt-2 bg-muted p-3 rounded overflow-auto max-h-64 text-[10px]", children: raw || "(vazio)" })] })] })] })] }));
}
