import type { KeyboardEvent, ReactNode, RefObject } from "react"

const small = "jf-focus rounded-lg border border-white/20 bg-black/40 px-2.5 py-2 text-sm text-white/75 hover:bg-white/10"

/** Linha de baixo: engrenagem (menu), conversas, historico, caixa de texto e enviar/parar. */
export default function Composer(p: {
  menu: ReactNode
  menuOpen: boolean
  onToggleMenu: () => void
  showThreadsButton: boolean
  threadsOpen: boolean
  onToggleThreads: () => void
  onOpenHistory: () => void
  taRef: RefObject<HTMLTextAreaElement>
  input: string
  onInput: (v: string) => void
  onKey: (e: KeyboardEvent<HTMLTextAreaElement>) => void
  streaming: boolean
  onStop: () => void
  onSend: () => void
}) {
  return (
    <div className="flex w-full max-w-2xl items-end gap-1.5">
      <div className="relative">
        <button type="button" onClick={p.onToggleMenu} aria-expanded={p.menuOpen} aria-label="Opções" className={small}>⚙</button>
        {p.menuOpen && p.menu}
      </div>
      {p.showThreadsButton && <button type="button" onClick={p.onToggleThreads} aria-pressed={p.threadsOpen} aria-label="Minhas conversas" className={small}>Conversas</button>}
      <button type="button" onClick={p.onOpenHistory} aria-label="Histórico da conversa" className={small}>Histórico</button>
      <textarea
        ref={p.taRef}
        value={p.input}
        onChange={e => p.onInput(e.target.value)}
        onKeyDown={p.onKey}
        rows={1}
        maxLength={10000}
        placeholder="Ou escreva aqui…"
        aria-label="Mensagem para o Jefrey"
        className="jf-focus max-h-28 min-h-[38px] flex-1 resize-none rounded-lg border border-white/15 bg-black/45 px-3 py-2 text-sm outline-none placeholder:text-white/35"
        style={{ height: "auto" }}
        onInput={e => {
          const el = e.currentTarget
          el.style.height = "auto"
          el.style.height = Math.min(el.scrollHeight, 112) + "px"
        }}
      />
      {p.streaming ? (
        <button type="button" onClick={p.onStop} className="jf-focus rounded-lg border border-white/25 bg-black/40 px-3 py-2 text-sm text-white/85 hover:bg-white/10">Parar</button>
      ) : (
        <button type="button" onClick={p.onSend} disabled={!p.input.trim()} className="jf-btn jf-focus px-3 py-2 text-sm">Enviar</button>
      )}
    </div>
  )
}
