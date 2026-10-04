import { describe, expect, it } from "vitest"
import { fitSize, glitchBands, hslToRgb, MAX_FILE_BYTES, smoothstep, tintImageData, validateImageFile } from "../holo"
import { greeting } from "../greeting"
import { DEFAULT_APPEARANCE, sanitizeAppearance } from "../appearance"

describe("validateImageFile", () => {
  it("aceita formatos comuns", () => {
    for (const type of ["image/png", "image/jpeg", "image/webp", "image/gif"]) expect(validateImageFile({ type, size: 1000 })).toBeNull()
  })

  it("recusa o que nao e imagem segura, vazio e gigante", () => {
    expect(validateImageFile({ type: "image/svg+xml", size: 1000 })).toMatch(/PNG, JPG/)
    expect(validateImageFile({ type: "application/pdf", size: 10 })).not.toBeNull()
    expect(validateImageFile({ type: "image/png", size: 0 })).toMatch(/vazio/)
    expect(validateImageFile({ type: "image/png", size: MAX_FILE_BYTES + 1 })).toMatch(/grande demais/)
  })
})

describe("fitSize", () => {
  it("reduz mantendo a proporcao e nao amplia", () => {
    expect(fitSize(2000, 1000, 640)).toEqual({ w: 640, h: 320 })
    expect(fitSize(300, 600, 640)).toEqual({ w: 300, h: 600 })
    expect(fitSize(1000, 4000, 400)).toEqual({ w: 100, h: 400 })
  })

  it("entradas invalidas viram 1x1", () => {
    expect(fitSize(0, 10, 640)).toEqual({ w: 1, h: 1 })
    expect(fitSize(NaN, 10, 640)).toEqual({ w: 1, h: 1 })
  })
})

describe("cores", () => {
  it("smoothstep limita em 0 e 1", () => {
    expect(smoothstep(0.2, 0.6, 0)).toBe(0)
    expect(smoothstep(0.2, 0.6, 1)).toBe(1)
    expect(smoothstep(0.2, 0.6, 0.4)).toBeCloseTo(0.5, 5)
    expect(smoothstep(0.5, 0.5, 0.2)).toBe(0)
  })

  it("hslToRgb nos pontos conhecidos", () => {
    expect(hslToRgb(0, 1, 0.5)).toEqual([255, 0, 0])
    expect(hslToRgb(120, 1, 0.5)).toEqual([0, 255, 0])
    expect(hslToRgb(240, 1, 0.5)).toEqual([0, 0, 255])
    expect(hslToRgb(-120, 1, 0.5)).toEqual([0, 0, 255]) // angulo negativo da a volta
  })
})

describe("tintImageData", () => {
  const px = (r: number, g: number, b: number, a = 255) => new Uint8ClampedArray([r, g, b, a])

  it("fundo preto fica transparente e o claro fica opaco na cor do tema", () => {
    const dark = px(0, 0, 0)
    tintImageData(dark, 191, 0.12, false)
    expect(dark[3]).toBe(0)
    const light = px(255, 255, 255)
    tintImageData(light, 191, 0.12, false)
    expect(light[3]).toBe(255)
    expect(light[2]! > light[0]!).toBe(true) // matiz 191 = ciano: mais azul que vermelho
  })

  it("invert troca fundo claro por transparente", () => {
    const white = px(255, 255, 255)
    tintImageData(white, 191, 0.12, true)
    expect(white[3]).toBe(0)
    const black = px(0, 0, 0)
    tintImageData(black, 191, 0.12, true)
    expect(black[3]).toBe(255)
  })

  it("respeita a transparencia original e nao passa do fim do buffer", () => {
    const p = px(255, 255, 255, 0)
    tintImageData(p, 40, 0.1, false)
    expect(p[3]).toBe(0)
    const odd = new Uint8ClampedArray(6) // tamanho que nao e multiplo de 4
    expect(() => tintImageData(odd, 40, 0.1, false)).not.toThrow()
  })

  it("corte maior apaga mais", () => {
    const mid = (cut: number) => {
      const p = px(100, 100, 100)
      tintImageData(p, 191, cut, false)
      return p[3]!
    }
    expect(mid(0.05)).toBeGreaterThan(mid(0.4))
  })
})

describe("glitchBands", () => {
  it("sem falha configurada nunca gera faixas", () => {
    expect(glitchBands(() => 0, 0, 512)).toEqual([])
  })

  it("e deterministico e fica dentro da imagem", () => {
    const seq = [0.0, 0.9, 0.5, 0.3, 0.7, 0.2, 0.8, 0.1, 0.6, 0.4]
    let i = 0
    const rand = () => seq[i++ % seq.length]!
    const bands = glitchBands(rand, 1, 512)
    expect(bands.length).toBeGreaterThan(0)
    for (const b of bands) {
      expect(b.y).toBeGreaterThanOrEqual(0)
      expect(b.y + b.h).toBeLessThanOrEqual(512)
      expect(Math.abs(b.dx)).toBeLessThanOrEqual(40)
    }
  })

  it("quase sempre nao falha (efeito raro)", () => {
    expect(glitchBands(() => 0.99, 1, 512)).toEqual([])
  })
})

describe("saudacao", () => {
  it("pelo horario e com nome", () => {
    expect(greeting(8, "Pedro")).toBe("Bom dia, Pedro.")
    expect(greeting(15, "Pedro")).toBe("Boa tarde, Pedro.")
    expect(greeting(22, "Pedro")).toBe("Boa noite, Pedro.")
    expect(greeting(3, null)).toBe("Boa noite.")
    expect(greeting(NaN, "  Ana ")).toBe("Boa tarde, Ana.")
  })
})

describe("aparencia do holograma", () => {
  it("padroes e validacao", () => {
    expect(DEFAULT_APPEARANCE.holoScan).toBeGreaterThan(0)
    const a = sanitizeAppearance({ shape: "hologram", holoScan: 5, holoGlitch: -2, holoCut: 99, holoInvert: "sim" })
    expect(a.shape).toBe("hologram")
    expect(a.holoScan).toBe(1)
    expect(a.holoGlitch).toBe(0)
    expect(a.holoCut).toBe(0.9)
    expect(a.holoInvert).toBe(false)
  })

  it("forma desconhecida volta ao padrao", () => {
    expect(sanitizeAppearance({ shape: "dragao" }).shape).toBe(DEFAULT_APPEARANCE.shape)
  })
})
