import { lazy, Suspense, useState } from "react"
import { useAppearance } from "@/lib/appearance"
import type { BrainState } from "./BrainScene"

const BrainScene = lazy(() => import("./BrainScene"))
const HologramAvatar = lazy(() => import("./HologramAvatar"))

export type { BrainState }

const LABEL: Record<BrainState, string> = {
  idle: "Pronto",
  listening: "Ouvindo",
  thinking: "Pensando",
  responding: "Respondendo",
  approval: "Aguardando sua aprovação",
}

/** Plano B leve (CSS puro) quando a visualizacao esta desligada ou o WebGL nao existe. */
function SimpleOrb({ state }: { state: BrainState }) {
  const busy = state !== "idle"
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div
        className={`jf-orb ${busy ? "jf-orb-busy" : ""}`}
        style={{ ["--orb-hue" as string]: state === "approval" ? 38 : undefined }}
      />
    </div>
  )
}

export function BrainStage({ state, level = 0, className = "", note = null }: { state: BrainState; level?: number; className?: string; note?: string | null }) {
  const { appearance, set } = useAppearance()
  const [noGl, setNoGl] = useState(false)
  const [slow, setSlow] = useState(false)

  const holo = appearance.visual && appearance.shape === "hologram"
  const show3d = appearance.visual && !noGl && !holo

  return (
    <div className={`relative ${className}`} role="img" aria-label={`Jefrey: ${note ?? LABEL[state]}`}>
      {holo ? (
        <Suspense fallback={<SimpleOrb state={state} />}>
          <HologramAvatar state={state} level={level} appearance={appearance} />
        </Suspense>
      ) : show3d ? (
        <Suspense fallback={<SimpleOrb state={state} />}>
          <BrainScene
            state={state}
            level={level}
            appearance={appearance}
            onUnavailable={() => setNoGl(true)}
            onSlow={() => setSlow(true)}
          />
        </Suspense>
      ) : (
        <SimpleOrb state={state} />
      )}
      <div className="pointer-events-none absolute bottom-1 left-0 right-0 text-center text-xs tracking-wide text-[hsl(var(--hue)_80%_75%)] opacity-80">
        {note ?? LABEL[state]}
      </div>
      {slow && show3d && (
        <button
          type="button"
          onClick={() => {
            set({ particles: 0.2, motion: false })
            setSlow(false)
          }}
          className="absolute right-2 top-2 rounded-md border border-white/15 bg-black/50 px-2 py-1 text-xs text-white/80 hover:bg-black/70"
        >
          Está lento? Usar modo leve
        </button>
      )}
      {noGl && appearance.visual && (
        <p className="absolute left-2 top-2 text-xs text-amber-300/80">3D indisponível neste navegador; usando modo simples.</p>
      )}
    </div>
  )
}
