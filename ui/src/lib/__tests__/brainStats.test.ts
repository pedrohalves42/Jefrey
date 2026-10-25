import { describe, expect, it } from "vitest"
import { statLine, toRows } from "../brainStats"

describe("desempenho de cada cerebro na tela", () => {
  it("ordena do mais rapido e deixa sem medida por ultimo", () => {
    const rows = toRows({
      "openai|gemini|x": { n: 10, ok: 5, median: 9.5 },
      "openai|groq|y": { n: 10, ok: 10, median: 0.9 },
      "openai|novo|z": { n: 2, ok: 0, median: null },
    })
    expect(rows.map(r => r.model)).toEqual(["groq", "gemini", "novo"])
    expect(rows[1]!.failPct).toBe(50)
  })
  it("poucos usos: diz que ainda esta medindo", () => {
    expect(statLine({ model: "m", n: 1, failPct: 0, median: 2 })).toBe("1 uso: ainda medindo (preciso de 5)")
  })
  it("com dados, mostra usos, falhas e tempo em portugues", () => {
    expect(statLine({ model: "m", n: 12, failPct: 8, median: 3.14 })).toBe("12 usos · 8% de falhas · responde em 3,1 s")
    expect(statLine({ model: "m", n: 9, failPct: 100, median: null })).toContain("sem resposta")
  })
})
