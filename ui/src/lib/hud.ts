import { authedFetch } from "@/lib/session"
import type { Activity } from "@/lib/briefing"
import type { Message } from "@/lib/chat"

export type Telemetry = { ram_pct: number; ram_total_gb: number; cpu_pct: number | null; uptime_s: number; brain: string | null; reserves: number }

export async function getTelemetry(): Promise<Telemetry | null> {
  try {
    const r = await authedFetch("/system/telemetry")
    return r.ok ? ((await r.json()) as Telemetry) : null
  } catch {
    return null
  }
}

export type Gauge = { label: string; value: number | null; text: string; warn: boolean }

/** Medidores do painel esquerdo. Sem medida = "—", nunca um numero inventado. */
export function gauges(t: Telemetry | null): Gauge[] {
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? null : Math.max(0, Math.min(100, v)))
  return [
    { label: "Memória", value: pct(t?.ram_pct), text: t ? `${Math.round(t.ram_pct)}% de ${t.ram_total_gb} GB` : "—", warn: (t?.ram_pct ?? 0) > 90 },
    { label: "Processador", value: pct(t?.cpu_pct), text: t?.cpu_pct == null ? "—" : `${Math.round(t.cpu_pct)}%`, warn: (t?.cpu_pct ?? 0) > 90 },
  ]
}

export function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

export function brainLine(t: Telemetry | null): string {
  if (!t || !t.brain) return "Nenhum conectado"
  return t.reserves > 0 ? `${t.brain} + ${t.reserves} reserva${t.reserves > 1 ? "s" : ""}` : t.brain
}

export type LogItem = { at: number; text: string; tone: "ok" | "info" | "warn" | "bad" }

const hhmm = (ms: number) => new Date(ms).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
export const logTime = hhmm

/** Registro de atividade (mais novo primeiro): o que o Jefrey fez, lembrou e esta fazendo sozinho. */
export function buildLog(messages: Message[], activity: Activity | null, now = Date.now(), limit = 8): LogItem[] {
  const out: LogItem[] = []
  for (const m of messages.slice(-12)) {
    if (m.role !== "assistant") continue
    for (const t of m.tools ?? []) {
      out.push({ at: m.at, text: `${t.state === "ok" ? "Fiz" : t.state === "failed" ? "Falhou" : t.state === "waiting" ? "Aguardando você" : "Fazendo"}: ${t.label}`, tone: t.state === "ok" ? "ok" : t.state === "failed" ? "bad" : "warn" })
    }
    for (const r of m.recall ?? []) out.push({ at: m.at, text: `Lembrei: ${r.text}`, tone: "info" })
    if (m.error) out.push({ at: m.at, text: "Algo deu errado numa resposta", tone: "bad" })
  }
  out.sort((a, b) => b.at - a.at)
  const live: LogItem[] = []
  if (activity?.studying) live.push({ at: now, text: activity.topic ? `Estudando ${activity.topic}` : "Estudando em segundo plano", tone: "info" })
  if (activity?.learning) live.push({ at: now, text: "Aprendendo com a conversa", tone: "info" })
  return [...live, ...out].slice(0, limit)
}

/** Alturas (0 a 1) das barras de voz: nivel real do microfone, ou onda suave quando o Jefrey fala. */
export function waveBars(n: number, level: number, speaking: boolean, t: number): number[] {
  return Array.from({ length: n }, (_, i) => {
    const base = speaking ? 0.35 + 0.35 * Math.abs(Math.sin(t / 220 + i * 0.7)) * Math.abs(Math.sin(t / 530 + i * 0.31)) : Math.max(0.04, level) * (0.5 + 0.5 * Math.abs(Math.sin(t / 160 + i * 0.9)))
    return Math.max(0.04, Math.min(1, base))
  })
}
