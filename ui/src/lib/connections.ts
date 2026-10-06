import { authedFetch } from "@/lib/session"
import { isDesktop, openExternal } from "@/lib/shell"

export type GoogleService = "calendar" | "email" | "drive" | "tasks" | "contacts"

export type GoogleStatus = {
  configured: boolean
  connected: boolean
  email: string | null
  services: GoogleService[]
  redirect_uri?: string
  diagnosis?: { ok: boolean; advice: string; client_type: string }
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
export const saveGoogleCredentials = (client_id: string, client_secret: string) =>
  json<{ configured: boolean }>("/connections/google/credentials", { method: "PUT", body: JSON.stringify({ client_id, client_secret }) })
export const disconnectGoogle = () => json<{ ok: boolean }>("/connections/google", { method: "DELETE" })

/** Leva a pessoa ao site do Google para entrar. Devolve um erro legivel se nao der. */
export async function startGoogle(services: GoogleService[]): Promise<string | null> {
  const r = await json<{ auth_url?: string; detail?: string }>("/connections/google/start", { method: "POST", body: JSON.stringify({ services }) })
  if (r.status === 409) return "Esta cópia do Jefrey ainda não foi liberada para entrar com o Google. Fale com quem te entregou o Jefrey."
  const url = r.data?.auth_url
  if (!r.ok || !url || !url.startsWith("https://accounts.google.com/")) return "Não consegui abrir o Google agora. Tente de novo em instantes."
  if (isDesktop()) {
    // dentro da janela do app o Google recusa o login: abre no navegador de verdade e a tela espera a volta
    return (await openExternal(url)) ? null : "Não consegui abrir o navegador. Tente de novo."
  }
  window.location.assign(url)
  return null
}

/** Mensagem da volta do Google (?google=ok|erro). */
export function googleReturnMessage(value: string | null): { ok: boolean; text: string } | null {
  if (value === "ok") return { ok: true, text: "Pronto! O Google foi conectado. Agora o Jefrey pode ver a sua agenda e ajudar com o seu e-mail." }
  if (value === "erro") return { ok: false, text: "A conexão com o Google não foi concluída. Se você cancelou, está tudo bem. Para tentar de novo, aperte o botão." }
  if (value === "chave") return { ok: false, text: "O Google chegou até aqui, mas recusou a chave secreta deste app: ela não confere com o ID. No Google Cloud, copie a chave atual do seu cliente e cole no quadro “Trocar o ID e a chave”, logo abaixo." }
  if (value === "retorno") return { ok: false, text: "O Google não conhece o endereço de retorno. Cadastre no Google Cloud o endereço que aparece logo abaixo." }
  if (value === "codigo") return { ok: false, text: "O código de acesso do Google venceu ou já foi usado. É só apertar o botão de novo." }
  return null
}

export const SERVICE_LABEL: Record<GoogleService, string> = { calendar: "Agenda", email: "E-mail", drive: "Arquivos (Drive)", tasks: "Tarefas", contacts: "Contatos" }
export const SERVICE_HINT: Record<GoogleService, string> = {
  calendar: "ver e marcar compromissos, e avisar antes de cada um",
  email: "ler e ajudar a responder e-mails",
  drive: "achar e ler seus arquivos",
  tasks: "ver, criar e marcar tarefas como feitas",
  contacts: "achar telefone e e-mail de alguém",
}
export const ALL_SERVICES: GoogleService[] = ["calendar", "email", "drive", "tasks", "contacts"]
