import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, mapHttpError, getToken } from "@/lib/api";
function riskVariant(r) {
    const v = (r || "").toLowerCase();
    if (v === "low")
        return "secondary";
    if (v === "medium")
        return "outline";
    if (v === "high" || v === "critical")
        return "destructive";
    return "secondary";
}
export default function Approvals() {
    const [items, setItems] = useState([]);
    const [filter, setFilter] = useState("pending");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [acting, setActing] = useState(null);
    async function load() {
        if (!getToken()) {
            setItems([]);
            setError("Sem token — cole seu Bearer em Settings para ver Approvals (Axiom #1 fail-closed, CIPHER-031). Nenhum request enviado.");
            setLoading(false);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const res = await apiFetch(`/approvals?status=${filter}`);
            if (!res.ok)
                throw new Error(mapHttpError(res.status) + " â€” " + (await res.text()).slice(0, 400));
            const data = await res.json().catch(() => ({}));
            const arr = data.items || data.approvals || data.results || (Array.isArray(data) ? data : []);
            setItems(arr);
            if (arr.length === 0)
                setError("Nenhum approval com status " + filter + " (CIPHER-032 HITL).");
        }
        catch (e) {
            setItems([]);
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }
    async function decide(id, decision) {
        if (!getToken()) {
            setError("Sem token — defina Bearer em Settings antes de decidir.");
            return;
        }
        setActing(id + decision);
        setError(null);
        try {
            const res = await apiFetch(`/approvals/${id}/decision`, {
                method: "POST",
                body: JSON.stringify({ decision }),
            });
            if (!res.ok)
                throw new Error(mapHttpError(res.status) + " â€” " + (await res.text()).slice(0, 400));
            await load();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setActing(null);
        }
    }
    useEffect(() => { if (getToken())
        load();
    else {
        setItems([]);
        setError("Sem token — cole seu Bearer em Settings para ver Approvals (Axiom #1 fail-closed). Nenhum request enviado.");
    } }, [filter]);
    useEffect(() => {
        if (!getToken())
            return;
        const t = setInterval(load, 15000);
        return () => clearInterval(t);
    }, [filter]);
    return (_jsx("div", { className: "space-y-4", children: _jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2", children: ["Approvals HITL ", _jsx(Badge, { variant: "secondary", children: "CIPHER-032" }), _jsx(Badge, { variant: "outline", children: filter })] }), _jsx("p", { className: "text-sm text-muted-foreground", children: "GET /approvals + POST /approvals/:id/decision \u00E2\u20AC\u201D so admin aprova (RBAC 403 se guest). Polling 15s." })] }), _jsxs(CardContent, { className: "space-y-3", children: [_jsxs("div", { className: "flex gap-2", children: [_jsxs("select", { className: "rounded-md border px-2 py-2 text-sm", value: filter, onChange: (e) => setFilter(e.target.value), children: [_jsx("option", { value: "pending", children: "pending" }), _jsx("option", { value: "approved", children: "approved" }), _jsx("option", { value: "rejected", children: "rejected" }), _jsx("option", { value: "all", children: "all" })] }), _jsx(Button, { variant: "outline", onClick: load, disabled: loading, children: loading ? "Carregandoâ€¦" : "Atualizar" })] }), error && _jsx("div", { className: "rounded-md border bg-muted p-3 text-sm", children: error }), _jsxs("div", { className: "space-y-2", children: [items.map((it) => (_jsxs("div", { className: "rounded-md border p-3 text-sm bg-card", children: [_jsxs("div", { className: "flex flex-wrap items-center gap-2 mb-2", children: [_jsx(Badge, { variant: "outline", className: "font-mono", children: String(it.id).slice(0, 12) }), it.tool && _jsx(Badge, { variant: "secondary", children: String(it.tool) }), it.status && _jsx(Badge, { variant: "outline", children: String(it.status) }), it.risk && _jsx(Badge, { variant: riskVariant(String(it.risk)), children: String(it.risk) }), it.user_id && _jsxs("span", { className: "text-xs text-muted-foreground", children: ["user ", String(it.user_id).slice(0, 8)] })] }), it.reason && _jsx("div", { className: "text-sm mb-2", children: String(it.reason) }), _jsx("pre", { className: "text-xs bg-muted p-2 rounded overflow-auto", children: JSON.stringify(it, null, 2).slice(0, 600) }), filter === "pending" && (_jsxs("div", { className: "flex gap-2 mt-2", children: [_jsx(Button, { size: "sm", onClick: () => decide(String(it.id), "approved"), disabled: !!acting, children: acting === String(it.id) + "approved" ? "Aprovandoâ€¦" : "Approve" }), _jsx(Button, { size: "sm", variant: "destructive", onClick: () => decide(String(it.id), "rejected"), disabled: !!acting, children: acting === String(it.id) + "rejected" ? "Rejeitandoâ€¦" : "Reject" })] }))] }, String(it.id)))), !loading && items.length === 0 && !error && _jsx("p", { className: "text-sm text-muted-foreground", children: "Sem itens." })] })] })] }) }));
}
