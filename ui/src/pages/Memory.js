import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, getUserId, mapHttpError } from "@/lib/api";
export default function Memory() {
    const [query, setQuery] = useState("");
    const [layer, setLayer] = useState("episodic");
    const [limit, setLimit] = useState(5);
    const [hits, setHits] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [latency, setLatency] = useState(null);
    async function search() {
        const q = query.trim();
        if (!q || loading)
            return;
        setError(null);
        setLoading(true);
        setLatency(null);
        const t0 = performance.now();
        try {
            const params = new URLSearchParams({ q, limit: String(limit) });
            const res = await apiFetch(`/memory/search?${params.toString()}`, { method: "GET" });
            const ms = Math.round(performance.now() - t0);
            setLatency(ms);
            if (!res.ok) {
                const body = await res.text();
                throw new Error(mapHttpError(res.status) + (body ? " - " + body.slice(0, 400) : ""));
            }
            const data = await res.json().catch(() => ({}));
            const results = data.results || data.hits || data.memories || data.items || [];
            const norm = results.map((r) => {
                if (typeof r === "string")
                    return { content: r };
                const o = r;
                return {
                    content: String(o.content || o.text || o.memory || JSON.stringify(o).slice(0, 500)),
                    score: typeof o.score === "number" ? o.score : undefined,
                    metadata: o.metadata || undefined,
                    type: String(o.type || o.layer || layer),
                    created_at: String(o.created_at || o.createdAt || ""),
                };
            });
            setHits(norm);
            if (norm.length === 0)
                setError("Nenhum resultado - HNSW m16 ef64 pode retornar Seq Scan em <10k linhas (DDIA cap12). Tente outro termo.");
        }
        catch (e) {
            setHits([]);
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    return (_jsx("div", { className: "space-y-4", children: _jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2", children: ["Memoria vetorial ", _jsx(Badge, { variant: "secondary", children: "HNSW m16 ef64" }), _jsx(Badge, { variant: "outline", children: "p50 48ms p95 55ms" }), latency !== null && _jsxs(Badge, { variant: latency < 300 ? "secondary" : "destructive", children: [latency, "ms"] })] }), _jsxs("p", { className: "text-sm text-muted-foreground", children: ["GET /memory/search?q= vetorial por user_id (", _jsx("span", { className: "font-mono", children: getUserId() }), ") - p95 <300ms SLO (Livro 5 DDIA cap12). Isolamento Axiom #2."] })] }), _jsxs(CardContent, { className: "space-y-3", children: [_jsxs("div", { className: "flex gap-2 flex-wrap", children: [_jsx("input", { className: "flex-1 min-w-[220px] rounded-md border px-3 py-2 text-sm", placeholder: "Busque: ex. 'teste' ou 'projeto jefrey'", value: query, onChange: (e) => setQuery(e.target.value), onKeyDown: (e) => { if (e.key === "Enter")
                                        search(); }, "aria-label": "query memoria" }), _jsxs("select", { className: "rounded-md border px-2 py-2 text-sm", value: layer, onChange: (e) => setLayer(e.target.value), "aria-label": "layer", children: [_jsx("option", { value: "episodic", children: "episodic" }), _jsx("option", { value: "semantic", children: "semantic" }), _jsx("option", { value: "procedural", children: "procedural" }), _jsx("option", { value: "all", children: "all" })] }), _jsxs("select", { className: "rounded-md border px-2 py-2 text-sm", value: limit, onChange: (e) => setLimit(Number(e.target.value)), "aria-label": "limit", children: [_jsx("option", { value: 5, children: "5" }), _jsx("option", { value: 10, children: "10" }), _jsx("option", { value: 20, children: "20" })] }), _jsx(Button, { onClick: search, disabled: loading || !query.trim(), children: loading ? "Buscando..." : "Buscar" })] }), error && _jsx("div", { className: "rounded-md border bg-muted p-3 text-sm", children: error }), _jsxs("div", { className: "space-y-2", children: [hits.map((h, i) => (_jsxs("div", { className: "rounded-md border p-3 text-sm bg-card", children: [_jsxs("div", { className: "flex items-center gap-2 mb-1", children: [_jsx(Badge, { variant: "outline", children: h.type || layer }), typeof h.score === "number" && _jsxs(Badge, { variant: "secondary", children: ["score ", h.score.toFixed(3)] }), h.created_at && _jsx("span", { className: "text-xs text-muted-foreground", children: h.created_at.slice(0, 19) })] }), _jsx("div", { className: "whitespace-pre-wrap break-words", children: h.content }), h.metadata && _jsx("pre", { className: "mt-2 text-xs bg-muted p-2 rounded overflow-auto", children: JSON.stringify(h.metadata, null, 2).slice(0, 800) })] }, i))), !loading && hits.length === 0 && !error && _jsx("p", { className: "text-sm text-muted-foreground", children: "Digite um termo e clique Buscar." })] }), _jsxs("p", { className: "text-xs text-muted-foreground", children: ["Curl: ", _jsx("code", { className: "font-mono bg-muted px-1 rounded", children: "curl \"http://localhost:8000/memory/search?q=teste&limit=5\" -H \"Authorization: Bearer $TOKEN\"" })] })] })] }) }));
}
