import { useQuery } from "@tanstack/react-query"

export type ServiceState = "ok" | "down"
export type Status = {
  reachable: boolean
  services: { id: string; label: string; state: ServiceState }[]
  summary: "ok" | "degraded" | "offline"
  model?: { name: string; provider: string; ok: boolean }
}

const LABELS: Record<string, string> = {
  api: "Jefrey",
  ollama: "Cérebro neste computador",
  postgres: "Memória",
  redis: "Cache",
  mcp: "Ferramentas",
  stt: "Ouvir você",
  tts: "Falar",
}

/** Servicos sem os quais o chat nao funciona de verdade. O resto so degrada recursos. */
const ESSENTIAL = new Set(["api"]) // o cerebro local so conta se for o usado (o servidor marca "off" quando e a nuvem)

export function summarize(services: Status["services"], reachable: boolean): Status["summary"] {
  if (!reachable) return "offline"
  if (services.some(s => ESSENTIAL.has(s.id) && s.state !== "ok")) return "offline"
  return services.every(s => s.state === "ok") ? "ok" : "degraded"
}

export function parseStatus(json: unknown): Status["services"] {
  const out: Status["services"] = []
  if (!json || typeof json !== "object") return out
  for (const [id, v] of Object.entries(json as Record<string, unknown>)) {
    if (id === "timestamp" || !v || typeof v !== "object") continue
    const st = (v as { status?: unknown }).status
    if (st === "off") continue // componente que nao faz parte deste modo (ex.: Redis sem Docker)
    out.push({ id, label: LABELS[id] ?? id, state: st === "ok" ? "ok" : "down" })
  }
  return out
}

async function fetchStatus(): Promise<Status> {
  try {
    const r = await fetch("/api/status", { cache: "no-store" })
    if (!r.ok) return { reachable: false, services: [], summary: "offline" }
    const services = parseStatus(await r.json())
    return { reachable: true, services, summary: summarize(services, true) }
  } catch {
    return { reachable: false, services: [], summary: "offline" }
  }
}

export function useStatus() {
  return useQuery({ queryKey: ["status"], queryFn: fetchStatus, refetchInterval: 10_000, staleTime: 5_000 })
}
