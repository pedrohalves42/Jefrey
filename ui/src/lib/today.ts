import { authedFetch } from "@/lib/session"

export type Status = "ok" | "parcial" | "erro" | "vazio" | "desconectado" | "falta_regiao"
export type NewsItem = { title: string; link: string }
export type Quote = { value: number; pct: number }
export type TodayData = {
  generated_at: string
  region: { city: string; uf: string }
  sections: {
    news: { status: Status; items: NewsItem[] }
    economy: { status: Status; items: NewsItem[] }
    region: { status: Status; items: NewsItem[] }
    market: { status: Status; usd?: Quote; eur?: Quote; btc?: Quote; ibov?: Quote }
    weather: { status: Status; summary?: string; place?: string }
    agenda: { status: Status; items: { title: string; time: string }[] }
    reminders: { status: Status; items: { text: string; due_label: string }[] }
  }
}

export const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

/** Garante todos os cartoes mesmo se o servidor mandar algo incompleto (a tela nunca quebra). */
export function normalizeToday(raw: unknown): TodayData | null {
  if (!raw || typeof raw !== "object" || !("sections" in raw)) return null
  const r = raw as Partial<TodayData>
  const s = (r.sections ?? {}) as Partial<TodayData["sections"]>
  const list = <T extends { status: Status; items: unknown[] }>(x: T | undefined): T => ({ status: x?.status ?? "erro", items: Array.isArray(x?.items) ? x!.items : [] }) as T
  return {
    generated_at: typeof r.generated_at === "string" ? r.generated_at : "",
    region: { city: r.region?.city ?? "", uf: r.region?.uf ?? "" },
    sections: {
      news: list(s.news), economy: list(s.economy), region: list(s.region), agenda: list(s.agenda), reminders: list(s.reminders),
      market: { status: s.market?.status ?? "erro", ...(s.market ?? {}) },
      weather: { status: s.weather?.status ?? "erro", ...(s.weather ?? {}) },
    },
  }
}

export async function getToday(): Promise<Res<TodayData>> {
  const r = await json<unknown>("/today")
  return { ok: r.ok, status: r.status, data: r.ok ? normalizeToday(r.data) : null }
}
export const saveRegion = (city: string, uf: string) => json<{ city: string; uf: string }>("/today/region", { method: "PUT", body: JSON.stringify({ city, uf }) })

/** "R$ 4,99" / "131.500 pts" e variacao com seta e sinal, em portugues. */
export function money(v: number): string {
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
export function points(v: number): string {
  return `${Math.round(v).toLocaleString("pt-BR")} pts`
}
export function change(pct: number): { text: string; tone: "up" | "down" | "flat" } {
  const r = Math.round(pct * 100) / 100
  if (r === 0) return { text: "estável", tone: "flat" }
  const n = Math.abs(r).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return r > 0 ? { text: `▲ +${n}%`, tone: "up" } : { text: `▼ -${n}%`, tone: "down" }
}

/** Frase falada do painel (para o botão "Ouvir"): so o essencial, sem numeros demais. */
export function spokenSummary(d: TodayData, name?: string): string {
  const s = d.sections
  const parts: string[] = [name ? `Bom dia, ${name}!` : "Bom dia!"]
  if (s.weather.status === "ok" && s.weather.summary) parts.push(s.weather.summary)
  if (s.agenda.status === "ok" && s.agenda.items.length) parts.push(`Você tem ${s.agenda.items.length} compromisso${s.agenda.items.length > 1 ? "s" : ""} hoje: ${s.agenda.items.slice(0, 3).map(i => `${i.title}${i.time ? ` às ${i.time}` : ""}`).join(", ")}.`)
  if (s.reminders.status === "ok" && s.reminders.items.length) parts.push(`Lembretes: ${s.reminders.items.slice(0, 3).map(i => i.text).join(", ")}.`)
  if (s.market.usd) parts.push(`O dólar está em ${money(s.market.usd.value).replace("R$ ", "")} reais.`)
  if (s.news.status === "ok" && s.news.items.length) parts.push(`Principais notícias: ${s.news.items.slice(0, 3).map(i => i.title).join(". ")}.`)
  return parts.join(" ")
}
