import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// F6-5 Tour — 4 steps Joyride leve (sem lib externa) + ?tour=1
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
const STEPS = [
    { title: "1/4 Chat", text: "Digite 'oi' e clique Enviar. Ja esta com token automatico (Pronto no header). Sem 401.", target: "/" },
    { title: "2/4 Voz", text: "Clique no microfone. Fale 'oi Jefrey' (ou 'Jarvis'). STT small pt → qwen2:0.5b → TTS piper 6 vozes. Wake 'Jefrey/Jarvis' em Settings.", target: "/" },
    { title: "3/4 Conexoes", text: "Use os 4 botoes abaixo do Chat: Navegar, Arquivo (500MB → HNSW), Buscar web (Tavily), Enviar WhatsApp/Telegram via n8n.", target: "/" },
    { title: "4/4 Observar", text: "Observabilidade mostra 3 luzes gigantes: p95 <300ms, 7/7 healthy, 42 tools. Grafana :3000 so para dev.", target: "/observability" },
];
export function Tour({ onDone }) {
    const [open, setOpen] = useState(false);
    const [step, setStep] = useState(0);
    useEffect(() => {
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.get("tour") === "1") {
                setOpen(true);
                setStep(0);
                return;
            }
            const seen = localStorage.getItem("jefrey_tour_seen");
            if (!seen)
                setOpen(true);
        }
        catch { }
    }, []);
    function close() {
        try {
            localStorage.setItem("jefrey_tour_seen", "1");
        }
        catch { }
        setOpen(false);
        onDone?.();
    }
    function next() {
        if (step < STEPS.length - 1)
            setStep(step + 1);
        else
            close();
    }
    if (!open)
        return null;
    const s = STEPS[step];
    return (_jsx("div", { className: "fixed bottom-4 right-4 z-50 w-80", children: _jsxs(Card, { className: "glass-strong border-cyan-500/30 shadow-xl", children: [_jsx(CardHeader, { className: "pb-2", children: _jsxs(CardTitle, { className: "text-sm flex items-center gap-2", children: [s.title, " ", _jsx(Badge, { variant: "secondary", children: "tour" })] }) }), _jsxs(CardContent, { className: "space-y-3", children: [_jsx("p", { className: "text-xs text-muted-foreground", children: s.text }), _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("span", { className: "text-xs font-mono", children: [step + 1, "/4"] }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: close, children: "Fechar" }), _jsx(Button, { size: "sm", onClick: next, children: step < STEPS.length - 1 ? "Proximo →" : "Entendi" })] })] }), _jsx("div", { className: "flex gap-1", children: STEPS.map((_, i) => _jsx("span", { className: "h-1 flex-1 rounded " + (i === step ? "bg-cyan-500" : "bg-muted") }, i)) })] })] }) }));
}
