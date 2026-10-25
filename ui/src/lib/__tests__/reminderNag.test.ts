import { describe, expect, it } from "vitest"
import { isQuietHour, MAX_SPOKEN, REPEAT_EVERY_MS, shouldSpeak, spokenText } from "../reminderNag"

describe("lembrete falado que repete", () => {
  it("fala assim que aparece", () => {
    expect(shouldSpeak({ spoken: 0, lastAt: null }, 1000, 10)).toBe(true)
  })
  it("repete so depois de 5 minutos", () => {
    expect(shouldSpeak({ spoken: 1, lastAt: 0 }, REPEAT_EVERY_MS - 1, 10)).toBe(false)
    expect(shouldSpeak({ spoken: 1, lastAt: 0 }, REPEAT_EVERY_MS, 10)).toBe(true)
  })
  it("para depois de 3 vezes", () => {
    expect(shouldSpeak({ spoken: MAX_SPOKEN, lastAt: 0 }, REPEAT_EVERY_MS * 9, 10)).toBe(false)
  })
  it("nunca fala de madrugada (22h as 8h)", () => {
    expect([22, 23, 0, 7].every(isQuietHour)).toBe(true)
    expect([8, 12, 21].some(isQuietHour)).toBe(false)
    expect(shouldSpeak({ spoken: 0, lastAt: null }, 1, 23)).toBe(false)
  })
  it("a primeira fala e curta; as seguintes reforcam", () => {
    expect(spokenText("ligar pro dentista", 0)).toBe("Lembrete: ligar pro dentista.")
    expect(spokenText("ligar pro dentista", 1)).toContain("reforçando")
  })
})
