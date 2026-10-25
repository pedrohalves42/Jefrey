import { describe, expect, it } from "vitest"
import { worthTranscribing, addressed, WINDOW_MS } from "../voiceGate"

const T0 = 1_000_000

describe("voz: so o que e dirigido ao Jefrey entra no chat", () => {
  it("fala que chama o Jefrey pelo nome entra, sem o nome", () => {
    expect(addressed("Jefrey, que horas são?", T0, 0)).toEqual({ ok: true, text: "que horas são?" })
    expect(addressed("jefrei me lembra do dentista", T0, 0).ok).toBe(true)
  })

  it("conversa de fundo (sem o nome e fora da janela) e descartada", () => {
    expect(addressed("vou pegar um café agora", T0, 0).ok).toBe(false)
    expect(addressed("não sei, tanto faz", T0, T0 - WINDOW_MS - 1).ok).toBe(false)
  })

  it("dentro da janela depois de falar com o Jefrey, a resposta vale sem repetir o nome", () => {
    expect(addressed("sim, pode marcar", T0, T0 - 5_000)).toEqual({ ok: true, text: "sim, pode marcar" })
  })

  it("nome no meio da frase nao conta como chamado (pode ser a TV ou outra pessoa)", () => {
    expect(addressed("ontem o jefrey do filme foi bom", T0, 0).ok).toBe(false)
  })

  it("o Whisper escreve o nome de varios jeitos: todos valem", () => {
    for (const nome of ["Jeffrey", "Geferi", "Jéfri", "Jefery", "jeferi", "Jefrei"]) {
      expect(addressed(`${nome}, abre o youtube`, T0, 0)).toEqual({ ok: true, text: "abre o youtube" })
    }
  })
  it("'oi', 'ei' e 'bom dia' antes do nome tambem valem", () => {
    expect(addressed("Oi, Jefrey, me lembra de beber agua", T0, 0).text).toBe("me lembra de beber agua")
    expect(addressed("Bom dia Jefrey que horas sao", T0, 0).ok).toBe(true)
    expect(addressed("Ei ei Jefrey vem ca", T0, 0).ok).toBe(true)
  })
  it("palavras parecidas ou outros nomes nao disparam", () => {
    for (const f of ["Jéssica, vem aqui", "o café ficou ótimo", "Jeferson chegou", "Geraldo, atende"]) expect(addressed(f, T0, 0).ok).toBe(false)
  })
  it("a janela de conversa e de 45 segundos", () => {
    expect(WINDOW_MS).toBe(45_000)
  })
  it("frase vazia nunca entra", () => {
    expect(addressed("   ", T0, T0).ok).toBe(false)
    expect(addressed("Jefrey", T0, 0).ok).toBe(false)
  })
})

describe("portao antes da transcricao (ambiente nao chega ao Whisper)", () => {
  it("trecho curtinho demais e descartado sempre", () => {
    expect(worthTranscribing({ peak: 0.3, durationMs: 100 }, T0, T0)).toBe(false)
  })
  it("fora de conversa: fraco (TV ao longe) ou longo demais e descartado", () => {
    expect(worthTranscribing({ peak: 0.005, durationMs: 2000 }, T0, 0)).toBe(false)
    expect(worthTranscribing({ peak: 0.2, durationMs: 40_000 }, T0, 0)).toBe(false)
  })
  it("fora de conversa: voz perto e de tamanho normal passa (pode ser 'Jefrey, ...')", () => {
    expect(worthTranscribing({ peak: 0.15, durationMs: 3000 }, T0, 0)).toBe(true)
  })
  it("voz baixinha de microfone de notebook (nivel 0,02) nunca e perdida", () => {
    expect(worthTranscribing({ peak: 0.02, durationMs: 3000 }, T0, 0)).toBe(true)
  })
  it("conversa aberta: qualquer trecho de tamanho normal passa, ate o mais baixo", () => {
    expect(worthTranscribing({ peak: 0.005, durationMs: 3000 }, T0 + 5000, T0)).toBe(true)
    expect(worthTranscribing({ peak: 0.01, durationMs: 3000 }, T0 + WINDOW_MS + 1, T0)).toBe(false)
  })
})
