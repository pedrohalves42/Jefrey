import { describe, expect, it } from "vitest"
import { voiceView, type VoiceInputs } from "../voiceMode"

const base: VoiceInputs = { micOn: false, listener: "idle", streaming: false, speaking: false, preparing: false }

describe("botao grande de voz", () => {
  it("parado: convida a falar", () => {
    expect(voiceView(base)).toMatchObject({ tone: "idle", label: "Toque aqui e fale comigo" })
  })
  it("ouvindo e escutando a fala", () => {
    expect(voiceView({ ...base, micOn: true, listener: "listening" }).tone).toBe("listening")
    expect(voiceView({ ...base, micOn: true, listener: "hearing" }).tone).toBe("hearing")
  })
  it("entendendo, pensando e falando, nessa ordem de prioridade", () => {
    expect(voiceView({ ...base, micOn: true, listener: "transcribing" }).tone).toBe("working")
    expect(voiceView({ ...base, micOn: true, streaming: true }).label).toBe("Pensando…")
    const f = voiceView({ ...base, micOn: true, streaming: true, speaking: true })
    expect(f.tone).toBe("speaking")
    expect(f.label).toMatch(/interromper/)
  })
  it("preparando a audicao vem primeiro e explica que e so a primeira vez", () => {
    const p = voiceView({ ...base, preparing: true, speaking: true })
    expect(p.tone).toBe("preparing")
    expect(p.hint).toMatch(/primeira vez/)
  })
  it("nenhuma frase usa jargao", () => {
    const todas = [
      voiceView(base), voiceView({ ...base, preparing: true }), voiceView({ ...base, speaking: true }), voiceView({ ...base, streaming: true }),
      voiceView({ ...base, listener: "transcribing" }), voiceView({ ...base, listener: "hearing" }), voiceView({ ...base, micOn: true }),
    ].map(v => `${v.label} ${v.hint}`.toLowerCase()).join(" ")
    for (const j of ["whisper", "modelo", "stt", "token", "api", "microfone ativo"]) expect(todas).not.toContain(j)
  })
})
