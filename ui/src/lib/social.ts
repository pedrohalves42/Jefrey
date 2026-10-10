import { authedFetch } from "@/lib/session"

export type Network = { id: string; name: string; unread: number }
export type CarouselResult = { ok: boolean; title: string; folder: string; files: string[]; caption: string; hashtags: string[]; slides: { title: string; body: string }[] }
export type PostResult = { ok: boolean; network: string; text: string }
type Res<T> = { ok: boolean; status: number; data: T | null; error: string }

async function call<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    const data = (await r.json().catch(() => null)) as (T & { detail?: unknown }) | null
    return { ok: r.ok, status: r.status, data: r.ok ? data : null, error: !r.ok && data && typeof data.detail === "string" ? data.detail : r.ok ? "" : "Não consegui agora. Tente de novo." }
  } catch {
    return { ok: false, status: 0, data: null, error: "Sem conexão com o Jefrey." }
  }
}

export const getNetworks = () => call<{ networks: Network[]; window: boolean }>("/social/networks")
export const openNetwork = (id: string) => call<{ ok: boolean }>(`/system/site/${encodeURIComponent(id)}`, { method: "POST" })
export const createCarousel = (topic: string, slides: number, theme: string) =>
  call<CarouselResult>("/social/carousel", { method: "POST", body: JSON.stringify({ topic, slides, theme }) })
export const createPost = (network: string, topic: string) => call<PostResult>("/social/post", { method: "POST", body: JSON.stringify({ network, topic }) })
export const openCarouselFolder = (path: string) => call<{ ok: boolean }>("/social/open-folder", { method: "POST", body: JSON.stringify({ path }) })

export const THEMES: { id: string; label: string }[] = [
  { id: "escuro", label: "Escuro" },
  { id: "claro", label: "Claro" },
  { id: "verde", label: "Verde" },
  { id: "quente", label: "Quente" },
]
export const POST_NETWORKS: { id: string; label: string }[] = [
  { id: "instagram", label: "Instagram" },
  { id: "facebook", label: "Facebook" },
  { id: "x", label: "X (Twitter)" },
  { id: "telegram", label: "Telegram" },
]
