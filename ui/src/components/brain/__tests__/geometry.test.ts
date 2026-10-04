import { describe, expect, it } from "vitest"
import { buildGraph, generatePoints, MAX_NEURONS, MIN_NEURONS, mulberry32, neuronCount } from "../geometry"

describe("neuronCount", () => {
  it("fica entre o minimo e o maximo", () => {
    expect(neuronCount(0)).toBe(MIN_NEURONS)
    expect(neuronCount(1)).toBe(MAX_NEURONS)
    expect(neuronCount(-3)).toBe(MIN_NEURONS)
    expect(neuronCount(9)).toBe(MAX_NEURONS)
  })
})

describe("generatePoints", () => {
  for (const shape of ["brain", "orb", "reactor"] as const) {
    it(`${shape}: tamanho certo, finito e dentro da cena`, () => {
      const p = generatePoints(shape, 300)
      expect(p).toHaveLength(900)
      for (const v of p) {
        expect(Number.isFinite(v)).toBe(true)
        expect(Math.abs(v)).toBeLessThanOrEqual(1.05)
      }
    })
    it(`${shape}: deterministico`, () => {
      expect(Array.from(generatePoints(shape, 50, 3))).toEqual(Array.from(generatePoints(shape, 50, 3)))
    })
  }

  it("cerebro tem dois hemisferios com a mesma quantidade de neuronios", () => {
    const p = generatePoints("brain", 400)
    let left = 0
    let right = 0
    for (let i = 0; i < 400; i++) {
      if ((p[i * 3] as number) < 0) left++
      else right++
    }
    expect(left).toBe(200)
    expect(right).toBe(200)
  })

  it("reator e achatado (quase plano em z)", () => {
    const p = generatePoints("reactor", 400)
    let maxZ = 0
    for (let i = 0; i < 400; i++) maxZ = Math.max(maxZ, Math.abs(p[i * 3 + 2] as number))
    expect(maxZ).toBeLessThan(0.2)
  })
})

describe("buildGraph", () => {
  it("sem duplicatas, sem laco e com vizinhanca simetrica", () => {
    const p = generatePoints("brain", 120)
    const g = buildGraph(p, 3)
    const seen = new Set<string>()
    for (let i = 0; i < g.edges.length; i += 2) {
      const a = g.edges[i] as number
      const b = g.edges[i + 1] as number
      expect(a).toBeLessThan(b)
      const key = `${a}-${b}`
      expect(seen.has(key)).toBe(false)
      seen.add(key)
      expect(g.neighbors[a]).toContain(b)
      expect(g.neighbors[b]).toContain(a)
    }
    expect(seen.size).toBeGreaterThan(120)
  })

  it("todo neuronio tem ao menos um vizinho", () => {
    const g = buildGraph(generatePoints("orb", 100), 3)
    expect(g.neighbors.every(n => n.length >= 1)).toBe(true)
  })

  it("o tamanho maximo constroi rapido (< 1.5 s)", () => {
    const p = generatePoints("brain", MAX_NEURONS)
    const t0 = performance.now()
    buildGraph(p, 3)
    expect(performance.now() - t0).toBeLessThan(1500)
  })
})

describe("mulberry32", () => {
  it("fica em [0,1) e repete com a mesma semente", () => {
    const a = mulberry32(1)
    const b = mulberry32(1)
    for (let i = 0; i < 100; i++) {
      const x = a()
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThan(1)
      expect(x).toBe(b())
    }
  })
})
