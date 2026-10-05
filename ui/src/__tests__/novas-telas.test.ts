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
