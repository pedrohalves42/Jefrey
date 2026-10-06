import { authedFetch } from "@/lib/session"

const KEY = "jf_app"

/** A tela foi aberta pela janela propria do app (o programa a abre com ?app=1)? Guarda para as proximas paginas. */
export function isDesktop(): boolean {
  try {
    if (new URLSearchParams(window.location.search).get("app") === "1") sessionStorage.setItem(KEY, "1")
    return sessionStorage.getItem(KEY) === "1"
  } catch {
    return false
  }
}

/** Abre um endereco do Google no navegador de verdade (o Google nao deixa entrar por dentro da janela do app). */
export async function openExternal(url: string): Promise<boolean> {
  try {
    const r = await authedFetch("/system/open-external", { method: "POST", body: JSON.stringify({ url }) })
    return r.ok
  } catch {
    return false
  }
}

export async function showMainWindow(): Promise<void> {
  try {
    await authedFetch("/system/show", { method: "POST" })
  } catch {
    /* sem janela propria nao ha o que mostrar */
  }
}

export async function showOrb(): Promise<boolean> {
  try {
    return (await authedFetch("/system/orb", { method: "POST" })).ok
  } catch {
    return false
  }
}

export type Autostart = { available: boolean; enabled: boolean }

export async function getAutostart(): Promise<Autostart | null> {
  try {
    const r = await authedFetch("/system/autostart")
    return r.ok ? ((await r.json()) as Autostart) : null
  } catch {
    return null
  }
}

export async function setAutostart(enabled: boolean): Promise<Autostart | null> {
  try {
    const r = await authedFetch("/system/autostart", { method: "PUT", body: JSON.stringify({ enabled }) })
    return r.ok ? ((await r.json()) as Autostart) : null
  } catch {
    return null
  }
}

/** Estado do cerebro compartilhado entre a janela principal e o orbe (mesmo perfil do WebView2). */
export type OrbState = { state: "idle" | "listening" | "thinking" | "responding" | "approval"; level: number }
const CHANNEL = "jefrey-state"

export function publishOrb(s: OrbState): void {
  try {
    const ch = new BroadcastChannel(CHANNEL)
    ch.postMessage(s)
    ch.close()
  } catch {
    /* sem BroadcastChannel o orbe so mostra o estado calmo */
  }
}

export function listenOrb(fn: (s: OrbState) => void): () => void {
  try {
    const ch = new BroadcastChannel(CHANNEL)
    ch.onmessage = e => fn(e.data as OrbState)
    return () => ch.close()
  } catch {
    return () => undefined
  }
}
