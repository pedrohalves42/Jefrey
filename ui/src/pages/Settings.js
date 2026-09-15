import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getToken, getUserId, getThreadId, setToken, setUserId, setThreadId } from "@/lib/api";
import { useWakeWord } from "@/hooks/useWakeWord";
export default function Settings() {
    const [token, setTokenState] = useState("");
    const [userId, setUserIdState] = useState("");
    const [threadId, setThreadIdLocal] = useState("");
    const [showToken, setShowToken] = useState(false);
    const [testResult, setTestResult] = useState(null);
    const [testing, setTesting] = useState(false);
    useEffect(() => {
        setTokenState(getToken() || "");
        setUserIdState(getUserId());
        setThreadIdLocal(getThreadId());
    }, []);
    function save() {
        setToken(token.trim());
        setUserId(userId.trim() || "demo");
        setThreadId(threadId.trim() || "demo-1");
        setTestResult("Salvo em localStorage. Chat/Memory ja usam este token + user_id (Axiom #2).");
    }
    async function testAuth() {
        setTesting(true);
        setTestResult(null);
        try {
            const headers = {};
            if (token.trim())
                headers["Authorization"] = `Bearer ${token.trim()}`;
            const res = await fetch("/health", { headers });
            const body = await res.text();
            setTestResult(`GET /health ${res.status}: ${body.slice(0, 500)}`);
            const res2 = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json", ...(token.trim() ? { Authorization: `Bearer ${token.trim()}` } : {}) },
                body: JSON.stringify({ message: "teste settings", thread_id: threadId || "demo-1", user_id: userId || "demo" }),
            });
            const chatText = await res2.text();
            setTestResult((prev) => (prev || "") + ` | POST /chat ${res2.status} ${chatText.slice(0, 300)}`);
        }
        catch (e) {
            setTestResult(e instanceof Error ? e.message : String(e));
        }
        finally {
            setTesting(false);
        }
    }
    async function fetchDevToken() {
        setTesting(true);
        setTestResult(null);
        try {
            const res = await fetch("/auth/dev-token", { method: "POST" });
            const j = await res.json().catch(() => ({}));
            if (!res.ok)
                throw new Error(j.detail || "dev-token falhou " + res.status);
            const devTok = String(j.token || "");
            if (!devTok)
                throw new Error("token vazio");
            setTokenState(devTok);
            setUserIdState(String(j.user_id || "demo"));
            setToken(devTok);
            setUserId(String(j.user_id || "demo"));
            setTestResult("Token dev obtido e salvo (" + j.env + "). Agora Chat -> 200.");
        }
        catch (e) {
            setTestResult(e instanceof Error ? e.message : String(e));
        }
        finally {
            setTesting(false);
        }
    }
    function clear() {
        try {
            localStorage.removeItem("jefrey_token");
            localStorage.removeItem("jefrey_user_id");
            localStorage.removeItem("jefrey_thread_id");
        }
        catch { }
        setTokenState("");
        setUserIdState("demo");
        setThreadIdLocal("demo-1");
        setTestResult("Limpo. Agora /chat voltara a 401 (fail-closed).");
    }
    const [vozWake, setVozWake] = useState(() => {
        try {
            return localStorage.getItem("jefrey_wake_enabled") === "1";
        }
        catch {
            return false;
        }
    });
    const [vozVoice, setVozVoice] = useState(() => {
        try {
            return localStorage.getItem("jefrey_voice_id") || "pt_BR-faber-medium";
        }
        catch {
            return "pt_BR-faber-medium";
        }
    });
    const wake = useWakeWord({ enabled: vozWake, keyword: "jefrey", onWake: () => {
            try {
                document.querySelector('[aria-label="Falar com Jefrey"]')?.click();
            }
            catch { }
        } });
    useEffect(() => {
        try {
            localStorage.setItem("jefrey_wake_enabled", vozWake ? "1" : "0");
        }
        catch { }
    }, [vozWake]);
    useEffect(() => {
        try {
            localStorage.setItem("jefrey_voice_id", vozVoice);
        }
        catch { }
    }, [vozVoice]);
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2", children: ["Settings ", _jsx(Badge, { variant: "secondary", children: "CIPHER-031" }), _jsx(Badge, { variant: "outline", children: "localStorage" })] }), _jsx("p", { className: "text-sm text-muted-foreground", children: "Unico lugar que persiste Bearer token (nunca em URL, Livro 3 cap8) + user_id/thread_id (Axiom #2). Token nunca logado (CIPHER-010)." })] }), _jsxs(CardContent, { className: "space-y-4", children: [_jsxs("div", { className: "space-y-2", children: [_jsx("label", { className: "text-sm font-medium", children: "Bearer token" }), _jsxs("div", { className: "flex gap-2", children: [_jsx("input", { className: "flex-1 rounded-md border px-3 py-2 text-sm font-mono", type: showToken ? "text" : "password", placeholder: "Bearer token (em dev: JEFREY_API__SECRET_KEY)", value: token, onChange: (e) => setTokenState(e.target.value), "aria-label": "bearer token", autoComplete: "off" }), _jsx(Button, { variant: "outline", onClick: () => setShowToken((v) => !v), children: showToken ? "Ocultar" : "Mostrar" })] }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Salvo em localStorage jefrey_token \u00E2\u20AC\u201D nunca enviado em query. Ja esta pronto apos abrir o app (Onboarding auto) \u00E2\u20AC\u201D este e so avancado." })] }), _jsxs("div", { className: "grid gap-4 md:grid-cols-2", children: [_jsxs("div", { className: "space-y-2", children: [_jsx("label", { className: "text-sm font-medium", children: "user_id (Axiom #2 isolamento)" }), _jsx("input", { className: "w-full rounded-md border px-3 py-2 text-sm font-mono", placeholder: "demo", value: userId, onChange: (e) => setUserIdState(e.target.value), "aria-label": "user_id" }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Todo POST leva este user_id \u00E2\u20AC\u201D sem default system." })] }), _jsxs("div", { className: "space-y-2", children: [_jsx("label", { className: "text-sm font-medium", children: "thread_id" }), _jsx("input", { className: "w-full rounded-md border px-3 py-2 text-sm font-mono", placeholder: "demo-1", value: threadId, onChange: (e) => setThreadIdLocal(e.target.value), "aria-label": "thread_id" }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Persistido como jefrey_thread_id." })] })] }), _jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsx(Button, { onClick: save, children: "Salvar" }), _jsx(Button, { variant: "outline", onClick: fetchDevToken, disabled: testing, children: testing ? "Obtendo..." : "Obter token dev" }), _jsx(Button, { variant: "outline", onClick: testAuth, disabled: testing, children: testing ? "Testando..." : "Testar /health + /chat" }), _jsx(Button, { variant: "destructive", onClick: clear, children: "Limpar" }), _jsx(Badge, { variant: "secondary", children: "ENV dev" }), _jsx("a", { href: "/docs", target: "_blank", rel: "noreferrer", className: "text-sm underline", children: "Abrir /docs" })] }), testResult && _jsx("div", { className: "rounded-md border bg-muted p-3 text-sm whitespace-pre-wrap break-words", children: testResult }), _jsxs("div", { className: "rounded-md border p-3 text-xs bg-muted/30", children: [_jsx("div", { className: "font-medium mb-1", children: "Como usar como 1 programa (Guia leigo):" }), _jsxs("ol", { className: "list-decimal ml-4 space-y-1", children: [_jsx("li", { children: "Clique Obter token dev (em dev) ou cole seu Bearer acima e clique Salvar." }), _jsx("li", { children: "Va em Chat e envie mensagem \u00E2\u20AC\u201D agora POST /chat 200 (antes 401)." }), _jsx("li", { children: "Va em Memoria e busque \u00E2\u20AC\u201D POST /memory/search com mesmo user_id." }), _jsx("li", { children: "Approvals/Observability leem /approvals e /metrics vivos (15s)." })] })] })] })] }), _jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2", children: ["Voz \u00E2\u20AC\u201D STT/TTS + Wake \"jarvis\" ", _jsx(Badge, { variant: "secondary", children: "P1" })] }), _jsx("p", { className: "text-sm text-muted-foreground", children: "Microfone MediaRecorder 16k - POST /stt (whisper small) - /chat qwen2:0.5b - POST /tts. Wake usa Web Speech jarvis (porcupine quando key configurada)." })] }), _jsxs(CardContent, { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsxs("label", { className: "flex items-center gap-2 text-sm", children: [_jsx("input", { type: "checkbox", checked: vozWake, onChange: (e) => setVozWake(e.target.checked) }), "Wake \"jarvis\" ", wake.listening ? "(ouvindo...)" : "(off)", " ", !wake.supported && _jsx("span", { className: "text-xs text-muted-foreground", children: " \u00E2\u20AC\u201D navegador sem SpeechRecognition" })] }), _jsx(Badge, { variant: wake.listening ? "default" : "outline", children: wake.listening ? "wake ativo" : "wake off" })] }), _jsxs("div", { className: "flex flex-col gap-2", children: [_jsx("label", { className: "text-sm font-medium", children: "Voz TTS (Mark-LII 5 vozes + Piper)" }), _jsxs("select", { value: vozVoice, onChange: (e) => setVozVoice(e.target.value), className: "rounded-md border px-3 py-2 text-sm", children: [_jsx("option", { value: "pt_BR-faber-medium", children: "Faber PT-BR (piper local, sem custo)" }), _jsx("option", { value: "Charon", children: "Charon \u00E2\u20AC\u201D masc grave (ElevenLabs)" }), _jsx("option", { value: "Puck", children: "Puck \u00E2\u20AC\u201D masc jovem (ElevenLabs)" }), _jsx("option", { value: "Kore", children: "Kore \u00E2\u20AC\u201D fem suave (ElevenLabs)" }), _jsx("option", { value: "Fenrir", children: "Fenrir \u00E2\u20AC\u201D masc forte (ElevenLabs)" }), _jsx("option", { value: "Aoede", children: "Aoede \u00E2\u20AC\u201D fem clara (ElevenLabs)" })] }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Requer JEFREY_TTS__API_KEY para ElevenLabs; sem key usa piper/pyttsx3 fallback (Building LLM Apps)." })] }), _jsxs("div", { className: "rounded-md border p-3 text-xs bg-muted/20", children: [_jsxs("div", { children: ["STT: ", _jsx("span", { className: "font-mono", children: "small pt int8" }), " \u00E2\u20AC\u201D mock dev via JEFREY_STT__MOCK=1"] }), _jsxs("div", { children: ["LLM: ", _jsx("span", { className: "font-mono", children: "qwen2:0.5b 352MB" }), " (workaround OOM 8b 3.3GB)"] }), _jsx("div", { children: "HUD pulse: Analyser reativa (CEOGPT) no botao mic" })] })] })] })] }));
}
