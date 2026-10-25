import { describe, expect, it } from "vitest"
import { parseAccess } from "../access"

describe("acessibilidade: letra e contraste", () => {
  it("padrao e letra normal e contraste comum", () => {
    expect(parseAccess(null)).toEqual({ text: "normal", contrast: false })
    expect(parseAccess("lixo")).toEqual({ text: "normal", contrast: false })
  })
  it("aceita so tamanhos conhecidos", () => {
    expect(parseAccess('{"text":"enorme","contrast":true}')).toEqual({ text: "enorme", contrast: true })
    expect(parseAccess('{"text":"gigante"}')).toEqual({ text: "normal", contrast: false })
  })
  it("alto contraste so vale com true de verdade", () => {
    expect(parseAccess('{"contrast":"sim"}').contrast).toBe(false)
  })
})
