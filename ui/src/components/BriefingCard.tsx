import { useEffect, useState } from "react"
import ListenButton from "@/components/ListenButton"
import { getBriefing, markBriefingSeen, shouldShowBriefing, type Briefing } from "@/lib/briefing"

/** Resumo do dia no topo da conversa. Some quando a pessoa der ciente. */
export default function BriefingCard() {
  const [b, setB] = useState<Briefing | null>(null)
  useEffect(() => {
    void getBriefing().then(r => setB(r.data?.briefing ?? null))
  }, [])
  if (!shouldShowBriefing(b)) return null
  return (
    <section className="jf-panel mb-1 border border-cyan-400/30 px-3 py-2" aria-label="Resumo do dia">
      <h2 className="text-sm font-medium text-cyan-200">Resumo do dia</h2>
      <p className="mt-0.5 max-h-20 overflow-y-auto whitespace-pre-line text-sm leading-snug text-white/80">{b.text}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <ListenButton text={b.text} label="Ouvir o resumo" />
        <button
          type="button"
          onClick={() => {
            setB(null)
            void markBriefingSeen()
          }}
          className="jf-btn jf-focus px-3 py-1.5 text-sm"
        >
          Entendi
        </button>
      </div>
    </section>
  )
}
