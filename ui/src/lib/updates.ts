import { authedFetch } from "@/lib/session"

export type UpdateInfo = { current: string; available: boolean; enabled?: boolean; version?: string; notes?: string; size?: number }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const checkUpdate = () => json<UpdateInfo>("/updates/check")
export const installUpdate = () => json<{ started: boolean; version: string; backup: string | null }>("/updates/install", { method: "POST" })

/** Frase simples sobre o resultado da busca por atualizacao. */
export function updateMessage(r: Res<UpdateInfo>): { ok: boolean; text: string } {
  if (r.status === 0) return { ok: false, text: "Não consegui falar com o Jefrey agora." }
  if (!r.ok) {
    const d = (r.data as { detail?: unknown } | null)?.detail
    return { ok: false, text: typeof d === "string" ? d : "Não consegui procurar atualizações agora." }
  }
  const d = r.data
  if (!d || d.enabled === false) return { ok: true, text: "As atualizações automáticas ainda não estão ligadas nesta cópia do Jefrey." }
  if (!d.available) return { ok: true, text: `Você está com a versão mais nova (${d.current}).` }
  return { ok: true, text: `Tem uma versão nova: ${d.version}.${d.notes ? ` ${d.notes}` : ""}` }
}

export function sizeLabel(bytes?: number): string {
  if (!bytes) return ""
  return bytes >= 1024 * 1024 * 1024 ? `${(bytes / 1024 ** 3).toFixed(1).replace(".", ",")} GB` : `${Math.round(bytes / 1024 ** 2)} MB`
}
