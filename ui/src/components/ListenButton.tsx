import { useState } from "react"
import { canSpeak, speak, stopSpeaking } from "@/lib/speak"

/** Botão "Ouvir": o Jefrey lê o texto da tela em voz alta. */
export default function ListenButton({ text, label = "Ouvir" }: { text: string; label?: string }) {
  const [on, setOn] = useState(false)
  if (!canSpeak()) return null
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={() => {
        if (on) {
          stopSpeaking()
          setOn(false)
          return
        }
        setOn(true)
        void speak(text, { onEnd: () => setOn(false) }).finally(() => setOn(false))
      }}
      className="jf-focus inline-flex items-center gap-2 rounded-lg border border-white/20 px-3 py-1.5 text-sm text-white/80 hover:bg-white/5"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 9v6h4l5 4V5L8 9H4zM17 8a5 5 0 010 8" />
      </svg>
      {on ? "Parar" : label}
    </button>
  )
}
