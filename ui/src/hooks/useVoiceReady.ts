import { useCallback, useRef, useState } from "react"
import { authedFetch } from "@/lib/session"

type Status = { ready: boolean; running: boolean; error: string | null }

async function call(path: string, method: "GET" | "POST"): Promise<Status | null> {
  try {
    const r = await authedFetch(path, { method })
    return r.ok ? ((await r.json()) as Status) : null
  } catch {
    return null
  }
}

const sleep = (ms: number) => new Promise(r => window.setTimeout(r, ms))

/**
 * Garante que a audicao do Jefrey (voz para texto) esta pronta antes de ouvir.
 * Na primeira vez o modelo e baixado em segundo plano; a tela mostra "preparando" em vez de parecer travada.
 */
export function useVoiceReady() {
  const [preparing, setPreparing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)

  const ensure = useCallback(async (): Promise<boolean> => {
    if (busy.current) return false
    busy.current = true
    setError(null)
    try {
      let st = await call("/system/voice", "GET")
      if (st?.ready) return true
      if (!st) return true // nao deu para saber (servidor sem esta rota): tenta ouvir mesmo assim
      setPreparing(true)
      st = await call("/system/voice/prepare", "POST")
      for (let i = 0; i < 400 && st; i++) {
        if (st.ready && !st.running) return true
        if (st.error && !st.running) {
          setError(st.error)
          return false
        }
        await sleep(1500)
        st = await call("/system/voice", "GET")
      }
      setError("A preparação está demorando. Verifique a internet e tente de novo.")
      return false
    } finally {
      setPreparing(false)
      busy.current = false
    }
  }, [])

  return { preparing, error, ensure }
}
