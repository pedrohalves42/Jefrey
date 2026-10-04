import { describe, expect, it } from "vitest"
import { chunkForSpeech } from "../useSpeaker"
import { micErrorMessage } from "../useListener"

describe("chunkForSpeech", () => {
  it("frase curta fica inteira", () => {
    expect(chunkForSpeech("Olá, tudo bem?")).toEqual(["Olá, tudo bem?"])
  })

  it("quebra frases longas sem passar do limite e sem perder texto", () => {
    const text = Array.from({ length: 40 }, (_, i) => `palavra${i}`).join(" ")
    const parts = chunkForSpeech(text, 60)
    expect(parts.length).toBeGreaterThan(3)
    expect(parts.every(p => p.length <= 60)).toBe(true)
    expect(parts.join(" ")).toBe(text)
  })

  it("prefere cortar em virgula", () => {
    const parts = chunkForSpeech("primeira parte da frase, segunda parte da frase que continua bastante", 40)
    expect(parts[0]).toBe("primeira parte da frase,")
  })

  it("texto sem espacos (url, base64) ainda e cortado", () => {
    const parts = chunkForSpeech("x".repeat(500), 100)
    expect(parts.every(p => p.length <= 100)).toBe(true)
    expect(parts.join("")).toBe("x".repeat(500))
  })

  it("vazio devolve lista vazia", () => {
    expect(chunkForSpeech("   ")).toEqual([])
  })
})

describe("micErrorMessage", () => {
  it("explica cada causa em portugues", () => {
    expect(micErrorMessage(new DOMException("x", "NotAllowedError"))).toMatch(/bloqueou/)
    expect(micErrorMessage(new DOMException("x", "NotFoundError"))).toMatch(/nenhum microfone/)
    expect(micErrorMessage(new DOMException("x", "NotReadableError"))).toMatch(/em uso/)
    expect(micErrorMessage(new Error("?"))).toMatch(/Não consegui usar/)
  })
})
