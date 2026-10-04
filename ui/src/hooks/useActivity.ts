import { useEffect, useState } from "react"
import { getActivity, type Activity } from "@/lib/briefing"

/** Pergunta de tempos em tempos o que o Jefrey esta fazendo sozinho (estudando, aprendendo). Pausa com a aba escondida. */
export function useActivity(intervalMs = 6000): Activity | null {
  const [act, setAct] = useState<Activity | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      if (document.hidden) return
      const r = await getActivity()
      if (alive) setAct(r.data)
    }
    void tick()
    const t = window.setInterval(() => void tick(), intervalMs)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [intervalMs])
  return act
}
