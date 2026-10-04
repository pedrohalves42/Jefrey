import { authedFetch } from "@/lib/session"

export type GoogleService = "calendar" | "email" | "drive"

export type GoogleStatus = {
  configured: boolean
  connected: boolean
  email: string | null
  services: GoogleService[]
  available_services: { id: GoogleService; label: string }[]
}

async function json<T>(path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: T | null }> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getGoogle = () => json<GoogleStatus>("/connections/google")
export const disconnectGoogle = () => json<{ ok: boolean }>("/connections/google", { method: "DELETE" })

/** Leva a pessoa ao site do Google para entrar. Devolve um erro legivel se nao der. */
export async function startGoogle(services: GoogleService[]): Promise<string | null> {
  const r = await json<{ auth_url?: string; detail?: string }>("/connections/google/start", { method: "POST", body: JSON.stringify({ services }) })
  if (r.status === 409) return "Esta cópia do Jefrey ainda não foi liberada para entrar com o Google. Fale com quem te entregou o Jefrey."
  const url = r.data?.auth_url
  if (!r.ok || !url || !url.startsWith("https://accounts.google.com/")) return "Não consegui abrir o Google agora. Tente de novo em instantes."
  window.location.assign(url)
  return null
}

/** Mensagem da volta do Google (?google=ok|erro). */
export function googleReturnMessage(value: string | null): { ok: boolean; text: string } | null {
  if (value === "ok") return { ok: true, text: "Pronto! O Google foi conectado. Agora o Jefrey pode ver a sua agenda e ajudar com o seu e-mail." }
  if (value === "erro") return { ok: false, text: "A conexão com o Google não foi concluída. Se você cancelou, está tudo bem. Para tentar de novo, aperte o botão." }
  return null
}

export const SERVICE_LABEL: Record<GoogleService, string> = { calendar: "Agenda", email: "E-mail", drive: "Arquivos" }
