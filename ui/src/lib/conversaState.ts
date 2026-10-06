import { loadActiveId, loadThreads, newThread, type Thread } from "@/lib/chat"

/** Preferencia salva; sem escolha ainda, usa o padrao (voz ligada: o caminho principal e falar e ouvir). */
export function readFlag(key: string, fallback = true): boolean {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v === "1"
  } catch {
    return fallback
  }
}

export function writeFlag(key: string, on: boolean): void {
  try {
    localStorage.setItem(key, on ? "1" : "0")
  } catch {
    /* sem armazenamento: vale so nesta sessao */
  }
}

/** Conversas guardadas (ou uma nova, vazia) e qual esta aberta. */
export function initThreads(): { threads: Thread[]; active: string } {
  const threads = loadThreads()
  const saved = loadActiveId()
  if (threads.length === 0) {
    const t = newThread()
    return { threads: [t], active: t.id }
  }
  return { threads, active: threads.some(t => t.id === saved) ? (saved as string) : (threads[0] as Thread).id }
}
