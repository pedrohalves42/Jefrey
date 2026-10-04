import { authedFetch } from "@/lib/session"

export type LlmConfig = {
  provider: string
  model: string
  base_url: string
  has_key: boolean
  is_cloud: boolean
  configured: boolean
  fallbacks: number
}

export type Preset = {
  id: string
  label: string
  provider: string
  base_url: string
  models: string[]
  needs_key: boolean
  one_click?: boolean
  recommended?: boolean
}

export type Advice = {
  suggest_local: boolean
  model: string | null
  reason: string
  measured: boolean
  gpu: { name: string; vram_gb: number } | null
  default: string
}

export type Fallback = { id: string; provider: string; model: string; base_url: string | null; has_key: boolean }

const SKIP_KEY = "jefrey_skip_welcome"

export function welcomeSkipped(): boolean {
  try {
    return sessionStorage.getItem(SKIP_KEY) === "1"
  } catch {
    return false
  }
}

export function skipWelcome(): void {
  try {
    sessionStorage.setItem(SKIP_KEY, "1")
  } catch {
    /* sem armazenamento: so vale ate recarregar */
  }
}

/** Deve mostrar o assistente de primeira execucao? So quando nada foi escolhido ainda e a pessoa nao pulou. */
export function needsWelcome(cfg: LlmConfig | undefined | null, skipped: boolean): boolean {
  return !!cfg && cfg.configured === false && !skipped
}

async function json<T>(path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: T | null }> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getConfig = () => json<LlmConfig>("/settings/llm")
export const getPresets = () => json<{ presets: Preset[] }>("/settings/llm/presets")
export const getAdvice = () => json<Advice>("/settings/llm/advice")
export const getFallbacks = () => json<{ fallbacks: Fallback[]; max: number }>("/settings/llm/fallbacks")
export const putFallbacks = (items: unknown[]) =>
  json<{ fallbacks: Fallback[] }>("/settings/llm/fallbacks", { method: "PUT", body: JSON.stringify(items) })
export const saveConfig = (body: Record<string, unknown>) => json<LlmConfig>("/settings/llm", { method: "PUT", body: JSON.stringify(body) })
export const testConfig = () => json<{ ok: boolean; detail?: string; model?: string }>("/settings/llm/test", { method: "POST" })

/** Mensagem humana para um resultado de teste de conexao. Nunca mostra detalhe tecnico bruto. */
export function testMessage(res: { ok: boolean; status: number; data: { ok?: boolean; detail?: string; model?: string } | null }): { ok: boolean; text: string } {
  if (res.status === 0) return { ok: false, text: "Não consegui falar com o Jefrey. Ele está aberto?" }
  if (!res.ok || !res.data) return { ok: false, text: "Não consegui testar agora. Tente de novo." }
  if (res.data.ok) return { ok: true, text: `Tudo certo! Conectado${res.data.model ? ` ao modelo ${res.data.model}` : ""}.` }
  const d = (res.data.detail || "").toLowerCase()
  if (d.includes("401") || d.includes("403") || d.includes("httpstatus")) return { ok: false, text: "A chave foi recusada. Confira se copiou inteira e se ainda está ativa." }
  if (d.includes("connect")) return { ok: false, text: "Não consegui chegar ao provedor. Verifique sua internet." }
  return { ok: false, text: "Não deu para conectar com essa configuração. Confira a chave e o modelo." }
}

/** Pede o endereco de login do OpenRouter e leva a pessoa para la. Devolve erro legivel se falhar. */
export async function startOpenRouter(): Promise<string | null> {
  const r = await json<{ auth_url: string }>("/settings/llm/openrouter/start", { method: "POST" })
  const url = r.data?.auth_url
  if (!r.ok || !url || !url.startsWith("https://openrouter.ai/")) return "Não consegui iniciar a conexão. Tente de novo."
  window.location.assign(url)
  return null
}
