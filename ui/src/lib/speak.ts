/** Fala um texto com a voz do aparelho (portugues). Usado para ler telas em voz alta e como reserva da voz do Jefrey. */

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined"
}

/** Tira simbolos que a voz le errado ("*", "#", links) e quebra em frases curtas. */
export function speechChunks(text: string, max = 220): string[] {
  const clean = (text || "")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[*_`#>~|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
  if (!clean) return []
  const out: string[] = []
  for (const sentence of clean.split(/(?<=[.!?…])\s+/)) {
    let s = sentence.trim()
    while (s.length > max) {
      const cut = s.lastIndexOf(" ", max)
      const at = cut > 40 ? cut : max
      out.push(s.slice(0, at).trim())
      s = s.slice(at).trim()
    }
    if (s) out.push(s)
  }
  return out
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel()
}

/** Le tudo (sem cortar). Devolve uma promessa que termina quando acaba ou e interrompida. */
export function speak(text: string, opts?: { rate?: number; onStart?: () => void; onEnd?: () => void }): Promise<void> {
  if (!canSpeak()) return Promise.resolve()
  const chunks = speechChunks(text)
  if (!chunks.length) return Promise.resolve()
  stopSpeaking()
  const voices = window.speechSynthesis.getVoices()
  const voice = voices.find(v => /pt[-_]BR/i.test(v.lang)) ?? voices.find(v => /^pt/i.test(v.lang))
  return new Promise<void>(resolve => {
    let i = 0
    const next = () => {
      if (i >= chunks.length) {
        opts?.onEnd?.()
        resolve()
        return
      }
      const u = new SpeechSynthesisUtterance(chunks[i++])
      u.lang = voice?.lang ?? "pt-BR"
      if (voice) u.voice = voice
      u.rate = opts?.rate ?? 0.95
      if (i === 1) u.onstart = () => opts?.onStart?.()
      u.onend = next
      u.onerror = () => {
        opts?.onEnd?.()
        resolve()
      }
      window.speechSynthesis.speak(u)
    }
    next()
  })
}
