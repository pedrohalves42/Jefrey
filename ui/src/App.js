import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Nav } from "@/components/Nav";
import { HealthBadge } from "@/components/HealthBadge";
import { OnboardingWizard } from "@/components/OnboardingWizard";
import { HudReactor } from "@/components/HudReactor";
import { useWakeWord } from "@/hooks/useWakeWord";
import { ThemeWheel } from "@/components/ThemeWheel";
import { ensureDevToken, getToken } from "@/lib/api";
import { playChime } from "@/lib/audio";
import Chat from "@/pages/Chat";
import Memory from "@/pages/Memory";
import Approvals from "@/pages/Approvals";
import Observability from "@/pages/Observability";
import Settings from "@/pages/Settings";
import Knowledge from "@/pages/KnowledgePage";
import { Tour } from "@/components/Tour";
import { AuthButton } from "@/components/AuthButton";
const qc = new QueryClient();
export default function App() {
    const [ready, setReady] = useState(!!getToken());
    const [hudLevel, setHudLevel] = useState(0);
    const [hudState, setHudState] = useState("idle");
    const [wakeEnabled, setWakeEnabled] = useState(false);
    const wake = useWakeWord({ enabled: wakeEnabled, onWake: () => { setHudState("listening"); setHudLevel(0.6); try {
            document.querySelector('[aria-label="Falar com Jefrey"]')?.click();
        }
        catch { } } });
    useEffect(() => {
        let cancelled = false;
        if (!getToken()) {
            ensureDevToken().then((t) => { if (!cancelled)
                setReady(!!t || !!getToken()); });
        }
        return () => { cancelled = true; };
    }, []);
    useEffect(() => { playChime(); }, []);
    // isair face_widget idle breathing + state wiring (listening via wake, thinking via chat, speaking via TTS)
    useEffect(() => {
        const id = setInterval(() => {
            if (hudState === "idle")
                setHudLevel(0.04 + Math.sin(Date.now() / 1200) * 0.02);
        }, 200);
        return () => clearInterval(id);
    }, [hudState]);
    // expose global hook for Chat/Voice to drive HUD (Stark lab)
    useEffect(() => { window.__setHudState = (s) => setHudState(s); window.__setHudLevel = (v) => setHudLevel(v); return () => { delete window.__setHudState; delete window.__setHudLevel; }; }, []);
    function onHudClick() {
        try {
            document.querySelector('[aria-label="Falar com Jefrey"]')?.click();
        }
        catch { }
        setHudLevel(0.7);
        setTimeout(() => setHudLevel(0.04), 800);
    }
    return (_jsx(QueryClientProvider, { client: qc, children: _jsx(BrowserRouter, { children: _jsxs("div", { className: "min-h-screen bg-background", children: [_jsx("header", { className: "sticky top-0 z-40 border-b glass-strong backdrop-blur-xl", children: _jsxs("div", { className: "max-w-5xl mx-auto p-3 flex items-center gap-3", children: [_jsx("h1", { className: "font-bold text-lg tracking-tight", children: "Jefrey" }), _jsx("span", { className: "text-xs text-muted-foreground hidden sm:inline", children: "1 programa, 7 pecas \u2014 175/175 + 21/21" }), _jsxs("div", { className: "ml-auto flex items-center gap-3", children: [_jsx("button", { onClick: () => setWakeEnabled(v => !v), title: wake.supported ? (wakeEnabled ? "Desativar wake Jefrey" : "Ativar wake Jefrey") : "Wake nao suportado neste browser", className: `text-[10px] px-2 py-1 rounded-full font-mono ${wakeEnabled ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" : "bg-white/5 text-white/50 border-white/10"}`, children: wakeEnabled ? "WAKE ON" : "WAKE OFF" }), _jsx(AuthButton, {}), _jsx(ThemeWheel, {}), ready && _jsx("span", { className: "text-xs text-emerald-600 font-medium hidden sm:inline", children: "Pronto" })] })] }) }), _jsxs("div", { className: "max-w-5xl mx-auto", children: [_jsx("div", { className: "flex justify-center pt-6 pb-2", children: _jsx(HudReactor, { level: hudLevel, state: hudState, onClick: onHudClick }) }), _jsx(Nav, {}), _jsxs("div", { className: "p-4 space-y-4", children: [_jsx(OnboardingWizard, { onDone: () => setReady(!!getToken()) }), _jsx(HealthBadge, {}), _jsx(SkillManager, {}), _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Chat, {}) }), _jsx(Route, { path: "/memory", element: _jsx(Memory, {}) }), _jsx(Route, { path: "/approvals", element: _jsx(Approvals, {}) }), _jsx(Route, { path: "/observability", element: _jsx(Observability, {}) }), _jsx(Route, { path: "/settings", element: _jsx(Settings, {}) }), _jsx(Route, { path: "/knowledge", element: _jsx(Knowledge, {}) })] }), _jsx(Tour, {})] })] })] }) }) }));
}
