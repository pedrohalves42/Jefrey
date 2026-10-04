import { describe, expect, it } from "vitest"
import { MODE_LABEL, minutesLeft, sortChats, whyText, WA_RISK_NOTE, type WaChat } from "../wa"

const c = (id: string, mode: WaChat["mode"], last = "2026-10-04T10:00:00"): WaChat => ({ id, display: id, mode, last_seen: last })

describe("WhatsApp na tela", () => {
  it("conversas novas aparecem primeiro, depois perguntar, responder sozinho e ignoradas", () => {
    const ordem = sortChats([c("a", "off"), c("b", "auto"), c("c", "pending"), c("d", "ask"), c("e", "pending", "2026-10-04T11:00:00")]).map(x => x.id)
    expect(ordem).toEqual(["e", "c", "d", "b", "a"])
  })
  it("motivo em linguagem simples", () => {
    expect(whyText("dinheiro, link")).toBe("Quero confirmar com você: dinheiro, link.")
    expect(whyText("")).toBe("Quero confirmar com você antes de enviar.")
  })
  it("minutos que faltam no codigo", () => {
    expect(minutesLeft(600, 0)).toBe(10)
    expect(minutesLeft(600, 61)).toBe(9)
    expect(minutesLeft(600, 700)).toBe(0)
  })
  it("textos sem jargao e com o aviso de risco", () => {
    expect(Object.values(MODE_LABEL).join(" ").toLowerCase()).not.toMatch(/token|api|webhook/)
    expect(WA_RISK_NOTE).toMatch(/bloquear/)
  })
})
