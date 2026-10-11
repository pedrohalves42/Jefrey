import { describe, expect, it } from "vitest"
import { feedbackPayload, FEEDBACK_LABEL } from "../feedback"

describe("feedback das respostas (👍/👎)", () => {
  it("monta o corpo que a API espera, sem o texto da conversa", () => {
    expect(feedbackPayload("m1", "up")).toEqual({ message_id: "m1", value: "up", note: "" })
    expect(feedbackPayload("m2", "down", "inventou a fonte")).toEqual({ message_id: "m2", value: "down", note: "inventou a fonte" })
  })
  it("corta nota longa em 300 caracteres e id em 120", () => {
    const p = feedbackPayload("x".repeat(200), "down", "n".repeat(500))
    expect(p.message_id).toHaveLength(120)
    expect(p.note).toHaveLength(300)
  })
  it("rotulos em portugues simples para quem usa leitor de tela", () => {
    expect(FEEDBACK_LABEL.up).toBe("Gostei da resposta")
    expect(FEEDBACK_LABEL.down).toBe("Não gostei da resposta")
  })
})
