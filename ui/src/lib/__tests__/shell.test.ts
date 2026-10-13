// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { isDesktop, listenOrb, publishOrb } from "../shell"

describe("isDesktop", () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => window.history.replaceState({}, "", "/"))

  it("so e verdadeiro quando o programa abriu a tela com ?app=1, e lembra nas outras paginas", () => {
    expect(isDesktop()).toBe(false)
    window.history.replaceState({}, "", "/?app=1")
    expect(isDesktop()).toBe(true)
    window.history.replaceState({}, "", "/conexoes") // o roteador tira o parametro
    expect(isDesktop()).toBe(true)
  })

  it("outro valor nao liga o modo app", () => {
    window.history.replaceState({}, "", "/?app=0")
    expect(isDesktop()).toBe(false)
  })
})

describe("estado do orbe", () => {
  it("nao quebra quando nao ha BroadcastChannel", () => {
    const original = (globalThis as { BroadcastChannel?: unknown }).BroadcastChannel
    ;(globalThis as { BroadcastChannel?: unknown }).BroadcastChannel = undefined
    try {
      expect(() => publishOrb({ state: "idle", level: 0 })).not.toThrow()
      const stop = listenOrb(() => undefined)
      expect(() => stop()).not.toThrow()
    } finally {
      ;(globalThis as { BroadcastChannel?: unknown }).BroadcastChannel = original
    }
  })

  it("entrega o estado publicado a quem escuta", async () => {
    if (typeof BroadcastChannel === "undefined") return
    const got = vi.fn()
    const stop = listenOrb(got)
    publishOrb({ state: "responding", level: 0.5 })
    await new Promise(r => setTimeout(r, 30))
    stop()
    if (got.mock.calls.length) expect(got.mock.calls[0][0]).toEqual({ state: "responding", level: 0.5 })
  })
})
