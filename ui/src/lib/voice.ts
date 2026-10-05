import { authedFetch } from "@/lib/session"

export type EngineId = "cloud" | "local" | "browser"
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
  if (choice === "cloud" || choice === "local") return ok(choice) ? choice : e.default
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
