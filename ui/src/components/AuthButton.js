import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
export function AuthButton() {
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const authOptions = [
        { label: "Google OAuth", onClick: () => navigate("/auth/google/start"), className: "text-primary" },
        { label: "Notion", onClick: () => navigate("/auth/notion"), className: "text-blue-500" },
        { label: "Gmail", onClick: () => navigate("/auth/gmail"), className: "text-red-500" },
        { label: "Google Drive", onClick: () => navigate("/auth/drive"), className: "text-green-500" },
        { label: "Calendar", onClick: () => navigate("/auth/calendar"), className: "text-orange-500" },
    ];
    return (_jsxs("div", { className: "relative", children: [_jsxs("button", { onClick: () => setShowDropdown(!showDropdown), title: showDropdown ? "Fechar autenticações" : "Adicionar conta", className: "flex items-center gap-2 px-3 py-1 rounded-md text-sm font-medium hover:bg-secondary transition-colors", children: [_jsx("svg", { className: "h-4 w-4", fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M13 16h-1v-4h-1m1-4h1v4h-1m0 0h.01M12 12h.01m-5.2 5.2a1 1 0 011.4 0l5.5-5.5m-5.6 5.6a1 1 0 001.4 0l5.5-5.5M12 12L16.34 16.34a18 18 0 012.64 2.32A8.5 8.5 0 0015 20a8.5 8.5 0 00-5.08-1.71L12 12z" }) }), _jsx("span", { children: "Auth" }), _jsx("svg", { className: "h-3 w-3 ml-1 transform rotate-180", fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M19 9l-7 7-7-7" }) })] }), showDropdown && (_jsxs("div", { className: "absolute right-0 mt-2 w-56 bg-card rounded-md shadow-lg p-1 z-50 border border-border", children: [_jsx("span", { className: "text-xs text-muted-foreground capitalize w-full mb-1 border-b border-border pb-1", children: "M\u00E9todos de autentica\u00E7\u00E3o" }), _jsx("div", { className: "space-y-1", children: authOptions.map((opt) => (_jsx(Button, { variant: "outline", size: "sm", className: opt.className, onClick: () => {
                                setIsLoading(true);
                                // Navigate to the auth route
                                setTimeout(() => {
                                    navigate(opt.onClick?.to || opt.onClick());
                                    setIsLoading(false);
                                }, 100);
                            }, children: opt.label }, opt.label))) })] }))] }));
}
