import type { BrainShape } from "@/lib/appearance"

/** Gerador pseudo-aleatorio deterministico: a forma nao "pula" a cada renderizacao. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const MIN_NEURONS = 80
export const MAX_NEURONS = 900

/** particles (0-1) -> numero de neuronios. */
export function neuronCount(particles: number): number {
  const p = Math.min(1, Math.max(0, particles))
  return Math.round(MIN_NEURONS + (MAX_NEURONS - MIN_NEURONS) * p)
}

/** Posicoes (x,y,z) de `n` neuronios na forma escolhida, dentro de ~[-1, 1]. */
export function generatePoints(shape: BrainShape, n: number, seed = 7): Float32Array {
  const rnd = mulberry32(seed)
  const out = new Float32Array(n * 3)
  for (let i = 0; i < n; i++) {
    let x = 0
    let y = 0
    let z = 0
    if (shape === "orb") {
      const yy = 1 - (2 * (i + 0.5)) / n
      const r = Math.sqrt(Math.max(0, 1 - yy * yy))
      const phi = i * Math.PI * (3 - Math.sqrt(5))
      const k = 0.8 * (0.93 + 0.07 * rnd())
      x = Math.cos(phi) * r * k
      y = yy * k
      z = Math.sin(phi) * r * k
    } else if (shape === "reactor") {
      if (i % 5 === 0) {
        // nucleo
        const th = rnd() * Math.PI * 2
        const ph = Math.acos(2 * rnd() - 1)
        const r = 0.13 * Math.cbrt(rnd())
        x = r * Math.sin(ph) * Math.cos(th)
        y = r * Math.sin(ph) * Math.sin(th)
        z = r * Math.cos(ph)
      } else {
        const radii = [0.36, 0.6, 0.86]
        const ring = radii[i % 3] as number
        const a = rnd() * Math.PI * 2
        x = Math.cos(a) * ring
        y = Math.sin(a) * ring
        z = (rnd() - 0.5) * 0.07
      }
    } else {
      // cerebro: dois hemisferios com fissura central e sulcos
      const hemi = i % 2 === 0 ? 1 : -1
      const th = rnd() * Math.PI * 2
      const ph = Math.acos(2 * rnd() - 1)
      const dx = Math.sin(ph) * Math.cos(th)
      const dy = Math.cos(ph)
      const dz = Math.sin(ph) * Math.sin(th)
      const wrinkle = 1 + 0.07 * Math.sin(9 * dx + 3 * dy) * Math.cos(7 * dz) + 0.04 * Math.sin(15 * dy + 5 * dz)
      const depth = 0.78 + 0.22 * rnd()
      const k = wrinkle * depth
      x = hemi * (0.05 + Math.abs(dx) * 0.5 * k)
      y = dy * 0.62 * k * (dy < 0 ? 0.8 : 1) - 0.02
      z = dz * 0.82 * k
    }
    out[i * 3] = x
    out[i * 3 + 1] = y
    out[i * 3 + 2] = z
  }
  return out
}

export type Graph = {
  /** pares de indices (a,b) das sinapses, sem duplicatas */
  edges: Uint32Array
  /** vizinhos de cada neuronio (para propagar o disparo) */
  neighbors: number[][]
}

/** Liga cada neuronio aos `k` mais proximos. O(n^2), roda uma vez por forma. */
export function buildGraph(points: Float32Array, k = 3): Graph {
  const n = points.length / 3
  const seen = new Set<number>()
  const pairs: number[] = []
  const neighbors: number[][] = Array.from({ length: n }, () => [])
  const d2 = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    const ix = points[i * 3] as number
    const iy = points[i * 3 + 1] as number
    const iz = points[i * 3 + 2] as number
    for (let j = 0; j < n; j++) {
      const dx = ix - (points[j * 3] as number)
      const dy = iy - (points[j * 3 + 1] as number)
      const dz = iz - (points[j * 3 + 2] as number)
      d2[j] = i === j ? Infinity : dx * dx + dy * dy + dz * dz
    }
    const nearest: number[] = []
    for (let c = 0; c < Math.min(k, n - 1); c++) {
      let best = -1
      let bd = Infinity
      for (let j = 0; j < n; j++) {
        if ((d2[j] as number) < bd && !nearest.includes(j)) {
          bd = d2[j] as number
          best = j
        }
      }
      if (best >= 0) nearest.push(best)
    }
    for (const j of nearest) {
      const a = Math.min(i, j)
      const b = Math.max(i, j)
      const key = a * n + b
      if (!seen.has(key)) {
        seen.add(key)
        pairs.push(a, b)
      }
      if (!neighbors[i]!.includes(j)) neighbors[i]!.push(j)
      if (!neighbors[j]!.includes(i)) neighbors[j]!.push(i)
    }
  }
  return { edges: Uint32Array.from(pairs), neighbors }
}
