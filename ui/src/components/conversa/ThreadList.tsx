import type { Thread } from "@/lib/chat"

/** Lista lateral de conversas guardadas (fora do modo Facil). */
export default function ThreadList({ threads, activeId, streaming, visible, onNew, onPick, onRemove }: {
  threads: Thread[]
  activeId: string
  streaming: boolean
  visible: boolean
  onNew: () => void
  onPick: (id: string) => void
  onRemove: (id: string) => void
}) {
  return (
    <aside className={`jf-panel absolute inset-y-0 left-0 z-20 w-72 shrink-0 flex-col p-3 ${visible ? "flex" : "hidden"}`} aria-label="Conversas">
      <button type="button" onClick={onNew} disabled={streaming} className="jf-btn jf-focus mb-3 px-3 py-2 text-sm">+ Nova conversa</button>
      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
        {threads.map(t => (
          <li key={t.id} className="group flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                if (!streaming) onPick(t.id)
              }}
              aria-current={t.id === activeId}
              className={`jf-focus min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-left text-sm ${t.id === activeId ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5"}`}
            >
              {t.title}
            </button>
            <button type="button" onClick={() => onRemove(t.id)} aria-label={`Apagar conversa ${t.title}`} className="jf-focus rounded px-2 py-1 text-white/30 opacity-0 hover:text-red-300 group-hover:opacity-100 focus:opacity-100">×</button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
