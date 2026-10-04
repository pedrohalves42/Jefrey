import { useEffect, useState } from "react"
import { getProfile, putProfile } from "@/lib/llm"

/** "Como posso te chamar?" Campo simples; salva ao confirmar. */
export default function NameField({ compact = false }: { compact?: boolean }) {
  const [name, setName] = useState("")
  const [saved, setSaved] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void getProfile().then(r => {
      const n = r.data?.display_name ?? null
      setSaved(n)
      if (n) setName(n)
    })
  }, [])

  async function save() {
    if (!name.trim()) return
    setBusy(true)
    setErr(null)
    const r = await putProfile(name.trim())
    setBusy(false)
    if (r.ok && r.data) {
      setSaved(r.data.display_name)
      setName(r.data.display_name)
    } else {
      const d = (r.data as unknown as { detail?: string } | null)?.detail
      setErr(typeof d === "string" ? d : "Não consegui salvar o nome.")
    }
  }

  return (
    <div className={compact ? "" : "jf-panel p-5"}>
      {!compact && <h2 className="text-lg font-medium text-white">Como posso te chamar?</h2>}
      <div className="mt-2 flex gap-2">
        <input
          className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/30"
          value={name}
          maxLength={40}
          placeholder="Seu nome ou apelido"
          aria-label="Seu nome"
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === "Enter" && void save()}
        />
        <button type="button" onClick={() => void save()} disabled={busy || !name.trim()} className="jf-btn jf-focus px-4 py-2 text-sm">
          Salvar
        </button>
      </div>
      {saved && !err && <p className="mt-2 text-sm text-emerald-300">Prazer, {saved}!</p>}
      {err && <p role="alert" className="mt-2 text-sm text-red-300">{err}</p>}
    </div>
  )
}
