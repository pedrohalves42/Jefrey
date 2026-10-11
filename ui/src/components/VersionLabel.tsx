import { useEffect, useState } from "react"
import { authedFetch } from "@/lib/session"

/** "v0.9.1 · compilação 2026-10-05 19:34 abc123": mostra QUAL instalador esta rodando (ajuda a ver se e o mais novo). */
export default function VersionLabel({ className = "" }: { className?: string }) {
  const [txt, setTxt] = useState("")
  useEffect(() => {
    let alive = true
    void (async () => {
      try {
        const r = await authedFetch("/health")
        const d = (await r.json()) as { version?: string; build?: string }
        if (alive && d.version) setTxt(`v${d.version}${d.build && d.build !== "desenvolvimento" ? ` · compilação ${d.build}` : " · desenvolvimento"}`)
      } catch {
        /* sem o rotulo: nada quebra */
      }
    })()
    return () => {
      alive = false
    }
  }, [])
  if (!txt) return null
  return <p className={`text-xs text-white/40 ${className}`} aria-label="Versão do Jefrey">{txt}</p>
}
