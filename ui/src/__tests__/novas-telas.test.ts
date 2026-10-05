import { describe, expect, it } from "vitest"
import { rowsToMap, ALEXA_STEPS } from "../lib/alexa"
import { learnMessage, looksLikeLink } from "../lib/studies"
import { nextPulse } from "../hooks/useVoicePulse"

describe("alexa.rowsToMap", () => {
  it("ignora linhas vazias e monta o mapa", () => {
    const r = rowsToMap([{ name: " sala ", id: " eco-sala " }, { name: "", id: "" }])
    expect(r).toEqual({ map: { sala: "eco-sala" }, problem: null })
  })
  it("meia linha é erro de preenchimento", () => {
    expect(rowsToMap([{ name: "sala", id: "" }]).problem).toMatch(/Preencha/)
    expect(rowsToMap([{ name: "", id: "x" }]).problem).toMatch(/Preencha/)
  })
  it("tem passos de ajuda", () => expect(ALEXA_STEPS.length).toBeGreaterThan(2))
})

describe("studies helpers", () => {
  it("reconhece links", () => {
    expect(looksLikeLink("https://exemplo.com/a")).toBe(true)
    expect(looksLikeLink("g1.globo.com/noticias")).toBe(true)
    expect(looksLikeLink("como funciona o pix")).toBe(false)
    expect(looksLikeLink("vovó fez bolo.")).toBe(false)
  })
  it("conta o que aconteceu em frases simples", () => {
    const a = learnMessage({ topic: { id: "1", title: "Pix" } as never })
    expect(a.ok).toBe(true)
    expect(a.text).toContain("Pix")
    const b = learnMessage({ topic: { id: "1", title: "Pix" } as never, run_error: "Sem nuvem conectada." })
    expect(b.ok).toBe(false)
    expect(b.text).toContain("Sem nuvem")
    const c = learnMessage({ saved_text: true, facts: 2 })
    expect(c.text).toContain("2 coisas")
  })
})

describe("useVoicePulse.nextPulse", () => {
  it("bate na palavra e decai", () => {
    expect(nextPulse(0, true, true, 0)).toBe(1)
    const d = nextPulse(1, true, false, 0)
    expect(d).toBeLessThan(1)
    expect(d).toBeGreaterThanOrEqual(0.3)
  })
  it("sem marcador de palavra, ondula sozinho", () => {
    expect(nextPulse(0, true, false, 100)).toBeGreaterThan(0.29)
  })
  it("ao parar de falar, volta a zero", () => {
    let v = 1
    for (let i = 0; i < 60; i++) v = nextPulse(v, false, false, 0)
    expect(v).toBe(0)
  })
})

import { bestVoice, voiceScore } from "../hooks/useSpeaker"

describe("escolha da voz", () => {
  it("prefere a voz neural à antiga", () => {
    const lista = [
      { name: "Microsoft Maria - Portuguese (Brazil)", lang: "pt-BR" },
      { name: "Microsoft Francisca Online (Natural) - Portuguese (Brazil)", lang: "pt-BR" },
      { name: "Microsoft Helia - Portuguese (Portugal)", lang: "pt-PT" },
    ]
    expect(bestVoice(lista)?.name).toContain("Francisca")
    expect(voiceScore(lista[1])).toBeGreaterThan(voiceScore(lista[0]))
  })
  it("lista vazia não quebra", () => expect(bestVoice([])).toBeUndefined())
})

import { downloadMessage, pickEngine, type Engines } from "../lib/voice"
import { currentLevel, rmsLevel, setLevelSource } from "../lib/voiceLevel"

const eng = (cloud: boolean, local: boolean): Engines => ({
  engines: [
    { id: "cloud", available: cloud, label: "n" },
    { id: "local", available: local, label: "l" },
    { id: "browser", available: true, label: "b" },
  ],
  default: cloud ? "cloud" : local ? "local" : "browser",
  local: { installed: local, size_mb: 60 },
})

describe("voz: escolha do motor", () => {
  it("sem escolha usa o padrao do servidor", () => {
    expect(pickEngine(null, eng(true, true))).toBe("cloud")
    expect(pickEngine(null, eng(false, true))).toBe("local")
    expect(pickEngine(null, null)).toBe("browser")
  })
  it("escolha indisponivel cai para o padrao; voz especifica do PC vira navegador", () => {
    expect(pickEngine("cloud", eng(false, true))).toBe("local")
    expect(pickEngine("local", eng(true, true))).toBe("local")
    expect(pickEngine("urn:voz-maria", eng(true, true))).toBe("browser")
  })
  it("mensagens do download", () => {
    expect(downloadMessage({ installed: false, size_mb: 60, state: "idle", pct: 0, error: "" })).toContain("60 MB")
    expect(downloadMessage({ installed: false, size_mb: 60, state: "running", pct: 42, error: "" })).toContain("42%")
    expect(downloadMessage({ installed: true, size_mb: 60, state: "idle", pct: 0, error: "" })).toBe("Voz natural pronta.")
    expect(downloadMessage({ installed: false, size_mb: 60, state: "error", pct: 0, error: "Sem internet." })).toBe("Sem internet.")
  })
})

describe("nivel real da voz", () => {
  it("silencio e 0 e sinal forte chega perto de 1", () => {
    expect(rmsLevel(new Uint8Array(256).fill(128))).toBe(0)
    const forte = Uint8Array.from({ length: 256 }, (_, i) => (i % 2 ? 240 : 16))
    expect(rmsLevel(forte)).toBeGreaterThan(0.9)
    expect(rmsLevel([])).toBe(0)
  })
  it("currentLevel usa a fonte, limita a 0..1 e sobrevive a erro", () => {
    setLevelSource(() => 5)
    expect(currentLevel()).toBe(1)
    setLevelSource(() => { throw new Error("x") })
    expect(currentLevel()).toBe(0)
    setLevelSource(null)
    expect(currentLevel()).toBe(0)
  })
  it("nextPulse com nivel alto bate perto de 1 e sem nivel mantem o comportamento", () => {
    expect(nextPulse(0, true, false, 0, 0.9)).toBeGreaterThan(0.85)
    expect(nextPulse(0, true, false, 100)).toBeGreaterThan(0.29)
    expect(nextPulse(0.8, true, false, 0, 0)).toBeLessThan(0.8)
    expect(nextPulse(0.5, false, false, 0, 0.9)).toBeLessThan(0.5)
  })
})
