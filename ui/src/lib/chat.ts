import { authedFetch } from "@/lib/session"
import { RECALL_KINDS, SseParser, type RecallItem } from "@/lib/sse"

export type Role = "user" | "assistant"
export type ToolStep = { tool: string; label: string; risk: string; state: "running" | "waiting" | "ok" | "failed"; summary?: string }
export type Message = { id: string; role: Role; content: string; error?: boolean; at: number; tools?: ToolStep[]; recall?: RecallItem[] }
export type Thread = { id: string; title: string; updated: number; messages: Message[] }

const KEY = "jefrey_threads_v1"
const ACTIVE = "jefrey_active_thread_v1"
const MAX_THREADS = 50
const MAX_MESSAGES = 200

const THREAD_RE = /^[a-zA-Z0-9_-]{1,128}$/

export function uid(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

export function newThread(): Thread {
  return { id: "t" + uid(), title: "Nova conversa", updated: Date.now(), messages: [] }
}

function sanitizeThreads(raw: unknown): Thread[] {
  if (!Array.isArray(raw)) return []
  const out: Thread[] = []
  for (const t of raw) {
    if (!t || typeof t !== "object") continue
    const id = String((t as Thread).id || "")
    if (!THREAD_RE.test(id)) continue
    const msgs = Array.isArray((t as Thread).messages) ? (t as Thread).messages : []
    out.push({
      id,
      title: String((t as Thread).title || "Nova conversa").slice(0, 80),
      updated: Number((t as Thread).updated) || 0,
      messages: msgs
        .filter(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
        .slice(-MAX_MESSAGES)
        .map(m => ({
          id: String(m.id || uid()), role: m.role, content: m.content, error: !!m.error, at: Number(m.at) || 0,
          tools: Array.isArray(m.tools)
            ? m.tools.slice(0, 20).map(t => ({
                tool: String(t.tool), label: String(t.label || t.tool), risk: String(t.risk || "unknown"),
                state: t.state === "ok" || t.state === "failed" ? t.state : "failed", summary: t.summary ? String(t.summary).slice(0, 300) : undefined,
              }))
            : undefined,
          recall: Array.isArray(m.recall)
            ? m.recall
                .filter(r => r && RECALL_KINDS.includes(r.kind) && typeof r.text === "string")
                .slice(0, 6)
                .map(r => ({ kind: r.kind, text: String(r.text).slice(0, 160) }))
            : undefined,
        })),
    })
  }
  return out.sort((a, b) => b.updated - a.updated).slice(0, MAX_THREADS)
}

export function loadThreads(): Thread[] {
  try {
    return sanitizeThreads(JSON.parse(localStorage.getItem(KEY) || "[]"))
  } catch {
    return []
  }
}

export function saveThreads(threads: Thread[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(threads.slice(0, MAX_THREADS)))
  } catch {
    /* sem espaco/privado: a conversa segue so em memoria */
  }
}

export function loadActiveId(): string | null {
  try {
    return localStorage.getItem(ACTIVE)
  } catch {
    return null
  }
}

export function saveActiveId(id: string): void {
  try {
    localStorage.setItem(ACTIVE, id)
  } catch {
    /* ignora */
  }
}

export function titleFrom(text: string): string {
  const t = text.replace(/\s+/g, " ").trim()
  return t.length > 42 ? t.slice(0, 41) + "…" : t || "Nova conversa"
}

/** Mensagem humana para cada falha de HTTP do chat. */
export function chatErrorMessage(status: number, detail?: string): string {
  if (status === 400) return detail?.toLowerCase().includes("bloque")
    ? "Essa mensagem foi bloqueada pelas regras de segurança (parece uma tentativa de burlar o assistente)."
    : "Não consegui entender essa mensagem."
  if (status === 401) return "Sua sessão expirou e não consegui renová-la. Recarregue a página."
  if (status === 422) return "Mensagem inválida (vazia ou grande demais)."
  if (status === 429) return "Muitas mensagens em pouco tempo. Aguarde alguns segundos."
  if (status >= 500) return "O servidor teve um problema. Tente de novo em instantes."
  return `Erro inesperado (HTTP ${status}).`
}

export type StreamHandlers = {
  onToken: (text: string) => void
  onPendingApproval?: (approvalId?: string) => void
  onToolStart?: (tool: string, label: string, risk: string) => void
  onToolEnd?: (tool: string, ok: boolean, summary: string) => void
  onApprovalRequired?: (approvalId: string, tool: string, label: string, detail?: string) => void
  onRecall?: (items: RecallItem[]) => void
}

export type StreamResult = { ok: boolean; error?: string; firstTokenMs?: number }

/** Envia ao /chat/stream e entrega os trechos conforme chegam. */
export async function streamChat(
  message: string,
  threadId: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<StreamResult> {
  const t0 = performance.now()
  let first: number | undefined
  let res: Response
  try {
    res = await authedFetch("/chat/stream", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId }),
      signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return { ok: false, error: "Interrompido." }
    return { ok: false, error: "Sem conexão com o Jefrey. Verifique se ele está rodando." }
  }
  if (!res.ok) {
    let detail = ""
    try {
      detail = String((await res.json()).detail || "")
    } catch {
      /* corpo nao-JSON */
    }
    return { ok: false, error: chatErrorMessage(res.status, detail) }
  }
  if (!res.body) return { ok: false, error: "O servidor não enviou resposta." }

  const reader = res.body.getReader()
  const dec = new TextDecoder()
  const parser = new SseParser()
  let failure: string | undefined
  const handle = (evs: ReturnType<SseParser["push"]>) => {
    for (const ev of evs) {
      if (ev.type === "token") {
        if (first === undefined) first = performance.now() - t0
        handlers.onToken(ev.content)
      } else if (ev.type === "error") failure = ev.message
      else if (ev.type === "pending_approval") handlers.onPendingApproval?.(ev.approval_id)
      else if (ev.type === "tool_start") handlers.onToolStart?.(ev.tool, ev.label, ev.risk)
      else if (ev.type === "tool_end") handlers.onToolEnd?.(ev.tool, ev.ok, ev.summary)
      else if (ev.type === "approval_required") handlers.onApprovalRequired?.(ev.approval_id, ev.tool, ev.label, ev.detail)
      else if (ev.type === "recall") handlers.onRecall?.(ev.items)
    }
  }
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      handle(parser.push(dec.decode(value, { stream: true })))
    }
    handle(parser.flush())
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return { ok: false, error: "Interrompido.", firstTokenMs: first }
    return { ok: false, error: "A conexão caiu no meio da resposta.", firstTokenMs: first }
  }
  return failure ? { ok: false, error: failure, firstTokenMs: first } : { ok: true, firstTokenMs: first }
}
