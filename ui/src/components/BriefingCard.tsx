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
    <section className="jf-panel mb-2 border border-cyan-400/30 p-4" aria-label="Resumo do dia">
      <h2 className="text-lg font-medium text-white">Resumo do dia</h2>
      <p className="mt-1 whitespace-pre-line text-base text-white/85">{b.text}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <ListenButton text={b.text} label="Ouvir o resumo" />
        <button
          type="button"
          onClick={() => {
            setB(null)
            void markBriefingSeen()
          }}
          className="jf-btn jf-focus px-4 py-2 text-base"
        >
          Entendi
        </button>
      </div>
    </section>
  )
}
