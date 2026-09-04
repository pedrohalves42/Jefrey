// Jefrey API helper — Axiom #1 FAIL-CLOSED + #2 ISOLAMENTO + CIPHER-031/033 + Livro 3 cap8 + Livro 6 cap8
// DRY: unico ponto de fetch com Bearer + user_id obrigatorio. Nunca envia token em query (Security Eng).
export function getToken(): string | null {
  try { return localStorage.getItem("jefrey_token"); } catch { return null; }
}
export function getUserId(): string {
  try { return localStorage.getItem("jefrey_user_id") || "demo"; } catch { return "demo"; }
}
export function getThreadId(): string {
  try { return localStorage.getItem("jefrey_thread_id") || "demo-1"; } catch { return "demo-1"; }
}
export function setThreadId(id: string): void {
  try { localStorage.setItem("jefrey_thread_id", id); } catch {}
}
export function setToken(t: string): void {
  try { localStorage.setItem("jefrey_token", t); } catch {}
}
export function setUserId(u: string): void {
  try { localStorage.setItem("jefrey_user_id", u); } catch {}
}
export function authHeaders(): Record<string, string> {
  const t = getToken();
  if (!t) return {};
  return { Authorization: `Bearer ${t}`, "X-User-Id": getUserId() };
}
export function mapHttpError(status: number): string {
  if (status === 401) return "Nao autenticado — va em Settings e informe seu Bearer token (Axiom #1 fail-closed).";
  if (status === 403) return "Acesso negado — seu papel (guest/user) nao permite esta acao (CIPHER-032 RBAC).";
  if (status === 429) return "Muitas requisicoes — aguarde Retry-After (CIPHER-026 rate-limit).";
  if (status >= 500) return "Erro interno do servidor — tente novamente.";
  if (status === 404) return "Recurso nao encontrado.";
  return `Erro HTTP ${status}`;
}
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...((init.headers as Record<string, string>) || {}),
  };
  // nunca loga token (CIPHER-010 redact_pii)
  return fetch(path, { ...init, headers });
}
export type ChatMessage = { role: "user" | "assistant"; content: string };
export type MemoryHit = { content: string; score?: number; metadata?: Record<string, unknown>; type?: string; created_at?: string };
