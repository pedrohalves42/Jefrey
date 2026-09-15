import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { isOnboarded, setOnboarded } from "@/lib/api";
export function OnboardingWizard({ onDone }) {
    const [open, setOpen] = useState(false);
    const [step, setStep] = useState(1);
    useEffect(() => {
        try {
            const params = new URLSearchParams(window.location.search);
            const tour = params.get("tour") === "1";
            if (tour) {
                setOpen(true);
                setStep(1);
                return;
            }
            if (!isOnboarded())
                setOpen(true);
        }
        catch { }
    }, []);
    function dismiss() {
        setOnboarded(true);
        setOpen(false);
        onDone?.();
    }
    function next() {
        if (step < 3)
            setStep(step + 1);
        else
            dismiss();
    }
    if (!open)
        return null;
    return (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4", role: "dialog", "aria-modal": "true", children: _jsxs(Card, { className: "w-full max-w-md border-cyan-500/30 shadow-xl shadow-cyan-500/10", children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { className: "flex items-center gap-2", children: [step === 1 && "Oi, sou o Jefrey", step === 2 && "Digite ou fale", step === 3 && "Pronto para usar", _jsx(Badge, { variant: "secondary", children: "1 programa, 7 pecas" })] }) }), _jsxs(CardContent, { className: "space-y-4", children: [step === 1 && (_jsxs("div", { className: "space-y-2 text-sm", children: [_jsx("p", { children: "1 programa, 7 pecas \u2014 175/175 validado. Postgres + Redis + LLM qwen2.5 + Voz + MCP + n8n + Grafana." }), _jsx("p", { className: "text-muted-foreground", children: "Voce nao precisa entender token. Ja deixei tudo pronto." }), _jsx("div", { className: "rounded-md border bg-muted/20 p-2 text-xs font-mono", children: "thread demo-1 pronta \u2022 7/7 healthy" })] })), step === 2 && (_jsxs("div", { className: "space-y-2 text-sm", children: [_jsx("p", { children: "Digite no Chat ou clique no microfone. Exemplos:" }), _jsxs("ul", { className: "list-disc ml-4 text-muted-foreground", children: [_jsx("li", { children: "\"oi, o que voce faz?\"" }), _jsx("li", { children: "\"salve uma memoria: meu projeto e Jarvis\"" })] }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Voz: STT small pt + TTS piper 6 vozes. Wake \"Jefrey/Jarvis\" em Settings." })] })), step === 3 && (_jsxs("div", { className: "space-y-2 text-sm", children: [_jsx("p", { children: "Tudo pronto. Nenhum manual." }), _jsx("p", { className: "text-muted-foreground", children: "Se ver 401, clique em \"Liberar acesso (1s)\" \u2014 eu renovo sozinho." }), _jsx("div", { className: "rounded-md border border-cyan-500/20 bg-cyan-500/10 p-2 text-xs", children: "Dica: use ?tour=1 para rever este guia." })] })), _jsxs("div", { className: "flex items-center justify-between pt-2", children: [_jsxs("span", { className: "text-xs text-muted-foreground", children: [step, "/3"] }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { variant: "ghost", onClick: dismiss, children: "Pular" }), _jsx(Button, { onClick: next, children: step < 3 ? "Proximo →" : "Comecar →" })] })] })] })] }) }));
}
