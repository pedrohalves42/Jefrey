import { useEffect, useState } from "react"
import { waPending } from "@/lib/wa"

const LIMIT_S = 180

/** Aviso discreto quando o WhatsApp esta pareado mas o Chrome parou de falar com o Jefrey (aba fechada, extensao recarregada...). */
export default function WaLinkBanner() {
  const [stale, setStale] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      if (document.hidden) return
      const r = await waPending()
      if (!alive || !r.data || !r.data.paired) return setStale(null)
      const s = r.data.seen_s
      if (s === null || s === undefined) setStale("O WhatsApp está conectado, mas ainda não falou com o Jefrey. Abra Conexões → WhatsApp e aperte “Abrir o WhatsApp no Jefrey”.")
      else if (s > LIMIT_S) setStale("O WhatsApp parou de falar com o Jefrey. Abra Conexões → WhatsApp e aperte “Abrir o WhatsApp no Jefrey”.")
      else setStale(null)
    }
    void tick()
    const id = window.setInterval(() => void tick(), 20000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])
  if (!stale) return null
  return (
    <div role="status" className="fixed bottom-3 left-3 z-[55] max-w-sm rounded-xl border border-amber-300/40 bg-[#1b1406]/95 px-4 py-2.5 text-sm text-amber-100 shadow-lg backdrop-blur">
      💬 {stale}
    </div>
  )
}
