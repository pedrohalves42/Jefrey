import { authedFetch } from "@/lib/session"

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export type LegalDocs = { version: string; termos: string; privacidade: string }
export type Summary = { nome: boolean; fatos: number; diario: number; assuntos: number; lembretes: number; memorias: number; mensagens: number; whatsapp: number; google: boolean }

export const getLegalStatus = () => json<{ accepted: boolean; version: string }>("/legal/status")
export const getLegalDocs = () => json<LegalDocs>("/legal/documents")
export const acceptLegal = () => json<{ accepted: boolean }>("/legal/accept", { method: "POST" })
export const getSummary = () => json<Summary>("/privacy/summary")
export const eraseAll = (confirm: string) => json<{ ok: boolean }>("/privacy/erase", { method: "POST", body: JSON.stringify({ confirm }) })

/** Baixa a copia dos dados como arquivo (o navegador abre "Salvar como"). */
export async function downloadMyData(): Promise<boolean> {
  try {
    const r = await authedFetch("/privacy/export")
    if (!r.ok) return false
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement("a")
    a.href = url
    a.download = "meus-dados-jefrey.json"
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}

export type DocBlock =
  | { type: "h1" | "h2" | "p" | "li"; text: string }
  | { type: "table"; header: string[]; rows: string[][] }

/** Markdown simples dos textos legais ("# ", "## ", "- ", tabelas e paragrafos) em blocos. Nunca usa HTML. */
export function parseDoc(md: string): DocBlock[] {
  const out: DocBlock[] = []
  const lines = md.split("\n")
  for (let i = 0; i < lines.length; i++) {
    const line = (lines[i] ?? "").trim()
    if (!line) continue
    if (line.startsWith("|")) {
      const rows: string[][] = []
      while (i < lines.length && (lines[i] ?? "").trim().startsWith("|")) {
        const cells = (lines[i] ?? "").trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim())
        if (!cells.every(c => /^-+$/.test(c))) rows.push(cells)
        i++
      }
      i--
      if (rows.length) out.push({ type: "table", header: rows[0]!, rows: rows.slice(1) })
    } else if (line.startsWith("## ")) out.push({ type: "h2", text: line.slice(3) })
    else if (line.startsWith("# ")) out.push({ type: "h1", text: line.slice(2) })
    else if (line.startsWith("- ")) out.push({ type: "li", text: line.slice(2) })
    else out.push({ type: "p", text: line })
  }
  return out
}

/** Tira ** e _ do texto (so para leitura em voz alta). */
export function plain(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/[_`]/g, "")
}

export function summaryLines(s: Summary): string[] {
  const n = (v: number, one: string, many: string) => (v === 1 ? `1 ${one}` : `${v} ${many}`)
  return [
    s.nome ? "O seu nome" : "",
    n(s.fatos, "coisa que aprendi sobre você", "coisas que aprendi sobre você"),
    n(s.mensagens, "mensagem de conversa", "mensagens de conversa"),
    n(s.memorias, "nota ou memória", "notas e memórias"),
    n(s.lembretes, "lembrete", "lembretes"),
    n(s.assuntos, "assunto estudado", "assuntos estudados"),
    n(s.diario, "dia no diário", "dias no diário"),
    s.whatsapp ? n(s.whatsapp, "resposta de WhatsApp", "respostas de WhatsApp") : "",
    s.google ? "Conexão com o Google" : "",
  ].filter(Boolean)
}
