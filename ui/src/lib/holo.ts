/** Funcoes puras do avatar holografico (sem DOM): testaveis e baratas. */

export const MAX_FILE_BYTES = 8 * 1024 * 1024
export const OK_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"]
export const MAX_STORED_CHARS = 1_200_000 // tamanho maximo da imagem guardada (texto data:)

/** Motivo (em portugues) para recusar o arquivo, ou null se serve. */
export function validateImageFile(f: { type: string; size: number }): string | null {
  if (!OK_TYPES.includes(f.type)) return "Use uma imagem PNG, JPG, WebP ou GIF."
  if (f.size <= 0) return "Esse arquivo está vazio."
  if (f.size > MAX_FILE_BYTES) return "Essa imagem é grande demais (máximo 8 MB)."
  return null
}

/** Reduz mantendo a proporcao, sem ampliar. */
export function fitSize(w: number, h: number, max: number): { w: number; h: number } {
  if (!(w > 0) || !(h > 0)) return { w: 1, h: 1 }
  const k = Math.min(1, max / Math.max(w, h))
  return { w: Math.max(1, Math.round(w * k)), h: Math.max(1, Math.round(h * k)) }
}

export function smoothstep(e0: number, e1: number, x: number): number {
  if (e1 === e0) return x < e0 ? 0 : 1
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)))
  return t * t * (3 - 2 * t)
}

export function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const hh = ((h % 360) + 360) % 360
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((hh / 60) % 2) - 1))
  const m = l - c / 2
  const [r, g, b] = hh < 60 ? [c, x, 0] : hh < 120 ? [x, c, 0] : hh < 180 ? [0, c, x] : hh < 240 ? [0, x, c] : hh < 300 ? [x, 0, c] : [c, 0, x]
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]
}

/**
 * Transforma a imagem em holograma monocromatico na cor do tema (altera `data` no lugar).
 * - brilho da imagem vira intensidade da cor;
 * - o que for mais escuro que `cut` fica transparente (fundo preto some);
 * - `invert` serve para imagens de fundo claro.
 */
export function tintImageData(data: Uint8ClampedArray, hue: number, cut: number, invert: boolean): void {
  const lo = Math.min(0.9, Math.max(0, cut))
  for (let i = 0; i + 3 < data.length; i += 4) {
    let l = (0.299 * (data[i] as number) + 0.587 * (data[i + 1] as number) + 0.114 * (data[i + 2] as number)) / 255
    if (invert) l = 1 - l
    const alpha = smoothstep(lo, lo + 0.25, l) * ((data[i + 3] as number) / 255)
    const [r, g, b] = hslToRgb(hue, 0.9, 0.3 + 0.5 * l)
    data[i] = r
    data[i + 1] = g
    data[i + 2] = b
    data[i + 3] = Math.round(alpha * 255)
  }
}

export type GlitchBand = { y: number; h: number; dx: number }

/** Faixas horizontais deslocadas (efeito de falha). `rand` injetado para ser deterministico nos testes. */
export function glitchBands(rand: () => number, glitch: number, height: number): GlitchBand[] {
  const g = Math.min(1, Math.max(0, glitch))
  if (g <= 0 || rand() > 0.06 + 0.25 * g) return []
  const n = 1 + Math.floor(rand() * (1 + 3 * g))
  const out: GlitchBand[] = []
  for (let i = 0; i < n; i++) {
    const h = Math.max(2, Math.round((0.01 + 0.05 * rand()) * height))
    out.push({ y: Math.round(rand() * (height - h)), h, dx: Math.round((rand() - 0.5) * 40 * (0.3 + g)) })
  }
  return out
}
