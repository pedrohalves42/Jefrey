import { useCallback, useEffect, useRef, useState } from "react"
import { speakable } from "@/lib/voice/sentences"
import { authedFetch } from "@/lib/session"

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

const VOICE_KEY = "jefrey_voice_uri"
export const CLOUD_VOICE = "cloud" // escolha especial: voz natural na nuvem (conta do ChatGPT)
const CLOUD_CHUNK = 400

/** Nota de naturalidade: vozes neurais ("Natural", "Online", "Neural", Google) soam bem menos roboticas que as antigas do Windows. */
export function voiceScore(v: { name: string; lang: string }): number {
  const n = v.name.toLowerCase()
  let s = 0
  if (/natural|neural/.test(n)) s += 100
  if (/online|google/.test(n)) s += 50
  if (v.lang.toLowerCase() === "pt-br") s += 20
  if (/desktop/.test(n)) s -= 10
  return s
}

export function bestVoice<T extends { name: string; lang: string }>(list: T[]): T | undefined {
  return [...list].sort((a, b) => voiceScore(b) - voiceScore(a))[0]
}

function savedVoice(): string | null {
  try {
    return localStorage.getItem(VOICE_KEY)
  } catch {
    return null
  }
}

/**
 * Fala com as vozes instaladas no sistema (local: nada sai do computador).
 * `say` enfileira frases; `cancel` interrompe tudo na hora (interrupcao pelo usuario).
 */
export function useSpeaker() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window
  const [speaking, setSpeaking] = useState(false)
  const [voices, setVoices] = useState<SpeakerVoice[]>([])
  const pending = useRef(0)
  const voiceUri = useRef<string | null>(savedVoice())
  const [voiceChoice, setVoiceChoice] = useState<string | null>(voiceUri.current)
  const [cloudOk, setCloudOk] = useState(false)
  const cloudOkRef = useRef(false)
  const gen = useRef(0) // cada cancel() invalida a fila de audio da nuvem
  const queue = useRef<Promise<void>>(Promise.resolve())
  const audio = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    let alive = true
    void (async () => {
      try {
        const r = await authedFetch("/voice/cloud")
        const d = r.ok ? ((await r.json()) as { available?: boolean }) : null
        if (alive && d?.available) {
          setCloudOk(true)
          cloudOkRef.current = true
        }
      } catch {
        /* sem nuvem: usa as vozes do computador */
      }
    })()
    return () => {
      alive = false
    }
  }, [])

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
    setVoiceChoice(uri)
    try {
      if (uri) localStorage.setItem(VOICE_KEY, uri)
      else localStorage.removeItem(VOICE_KEY)
    } catch {
      /* sem armazenamento: vale so ate fechar */
    }
  }, [])

  const pickVoice = (): SpeechSynthesisVoice | undefined => {
    const all = window.speechSynthesis.getVoices()
    return all.find(v => v.voiceURI === voiceUri.current) || bestVoice(all.filter(v => v.lang.toLowerCase().startsWith("pt")))
  }

  /** Automatica = nuvem quando o ChatGPT esta conectado; a pessoa pode escolher uma voz do computador. */
  const wantsCloud = () => cloudOkRef.current && (voiceUri.current === null || voiceUri.current === CLOUD_VOICE)

  const playCloud = async (piece: string, myGen: number): Promise<boolean> => {
    try {
      const r = await authedFetch("/voice/cloud/speak", { method: "POST", body: JSON.stringify({ text: piece }) })
      if (!r.ok) {
        if (r.status === 409) cloudOkRef.current = false // sem conta/saldo: cai para a voz do computador nas proximas falas
        return false
      }
      const blob = await r.blob()
      if (myGen !== gen.current) return true // cancelado enquanto baixava
      const url = URL.createObjectURL(blob)
      const a = new Audio(url)
      audio.current = a
      let pulse = 0
      await new Promise<void>(resolve => {
        const end = () => {
          window.clearInterval(pulse)
          URL.revokeObjectURL(url)
          resolve()
        }
        a.onended = end
        a.onerror = end
        a.onpause = () => {
          if (a.ended || myGen !== gen.current) end()
        }
        pulse = window.setInterval(() => window.dispatchEvent(new Event("jefrey-word")), 320) // sem marcador de palavra: bate no ritmo medio da fala
        void a.play().catch(end)
      })
      return true
    } catch {
      return false
    }
  }

  const sayBrowser = (piece: string) => {
    if (!supported) return
    {
      {
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
    }
  }

  const say = useCallback(
    (raw: string) => {
      const text = speakable(raw)
      if (!text) return
      if (wantsCloud()) {
        const myGen = gen.current
        pending.current += 1
        setSpeaking(true)
        const pieces = chunkForSpeech(text, CLOUD_CHUNK)
        queue.current = queue.current.then(async () => {
          for (const piece of pieces) {
            if (myGen !== gen.current) break
            const ok = await playCloud(piece, myGen)
            if (!ok && myGen === gen.current) sayBrowser(piece) // falhou: o computador fala no lugar
          }
          if (myGen === gen.current) {
            pending.current = Math.max(0, pending.current - 1)
            if (pending.current === 0) setSpeaking(false)
          }
        })
        return
      }
      for (const piece of chunkForSpeech(text)) sayBrowser(piece)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [supported],
  )

  const cancel = useCallback(() => {
    gen.current += 1
    queue.current = Promise.resolve()
    audio.current?.pause()
    audio.current = null
    pending.current = 0
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  useEffect(() => () => cancel(), [cancel])

  const sorted = [...voices].sort((a, b) => voiceScore(b) - voiceScore(a))
  return { supported: supported || cloudOk, speaking, voices: sorted, voiceChoice, cloudOk, setVoice, say, cancel }
}
