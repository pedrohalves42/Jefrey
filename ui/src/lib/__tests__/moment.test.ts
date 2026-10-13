import { describe, expect, it } from "vitest"
import { momentActions, ALL_ACTIONS } from "../moment"

describe("acoes faceis por momento do dia", () => {
  it("de manha: resumo do dia primeiro", () => {
    expect(momentActions(8)[0].id).toBe("resumo")
  })
  it("a tarde: mensagens e agenda na frente", () => {
    const ids = momentActions(14).slice(0, 3).map(a => a.id)
    expect(ids).toContain("whatsapp")
    expect(ids).toContain("agenda")
  })
  it("a noite: lembretes de amanha e musica", () => {
    const ids = momentActions(21).slice(0, 3).map(a => a.id)
    expect(ids).toContain("lembretes")
    expect(ids).toContain("musica")
  })
  it("nenhuma acao some: so a ordem muda, sem repetir", () => {
    for (const h of [0, 6, 13, 19, 23]) {
      const ids = momentActions(h).map(a => a.id)
      expect(new Set(ids).size).toBe(ids.length)
      expect(ids.length).toBe(ALL_ACTIONS.length)
    }
  })
  it("cada acao tem rotulo e um pedido ou um destino", () => {
    for (const a of ALL_ACTIONS) {
      expect(a.label.length).toBeGreaterThan(2)
      expect(Boolean(a.ask) || Boolean(a.to) || a.id === "resumo").toBe(true)
    }
  })
})
