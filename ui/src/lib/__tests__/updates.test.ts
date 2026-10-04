import { describe, expect, it } from "vitest"
import { sizeLabel, updateMessage } from "../updates"

const res = (ok: boolean, status: number, data: unknown) => ({ ok, status, data }) as Parameters<typeof updateMessage>[0]

describe("atualizacoes na tela", () => {
  it("diz em portugues simples o que aconteceu", () => {
    expect(updateMessage(res(true, 200, { current: "1.0.0", available: false, enabled: false })).text).toMatch(/ainda não estão ligadas/)
    expect(updateMessage(res(true, 200, { current: "1.0.0", available: false, enabled: true })).text).toBe("Você está com a versão mais nova (1.0.0).")
    expect(updateMessage(res(true, 200, { current: "1.0.0", available: true, enabled: true, version: "1.2.0", notes: "Melhorias." })).text).toBe("Tem uma versão nova: 1.2.0. Melhorias.")
  })
  it("erros usam o texto do servidor ou um padrao", () => {
    expect(updateMessage(res(false, 502, { detail: "Não consegui consultar as atualizações agora." }))).toEqual({ ok: false, text: "Não consegui consultar as atualizações agora." })
    expect(updateMessage(res(false, 500, null)).text).toMatch(/procurar atualizações/)
    expect(updateMessage(res(false, 0, null)).text).toMatch(/falar com o Jefrey/)
  })
  it("tamanho legivel", () => {
    expect(sizeLabel(undefined)).toBe("")
    expect(sizeLabel(480 * 1024 * 1024)).toBe("480 MB")
    expect(sizeLabel(1.5 * 1024 ** 3)).toBe("1,5 GB")
  })
})
