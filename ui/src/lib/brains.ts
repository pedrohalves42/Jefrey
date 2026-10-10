import { authedFetch } from "@/lib/session"

export type BrainCard = { id: string; name: string; tagline: string; kind: "oneclick" | "key" | "local"; key_url: string; recommended: boolean }
export type BrainRole = "principal" | "reserva"
export type RoleInfo = { id: string; label: string }
export type BrainsState = {
  brains: { id: string; role: BrainRole; model: string; roles?: string[]; all_roles?: boolean }[]
  catalog: BrainCard[]
  max: number
  machine?: { ram_gb: number; local_recommended: boolean }
  roles?: RoleInfo[]
  team?: string[]
  team_roles?: string[]
}

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export type BrainCheck = { id: string; role: BrainRole; model: string; ok: boolean; seconds: number; problem: string }
export const checkBrains = () => json<{ results: BrainCheck[] }>("/brains/check")
export const getBrains = () => json<BrainsState>("/brains")
export const connectBrain = (id: string, api_key?: string) =>
  json<BrainsState>(`/brains/${encodeURIComponent(id)}/connect`, { method: "POST", body: JSON.stringify({ api_key }) })
export const makePrimary = (id: string) => json<BrainsState>(`/brains/${encodeURIComponent(id)}/primary`, { method: "POST" })
/** O que este cerebro faz. `null` = serve para tudo. */
export const setBrainRoles = (id: string, roles: string[] | null) =>
  json<BrainsState>(`/brains/${encodeURIComponent(id)}/roles`, { method: "PUT", body: JSON.stringify({ roles }) })
/** Funcoes em que dois cerebros trabalham juntos (um escreve, outro revisa). */
export const setBrainTeam = (roles: string[]) => json<BrainsState>("/brains/team", { method: "PUT", body: JSON.stringify({ roles }) })
export const disconnectBrain = (id: string) => json<BrainsState>(`/brains/${encodeURIComponent(id)}`, { method: "DELETE" })

export function roleOf(state: BrainsState | null, id: string): BrainRole | null {
  return state?.brains.find(b => b.id === id)?.role ?? null
}

/** Frase simples sobre como os cerebros conectados trabalham juntos. */
export function routingSummary(state: BrainsState | null, names: Record<string, string>): string {
  const list = state?.brains ?? []
  if (list.length === 0) return "Nenhum cérebro conectado ainda. Escolha um abaixo para o Jefrey poder pensar."
  const first = names[list[0]!.id] ?? list[0]!.id
  if (list.length === 1) return `O Jefrey está pensando com ${first}. Conecte mais um para ter uma reserva: se este falhar, ele usa o outro sozinho.`
  const rest = list.slice(1).map(b => names[b.id] ?? b.id).join(", ")
  const split = list.some(b => b.all_roles === false)
  if (split) return `O Jefrey usa os ${list.length} cérebros em equipe: cada um faz o que você marcou, e se um falhar outro assume sozinho.`
  return `O Jefrey pensa com ${first}. Se falhar ou acabar o crédito, ele usa sozinho: ${rest}.`
}

export function steps(name: string): string[] {
  return [
    `Aperte o botão azul. O site do ${name} abre em outra aba.`,
    "Entre na sua conta (ou crie uma) e procure o botão para criar um código de acesso (costuma se chamar “Create key” ou “Criar chave”). Pode dar o nome “Jefrey”.",
    "Copie o código que aparecer, volte aqui e cole no campo.",
  ]
}

export function apiDetail(res: Res<unknown>, fallback: string): string {
  const d = (res.data as { detail?: unknown } | null)?.detail
  return typeof d === "string" && d.trim() ? d : fallback
}
