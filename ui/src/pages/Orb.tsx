import { useEffect, useRef, useState } from "react"
import { BrainStage } from "@/components/brain/BrainStage"
import { ensureSession } from "@/lib/session"
import { listenOrb, showMainWindow, type OrbState } from "@/lib/shell"

declare global {
  interface Window {
    pywebview?: { api?: { expand?: () => Promise<boolean> } }
  }
}

/** Bolinha pequena, sempre visivel: mostra o que o Jefrey esta fazendo; um clique abre a janela grande. */
export default function Orb() {
  const [s, setS] = useState<OrbState>({ state: "idle", level: 0 })
  const down = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    document.documentElement.style.background = "#030a10"
    document.body.style.background = "#030a10"
    document.body.style.overflow = "hidden"
    void ensureSession()
    return listenOrb(setS)
  }, [])

  const open = async () => {
    try {
      if (window.pywebview?.api?.expand) {
        await window.pywebview.api.expand()
        return
      }
    } catch {
      /* cai no pedido pelo servidor */
    }
    await showMainWindow()
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Abrir o Jefrey"
      title="Clique para abrir o Jefrey (arraste para mover)"
      className="h-screen w-screen cursor-pointer select-none"
      onPointerDown={e => {
        down.current = { x: e.clientX, y: e.clientY }
      }}
      onPointerUp={e => {
        const d = down.current
        down.current = null
        if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) void open() // arrastar nao abre
      }}
      onKeyDown={e => {
        if (e.key === "Enter" || e.key === " ") void open()
      }}
    >
      <BrainStage state={s.state} level={s.level} className="h-full w-full" />
    </div>
  )
}
