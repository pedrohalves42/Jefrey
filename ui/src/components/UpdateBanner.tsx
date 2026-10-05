import { useEffect, useState } from "react"
import { checkUpdate, installUpdate, sizeLabel, type UpdateInfo } from "@/lib/updates"

const EVERY_MS = 6 * 60 * 60 * 1000
const SNOOZE_KEY = "jefrey_update_snooze"

function snoozed(version: string): boolean {
  try {
    return localStorage.getItem(SNOOZE_KEY) === version
  } catch {
    return false
  }
}

/** Procura versao nova ao abrir e a cada 6 h. So avisa: nada instala sem a pessoa tocar em "Atualizar agora". */
export function UpdateBanner() {
  const [info, setInfo] = useState<UpdateInfo | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState("")

  useEffect(() => {
    let alive = true
    const look = async () => {
      const r = await checkUpdate()
      if (alive && r.ok && r.data?.available && r.data.version && !snoozed(r.data.version)) setInfo(r.data)
    }
    void look()
    const id = window.setInterval(() => void look(), EVERY_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  if (!info) return null

  async function go() {
    setBusy(true)
    setErr("")
    const r = await installUpdate()
    setBusy(false)
    if (!r.ok) {
      const d = (r.data as { detail?: unknown } | null)?.detail
      setErr(typeof d === "string" ? d : "Não consegui atualizar agora. Tente de novo mais tarde.")
    }
  }
  function later() {
    try {
      if (info?.version) localStorage.setItem(SNOOZE_KEY, info.version)
    } catch {
      /* sem armazenamento: o aviso volta na proxima abertura */
    }
    setInfo(null)
  }

  return (
    <div role="status" className="jf-panel fixed bottom-4 right-4 z-50 w-[min(94vw,24rem)] border border-cyan-400/40 p-4 text-base text-white">
      <p className="font-medium">Tem uma versão nova do Jefrey ({info.version}){info.size ? ` · ${sizeLabel(info.size)}` : ""}</p>
      {info.notes && <p className="mt-1 text-sm text-white/70">{info.notes}</p>}
      <p className="mt-1 text-sm text-white/60">Seus dados ficam guardados. O Jefrey fecha e abre sozinho.</p>
      {err && <p role="alert" className="mt-2 text-sm text-red-200">{err}</p>}
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={() => void go()} disabled={busy} className="jf-btn jf-focus px-4 py-2">{busy ? "Atualizando…" : "Atualizar agora"}</button>
        <button type="button" onClick={later} disabled={busy} className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-white/85 hover:bg-white/5">Depois</button>
      </div>
    </div>
  )
}
