import { describe, expect, it } from "vitest"
import { liveStatus } from "../liveStatus"

const base = { streaming: true, gotToken: false, approval: false, tool: null, elapsedS: 0 }

describe("o que o Jefrey diz que esta fazendo", () => {
  it("nada quando nao esta trabalhando", () => {
    expect(liveStatus({ ...base, streaming: false })).toBeNull()
  })
  it("ferramenta em andamento aparece pelo nome em portugues", () => {
    expect(liveStatus({ ...base, tool: { tool: "search_news", label: "Buscar noticias" } })).toBe("Procurando notícias…")
    expect(liveStatus({ ...base, tool: { tool: "coisa_nova", label: "Fazer coisa" } })).toBe("Fazendo: fazer coisa…")
  })
  it("aprovacao pendente tem prioridade", () => {
    expect(liveStatus({ ...base, approval: true, tool: { tool: "search", label: "Buscar na web" } })).toBe("Aguardando sua aprovação")
  })
  it("com texto chegando, esta escrevendo", () => {
    expect(liveStatus({ ...base, gotToken: true })).toBe("Escrevendo a resposta…")
  })
  it("espera longa e dita com honestidade, sem prometer prazo", () => {
    expect(liveStatus({ ...base, elapsedS: 1 })).toBe("Pensando…")
    expect(liveStatus({ ...base, elapsedS: 6 })).toBe("Ainda pensando…")
    expect(liveStatus({ ...base, elapsedS: 15 })).toBe("Está demorando mais que o normal. Continuo tentando…")
  })
})
