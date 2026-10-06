import { authedFetch } from "@/lib/session"

export type Status = "ok" | "parcial" | "erro" | "vazio" | "desconectado" | "falta_regiao" | "sem_interesses"
export type NewsItem = { title: string; link: string; topic?: string }
export type Quote = { value: number; pct: number }
export type TodayData = {
  generated_at: string
  region: { city: string; uf: string }
  sections: {
    news: { status: Status; items: NewsItem[] }
    economy: { status: Status; items: NewsItem[] }
    region: { status: Status; items: NewsItem[] }
    foryou: { status: Status; items: NewsItem[] }
    market: { status: Status; usd?: Quote; eur?: Quote; btc?: Quote; ibov?: Quote }
    weather: { status: Status; summary?: string; place?: string; temp?: number }
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
      news: list(s.news), economy: list(s.economy), region: list(s.region), foryou: s.foryou ? list(s.foryou) : { status: "sem_interesses" as Status, items: [] }, agenda: list(s.agenda), reminders: list(s.reminders),
      market: { status: s.market?.status ?? "erro", ...(s.market ?? {}) },
      weather: { status: s.weather?.status ?? "erro", ...(s.weather ?? {}) },
    },
  }
}

export async function getToday(): Promise<Res<TodayData>> {
  const r = await json<unknown>("/today")
  return { ok: r.ok, status: r.status, data: r.ok ? normalizeToday(r.data) : null }
}
export type InterestOption = { id: string; label: string }
export type Interests = { selected: string[]; options: InterestOption[]; max: number }
export const getInterests = () => json<Interests>("/today/interests")
export const saveInterests = (ids: string[]) => json<{ selected: string[] }>("/today/interests", { method: "PUT", body: JSON.stringify({ ids }) })
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

let cache: { at: number; data: TodayData } | null = null
let inflight: Promise<Res<TodayData>> | null = null

/** Uma busca so a cada 5 minutos para todos os lugares da tela (painel, popup, faixa do dia). `force` ignora o cache. */
export async function getTodayCached(force = false): Promise<Res<TodayData>> {
  if (!force && cache && Date.now() - cache.at < 5 * 60 * 1000) return { ok: true, status: 200, data: cache.data }
  if (inflight) return inflight
  inflight = getToday()
    .then(r => {
      if (r.data) cache = { at: Date.now(), data: r.data }
      return r
    })
    .finally(() => {
      inflight = null
    })
  return inflight
}

export function resetTodayCache(): void {
  cache = null
}

/** Faixa de uma linha com o essencial do dia, para a tela principal. */
export function dayStrip(d: TodayData): string[] {
  const s = d.sections
  const out: string[] = []
  if (s.weather.status === "ok" && s.weather.temp !== undefined) out.push(`🌤 ${Math.round(Number((s.weather as { temp?: number }).temp))} °C${s.weather.place ? ` em ${s.weather.place.split(",")[0]}` : ""}`)
  const first = s.agenda.items[0]
  if (first) out.push(`📅 ${first.time ? first.time + " " : ""}${first.title}`)
  else if (s.reminders.items[0]) out.push(`🔔 ${s.reminders.items[0].text}`)
  else if (s.agenda.status === "ok" || s.reminders.status === "ok") out.push("📅 Nada marcado hoje")
  if (s.market.usd) out.push(`💵 ${money(s.market.usd.value)}`)
  return out
}
