import { useEffect, useRef, useState } from "react"
import { downloadMessage, getLocalStatus, startModelDownload, type LocalStatus } from "@/lib/voice"

/** Baixa a voz natural que roda neste computador (uma vez so). Sem internet depois, e o texto nao sai do PC. */
export default function VoiceDownload() {
  const [st, setSt] = useState<LocalStatus | null>(null)
  const timer = useRef<number>(0)

  async function refresh() {
    const r = await getLocalStatus()
    if (r.data) setSt(r.data)
    return r.data
  }
  function poll() {
    window.clearInterval(timer.current)
    timer.current = window.setInterval(async () => {
      const d = await refresh()
      if (d && d.state !== "running") window.clearInterval(timer.current)
    }, 1500)
  }
  useEffect(() => {
    void refresh().then(d => d?.state === "running" && poll())
    return () => window.clearInterval(timer.current)
  }, [])

  async function go() {
    const r = await startModelDownload()
    if (r.data) setSt(prev => ({ ...(prev as LocalStatus), ...r.data! }))
    poll()
  }

  const ready = !!st && (st.installed || st.state === "done")
  return (
    <section className="jf-panel p-4" aria-label="Voz natural neste computador">
      <h2 className="text-lg font-semibold text-white">Voz natural neste computador</h2>
      <p className="text-sm text-white/55">Uma voz mais natural, que funciona sem internet e não envia o que o Jefrey fala para fora.</p>
      <p role="status" className="mt-2 text-base text-white/85">{downloadMessage(st)}</p>
      {st?.state === "running" && (
        <div className="mt-2 h-2 overflow-hidden rounded bg-white/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={st.pct} aria-label="Progresso do download">
          <div className="h-full bg-[hsl(var(--hue)_90%_60%)]" style={{ width: `${st.pct}%` }} />
        </div>
      )}
      {!ready && st?.state !== "running" && (
        <button type="button" onClick={() => void go()} className="jf-btn jf-focus mt-3 px-5 py-3 text-base">Baixar a voz natural</button>
      )}
    </section>
  )
}
