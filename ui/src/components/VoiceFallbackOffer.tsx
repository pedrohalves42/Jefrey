import { useEffect, useState } from "react"
import { getLocalStatus, startModelDownload } from "@/lib/voice"
import { DISMISS_KEY, FAILS_TO_OFFER, offerText, shouldOffer, VOICE_FAIL_EVENT } from "@/lib/voiceOffer"

function wasDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "1"
  } catch {
    return false
  }
}

/** Aviso discreto: a voz da internet falhou duas vezes e a voz local nao esta instalada. Nunca baixa sozinho. */
export default function VoiceFallbackOffer() {
  const [failures, setFailures] = useState(0)
  const [sizeMb, setSizeMb] = useState(60)
  const [installed, setInstalled] = useState(true)
  const [dismissed, setDismissed] = useState(wasDismissed)
  const [msg, setMsg] = useState("")

  useEffect(() => {
    const onFail = () => setFailures(n => n + 1)
    const onOk = () => setFailures(0)
    window.addEventListener(VOICE_FAIL_EVENT, onFail)
    window.addEventListener(VOICE_FAIL_EVENT + "-ok", onOk)
    return () => {
      window.removeEventListener(VOICE_FAIL_EVENT, onFail)
      window.removeEventListener(VOICE_FAIL_EVENT + "-ok", onOk)
    }
  }, [])

  useEffect(() => {
    if (failures < FAILS_TO_OFFER) return
    void getLocalStatus().then(r => {
      if (r.data) {
        setInstalled(r.data.installed)
        setSizeMb(r.data.size_mb)
      }
    })
  }, [failures])

  if (msg) return <p role="status" className="jf-panel mx-4 mb-2 p-3 text-sm text-cyan-200">{msg}</p>
  if (!shouldOffer({ failures, localInstalled: installed, dismissed })) return null
  return (
    <div role="region" aria-label="Voz sem internet" className="jf-panel mx-4 mb-2 flex flex-wrap items-center gap-3 p-3 text-sm text-white/85">
      <span className="flex-1">{offerText(sizeMb)}</span>
      <button
        type="button"
        className="jf-btn jf-focus px-4 py-2"
        onClick={() => void startModelDownload().then(r => setMsg(r.ok ? "Baixando a voz em segundo plano. Você pode continuar usando o Jefrey." : "Não consegui começar o download agora."))}
      >
        Baixar
      </button>
      <button
        type="button"
        className="jf-focus px-3 py-2 underline"
        onClick={() => {
          try {
            sessionStorage.setItem(DISMISS_KEY, "1")
          } catch {
            /* sem armazenamento: so fecha agora */
          }
          setDismissed(true)
        }}
      >
        Agora não
      </button>
    </div>
  )
}
