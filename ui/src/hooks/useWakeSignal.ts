import { useEffect, useRef } from "react"
import { authedFetch } from "@/lib/session"

/**
 * Atalho global do Windows (Ctrl+Alt+J): o programa avisa e a tela comeca a ouvir.
 * Continua perguntando mesmo com a aba em segundo plano (o navegador so desacelera, nao para).
 */
export function useWakeSignal(onWake: () => void, intervalMs = 1500): void {
  const cb = useRef(onWake)
  cb.current = onWake
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const r = await authedFetch("/system/wake")
        if (alive && r.ok && ((await r.json()) as { wake?: boolean }).wake) cb.current()
      } catch {
        /* programa fechando ou sem rede local: tenta de novo no proximo ciclo */
      }
    }
    void tick()
    const t = window.setInterval(() => void tick(), intervalMs)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [intervalMs])
}
