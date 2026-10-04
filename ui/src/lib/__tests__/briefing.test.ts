import { describe, expect, it } from "vitest"
import { ambientLabel, shouldShowBriefing } from "../briefing"

describe("proatividade", () => {
  it("texto sob o avatar quando ele faz algo sozinho", () => {
    expect(ambientLabel(null)).toBeNull()
    expect(ambientLabel({ studying: false, learning: false, topic: null })).toBeNull()
    expect(ambientLabel({ studying: true, learning: false, topic: "horta" })).toBe("Estudando horta…")
    expect(ambientLabel({ studying: true, learning: false, topic: null })).toBe("Estudando em segundo plano…")
    expect(ambientLabel({ studying: false, learning: true, topic: null })).toBe("Aprendendo com a conversa…")
    expect(ambientLabel({ studying: true, learning: true, topic: "x" })).toBe("Estudando x…")
  })
  it("o resumo so aparece se existe, nao foi visto e tem texto", () => {
    expect(shouldShowBriefing(null)).toBe(false)
    expect(shouldShowBriefing({ day: "d", text: "Bom dia!", seen: true })).toBe(false)
    expect(shouldShowBriefing({ day: "d", text: "  ", seen: false })).toBe(false)
    expect(shouldShowBriefing({ day: "d", text: "Bom dia!", seen: false })).toBe(true)
  })
})
