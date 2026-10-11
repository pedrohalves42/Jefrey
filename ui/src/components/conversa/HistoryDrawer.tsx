import type { ReactNode, RefObject } from "react"

/** Gaveta do historico (lado direito). O conteudo (lista de mensagens) vem de fora. */
export default function HistoryDrawer({ empty, onClose, endRef, children }: { empty: boolean; onClose: () => void; endRef: RefObject<HTMLDivElement>; children: ReactNode }) {
  return (
    <div className="absolute inset-y-0 right-0 z-50 flex w-[min(30rem,100%)] flex-col border-l border-white/10 bg-[#050d13]/95 backdrop-blur" role="dialog" aria-label="Histórico da conversa">
      <div className="flex items-center justify-between border-b border-white/10 p-3">
        <h2 className="text-lg font-medium text-white">Histórico</h2>
        <button type="button" onClick={onClose} className="jf-focus rounded-lg border border-white/20 px-3 py-1.5 text-sm text-white/85 hover:bg-white/10">Fechar</button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3" role="log" aria-live="polite" aria-label="Mensagens">
        {empty ? <p className="py-6 text-center text-base text-white/60">Ainda não conversamos. Toque no botão de voz e fale comigo.</p> : children}
        <div ref={endRef} />
      </div>
    </div>
  )
}
