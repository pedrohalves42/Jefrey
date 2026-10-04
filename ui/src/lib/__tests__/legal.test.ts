import { describe, expect, it } from "vitest"
import { parseDoc, plain, summaryLines, type Summary } from "../legal"

describe("textos legais", () => {
  it("le titulos, listas, paragrafos e tabelas", () => {
    const b = parseDoc("# Política\nVersão 1\n\n## 1. Em poucas palavras\n- Roda no seu computador\n- Você apaga tudo\n\n| Quando | O que sai |\n|---|---|\n| Conversa | O texto |\n| Voz | Nada |\n\nFim.")
    expect(b.map(x => x.type)).toEqual(["h1", "p", "h2", "li", "li", "table", "p"])
    const t = b[5]!
    expect(t.type === "table" && t.header).toEqual(["Quando", "O que sai"])
    expect(t.type === "table" && t.rows).toEqual([["Conversa", "O texto"], ["Voz", "Nada"]])
  })
  it("nunca devolve HTML: tags ficam como texto", () => {
    const b = parseDoc("<script>alert(1)</script>")
    expect(b).toEqual([{ type: "p", text: "<script>alert(1)</script>" }])
  })
  it("tira marcas de negrito para leitura em voz alta", () => {
    expect(plain("O **Jefrey** roda em `casa`_")).toBe("O Jefrey roda em casa")
  })
  it("resumo dos dados em linguagem simples, no singular e no plural", () => {
    const s: Summary = { nome: true, fatos: 1, diario: 0, assuntos: 2, lembretes: 1, memorias: 0, mensagens: 6, whatsapp: 0, google: true }
    const l = summaryLines(s)
    expect(l).toContain("O seu nome")
    expect(l).toContain("1 coisa que aprendi sobre você")
    expect(l).toContain("2 assuntos estudados")
    expect(l).toContain("1 lembrete")
    expect(l).toContain("Conexão com o Google")
    expect(l.some(x => x.includes("WhatsApp"))).toBe(false)
  })
})
