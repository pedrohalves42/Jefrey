export type ChatEvent =
  | { type: "token"; content: string }
  | { type: "done"; thread_id?: string }
  | { type: "error"; message: string }
  | { type: "pending_approval"; approval_id?: string; thread_id?: string }
  | { type: "tool_start"; tool: string; label: string; risk: string }
  | { type: "tool_end"; tool: string; ok: boolean; status: string; summary: string }
  | { type: "approval_required"; approval_id: string; tool: string; label: string; risk?: string }

/**
 * Parser incremental de Server-Sent Events. Aceita pedacos arbitrarios (um evento pode chegar
 * partido em varios chunks) e ignora linhas invalidas sem derrubar o stream.
 */
export class SseParser {
  private buf = ""

  push(chunk: string): ChatEvent[] {
    this.buf += chunk.replace(/\r\n/g, "\n")
    const events: ChatEvent[] = []
    let idx: number
    while ((idx = this.buf.indexOf("\n\n")) !== -1) {
      const block = this.buf.slice(0, idx)
      this.buf = this.buf.slice(idx + 2)
      const ev = parseBlock(block)
      if (ev) events.push(ev)
    }
    return events
  }

  /** Processa o que sobrou quando o stream fecha sem a linha em branco final. */
  flush(): ChatEvent[] {
    const rest = this.buf.trim()
    this.buf = ""
    if (!rest) return []
    const ev = parseBlock(rest)
    return ev ? [ev] : []
  }
}

function parseBlock(block: string): ChatEvent | null {
  const data = block
    .split("\n")
    .filter(l => l.startsWith("data:"))
    .map(l => l.slice(5).replace(/^ /, ""))
    .join("\n")
  if (!data) return null
  try {
    const j = JSON.parse(data)
    if (!j || typeof j !== "object") return null
    switch (j.type) {
      case "token":
        return typeof j.content === "string" ? { type: "token", content: j.content } : null
      case "done":
        return { type: "done", thread_id: typeof j.thread_id === "string" ? j.thread_id : undefined }
      case "error":
        return { type: "error", message: typeof j.message === "string" ? j.message : "Erro desconhecido" }
      case "pending_approval":
        return { type: "pending_approval", approval_id: j.approval_id, thread_id: j.thread_id }
      case "tool_start":
        return typeof j.tool === "string"
          ? { type: "tool_start", tool: j.tool, label: typeof j.label === "string" ? j.label : j.tool, risk: String(j.risk ?? "unknown") }
          : null
      case "tool_end":
        return typeof j.tool === "string"
          ? { type: "tool_end", tool: j.tool, ok: j.ok === true, status: String(j.status ?? ""), summary: String(j.summary ?? "") }
          : null
      case "approval_required":
        return typeof j.approval_id === "string" && typeof j.tool === "string"
          ? { type: "approval_required", approval_id: j.approval_id, tool: j.tool, label: typeof j.label === "string" ? j.label : j.tool, risk: j.risk }
          : null
      default:
        return null
    }
  } catch {
    return null
  }
}
