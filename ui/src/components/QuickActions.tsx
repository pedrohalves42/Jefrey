import { useNavigate } from "react-router-dom"
import { momentActions, type Action } from "@/lib/moment"

type Props = { onAsk: (text: string) => void; onSummary: () => void; busy?: boolean }

/** Atalhos de um toque na tela principal. A ordem acompanha o momento do dia: as tres primeiras ficam em destaque. */
export default function QuickActions({ onAsk, onSummary, busy = false }: Props) {
  const nav = useNavigate()
  const actions = momentActions(new Date().getHours())

  function run(a: Action) {
    if (a.id === "resumo") onSummary()
    else if (a.ask) onAsk(a.ask)
    else if (a.to) nav(a.to)
  }

  return (
    <ul className="flex w-full max-w-6xl flex-nowrap gap-1.5 overflow-x-auto pb-0.5 sm:justify-center" aria-label="Atalhos">
      {actions.map((a, i) => (
        <li key={a.id} className="shrink-0">
          <button
            type="button"
            onClick={() => run(a)}
            disabled={busy && a.id === "resumo"}
            className={`jf-focus jf-chip flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs hover:bg-white/10 ${
              i < 3 ? "border-[hsl(var(--hue)_70%_60%/0.6)] bg-[hsl(var(--hue)_60%_30%/0.25)] text-white" : "border-white/20 bg-black/35 text-white/85"
            }`}
          >
            <span aria-hidden="true">{a.icon}</span>
            {a.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
