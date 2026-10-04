import { useCallback, useEffect, useRef, useState } from "react"
import { authedFetch } from "@/lib/session"
import { Endpointer } from "@/lib/voice/vad"

export type ListenerState = "idle" | "listening" | "hearing" | "transcribing" | "error"

function pickMime(): string | undefined {
  const opts = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
  return opts.find(m => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m))
}

function rmsOf(buf: Float32Array): number {
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += (buf[i] as number) * (buf[i] as number)
  return Math.sqrt(sum / Math.max(1, buf.length))
}

export function micErrorMessage(e: unknown): string {
  const name = e instanceof DOMException ? e.name : ""
  if (name === "NotAllowedError" || name === "SecurityError") return "O navegador bloqueou o microfone. Clique no cadeado ao lado do endereço, escolha Microfone e marque Permitir."
  if (name === "NotFoundError" || name === "OverconstrainedError") return "Não encontrei nenhum microfone neste computador. Conecte um fone com microfone ou escreva a sua mensagem."
  if (name === "NotReadableError") return "O microfone está em uso por outro programa."
  return "Não consegui usar o microfone."
}

type Options = {
  /** texto transcrito (so chamado se houver texto) */
  onTranscript: (text: string) => void
  /** o usuario comecou a falar (use para interromper a fala do Jefrey) */
  onSpeechStart?: () => void
  /** nivel de voz 0-1 para animar a visualizacao */
  onLevel?: (level: number) => void
  /** o audio nao rendeu texto (ruido, fala curta): a tela pode dizer "nao entendi, pode repetir?" */
  onUnclear?: () => void
}

/**
 * Ouve pelo microfone, detecta o fim da fala no proprio navegador (nada e enviado antes disso) e
 * transcreve com o Whisper LOCAL do servidor. Sem Web Speech API (que mandaria o audio ao Google).
 */
export function useListener({ onTranscript, onSpeechStart, onLevel, onUnclear }: Options) {
  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined"
  const [state, setState] = useState<ListenerState>("idle")
  const [error, setError] = useState<string | null>(null)
  const cleanup = useRef<(() => void) | null>(null)
  const starting = useRef(false)
  const cb = useRef({ onTranscript, onSpeechStart, onLevel, onUnclear })
  cb.current = { onTranscript, onSpeechStart, onLevel, onUnclear }

  const stop = useCallback(() => {
    cleanup.current?.()
    cleanup.current = null
    cb.current.onLevel?.(0)
    setState(s => (s === "transcribing" ? s : "idle"))
  }, [])

  const transcribe = useCallback(async (blob: Blob) => {
    setState("transcribing")
    try {
      const fd = new FormData()
      fd.append("audio", blob, "voz.webm")
      const r = await authedFetch("/stt", { method: "POST", body: fd })
      if (r.status === 400) {
        // ruido ou fala que nao deu para entender: nao e erro, e so pedir de novo
        setState("idle")
        cb.current.onUnclear?.()
        return
      }
      if (!r.ok) {
        setError(r.status === 429 ? "Muitos pedidos de voz seguidos. Espere um pouco." : "Não consegui transcrever o áudio agora.")
        setState("error")
        return
      }
      const text = String((await r.json()).transcript ?? "").trim()
      setState("idle")
      if (text) cb.current.onTranscript(text)
    } catch {
      setError("Sem conexão com o Jefrey para transcrever.")
      setState("error")
    }
  }, [])

  const start = useCallback(async () => {
    if (!supported || cleanup.current || starting.current) return
    starting.current = true
    setError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, // AEC: nao ouve a propria voz
      })
    } catch (e) {
      starting.current = false
      setError(micErrorMessage(e))
      setState("error")
      return
    }
    const ctx = new AudioContext()
    const src = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    src.connect(analyser)
    const buf = new Float32Array(analyser.fftSize)
    const mime = pickMime()
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    const chunks: Blob[] = []
    rec.ondataavailable = e => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    const ep = new Endpointer()
    let heard = false
    let finished = false

    const release = () => {
      window.clearInterval(timer)
      stream.getTracks().forEach(t => t.stop())
      void ctx.close().catch(() => {})
      cleanup.current = null
    }
    rec.onstop = () => {
      release()
      cb.current.onLevel?.(0)
      if (heard && chunks.length) void transcribe(new Blob(chunks, { type: rec.mimeType || "audio/webm" }))
      else setState("idle")
    }
    const finish = () => {
      if (finished) return
      finished = true
      if (rec.state !== "inactive") rec.stop()
      else rec.onstop?.(new Event("stop"))
    }
    const timer = window.setInterval(() => {
      analyser.getFloatTimeDomainData(buf)
      const rms = rmsOf(buf)
      cb.current.onLevel?.(Math.min(1, rms * 8))
      const ev = ep.update(rms, performance.now())
      if (ev === "speech_start") {
        heard = true
        setState("hearing")
        cb.current.onSpeechStart?.()
      } else if (ev === "speech_end" || ev === "timeout") {
        finish()
      }
    }, 50)

    cleanup.current = () => {
      finished = true
      heard = false // cancelado pelo usuario: nao transcreve
      if (rec.state !== "inactive") rec.stop()
      else release()
    }
    rec.start()
    starting.current = false
    setState("listening")
  }, [supported, transcribe])

  useEffect(() => () => cleanup.current?.(), [])

  return { supported, state, error, start, stop }
}
