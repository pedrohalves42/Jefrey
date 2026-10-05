import { useState } from "react"
import { authedFetch } from "@/lib/session"

/** "Algo deu errado": gera um arquivo para o suporte, sem senhas nem chaves. A pessoa decide se envia. */
export default function ReportProblem() {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  async function go() {
    setBusy(true)
    setMsg(null)
    try {
      const r = await authedFetch("/support/report", { method: "POST" })
      const d = (await r.json().catch(() => null)) as { path?: string } | null
      setMsg(r.ok && d?.path
        ? { ok: true, text: `Pronto! Guardei o relatório em ${d.path}. Mande esse arquivo para quem te ajuda. Ele não tem senhas nem chaves.` }
        : { ok: false, text: "Não consegui gerar o relatório agora. Tente de novo." })
    } catch {
      setMsg({ ok: false, text: "Não consegui gerar o relatório agora. Tente de novo." })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="jf-panel p-5" aria-label="Algo deu errado">
      <h2 className="text-xl font-medium text-white">Algo deu errado?</h2>
      <p className="mt-2 text-base text-white/80">Eu preparo um arquivo com o que aconteceu, sem senhas nem chaves, para você mandar a quem te ajuda.</p>
      <button type="button" onClick={() => void go()} disabled={busy} className="jf-btn jf-focus mt-3 px-5 py-3 text-base">{busy ? "Preparando…" : "Preparar o relatório"}</button>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-3 text-base ${msg.ok ? "text-emerald-100" : "text-red-200"}`}>{msg.text}</p>}
    </section>
  )
}
