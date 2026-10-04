import { getToken, setToken, setUserId, getUserId } from "@/lib/api"

let inflight: Promise<string | null> | null = null

/** Pede um token novo (dev). Varias chamadas simultaneas compartilham a mesma requisicao. */
export function refreshToken(): Promise<string | null> {
  if (!inflight) {
    inflight = (async () => {
      try {
        const r = await fetch("/auth/dev-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: getUserId() }),
        })
        if (!r.ok) return null
        const j = await r.json().catch(() => ({}))
        const tok = String(j.access_token || j.token || "")
        if (!tok) return null
        setToken(tok)
        if (j.user_id) setUserId(String(j.user_id))
        return tok
      } catch {
        return null
      } finally {
        setTimeout(() => {
          inflight = null
        }, 0)
      }
    })()
  }
  return inflight
}

export async function ensureSession(): Promise<boolean> {
  return !!(getToken() || (await refreshToken()))
}

/**
 * fetch autenticado. Se a API responder 401 (token expirado), renova o token uma vez e repete.
 * Nunca coloca token na URL.
 */
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const run = () => {
    const t = getToken()
    const headers = new Headers(init.headers)
    // JSON so quando o corpo e texto; FormData (audio, arquivos) precisa do boundary automatico do navegador
    if (!headers.has("Content-Type") && typeof init.body === "string") headers.set("Content-Type", "application/json; charset=utf-8")
    if (t) headers.set("Authorization", `Bearer ${t}`)
    return fetch(path, { ...init, headers })
  }
  let res = await run()
  if (res.status === 401 && (await refreshToken())) res = await run()
  return res
}
