import { useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { TodayCards, TodayFooter, useToday } from "@/pages/Hoje"
import { spokenSummary } from "@/lib/today"

/** "Hoje" em janela por cima da tela principal: a pessoa ve o dia sem sair da conversa. Esc ou "Fechar" volta. */
export default function TodayPopup({ name, onClose }: { name?: string; onClose: () => void }) {
  const { d, failed, reload } = useToday()
  const box = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    box.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("keydown", onKey)
      prev?.focus?.()
    }
  }, [onClose])

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 p-3 sm:p-6" role="presentation" onClick={onClose}>
      <div
        ref={box}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Hoje"
        onClick={e => e.stopPropagation()}
        className="jf-panel flex max-h-full w-full max-w-4xl flex-col overflow-hidden border border-white/15 bg-[#06121a]/95 shadow-2xl outline-none"
      >
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
          <h2 className="text-xl font-semibold text-white">Hoje{name ? `, ${name}` : ""}</h2>
          <div className="flex items-center gap-2">
            {d && <ListenButton text={spokenSummary(d, name)} />}
            <Link to="/hoje" onClick={onClose} className="jf-focus rounded-lg border border-white/20 px-3 py-2 text-sm text-white/80 hover:bg-white/5">Abrir em tela cheia</Link>
            <button type="button" onClick={onClose} className="jf-btn jf-focus px-4 py-2 text-base">Fechar</button>
          </div>
        </header>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
          {failed && !d && <p role="alert" className="text-base text-red-200">Não consegui montar o painel agora. Verifique a internet.</p>}
          {!d && !failed && <p className="text-base text-white/60">Buscando as novidades…</p>}
          {d && <TodayCards d={d} reload={reload} />}
          {d && <TodayFooter d={d} />}
        </div>
      </div>
    </div>
  )
}
