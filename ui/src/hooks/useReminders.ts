import { useCallback, useEffect, useRef, useState } from "react"
import { authedFetch } from "@/lib/session"

export type DueReminder = { id: string; text: string; due_label: string; repeat: string }

/** Lembretes novos: os que ainda nao foram mostrados nesta sessao (evita repetir o aviso a cada consulta). */
export function newOnes(shown: Set<string>, due: DueReminder[]): DueReminder[] {
  return due.filter(d => d && typeof d.id === "string" && !shown.has(d.id))
}

const POLL_MS = 20_000

/**
 * Consulta os lembretes vencidos e os mostra. Um lembrete so sai da fila no servidor quando a pessoa
 * dispensa o aviso (ack): se o app estava fechado ou a aba em segundo plano, ele aparece quando voltar.
 */
export function useReminders() {
  const [items, setItems] = useState<DueReminder[]>([])
  const shown = useRef<Set<string>>(new Set())
  const [canNotify, setCanNotify] = useState(() => typeof Notification !== "undefined" && Notification.permission === "default")

  const poll = useCallback(async () => {
    try {
      const r = await authedFetch("/reminders/due", { cache: "no-store" })
      if (!r.ok) return
      const fresh = newOnes(shown.current, ((await r.json()).reminders ?? []) as DueReminder[])
      if (!fresh.length) return
      fresh.forEach(f => shown.current.add(f.id))
      setItems(prev => [...prev, ...fresh])
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        for (const f of fresh) {
          try {
            new Notification("Lembrete do Jefrey", { body: f.text, tag: f.id })
          } catch {
            /* sem notificacao do sistema: o aviso na tela continua */
          }
        }
      }
    } catch {
      /* sem conexao agora: tenta de novo na proxima consulta */
    }
  }, [])

  useEffect(() => {
    void poll()
    const t = window.setInterval(() => void poll(), POLL_MS)
    const onFocus = () => void poll()
    window.addEventListener("focus", onFocus)
    return () => {
      window.clearInterval(t)
      window.removeEventListener("focus", onFocus)
    }
  }, [poll])

  const dismiss = useCallback(async (id: string) => {
    setItems(prev => prev.filter(i => i.id !== id))
    try {
      await authedFetch(`/reminders/${id}/ack`, { method: "POST" })
    } catch {
      shown.current.delete(id) // nao confirmou: aparece de novo na proxima consulta
    }
  }, [])

  const enableNotifications = useCallback(async () => {
    if (typeof Notification === "undefined") return
    try {
      await Notification.requestPermission()
    } finally {
      setCanNotify(Notification.permission === "default")
    }
  }, [])

  return { items, dismiss, canNotify, enableNotifications }
}
