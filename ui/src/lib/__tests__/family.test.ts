import { describe, expect, it } from "vitest"
import { canEnable } from "../family"

describe("modo familia na tela", () => {
  it("so liga com o nome de quem recebe", () => {
    expect(canEnable("")).toBe(false)
    expect(canEnable("   ")).toBe(false)
    expect(canEnable("Ana")).toBe(true)
  })
})
