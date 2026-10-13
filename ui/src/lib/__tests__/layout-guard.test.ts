import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"
import { MAX_SHOWN } from "../../components/ReminderBanner"

describe("layout: nada passa da largura da tela", () => {
  it("o holograma e quadrado mas nunca mais largo que a caixa (bug no celular)", () => {
    const src = readFileSync(new URL("../../components/brain/HologramAvatar.tsx", import.meta.url), "utf8")
    expect(src).toContain("max-w-full")
    expect(src).toContain("object-contain")
    expect(src).not.toMatch(/aspectRatio:\s*"1 \/ 1"/)
  })
  it("pilha de lembretes tem limite", () => {
    expect(MAX_SHOWN).toBeLessThanOrEqual(3)
  })
})
