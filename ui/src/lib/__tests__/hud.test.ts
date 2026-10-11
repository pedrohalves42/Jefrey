import { describe, expect, it } from "vitest"
import { brainLine, buildLog, fmtUptime, gauges, waveBars, type Telemetry } from "../hud"
import type { Message } from "../chat"

const tele: Telemetry = { ram_pct: 62.4, ram_total_gb: 16, cpu_pct: 12.6, uptime_s: 3 * 3600 + 5 * 60, brain: "Claude", reserves: 2 }

describe("painel Jarvis", () => {
  it("medidores reais, e sem medida mostra traco em vez de inventar", () => {
    const g = gauges(tele)
    expect(g[0]).toMatchObject({ label: "Memória", value: 62.4, text: "62% de 16 GB", warn: false })
    expect(g[1]).toMatchObject({ label: "Processador", text: "13%" })
    expect(gauges(null).map(x => x.text)).toEqual(["—", "—"])
    expect(gauges({ ...tele, cpu_pct: null })[1]).toMatchObject({ value: null, text: "—" })
    expect(gauges({ ...tele, ram_pct: 95 })[0]!.warn).toBe(true)
  })
  it("tempo ligado e cerebro em portugues", () => {
    expect(fmtUptime(3 * 3600 + 5 * 60)).toBe("3 h 5 min")
    expect(fmtUptime(125)).toBe("2 min")
    expect(brainLine(tele)).toBe("Claude + 2 reservas")
    expect(brainLine({ ...tele, reserves: 1 })).toBe("Claude + 1 reserva")
    expect(brainLine({ ...tele, reserves: 0 })).toBe("Claude")
    expect(brainLine(null)).toBe("Nenhum conectado")
    expect(brainLine({ ...tele, brain: null })).toBe("Nenhum conectado")
  })
  it("registro: o mais novo primeiro, com o que ele esta fazendo sozinho no topo", () => {
    const msgs: Message[] = [
      { id: "1", role: "user", content: "oi", at: 1000 },
      { id: "2", role: "assistant", content: "x", at: 2000, tools: [{ tool: "open_app", label: "Abrir programa", risk: "medium", state: "ok" }], recall: [{ kind: "fato", text: "Mora em Curitiba." }] },
      { id: "3", role: "assistant", content: "", at: 3000, error: true, tools: [{ tool: "open_website", label: "Abrir site", risk: "medium", state: "failed" }] },
    ]
    const l = buildLog(msgs, { studying: true, learning: false, topic: "horta" }, 9999)
    expect(l[0]).toMatchObject({ text: "Estudando horta", at: 9999 })
    const textos = l.map(x => x.text)
    expect(textos.indexOf("Falhou: Abrir site")).toBeLessThan(textos.indexOf("Fiz: Abrir programa"))
    expect(textos).toContain("Lembrei: Mora em Curitiba.")
    expect(textos).toContain("Algo deu errado numa resposta")
    expect(l.find(x => x.text.startsWith("Falhou"))!.tone).toBe("bad")
  })
  it("registro respeita o limite e fica vazio sem nada", () => {
    expect(buildLog([], null)).toEqual([])
    const many: Message[] = Array.from({ length: 12 }, (_, i) => ({ id: String(i), role: "assistant" as const, content: "", at: i, recall: [{ kind: "fato" as const, text: `f${i}` }] }))
    expect(buildLog(many, { studying: false, learning: true, topic: null }, 5).length).toBe(8)
  })
  it("barras da onda: tamanho certo, entre 0 e 1, e mais altas quando fala ou o microfone ouve", () => {
    const calma = waveBars(48, 0, false, 1234)
    const voz = waveBars(48, 0.9, false, 1234)
    const fala = waveBars(48, 0, true, 1234)
    for (const b of [calma, voz, fala]) {
      expect(b).toHaveLength(48)
      expect(b.every(v => v >= 0.04 && v <= 1)).toBe(true)
    }
    const media = (a: number[]) => a.reduce((x, y) => x + y, 0) / a.length
    expect(media(voz)).toBeGreaterThan(media(calma))
    expect(media(fala)).toBeGreaterThan(media(calma))
  })
})
