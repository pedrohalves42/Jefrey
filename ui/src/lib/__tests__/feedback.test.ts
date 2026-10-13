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
  it("so o 👎 leva a pergunta e a resposta (para virar caso de teste local); o 👍 nunca leva texto", () => {
    const down = feedbackPayload("m3", "down", "", "Qual a capital da Austrália?", "É Sydney.")
    expect(down).toMatchObject({ question: "Qual a capital da Austrália?", answer: "É Sydney." })
    const up = feedbackPayload("m4", "up", "", "pergunta", "resposta")
    expect(up).not.toHaveProperty("question")
    expect(up).not.toHaveProperty("answer")
    expect(feedbackPayload("m5", "down", "", "p".repeat(900), "r".repeat(3000)).question).toHaveLength(500)
    expect(feedbackPayload("m5", "down", "", "p", "r".repeat(3000)).answer).toHaveLength(2000)
  })
  it("rotulos em portugues simples para quem usa leitor de tela", () => {
    expect(FEEDBACK_LABEL.up).toBe("Gostei da resposta")
    expect(FEEDBACK_LABEL.down).toBe("Não gostei da resposta")
  })
})
