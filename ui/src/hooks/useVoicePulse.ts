import { useEffect, type RefObject } from "react"
import { currentLevel, hasLevelSource } from "@/lib/voiceLevel"

/** Evento disparado a cada palavra falada (useSpeaker): o avatar "bate" no ritmo da fala. */
export const WORD_EVENT = "jefrey-word"

/** Envelope do pulso (0 a 1): sobe na palavra, desce suave; sem eventos de palavra, ondula devagar enquanto fala. */
export function nextPulse(prev: number, speaking: boolean, word: boolean, t: number, measured?: number): number {
  if (!speaking) return prev * 0.85 < 0.01 ? 0 : prev * 0.85
  if (measured !== undefined) return Math.max(measured, prev * 0.85) // volume REAL da voz (audio da nuvem/local): sobe junto e desce suave
  const base = 0.3 + 0.25 * Math.abs(Math.sin(t / 240)) // fala sem marcador de palavra (algumas vozes): ondula sozinho
  return word ? 1 : Math.max(base, prev * 0.9)
}

/** Aplica o pulso direto no elemento (sem re-renderizar a tela): escala e brilho acompanham a voz. */
export function useVoicePulse(ref: RefObject<HTMLElement | null>, speaking: boolean, onLevel?: (v: number) => void): void {
  useEffect(() => {
    let raf = 0
    let level = 0
    let word = false
    let lastEmit = 0
    const onWord = () => {
      word = true
    }
    window.addEventListener(WORD_EVENT, onWord)
    const tick = (t: number) => {
      level = nextPulse(level, speaking, word, t, hasLevelSource() ? currentLevel() : undefined)
      word = false
      if (onLevel && t - lastEmit > 66) {
        lastEmit = t
        onLevel(level) // ~15x por segundo: o cerebro 3D reage ao volume sem re-renderizar a tela inteira
      }
      const el = ref.current
      if (el) {
        el.style.transform = level > 0 ? `scale(${(1 + level * 0.14).toFixed(4)})` : ""
        el.style.setProperty("--pulse", level.toFixed(3))
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      window.removeEventListener(WORD_EVENT, onWord)
      cancelAnimationFrame(raf)
    }
  }, [ref, speaking, onLevel])
}
