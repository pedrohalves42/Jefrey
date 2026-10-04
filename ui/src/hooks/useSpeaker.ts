import { useCallback, useEffect, useRef, useState } from "react"
import { speakable } from "@/lib/voice/sentences"

const MAX_CHUNK = 200 // alguns motores de voz travam em falas longas

/** Divide uma frase longa em pedacos falaveis, preferindo virgulas e espacos. */
export function chunkForSpeech(text: string, max = MAX_CHUNK): string[] {
  const out: string[] = []
  let rest = text.trim()
  while (rest.length > max) {
    let cut = Math.max(rest.lastIndexOf(", ", max), rest.lastIndexOf("; ", max), rest.lastIndexOf(": ", max))
    if (cut < max * 0.4) cut = rest.lastIndexOf(" ", max)
    const end = cut < 1 ? max : cut + 1 // sem ponto de corte natural: corte duro em `max`
    out.push(rest.slice(0, end).trim())
    rest = rest.slice(end).trim()
  }
  if (rest) out.push(rest)
  return out
}

export type SpeakerVoice = { uri: string; name: string; lang: string }

/**
 * Fala com as vozes instaladas no sistema (local: nada sai do computador).
 * `say` enfileira frases; `cancel` interrompe tudo na hora (interrupcao pelo usuario).
 */
export function useSpeaker() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window
  const [speaking, setSpeaking] = useState(false)
  const [voices, setVoices] = useState<SpeakerVoice[]>([])
  const pending = useRef(0)
  const voiceUri = useRef<string | null>(null)

  useEffect(() => {
    if (!supported) return
    const load = () =>
      setVoices(
        window.speechSynthesis
          .getVoices()
          .filter(v => v.lang.toLowerCase().startsWith("pt"))
          .map(v => ({ uri: v.voiceURI, name: v.name, lang: v.lang })),
      )
    load()
    window.speechSynthesis.addEventListener("voiceschanged", load)
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load)
  }, [supported])

  const setVoice = useCallback((uri: string | null) => {
    voiceUri.current = uri
  }, [])

  const pickVoice = (): SpeechSynthesisVoice | undefined => {
    const all = window.speechSynthesis.getVoices()
    return (
      all.find(v => v.voiceURI === voiceUri.current) ||
      all.find(v => v.lang.toLowerCase() === "pt-br") ||
      all.find(v => v.lang.toLowerCase().startsWith("pt"))
    )
  }

  const say = useCallback(
    (raw: string) => {
      if (!supported) return
      const text = speakable(raw)
      if (!text) return
      for (const piece of chunkForSpeech(text)) {
        const u = new SpeechSynthesisUtterance(piece)
        const v = pickVoice()
        if (v) {
          u.voice = v
          u.lang = v.lang
        } else {
          u.lang = "pt-BR"
        }
        pending.current += 1
        setSpeaking(true)
        const done = () => {
          pending.current = Math.max(0, pending.current - 1)
          if (pending.current === 0) setSpeaking(false)
        }
        u.onboundary = e => {
          if (e.name === "word" || e.name === undefined) window.dispatchEvent(new Event("jefrey-word")) // o avatar pulsa a cada palavra
        }
        u.onend = done
        u.onerror = done
        window.speechSynthesis.speak(u)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [supported],
  )

  const cancel = useCallback(() => {
    if (!supported) return
    pending.current = 0
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  useEffect(() => () => cancel(), [cancel])

  return { supported, speaking, voices, setVoice, say, cancel }
}
