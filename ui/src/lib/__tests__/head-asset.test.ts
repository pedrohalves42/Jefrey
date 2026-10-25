import { existsSync, readFileSync, statSync } from "node:fs"
import { describe, expect, it } from "vitest"
import { HEAD_MODEL_URL } from "../../components/brain/HeadHologram"

describe("holograma humano: modelo e credito", () => {
  it("o arquivo do modelo existe, e um .glb valido e pequeno", () => {
    const f = new URL("../../../public" + HEAD_MODEL_URL, import.meta.url)
    expect(existsSync(f)).toBe(true)
    expect(readFileSync(f).subarray(0, 4).toString()).toBe("glTF")
    expect(statSync(f).size).toBeLessThan(1_000_000)
  })
  it("a licenca CC BY exige credito: ele esta na tela de Ajuda e nos documentos", () => {
    const ajuda = readFileSync(new URL("../../pages/Ajuda.tsx", import.meta.url), "utf8")
    expect(ajuda).toContain("Lee Perry-Smith")
    expect(ajuda).toContain("CC BY 3.0")
    const docs = readFileSync(new URL("../../../../docs/LICENCAS_TERCEIROS.md", import.meta.url), "utf8")
    expect(docs).toContain("Lee Perry-Smith")
  })
})
