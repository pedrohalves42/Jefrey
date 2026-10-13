import { describe, expect, it } from "vitest"
import { addressed, WINDOW_MS } from "../voiceGate"

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

  it("frase vazia nunca entra", () => {
    expect(addressed("   ", T0, T0).ok).toBe(false)
    expect(addressed("Jefrey", T0, 0).ok).toBe(false)
  })
})
