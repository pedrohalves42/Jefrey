import { describe, expect, it } from "vitest"
import { formatDuration, formatSeconds, histogramQuantile, parsePrometheus, sum } from "../metrics"

const TEXT = `# HELP jefrey_llm_latency_seconds x
# TYPE jefrey_llm_latency_seconds histogram
jefrey_llm_latency_seconds_bucket{le="0.5"} 2
jefrey_llm_latency_seconds_bucket{le="1.0"} 6
jefrey_llm_latency_seconds_bucket{le="5.0"} 10
jefrey_llm_latency_seconds_bucket{le="+Inf"} 10
jefrey_llm_latency_seconds_count 10
jefrey_uptime_seconds 3725.5
jefrey_tools_blocked_total{tool="a",reason="x"} 2
jefrey_tools_blocked_total{tool="b",reason="y"} 3
linha invalida sem formato
jefrey_bad NaN
`

describe("parsePrometheus", () => {
  const m = parsePrometheus(TEXT)
  it("le valores e labels", () => {
    expect(m.get("jefrey_uptime_seconds")?.[0]?.value).toBe(3725.5)
    expect(m.get("jefrey_tools_blocked_total")).toHaveLength(2)
    expect(m.get("jefrey_tools_blocked_total")?.[0]?.labels).toEqual({ tool: "a", reason: "x" })
  })
  it("ignora comentarios, lixo e NaN", () => {
    expect(m.has("jefrey_bad")).toBe(false)
    expect(m.has("linha")).toBe(false)
  })
})

describe("sum", () => {
  const m = parsePrometheus(TEXT)
  it("soma as series", () => expect(sum(m, "jefrey_tools_blocked_total")).toBe(5))
  it("undefined quando a metrica nao existe (nao inventa zero)", () => expect(sum(m, "nao_existe")).toBeUndefined())
})

describe("histogramQuantile", () => {
  const m = parsePrometheus(TEXT)
  it("interpola dentro do balde (p50 de 10 amostras)", () => {
    // rank 5 cai no balde (0.5,1.0]: 2 ate 6 -> 0.5 + 0.5*(3/4)
    expect(histogramQuantile(m, "jefrey_llm_latency_seconds", 0.5)).toBeCloseTo(0.875, 5)
  })
  it("p95 fica no ultimo balde finito", () => {
    const v = histogramQuantile(m, "jefrey_llm_latency_seconds", 0.95) as number
    expect(v).toBeGreaterThan(1)
    expect(v).toBeLessThanOrEqual(5)
  })
  it("sem observacoes ou sem metrica -> undefined", () => {
    expect(histogramQuantile(parsePrometheus('x_bucket{le="1"} 0\nx_bucket{le="+Inf"} 0'), "x", 0.5)).toBeUndefined()
    expect(histogramQuantile(m, "nada", 0.5)).toBeUndefined()
  })
  it("agrega varias series por le", () => {
    const t = parsePrometheus('h_bucket{le="1",a="x"} 1\nh_bucket{le="1",a="y"} 1\nh_bucket{le="+Inf",a="x"} 1\nh_bucket{le="+Inf",a="y"} 1')
    expect(histogramQuantile(t, "h", 0.5)).toBeCloseTo(0.5, 5)
  })
})

describe("formatadores", () => {
  it("segundos", () => {
    expect(formatSeconds(undefined)).toBe("sem dados")
    expect(formatSeconds(0.25)).toBe("250 ms")
    expect(formatSeconds(2.34)).toBe("2.3 s")
  })
  it("duracao", () => {
    expect(formatDuration(undefined)).toBe("sem dados")
    expect(formatDuration(45)).toBe("45 s")
    expect(formatDuration(3725)).toBe("1 h 2 min")
    expect(formatDuration(90000)).toBe("1 d 1 h")
  })
})
