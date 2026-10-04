import { describe, expect, it } from "vitest"
import { DEFAULT_APPEARANCE, sanitizeAppearance } from "../appearance"

describe("sanitizeAppearance", () => {
  it("retorna o padrao para lixo", () => {
    expect(sanitizeAppearance(null)).toEqual(DEFAULT_APPEARANCE)
    expect(sanitizeAppearance("x")).toEqual(DEFAULT_APPEARANCE)
    expect(sanitizeAppearance(42)).toEqual(DEFAULT_APPEARANCE)
  })

  it("limita faixas numericas", () => {
    const a = sanitizeAppearance({ hue: 9999, intensity: -5, particles: 7 })
    expect(a.hue).toBe(360)
    expect(a.intensity).toBe(0)
    expect(a.particles).toBe(1)
  })

  it("rejeita forma desconhecida e tipos errados", () => {
    const a = sanitizeAppearance({ shape: "<script>", motion: "sim", visual: 1, hue: "azul" })
    expect(a.shape).toBe(DEFAULT_APPEARANCE.shape)
    expect(a.motion).toBe(DEFAULT_APPEARANCE.motion)
    expect(a.visual).toBe(DEFAULT_APPEARANCE.visual)
    expect(a.hue).toBe(DEFAULT_APPEARANCE.hue)
  })

  it("aceita valores validos e arredonda a cor", () => {
    expect(sanitizeAppearance({ hue: 268.6, shape: "reactor", motion: false, visual: false })).toMatchObject({
      hue: 269,
      shape: "reactor",
      motion: false,
      visual: false,
    })
  })

  it("ignora NaN e Infinity", () => {
    expect(sanitizeAppearance({ hue: NaN, intensity: Infinity }).hue).toBe(DEFAULT_APPEARANCE.hue)
    expect(sanitizeAppearance({ intensity: Infinity }).intensity).toBe(DEFAULT_APPEARANCE.intensity)
  })
})
