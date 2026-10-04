/** Texto e cor do botao grande de voz. Uma frase curta que diz o que esta acontecendo agora. */

export type VoiceTone = "idle" | "listening" | "hearing" | "working" | "speaking" | "preparing"

export type VoiceInputs = {
  micOn: boolean
  listener: "idle" | "listening" | "hearing" | "transcribing" | "error"
  streaming: boolean
  speaking: boolean
  preparing: boolean
}

export function voiceView(i: VoiceInputs): { label: string; hint: string; tone: VoiceTone } {
  if (i.preparing) return { label: "Preparando a minha audição…", hint: "Só na primeira vez. Pode demorar alguns minutos.", tone: "preparing" }
  if (i.speaking) return { label: "Falando… toque para me interromper", hint: "", tone: "speaking" }
  if (i.streaming) return { label: "Pensando…", hint: "", tone: "working" }
  if (i.listener === "transcribing") return { label: "Entendendo o que você disse…", hint: "", tone: "working" }
  if (i.listener === "hearing") return { label: "Estou ouvindo você…", hint: "", tone: "hearing" }
  if (i.micOn || i.listener === "listening") return { label: "Pode falar, estou ouvindo", hint: "Toque de novo para parar.", tone: "listening" }
  return { label: "Toque aqui e fale comigo", hint: "", tone: "idle" }
}
