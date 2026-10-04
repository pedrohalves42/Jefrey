export type Sample = { labels: Record<string, string>; value: number }
export type Metrics = Map<string, Sample[]>

/** Le o formato de texto do Prometheus. Linhas invalidas sao ignoradas. */
export function parsePrometheus(text: string): Metrics {
  const out: Metrics = new Map()
  for (const raw of text.split("\n")) {
    const line = raw.trim()
    if (!line || line.startsWith("#")) continue
    const m = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})?\s+(\S+)/.exec(line)
    if (!m) continue
    const value = Number(m[4])
    if (!Number.isFinite(value)) continue
    const labels: Record<string, string> = {}
    if (m[3]) {
      const re = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g
      let l: RegExpExecArray | null
      while ((l = re.exec(m[3])) !== null) labels[l[1] as string] = (l[2] as string).replace(/\\(.)/g, "$1")
    }
    const name = m[1] as string
    const arr = out.get(name)
    if (arr) arr.push({ labels, value })
    else out.set(name, [{ labels, value }])
  }
  return out
}

/** Soma de todas as series de um contador/gauge; undefined se a metrica nao existe. */
export function sum(metrics: Metrics, name: string): number | undefined {
  const s = metrics.get(name)
  if (!s || s.length === 0) return undefined
  return s.reduce((a, b) => a + b.value, 0)
}

/**
 * Quantil (0-1) de um histograma, agregando as series por `le`.
 * Interpola linearmente dentro do balde, como o histogram_quantile do Prometheus.
 * Retorna undefined sem observacoes.
 */
export function histogramQuantile(metrics: Metrics, base: string, q: number): number | undefined {
  const buckets = metrics.get(`${base}_bucket`)
  if (!buckets) return undefined
  const byLe = new Map<number, number>()
  for (const b of buckets) {
    const le = b.labels.le === "+Inf" ? Infinity : Number(b.labels.le)
    if (Number.isNaN(le)) continue
    byLe.set(le, (byLe.get(le) ?? 0) + b.value)
  }
  const sorted = [...byLe.entries()].sort((a, b) => a[0] - b[0])
  const total = sorted.length ? (sorted[sorted.length - 1] as [number, number])[1] : 0
  if (total <= 0) return undefined
  const rank = q * total
  let prevLe = 0
  let prevCount = 0
  for (const [le, count] of sorted) {
    if (count >= rank) {
      if (!Number.isFinite(le)) return prevLe
      const span = count - prevCount
      return span <= 0 ? le : prevLe + ((le - prevLe) * (rank - prevCount)) / span
    }
    prevLe = Number.isFinite(le) ? le : prevLe
    prevCount = count
  }
  return prevLe
}

export function formatSeconds(s: number | undefined): string {
  if (s === undefined) return "sem dados"
  if (s < 1) return `${Math.round(s * 1000)} ms`
  return `${s.toFixed(1)} s`
}

export function formatDuration(totalSeconds: number | undefined): string {
  if (totalSeconds === undefined) return "sem dados"
  const s = Math.floor(totalSeconds)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d} d ${h} h`
  if (h > 0) return `${h} h ${m} min`
  if (m > 0) return `${m} min`
  return `${s} s`
}
