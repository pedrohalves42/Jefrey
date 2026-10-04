import { useReminders } from "@/hooks/useReminders"

/** Avisos de lembrete no canto da tela. Fica invisivel quando nao ha nada vencido. */
export function ReminderBanner() {
  const { items, dismiss, canNotify, enableNotifications } = useReminders()
  if (!items.length) return null
  return (
    <div className="pointer-events-none fixed right-3 top-3 z-50 flex w-[min(92vw,22rem)] flex-col gap-2" role="region" aria-label="Lembretes">
      {items.map(i => (
        <div key={i.id} role="alert" className="jf-panel pointer-events-auto border border-amber-300/40 p-3 shadow-lg">
          <p className="text-xs uppercase tracking-wide text-amber-200/80">Lembrete{i.repeat !== "none" ? " (repete)" : ""}</p>
          <p className="mt-1 break-words text-sm text-white">{i.text}</p>
          <div className="mt-2 flex items-center justify-between gap-2">
            {canNotify ? (
              <button type="button" onClick={() => void enableNotifications()} className="jf-focus text-xs text-white/60 underline">
                Avisar também fora desta janela
              </button>
            ) : (
              <span />
            )}
            <button type="button" onClick={() => void dismiss(i.id)} className="jf-btn jf-focus px-3 py-1 text-sm">
              Ok
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
