import { describe, expect, it } from "vitest"
import { needsWelcome, testMessage, type LlmConfig } from "../llm"

const cfg = (over: Partial<LlmConfig> = {}): LlmConfig => ({
  provider: "ollama", model: "qwen3:1.7b", base_url: "", has_key: false, is_cloud: false, configured: true, fallbacks: 0, ...over,
})

describe("needsWelcome", () => {
  it("so mostra o assistente na primeira execucao", () => {
    expect(needsWelcome(cfg({ configured: false }), false)).toBe(true)
    expect(needsWelcome(cfg({ configured: true }), false)).toBe(false)
  })

  it("respeita quando a pessoa pulou", () => {
    expect(needsWelcome(cfg({ configured: false }), true)).toBe(false)
  })

  it("sem resposta do servidor nao redireciona", () => {
    expect(needsWelcome(undefined, false)).toBe(false)
    expect(needsWelcome(null, false)).toBe(false)
  })
})

describe("testMessage", () => {
  it("sucesso mostra o modelo", () => {
    const m = testMessage({ ok: true, status: 200, data: { ok: true, model: "gpt-6-luna" } })
    expect(m.ok).toBe(true)
    expect(m.text).toContain("gpt-6-luna")
  })

  it("servidor fora do ar", () => {
    expect(testMessage({ ok: false, status: 0, data: null }).text).toMatch(/Jefrey/)
  })

  it("chave recusada vira texto humano", () => {
    const m = testMessage({ ok: true, status: 200, data: { ok: false, detail: "HTTPStatusError: indisponivel" } })
    expect(m.ok).toBe(false)
    expect(m.text).toMatch(/chave foi recusada/)
  })

  it("sem internet", () => {
    expect(testMessage({ ok: true, status: 200, data: { ok: false, detail: "ConnectError: indisponivel" } }).text).toMatch(/internet/)
  })

  it("nunca vaza o detalhe tecnico bruto", () => {
    const m = testMessage({ ok: true, status: 200, data: { ok: false, detail: "Traceback segredo sk-123" } })
    expect(m.text).not.toContain("sk-123")
    expect(m.text).not.toContain("Traceback")
  })

  it("resposta invalida do servidor", () => {
    expect(testMessage({ ok: false, status: 500, data: null }).ok).toBe(false)
  })
})

import { overallPercent, type PullStatus } from "../llm"

describe("overallPercent", () => {
  const st = (models: PullStatus["models"]): PullStatus => ({ running: true, done: false, error: null, models })

  it("media dos modelos", () => {
    expect(overallPercent(st({ a: { status: "x", percent: 100 }, b: { status: "x", percent: 0 } }))).toBe(50)
    expect(overallPercent(st({ a: { status: "x", percent: 33 } }))).toBe(33)
  })

  it("sem dados vale zero", () => {
    expect(overallPercent(null)).toBe(0)
    expect(overallPercent(st({}))).toBe(0)
  })
})
