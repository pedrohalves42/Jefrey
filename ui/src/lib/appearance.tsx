import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

export type BrainShape = "brain" | "orb" | "reactor" | "hologram"

export type Appearance = {
  hue: number // 0-360, cor principal
  shape: BrainShape // forma da visualizacao
  intensity: number // 0-1, brilho/energia
  particles: number // 0-1, densidade de neuronios/particulas
  motion: boolean // animacoes ligadas
  visual: boolean // visualizacao 3D ligada (desligar = so chat, mais leve)
  holoScan: number // 0-1, linhas de varredura do holograma
  holoGlitch: number // 0-1, falhas e aberracao de cor do holograma
  holoCut: number // 0-1, quanto do fundo escuro some
  holoInvert: boolean // imagem de fundo claro
}

export const DEFAULT_APPEARANCE: Appearance = {
  hue: 32,
  shape: "brain",
  intensity: 0.7,
  particles: 0.6,
  motion: true,
  visual: true,
  holoScan: 0.5,
  holoGlitch: 0.25,
  holoCut: 0.12,
  holoInvert: false,
}

export const PRESETS: { id: string; label: string; value: Partial<Appearance> }[] = [
  { id: "jefrey", label: "Jefrey (cobre, padrão)", value: { hue: 32, shape: "brain", intensity: 0.7 } },
  { id: "stark", label: "Stark (ciano)", value: { hue: 191, shape: "reactor", intensity: 0.8 } },
  { id: "holo", label: "Holograma", value: { hue: 191, shape: "hologram", intensity: 0.85, holoScan: 0.55, holoGlitch: 0.3 } },
  { id: "neural", label: "Neural (violeta)", value: { hue: 268, shape: "brain", intensity: 0.7 } },
  { id: "matrix", label: "Matrix (verde)", value: { hue: 140, shape: "brain", intensity: 0.6 } },
  { id: "ambar", label: "Ambar (JARVIS)", value: { hue: 38, shape: "orb", intensity: 0.75 } },
  { id: "calmo", label: "Calmo (sem animacao)", value: { hue: 210, shape: "orb", intensity: 0.4, motion: false } },
]

const KEY = "jefrey_appearance_v2" // v2: identidade nova (cobre); quem personalizou antes escolhe de novo em Aparencia

function clamp(n: unknown, lo: number, hi: number, fallback: number): number {
  const v = typeof n === "number" && Number.isFinite(n) ? n : fallback
  return Math.min(hi, Math.max(lo, v))
}

/** Valida qualquer objeto vindo do localStorage/importacao; nunca confia no formato. */
export function sanitizeAppearance(raw: unknown): Appearance {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>
  const shape: BrainShape = r.shape === "orb" || r.shape === "reactor" || r.shape === "brain" || r.shape === "hologram" ? r.shape : DEFAULT_APPEARANCE.shape
  return {
    hue: Math.round(clamp(r.hue, 0, 360, DEFAULT_APPEARANCE.hue)),
    shape,
    intensity: clamp(r.intensity, 0, 1, DEFAULT_APPEARANCE.intensity),
    particles: clamp(r.particles, 0, 1, DEFAULT_APPEARANCE.particles),
    motion: typeof r.motion === "boolean" ? r.motion : DEFAULT_APPEARANCE.motion,
    visual: typeof r.visual === "boolean" ? r.visual : DEFAULT_APPEARANCE.visual,
    holoScan: clamp(r.holoScan, 0, 1, DEFAULT_APPEARANCE.holoScan),
    holoGlitch: clamp(r.holoGlitch, 0, 1, DEFAULT_APPEARANCE.holoGlitch),
    holoCut: clamp(r.holoCut, 0, 0.9, DEFAULT_APPEARANCE.holoCut),
    holoInvert: typeof r.holoInvert === "boolean" ? r.holoInvert : DEFAULT_APPEARANCE.holoInvert,
  }
}

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
  } catch {
    return false
  }
}

function load(): Appearance {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return sanitizeAppearance(JSON.parse(raw))
  } catch {
    /* localStorage indisponivel ou JSON invalido: cai no padrao */
  }
  return { ...DEFAULT_APPEARANCE, motion: !prefersReducedMotion() }
}

type Ctx = {
  appearance: Appearance
  set: (patch: Partial<Appearance>) => void
  reset: () => void
  exportJson: () => string
  importJson: (text: string) => boolean
}

const AppearanceContext = createContext<Ctx | null>(null)

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState<Appearance>(load)

  useEffect(() => {
    document.documentElement.style.setProperty("--hue", String(appearance.hue))
    document.documentElement.dataset.motion = appearance.motion ? "on" : "off"
    try {
      localStorage.setItem(KEY, JSON.stringify(appearance))
    } catch {
      /* ignora */
    }
  }, [appearance])

  const set = useCallback((patch: Partial<Appearance>) => {
    setAppearance(prev => sanitizeAppearance({ ...prev, ...patch }))
  }, [])
  const reset = useCallback(() => setAppearance({ ...DEFAULT_APPEARANCE }), [])
  const exportJson = useCallback(() => JSON.stringify(appearance, null, 2), [appearance])
  const importJson = useCallback((text: string) => {
    try {
      setAppearance(sanitizeAppearance(JSON.parse(text)))
      return true
    } catch {
      return false
    }
  }, [])

  const value = useMemo(() => ({ appearance, set, reset, exportJson, importJson }), [appearance, set, reset, exportJson, importJson])
  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>
}

export function useAppearance(): Ctx {
  const c = useContext(AppearanceContext)
  if (!c) throw new Error("useAppearance fora do AppearanceProvider")
  return c
}
