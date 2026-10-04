import { describe, expect, it } from "vitest"
import { chatErrorMessage, titleFrom } from "../chat"

describe("chatErrorMessage", () => {
  it("explica bloqueio de seguranca", () => {
    expect(chatErrorMessage(400, "Mensagem bloqueada por regras de segurança")).toMatch(/bloqueada/)
  })
  it("mapeia os status comuns sem jargao", () => {
    expect(chatErrorMessage(401)).toMatch(/sessão/)
    expect(chatErrorMessage(422)).toMatch(/inválida/)
    expect(chatErrorMessage(429)).toMatch(/Muitas/)
    expect(chatErrorMessage(503)).toMatch(/servidor/)
    expect(chatErrorMessage(418)).toMatch(/418/)
  })
})

describe("titleFrom", () => {
  it("encurta e normaliza espacos", () => {
    expect(titleFrom("  oi   tudo   bem  ")).toBe("oi tudo bem")
    expect(titleFrom("a".repeat(100))).toHaveLength(42)
    expect(titleFrom("   ")).toBe("Nova conversa")
  })
})
