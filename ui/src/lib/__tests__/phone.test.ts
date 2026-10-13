import { describe, expect, it } from "vitest"
import { expiresText, qrImageSrc } from "../phone"

describe("celular por QR", () => {
  it("so aceita SVG e entrega como imagem, nao como HTML", () => {
    expect(qrImageSrc("<svg xmlns='x'></svg>")).toMatch(/^data:image\/svg\+xml/)
    expect(qrImageSrc("<script>alert(1)</script>")).toBeNull()
    expect(qrImageSrc("")).toBeNull()
  })
  it("diz a validade em palavras simples", () => {
    expect(expiresText(300)).toBe("O código vale por 5 minutos e só uma vez.")
    expect(expiresText(60)).toBe("O código vale por 1 minuto e só uma vez.")
  })
})
