import { authedFetch } from "@/lib/session"

export type WaMode = "pending" | "auto" | "ask" | "off"
export type WaChat = { id: string; display: string; mode: WaMode; last_seen: string }
export type WaDraft = { id: string; chat: string; incoming: string; reply: string; why: string; status: string; created_at: string }
export type WaDevice = { id: string; label: string; created_at: string; last_seen: string | null }
export type WaStatus = { devices: WaDevice[]; paused: boolean; chats: WaChat[]; pending: WaDraft[]; recent: WaDraft[] }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const waStatus = () => json<WaStatus>("/wa/status")
export const waPending = () => json<{ pending: WaDraft[]; paired: boolean }>("/wa/pending")
export const waPairing = () => json<{ code: string; expires_in: number }>("/wa/pairing", { method: "POST" })
export const waSetMode = (id: string, mode: WaMode) => json<WaChat>(`/wa/chats/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ mode }) })
export const waDeleteChat = (id: string) => json<{ ok: boolean }>(`/wa/chats/${encodeURIComponent(id)}`, { method: "DELETE" })
export const waSetPaused = (paused: boolean) => json<{ paused: boolean }>("/wa/paused", { method: "PUT", body: JSON.stringify({ paused }) })
export const waDecide = (id: string, decision: "approve" | "reject", text?: string) =>
  json<WaDraft>(`/wa/drafts/${encodeURIComponent(id)}/decide`, { method: "POST", body: JSON.stringify({ decision, text }) })
export const waRevoke = (id: string) => json<{ ok: boolean }>(`/wa/devices/${encodeURIComponent(id)}`, { method: "DELETE" })
export const waForgetAll = () => json<{ ok: boolean }>("/wa/data", { method: "DELETE" })
export const waOpenFolder = () => json<{ ok: boolean; path?: string }>("/wa/open-extension-folder", { method: "POST" })

export const MODE_LABEL: Record<WaMode, string> = {
  pending: "Ainda não liberada",
  auto: "Responde sozinho",
  ask: "Pergunta antes",
  off: "Ignorada",
}

/** Conversas novas primeiro (a pessoa precisa decidir); depois as liberadas. */
export function sortChats(chats: WaChat[]): WaChat[] {
  const rank: Record<WaMode, number> = { pending: 0, ask: 1, auto: 2, off: 3 }
  return [...chats].sort((a, b) => rank[a.mode] - rank[b.mode] || b.last_seen.localeCompare(a.last_seen))
}

/** Frase simples para o motivo de pedir aprovacao. */
export function whyText(why: string): string {
  const w = (why || "").trim()
  if (!w) return "Quero confirmar com você antes de enviar."
  return `Quero confirmar com você: ${w}.`
}

/** Minutos restantes do codigo de pareamento, para a contagem na tela. */
export function minutesLeft(expiresIn: number, elapsedS: number): number {
  return Math.max(0, Math.ceil((expiresIn - elapsedS) / 60))
}

export const WA_RISK_NOTE =
  "O WhatsApp não gosta de programas que respondem sozinhos e, se perceber, pode bloquear o número. Por isso, comece em \"Pergunta antes\" e, se puder, use um número só para isso."
export const WA_PRIVACY_NOTE =
  "O texto das mensagens que você liberar é enviado à inteligência na nuvem para escrever a resposta. Eu só olho conversas que você liberar, nunca grupos, e guardo tudo por 30 dias."
