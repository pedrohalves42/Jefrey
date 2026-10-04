import { describe, expect, it } from "vitest"
import { apiMessage, budgetPercent, lastStudied, levelDots, parseGuide, safeHref, sourceLabel, usd } from "../studies"

describe("estudos", () => {
  it("pontinhos de nivel", () => {
    expect(levelDots(2)).toEqual([true, true, false, false, false])
    expect(levelDots(9)).toEqual([true, true, true, true, true])
    expect(levelDots(-1).some(Boolean)).toBe(false)
  })
  it("barra de gasto nunca passa de 100 e limite zero conta como cheio", () => {
    expect(budgetPercent(0.05, 0.1)).toBe(50)
    expect(budgetPercent(0.3, 0.1)).toBe(100)
    expect(budgetPercent(0, 0)).toBe(100)
  })
  it("dinheiro e tempo em portugues", () => {
    expect(usd(0.1)).toBe("US$ 0,10")
    const agora = new Date("2026-10-04T12:00:00Z")
    expect(lastStudied(null, agora)).toBe("ainda não estudei")
    expect(lastStudied("2026-10-04T08:00:00", agora)).toBe("estudei hoje")
    expect(lastStudied("2026-10-03T08:00:00", agora)).toBe("estudei ontem")
    expect(lastStudied("2026-10-01T08:00:00", agora)).toBe("estudei há 3 dias")
    expect(lastStudied("lixo", agora)).toBe("ainda não estudei")
    expect(sourceLabel("memoria")).toBe("pela sua memória")
  })
  it("so abre links http(s) (o texto veio da web)", () => {
    expect(safeHref("https://exemplo.com/a")).toBe("https://exemplo.com/a")
    expect(safeHref("javascript:alert(1)")).toBeNull()
    expect(safeHref("data:text/html,<b>")).toBeNull()
    expect(safeHref("não é link")).toBeNull()
  })
  it("transforma o guia em blocos simples", () => {
    const b = parseGuide("Resumo curto.\n\n**Passo a passo**\n1. Escolha o sol\n2. Regue\n\n**Dicas**\n- Comece pequeno")
    expect(b.map(x => x.type)).toEqual(["p", "h", "li", "li", "h", "li"])
    expect(b[5]!.text).toBe("• Comece pequeno")
    expect(b[1]!.text).toBe("Passo a passo")
  })
  it("mensagem de erro usa o texto do servidor ou um padrao", () => {
    expect(apiMessage({ ok: false, status: 409, data: { detail: "O limite de hoje acabou." } })).toBe("O limite de hoje acabou.")
    expect(apiMessage({ ok: false, status: 0, data: null })).toMatch(/Tente de novo/)
    expect(apiMessage({ ok: false, status: 422, data: { detail: ["x"] } }, "padrão")).toBe("padrão")
  })
})
