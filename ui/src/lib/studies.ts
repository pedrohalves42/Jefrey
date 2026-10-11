import { authedFetch } from "@/lib/session"

export type Topic = {
  id: string
  title: string
  status: "active" | "paused"
  level: number
  level_label: string
  source: "memoria" | "curiosidade" | "manual"
  guides: number
  last_studied_at: string | null
  last_error: string | null
}
export type Prefs = { enabled: boolean; budget_usd: number; quiet_start: number; quiet_end: number }
export type Overview = { topics: Topic[]; prefs: Prefs; spent_today: number; cloud_ready: boolean }
export type Source = { title: string; url: string; date: string }
export type Guide = { id: string; title: string; summary: string; body: string; sources: Source[]; level: number; level_label: string; created_at: string }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getStudies = () => json<Overview>("/studies")
export const addTopic = (title: string) => json<Topic>("/studies", { method: "POST", body: JSON.stringify({ title }) })
export const suggestTopics = () => json<{ added: Topic[] }>("/studies/suggest", { method: "POST" })
export const setTopicStatus = (id: string, status: "active" | "paused") =>
  json<Topic>(`/studies/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ status }) })
export const deleteTopic = (id: string) => json<{ ok: boolean }>(`/studies/${encodeURIComponent(id)}`, { method: "DELETE" })
export const getGuide = (id: string) => json<Guide>(`/studies/${encodeURIComponent(id)}/guide`)
export const runStudy = (id: string) => json<Guide>(`/studies/${encodeURIComponent(id)}/run`, { method: "POST" })
export const putPrefs = (p: Partial<Prefs>) => json<Prefs>("/studies/prefs", { method: "PUT", body: JSON.stringify(p) })

export type UserSource = { id: string; topic_id: string | null; url: string; title: string }
export type LearnResult = { topic?: Topic; source?: string; saved_text?: boolean; facts?: number; guide?: Guide; run_error?: string }

export const learnRequest = (body: { topic?: string; url?: string; text?: string; run?: boolean }) =>
  json<LearnResult>("/studies/learn", { method: "POST", body: JSON.stringify(body) })
export const getUserSources = () => json<{ sources: UserSource[] }>("/studies/sources")
export const addUserSource = (url: string, topicId = "any", title = "") =>
  json<UserSource>(`/studies/${encodeURIComponent(topicId)}/sources`, { method: "POST", body: JSON.stringify({ url, title }) })
export const deleteUserSource = (id: string) => json<{ ok: boolean }>(`/studies/sources/${encodeURIComponent(id)}`, { method: "DELETE" })

/** O que a pessoa digitou parece um link? (para mandar no campo certo) */
export function looksLikeLink(s: string): boolean {
  return /^(https?:\/\/\S+|[\w-]+(\.[\w-]+)+(\/\S*)?)$/i.test(s.trim())
}

/** Frase simples sobre o que aconteceu com o pedido de aprender. */
export function learnMessage(r: LearnResult): { ok: boolean; text: string } {
  const parts: string[] = []
  if (r.saved_text) parts.push(r.facts ? `Guardei o texto e aprendi ${r.facts} coisa${r.facts > 1 ? "s" : ""} sobre você.` : "Guardei o texto nas suas notas.")
  if (r.topic) parts.push(r.source ? `Anotei o link para o assunto “${r.topic.title}”.` : `Anotei o assunto “${r.topic.title}”.`)
  if (r.guide) return { ok: true, text: `${parts.join(" ")} Estudei e escrevi um guia: “${r.guide.title}”. Veja em Estudos.`.trim() }
  if (r.run_error) return { ok: false, text: `${parts.join(" ")} ${r.run_error}`.trim() }
  return { ok: true, text: `${parts.join(" ")} Eu estudo quando você estiver longe do computador, ou aperte “Estudar agora” em Estudos.`.trim() }
}

/** Mensagem humana a partir de um erro da API (o servidor ja manda o texto em portugues simples). */
export function apiMessage(res: Res<unknown>, fallback = "Não consegui agora. Tente de novo."): string {
  const d = (res.data as { detail?: unknown } | null)?.detail
  return typeof d === "string" && d.trim() ? d : fallback
}

/** Pontinhos do nivel: [true,true,false,false,false]. */
export function levelDots(level: number, max = 5): boolean[] {
  return Array.from({ length: max }, (_, i) => i < Math.max(0, Math.min(max, level)))
}

/** Quanto do limite do dia ja foi usado (0 a 100). Limite zero conta como cheio. */
export function budgetPercent(spent: number, limit: number): number {
  if (limit <= 0) return 100
  return Math.max(0, Math.min(100, Math.round((spent / limit) * 100)))
}

export function usd(v: number): string {
  return `US$ ${v.toFixed(2).replace(".", ",")}`
}

export const BUDGET_CHOICES = [0.05, 0.1, 0.25, 0.5, 1]

/** "hoje", "ontem", "há 3 dias", "nunca". */
export function lastStudied(iso: string | null, now = new Date()): string {
  if (!iso) return "ainda não estudei"
  const t = new Date(iso.endsWith("Z") ? iso : iso + "Z").getTime()
  if (Number.isNaN(t)) return "ainda não estudei"
  const days = Math.floor((now.getTime() - t) / 86_400_000)
  if (days <= 0) return "estudei hoje"
  if (days === 1) return "estudei ontem"
  return `estudei há ${days} dias`
}

export function sourceLabel(s: Topic["source"]): string {
  return s === "memoria" ? "pela sua memória" : s === "curiosidade" ? "pela sua curiosidade" : "a seu pedido"
}

/** So abre links http(s): o texto veio da web e nao e confiavel. */
export function safeHref(url: string): string | null {
  try {
    const u = new URL(url)
    return u.protocol === "https:" || u.protocol === "http:" ? u.toString() : null
  } catch {
    return null
  }
}

export type GuideBlock = { type: "p" | "h" | "li"; text: string }

/** Transforma o texto do guia ("**Titulo**", "1. passo", "- dica") em blocos simples. Nunca usa HTML. */
export function parseGuide(body: string): GuideBlock[] {
  const out: GuideBlock[] = []
  for (const raw of body.split("\n")) {
    const line = raw.trim()
    if (!line) continue
    const h = /^\*\*(.+)\*\*$/.exec(line)
    if (h) out.push({ type: "h", text: h[1]! })
    else if (/^\d+\.\s+/.test(line)) out.push({ type: "li", text: line })
    else if (line.startsWith("- ")) out.push({ type: "li", text: "• " + line.slice(2) })
    else out.push({ type: "p", text: line })
  }
  return out
}

export function hourLabel(h: number): string {
  return `${String(h).padStart(2, "0")}h`
}
