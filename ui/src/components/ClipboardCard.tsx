import { useEffect, useState } from "react"
import { ACTION_LABEL, clipboardPrompt, dismissClipboard, getClipboard, knownOffers, offerTitle, type ClipState } from "@/lib/clipboard"

/** Oferta da area de transferencia: aparece so quando a pessoa ligou o recurso e copiou um texto. Nada e colado de volta. */
export default function ClipboardCard({ onAsk }: { onAsk: (prompt: string) => void }) {
  const [st, setSt] = useState<ClipState | null>(null)

  useEffect(() => {
    let alive = true
    const tick = () => void getClipboard().then(s => alive && setSt(s))
    tick()
    const t = window.setInterval(tick, 3000)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [])

  if (!st?.enabled || !st.offer) return null
  const offers = knownOffers(st.offer.offers)
  if (offers.length === 0) return null

  async function act(action: string) {
    const p = await clipboardPrompt(action)
    await dismissClipboard()
    setSt(s => (s ? { ...s, offer: null } : s))
    if (p) onAsk(p)
  }

  return (
    <div className="jf-glass w-full max-w-lg rounded-xl px-4 py-2 text-sm" role="region" aria-label="Texto copiado">
      <p className="text-white/85">{offerTitle(offers)}</p>
      <p className="mt-0.5 line-clamp-1 text-xs text-white/45">{st.offer.preview}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {offers.map(a => (
          <button key={a} type="button" onClick={() => void act(a)} className="jf-btn jf-focus px-3 py-1 text-sm">
            {ACTION_LABEL[a]}
          </button>
        ))}
        <button type="button" onClick={() => { void dismissClipboard(); setSt(s => (s ? { ...s, offer: null } : s)) }} className="jf-focus px-2 py-1 text-xs text-white/55 underline">
          Agora não
        </button>
      </div>
    </div>
  )
}
