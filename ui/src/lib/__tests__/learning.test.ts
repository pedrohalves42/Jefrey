import { describe, expect, it } from "vitest"
import { correctionError, groupFacts, kindLabel, type Fact } from "../learning"

const f = (id: string, kind: string, text = "x"): Fact => ({ id, kind, key: id, text, sensitive: false, active: true, created_at: "2026-10-04T10:00:00" })

describe("O que aprendi", () => {
  it("agrupa por assunto na ordem esperada e junta o desconhecido em Outras coisas", () => {
    const g = groupFacts([f("1", "gosto"), f("2", "pessoa"), f("3", "inventado"), f("4", "pessoa")])
    expect(g.map(x => x.label)).toEqual(["Sobre você", "Gostos", "Outras coisas"])
    expect(g[0]!.items.map(i => i.id)).toEqual(["2", "4"])
  })
  it("sem fatos, sem grupos", () => {
    expect(groupFacts([])).toEqual([])
  })
  it("nomes de assunto em portugues simples", () => {
    expect(kindLabel("familia")).toBe("Família e amigos")
    expect(kindLabel("zzz")).toBe("Outras coisas")
  })
  it("erros de correcao falam como gente", () => {
    expect(correctionError(422)).toMatch(/senha/)
    expect(correctionError(404)).toMatch(/Não encontrei/)
    expect(correctionError(0)).toMatch(/Tente de novo/)
  })
})
