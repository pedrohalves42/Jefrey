import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
const links = [
    { to: "/", label: "Chat" },
    { to: "/memory", label: "Memoria" },
    { to: "/approvals", label: "Approvals" },
    { to: "/observability", label: "Observabilidade" },
    { to: "/settings", label: "Settings" },
    { to: "/knowledge", label: "Conhecimento" }
];
export function Nav() {
    return (_jsxs("nav", { className: "flex gap-1 p-2 border-b bg-card", children: [links.map(l => (_jsx(NavLink, { to: l.to, className: ({ isActive }) => cn("px-3 py-2 rounded-md text-sm font-medium", isActive ? "bg-primary text-primary-foreground" : "hover:bg-secondary"), children: l.label }, l.to))), _jsxs("div", { className: "ml-auto flex gap-2 text-xs items-center", children: [_jsx("a", { href: "/docs", target: "_blank", className: "px-2 py-1 rounded border", children: "API /docs" }), _jsx("a", { href: "http://localhost:3000", target: "_blank", className: "px-2 py-1 rounded border", children: "Grafana" }), _jsx("a", { href: "http://localhost:9090", target: "_blank", className: "px-2 py-1 rounded border", children: "Prometheus" })] })] }));
}
