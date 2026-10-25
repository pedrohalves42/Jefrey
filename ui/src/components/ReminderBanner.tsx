import { useEffect, useRef } from "react"
import { useReminders } from "@/hooks/useReminders"
import { useSpeaker } from "@/hooks/useSpeaker"
import { readFlag } from "@/lib/conversaState"
import { shouldSpeak, spokenText, type NagState } from "@/lib/reminderNag"

/** No maximo 2 avisos por vez: uma pilha de lembretes nao pode cobrir a tela. */
export const MAX_SHOWN = 2

/** Avisos de lembrete no canto da tela. Fica invisivel quando nao ha nada vencido. */
export function ReminderBanner() {
  const { items, dismiss, canNotify, enableNotifications } = useReminders()
  const speaker = useSpeaker()
  const nag = useRef<Map<string, NagState>>(new Map())
  // fala o lembrete e repete (a cada 5 min, ate 3 vezes) enquanto a pessoa nao disser Ok; so com a voz ligada e fora do horario de silencio
  useEffect(() => {
    const tick = () => {
      if (!readFlag("jefrey_voice_reply")) return
      const now = Date.now()
      const hour = new Date().getHours()
      for (const i of items) {
        const s = nag.current.get(i.id) ?? { spoken: 0, lastAt: null }
        if (shouldSpeak(s, now, hour)) {
          speaker.say(spokenText(i.text, s.spoken))
          nag.current.set(i.id, { spoken: s.spoken + 1, lastAt: now })
        }
      }
      for (const id of [...nag.current.keys()]) if (!items.some(x => x.id === id)) nag.current.delete(id)
    }
    tick()
    const id = window.setInterval(tick, 30_000)
    return () => window.clearInterval(id)
  }, [items, speaker])
  if (!items.length) return null
  const shown = items.slice(0, MAX_SHOWN)
  const extra = items.length - shown.length
  return (
    <div className="pointer-events-none fixed right-3 top-3 z-50 flex w-[min(92vw,22rem)] flex-col gap-2" role="region" aria-label="Lembretes">
      {shown.map(i => (
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
      {extra > 0 && (
        <div className="jf-panel pointer-events-auto flex items-center justify-between gap-2 border border-amber-300/40 p-3 text-sm text-white">
          <span>+ {extra} {extra === 1 ? "lembrete" : "lembretes"}</span>
          <button type="button" onClick={() => items.forEach(i => void dismiss(i.id))} className="jf-btn jf-focus px-3 py-1 text-sm">
            Ok em todos
          </button>
        </div>
      )}
    </div>
  )
}
