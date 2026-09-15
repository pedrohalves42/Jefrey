// Jefrey API helper — Axiom #1 FAIL-CLOSED + #2 ISOLAMENTO + CIPHER-031/033 + Livro 3 cap8 + Livro 6 cap8
// DRY: unico ponto de fetch com Bearer + user_id obrigatorio. Nunca envia token em query (Security Eng).
export function getToken() {
    try {
        return localStorage.getItem("jefrey_token");
    }
    catch {
        return null;
    }
}
export function getUserId() {
    try {
        return localStorage.getItem("jefrey_user_id") || "demo";
    }
    catch {
        return "demo";
    }
}
export function getThreadId() {
    try {
        return localStorage.getItem("jefrey_thread_id") || "demo-1";
    }
    catch {
        return "demo-1";
    }
}
export function setThreadId(id) {
    try {
        localStorage.setItem("jefrey_thread_id", id);
    }
    catch { }
}
export function setToken(t) {
    try {
        localStorage.setItem("jefrey_token", t);
    }
    catch { }
}
export function setUserId(u) {
    try {
        localStorage.setItem("jefrey_user_id", u);
    }
    catch { }
}
export function authHeaders() {
    const t = getToken();
    if (!t)
        return {};
    return { Authorization: `Bearer ${t}`, "X-User-Id": getUserId() };
}
export function mapHttpError(status) {
    if (status === 401)
        return "Nao autenticado — va em Settings e informe seu Bearer token (Axiom #1 fail-closed).";
    if (status === 403)
        return "Acesso negado — seu papel (guest/user) nao permite esta acao (CIPHER-032 RBAC).";
    if (status === 429)
        return "Muitas requisicoes — aguarde Retry-After (CIPHER-026 rate-limit).";
    if (status >= 500)
        return "Erro interno do servidor — tente novamente.";
    if (status === 404)
        return "Recurso nao encontrado.";
    return `Erro HTTP ${status}`;
}
export async function apiFetch(path, init = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init.headers || {}),
    };
    // nunca loga token (CIPHER-010 redact_pii)
    return fetch(path, { ...init, headers });
}
// F3 LLM probe helper (Axiom #1 visible, never crash)
export async function probeHealth() { try {
    const r = await fetch('/health');
    return { ok: r.ok };
}
catch {
    return { ok: false };
} }
// F6-1 Onboarding zero-clique — auto POST /auth/dev-token em dev (fail-closed 403 em prod)
// Nunca mostra token em URL (Security Eng). Silencioso, idempotente.
export function isOnboarded() {
    try {
        return localStorage.getItem("jefrey_onboarded") === "1";
    }
    catch {
        return false;
    }
}
export function setOnboarded(v) {
    try {
        if (v)
            localStorage.setItem("jefrey_onboarded", "1");
        else
            localStorage.removeItem("jefrey_onboarded");
    }
    catch { }
}
export async function ensureDevToken() {
    const existing = getToken();
    if (existing)
        return existing;
    try {
        const r = await fetch("/auth/dev-token", { method: "POST", headers: { "X-User-Id": getUserId(), "Content-Type": "application/json" }, body: JSON.stringify({}) });
        if (!r.ok)
            return null;
        const j = await r.json().catch(() => ({}));
        const tok = String(j.token || "");
        const uid = String(j.user_id || getUserId());
        if (!tok)
            return null;
        setToken(tok);
        if (uid)
            setUserId(uid);
        return tok;
    }
    catch {
        return null;
    }
}
