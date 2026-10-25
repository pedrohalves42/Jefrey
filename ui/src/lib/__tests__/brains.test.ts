import { describe, expect, it } from "vitest"
import { apiDetail, roleOf, routingSummary, steps, type BrainsState } from "../brains"

const names = { anthropic: "Claude", groq: "Groq", openrouter: "OpenRouter" }
const st = (brains: BrainsState["brains"]): BrainsState => ({ brains, catalog: [], max: 4 })

describe("cerebros na tela", () => {
  it("explica em portugues simples como os cerebros trabalham juntos", () => {
    expect(routingSummary(null, names)).toMatch(/Nenhum cérebro conectado/)
    expect(routingSummary(st([{ id: "anthropic", role: "principal", model: "m" }]), names)).toMatch(/pensando com Claude.*reserva/)
    const dois = routingSummary(st([{ id: "anthropic", role: "principal", model: "m" }, { id: "groq", role: "reserva", model: "m" }]), names)
    expect(dois).toBe("O Jefrey pensa com Claude. Se falhar ou acabar o crédito, ele usa sozinho: Groq.")
  })
  it("papel de cada cartao", () => {
    const s = st([{ id: "anthropic", role: "principal", model: "m" }, { id: "groq", role: "reserva", model: "m" }])
    expect(roleOf(s, "anthropic")).toBe("principal")
    expect(roleOf(s, "groq")).toBe("reserva")
    expect(roleOf(s, "xai")).toBeNull()
    expect(roleOf(null, "groq")).toBeNull()
  })
  it("passo a passo sem jargao", () => {
    const t = steps("Groq").join(" ").toLowerCase()
    expect(t).toContain("groq")
    for (const j of ["api", "token", "endpoint", "modelo", "provedor"]) expect(t).not.toContain(j)
    expect(steps("X")).toHaveLength(3)
  })
  it("mensagem de erro vem do servidor ou e um padrao", () => {
    expect(apiDetail({ ok: false, status: 422, data: { detail: "O serviço recusou esse código." } }, "padrão")).toBe("O serviço recusou esse código.")
    expect(apiDetail({ ok: false, status: 0, data: null }, "padrão")).toBe("padrão")
  })
})
