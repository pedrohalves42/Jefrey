import { describe, expect, it } from "vitest"
import { newOnes, type DueReminder } from "../useReminders"

const r = (id: string): DueReminder => ({ id, text: "t", due_label: "hoje", repeat: "none" })

describe("newOnes", () => {
  it("so devolve lembretes ainda nao mostrados", () => {
    const shown = new Set(["a"])
    expect(newOnes(shown, [r("a"), r("b"), r("c")]).map(x => x.id)).toEqual(["b", "c"])
  })

  it("ignora entradas invalidas sem quebrar", () => {
    expect(newOnes(new Set(), [r("a"), null as unknown as DueReminder, { text: "sem id" } as unknown as DueReminder]).map(x => x.id)).toEqual(["a"])
  })

  it("lista vazia", () => {
    expect(newOnes(new Set(["a"]), [])).toEqual([])
  })
})
