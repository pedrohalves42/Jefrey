import { describe, expect, it } from "vitest"
import { offerText, shouldOffer } from "../voiceOffer"

describe("oferta da voz local", () => {
  it("so depois de 2 falhas seguidas da nuvem", () => {
    expect(shouldOffer({ failures: 1, localInstalled: false, dismissed: false })).toBe(false)
    expect(shouldOffer({ failures: 2, localInstalled: false, dismissed: false })).toBe(true)
  })
  it("nao oferece se ja esta instalada ou se a pessoa dispensou", () => {
    expect(shouldOffer({ failures: 5, localInstalled: true, dismissed: false })).toBe(false)
    expect(shouldOffer({ failures: 5, localInstalled: false, dismissed: true })).toBe(false)
  })
  it("texto diz o tamanho e que e uma vez so", () => {
    expect(offerText(60)).toContain("60 MB")
    expect(offerText(60)).toContain("uma vez só")
  })
})
