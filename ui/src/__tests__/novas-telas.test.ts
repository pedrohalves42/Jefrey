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

import { change, money, points, spokenSummary, type TodayData } from "../lib/today"

describe("painel Hoje: formatacao", () => {
  it("dinheiro, pontos e variacao em portugues", () => {
    expect(money(4.9988)).toBe("R$ 5,00")
    expect(money(131500)).toContain("131.500,00")
    expect(points(131500.4)).toBe("131.500 pts")
    expect(change(1.154)).toEqual({ text: "▲ +1,15%", tone: "up" })
    expect(change(-4.2742)).toEqual({ text: "▼ -4,27%", tone: "down" })
    expect(change(0.001).tone).toBe("flat")
  })
  it("frase falada traz o essencial e nunca quebra com cartoes vazios", () => {
    const base = { status: "ok" as const, items: [] }
    const d: TodayData = {
      generated_at: "2026-10-05T08:00",
      region: { city: "São Paulo", uf: "sp" },
      sections: {
        news: { status: "ok", items: [{ title: "Governo anuncia plano", link: "https://g1.globo.com/a" }] },
        economy: base,
        region: base,
        market: { status: "ok", usd: { value: 5, pct: 0.1 } },
        weather: { status: "ok", summary: "Agora 24 °C, chuva fraca." },
        agenda: { status: "ok", items: [{ title: "Consulta", time: "09:30" }] },
        reminders: { status: "ok", items: [{ text: "Beber água", due_label: "hoje às 15:00" }] },
      },
    }
    const t = spokenSummary(d, "Ana")
    expect(t).toContain("Bom dia, Ana!")
    expect(t).toContain("Consulta às 09:30")
    expect(t).toContain("Beber água")
    expect(t).toContain("Governo anuncia plano")
    expect(spokenSummary({ ...d, sections: { ...d.sections, agenda: { status: "erro", items: [] }, weather: { status: "erro" } } })).toContain("Bom dia!")
  })
})

import { normalizeToday } from "../lib/today"

describe("painel Hoje: resposta incompleta nunca quebra a tela", () => {
  it("normaliza o que faltar", () => {
    const d = normalizeToday({ sections: { news: { status: "ok", items: [{ title: "x", link: "https://a.com" }] } } })!
    expect(d.sections.news.items).toHaveLength(1)
    expect(d.sections.weather.status).toBe("erro")
    expect(d.sections.agenda.items).toEqual([])
    expect(d.region).toEqual({ city: "", uf: "" })
  })
  it("lixo vira null", () => {
    expect(normalizeToday(null)).toBeNull()
    expect(normalizeToday({ skills: [] })).toBeNull()
    expect(normalizeToday("texto")).toBeNull()
  })
})

import { splitSentences } from "../lib/voice"

describe("voz fluida: divisao em frases", () => {
  it("a primeira frase sai sozinha (a fala comeca mais rapido) e as seguintes se juntam ate o limite", () => {
    const t = "Bom dia, Pedro! Hoje o dia está lindo. Você tem uma consulta às nove e meia. Não se esqueça do remédio, tá?"
    const p = splitSentences(t, 70)
    expect(p[0]).toBe("Bom dia, Pedro!")
    expect(p.every(x => x.length <= 70)).toBe(true)
    expect(p.join(" ")).toBe(t)
  })
  it("frase gigante sem pontuacao e cortada em virgulas/espacos", () => {
    const t = Array.from({ length: 60 }, (_, i) => `palavra${i}`).join(" ")
    const p = splitSentences(t, 80)
    expect(p.every(x => x.length <= 80)).toBe(true)
    expect(p.join(" ")).toBe(t)
  })
  it("vazio, reticencias e abreviacoes nao quebram a conta", () => {
    expect(splitSentences("   ")).toEqual([])
    expect(splitSentences("Espera... já vou. Sr. Silva chegou.", 200)[0]).toBe("Espera...")
    expect(splitSentences("Oi")).toEqual(["Oi"])
  })
})

import { newFacts, type Fact } from "../lib/learning"

describe("aprende entre conversas: o que e novo", () => {
  const f = (id: string, extra: Partial<Fact> = {}): Fact => ({ id, kind: "gosto", key: id, text: `fato ${id}`, sensitive: false, active: true, created_at: `2026-10-0${id}`, ...extra })
  it("so devolve fatos novos, ativos e nao sensiveis, do mais novo para o mais antigo", () => {
    const out = newFacts(new Set(["1"]), [f("1"), f("2"), f("3"), f("4", { sensitive: true }), f("5", { active: false })])
    expect(out.map(x => x.id)).toEqual(["3", "2"])
  })
  it("nada novo = lista vazia", () => expect(newFacts(new Set(["1", "2"]), [f("1"), f("2")])).toEqual([]))
})

import { dayStrip } from "../lib/today"

describe("faixa do dia na tela principal", () => {
  const base = { status: "ok" as const, items: [] }
  const mk = (over: Partial<TodayData["sections"]>): TodayData => ({
    generated_at: "2026-10-05T08:00",
    region: { city: "São Paulo", uf: "sp" },
    sections: { news: base, economy: base, region: base, market: { status: "ok" }, weather: { status: "ok" }, agenda: base, reminders: base, ...over },
  })
  it("junta tempo, proximo compromisso e dolar", () => {
    const d = mk({ weather: { status: "ok", temp: 16.4, place: "São Paulo, São Paulo" }, agenda: { status: "ok", items: [{ title: "Consulta", time: "09:30" }] }, market: { status: "ok", usd: { value: 5, pct: 0 } } })
    expect(dayStrip(d)).toEqual(["🌤 16 °C em São Paulo", "📅 09:30 Consulta", "💵 R$ 5,00"])
  })
  it("sem compromisso mostra lembrete ou 'nada marcado'; sem dados, lista vazia", () => {
    expect(dayStrip(mk({ reminders: { status: "ok", items: [{ text: "Beber água", due_label: "hoje" }] } }))).toContain("🔔 Beber água")
    expect(dayStrip(mk({}))).toContain("📅 Nada marcado hoje")
    expect(dayStrip(mk({ agenda: { status: "erro", items: [] }, reminders: { status: "erro", items: [] }, weather: { status: "erro" } }))).toEqual([])
  })
})
