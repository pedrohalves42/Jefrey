import { authedFetch } from "@/lib/session"

export type EngineId = string // "edge", "edge-francisca", "edge-antonio", "cloud", "local" ou "browser" (o servidor diz quais existem)
export type Engines = {
  engines: { id: EngineId; available: boolean; label: string }[]
  default: EngineId
  local: { installed: boolean; size_mb: number }
}
export type LocalStatus = { installed: boolean; size_mb: number; state: "idle" | "running" | "done" | "error"; pct: number; error: string }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getEngines = () => json<Engines>("/voice/engines")
export const getLocalStatus = () => json<LocalStatus>("/voice/local")
export const startModelDownload = () => json<LocalStatus>("/voice/local/download", { method: "POST" })

/** Qual motor falar agora: a escolha da pessoa ("cloud"/"local"), senao o padrao do servidor. "browser" = voz do computador. */
export function pickEngine(choice: string | null, e: Engines | null): EngineId {
  if (!e) return "browser"
  const ok = (id: EngineId) => e.engines.some(x => x.id === id && x.available)
  if (choice && choice !== "browser" && e.engines.some(x => x.id === choice && x.id !== "browser")) return ok(choice) ? choice : e.default
  if (choice) return "browser" // escolheu uma voz especifica do computador
  return e.default
}

/** Frase simples para a barra de download da voz natural. */
export function downloadMessage(s: LocalStatus | null): string {
  if (!s) return ""
  if (s.installed || s.state === "done") return "Voz natural pronta."
  if (s.state === "running") return `Baixando a voz natural… ${s.pct}%`
  if (s.state === "error") return s.error || "Não consegui baixar agora. Tente de novo."
  return `Baixar a voz natural (${s.size_mb} MB, uma vez só).`
}

/**
 * Divide o texto em pedacos para falar: a PRIMEIRA frase sai sozinha (o Jefrey comeca a falar mais cedo) e as demais se juntam
 * ate `max` letras (menos pausas entre pedacos). Frases enormes sao cortadas em virgulas e espacos.
 */
export function splitSentences(text: string, max = 220): string[] {
  const clean = (text || "").replace(/\s+/g, " ").trim()
  if (!clean) return []
  const sentences = clean.match(/[^.!?…]+(?:\.{3}|[.!?…]+)(?:\s|$)|[^.!?…]+$/g)?.map(s => s.trim()).filter(Boolean) ?? [clean]
  // "Sr. Silva": ponto de abreviacao nao encerra frase
  const merged: string[] = []
  for (const s of sentences) {
    const prev = merged[merged.length - 1]
    if (prev && /\b(?:Sr|Sra|Dr|Dra|Prof|Profa|etc|ex|av|nº|n°)\.$/i.test(prev)) merged[merged.length - 1] = `${prev} ${s}`
    else merged.push(s)
  }
  const cut = (s: string): string[] => {
    const out: string[] = []
    let rest = s
    while (rest.length > max) {
      let i = Math.max(rest.lastIndexOf(", ", max), rest.lastIndexOf("; ", max))
      if (i < max * 0.4) i = rest.lastIndexOf(" ", max)
      const end = i < 1 ? max : i + 1
      out.push(rest.slice(0, end).trim())
      rest = rest.slice(end).trim()
    }
    if (rest) out.push(rest)
    return out
  }
  const out: string[] = []
  let cur = ""
  merged.forEach((s, idx) => {
    const parts = s.length > max ? cut(s) : [s]
    for (const p of parts) {
      if (idx === 0 && out.length === 0 && !cur) {
        out.push(p) // primeira frase sozinha
      } else if (cur && cur.length + 1 + p.length <= max) cur += " " + p
      else {
        if (cur) out.push(cur)
        cur = p
      }
    }
  })
  if (cur) out.push(cur)
  return out
}
