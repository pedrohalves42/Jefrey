import { useNavigate } from "react-router-dom"

type Props = { onAsk: (text: string) => void; onSummary: () => void; busy?: boolean }

/** Atalhos de um toque na tela principal: o que a pessoa mais pede, sem digitar nem lembrar o que dizer. */
export default function QuickActions({ onAsk, onSummary, busy = false }: Props) {
  const nav = useNavigate()
  const items: { icon: string; label: string; run: () => void }[] = [
    { icon: "☀️", label: "Resumo do dia", run: onSummary },
    { icon: "⏰", label: "Criar lembrete", run: () => onAsk("Quero criar um lembrete") },
    { icon: "📰", label: "Notícias", run: () => nav("/hoje") },
    { icon: "📈", label: "Bolsa e dólar", run: () => nav("/hoje") },
    { icon: "🎓", label: "Aprender algo", run: () => nav("/aprender") },
    { icon: "🧠", label: "O que você sabe de mim?", run: () => onAsk("O que você sabe sobre mim?") },
    { icon: "💡", label: "O que posso pedir?", run: () => onAsk("O que você consegue fazer por mim?") },
  ]
  return (
    <ul className="flex w-full max-w-3xl snap-x gap-2 overflow-x-auto pb-1" aria-label="Atalhos">
      {items.map(i => (
        <li key={i.label} className="snap-start">
          <button
            type="button"
            onClick={i.run}
            disabled={busy && i.label === "Resumo do dia"}
            className="jf-focus jf-chip flex items-center gap-1.5 whitespace-nowrap rounded-full border border-white/20 bg-black/35 px-3 py-1.5 text-sm text-white/90 hover:bg-white/10"
          >
            <span aria-hidden="true">{i.icon}</span>
            {i.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
