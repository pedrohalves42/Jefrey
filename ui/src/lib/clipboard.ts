import { authedFetch } from "@/lib/session"

export const ACTION_LABEL: Record<string, string> = { traduzir: "Traduzir", resumir: "Resumir", explicar: "Explicar", corrigir: "Corrigir" }
export type ClipState = { enabled: boolean; offer: { preview: string; offers: string[] } | null }

/** So as acoes que o Jefrey conhece, na ordem em que vieram e sem repetir. */
export function knownOffers(offers: string[]): string[] {
  return [...new Set(offers.filter(o => o in ACTION_LABEL))]
}

export function offerTitle(offers: string[]): string {
  return offers.includes("traduzir") ? "Você copiou um texto em outra língua. Quer que eu traduza?" : "Você copiou um texto. Quer que eu ajude?"
}

export async function getClipboard(): Promise<ClipState | null> {
  try {
    const r = await authedFetch("/clipboard")
    return r.ok ? ((await r.json()) as ClipState) : null
  } catch {
    return null
  }
}

export async function setClipboardEnabled(enabled: boolean): Promise<boolean> {
  try {
    return (await authedFetch("/clipboard/enabled", { method: "PUT", body: JSON.stringify({ enabled }) })).ok
  } catch {
    return false
  }
}

export async function clipboardPrompt(action: string): Promise<string | null> {
  try {
    const r = await authedFetch("/clipboard/prompt", { method: "POST", body: JSON.stringify({ action }) })
    return r.ok ? ((await r.json()) as { prompt: string }).prompt : null
  } catch {
    return null
  }
}

export async function dismissClipboard(): Promise<void> {
  try {
    await authedFetch("/clipboard/dismiss", { method: "POST" })
  } catch {
    /* sem conexao: a oferta some sozinha na proxima copia */
  }
}
