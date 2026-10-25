import { useEffect, useState } from "react"
import { isDesktop } from "@/lib/shell"

type Api = { toggle_fullscreen?: () => Promise<boolean>; is_fullscreen?: () => Promise<boolean>; minimize?: () => Promise<boolean>; hide_window?: () => Promise<boolean> }
declare global {
  interface Window {
    pywebview?: { api?: Api & { expand?: () => Promise<boolean> } }
  }
}

function api(): Api | undefined {
  return window.pywebview?.api
}

/** Em tela cheia sem bordas nao ha barra de titulo: estes tres botoes (e a tecla F11) fazem o papel dela. So no app. */
export default function WindowControls() {
  const desktop = isDesktop()
  const [ready, setReady] = useState(false)
  const [full, setFull] = useState(true)

  useEffect(() => {
    if (!desktop) return
    let alive = true
    const check = async () => {
      const a = api()
      if (!a?.is_fullscreen) return false
      try {
        const f = await a.is_fullscreen()
        if (alive) {
          setFull(!!f)
          setReady(true)
        }
        return true
      } catch {
        return false
      }
    }
    void check()
    const id = window.setInterval(() => void check().then(ok => ok && window.clearInterval(id)), 500) // a ponte do app pode demorar um instante
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [desktop])

  async function toggle() {
    const f = await api()?.toggle_fullscreen?.()
    if (typeof f === "boolean") setFull(f)
  }

  useEffect(() => {
    if (!desktop) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "F11") {
        e.preventDefault()
        void toggle()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [desktop])

  if (!desktop || !ready) return null
  const btn = "jf-focus flex h-8 w-9 items-center justify-center text-sm text-white/70 hover:bg-white/15 hover:text-white"
  return (
    <div className="fixed left-1/2 top-0 z-[70] flex -translate-x-1/2 overflow-hidden rounded-lg border border-white/10 bg-black/40 opacity-30 backdrop-blur transition-opacity hover:opacity-100 focus-within:opacity-100" role="toolbar" aria-label="Janela">
      <button type="button" className={btn} title="Minimizar" aria-label="Minimizar" onClick={() => void api()?.minimize?.()}>–</button>
      <button type="button" className={btn} title={full ? "Sair da tela cheia (F11)" : "Tela cheia (F11)"} aria-label={full ? "Sair da tela cheia" : "Tela cheia"} onClick={() => void toggle()}>{full ? "❐" : "□"}</button>
      <button type="button" className={btn} title="Esconder no relógio (o Jefrey continua)" aria-label="Esconder no relógio" onClick={() => void api()?.hide_window?.()}>×</button>
    </div>
  )
}
