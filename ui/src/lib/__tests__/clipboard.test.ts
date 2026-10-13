import { describe, expect, it } from "vitest"
import { ACTION_LABEL, knownOffers, offerTitle } from "../clipboard"

describe("area de transferencia inteligente na tela", () => {
  it("rotulos em portugues simples", () => {
    expect(ACTION_LABEL.traduzir).toBe("Traduzir")
    expect(ACTION_LABEL.resumir).toBe("Resumir")
    expect(ACTION_LABEL.explicar).toBe("Explicar")
    expect(ACTION_LABEL.corrigir).toBe("Corrigir")
  })
  it("so mostra acoes conhecidas, sem repetir", () => {
    expect(knownOffers(["traduzir", "apagar", "traduzir", "resumir"])).toEqual(["traduzir", "resumir"])
    expect(knownOffers([])).toEqual([])
  })
  it("titulo curto e claro, sem jargao", () => {
    expect(offerTitle(["traduzir"])).toMatch(/copiou/i)
    expect(offerTitle(["traduzir"]).toLowerCase()).not.toContain("clipboard")
  })
})
