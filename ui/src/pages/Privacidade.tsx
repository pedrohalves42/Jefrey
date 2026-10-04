import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { DocView } from "@/pages/Termos"
import { downloadMyData, eraseAll, getLegalDocs, getSummary, summaryLines, type LegalDocs, type Summary } from "@/lib/legal"

const card = "jf-panel p-5"

export default function Privacidade() {
  const [sum, setSum] = useState<Summary | null>(null)
  const [docs, setDocs] = useState<LegalDocs | null>(null)
  const [show, setShow] = useState<"" | "privacidade" | "termos">("")
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [confirm, setConfirm] = useState("")
  const [ask, setAsk] = useState(false)
  const [busy, setBusy] = useState(false)

  async function load() {
    const r = await getSummary()
    if (r.data) setSum(r.data)
  }
  useEffect(() => {
    void load()
    void getLegalDocs().then(r => setDocs(r.data))
  }, [])

  async function download() {
    const ok = await downloadMyData()
    setMsg(ok ? { ok: true, text: "Pronto. O arquivo “meus-dados-jefrey.json” foi baixado." } : { ok: false, text: "Não consegui baixar agora. Tente de novo." })
  }

  async function erase() {
    setBusy(true)
    const r = await eraseAll(confirm)
    setBusy(false)
    if (r.ok) {
      setAsk(false)
      setConfirm("")
      setMsg({ ok: true, text: "Pronto. Apaguei os seus dados deste computador." })
      await load()
    } else setMsg({ ok: false, text: r.status === 422 ? "Para apagar, digite a palavra APAGAR." : "Não consegui apagar agora. Tente de novo." })
  }

  const lines = sum ? summaryLines(sum) : []
  const intro = "Aqui você vê o que eu guardo sobre você, baixa uma cópia ou apaga tudo. Tudo fica só neste computador."
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Meus dados e privacidade</h1>
        <p className="mt-1 text-base text-white/70">{intro}</p>
        <div className="mt-3"><ListenButton text={intro} /></div>
      </header>

      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>
          {msg.text}
        </p>
      )}

      <section className={card} aria-labelledby="p-guardo">
        <h2 id="p-guardo" className="text-xl font-medium text-white">O que eu guardo</h2>
        {lines.length === 0 ? <p className="mt-2 text-base text-white/70">Ainda não guardo nada sobre você.</p> : (
          <ul className="mt-2 space-y-1 text-base text-white/85">{lines.map(l => <li key={l}>• {l}</li>)}</ul>
        )}
        <p className="mt-3 text-sm text-white/60">
          Para ver e corrigir o que aprendi, abra <Link className="underline" to="/aprendi">O que aprendi</Link>.
        </p>
      </section>

      <section className={card} aria-labelledby="p-copia">
        <h2 id="p-copia" className="text-xl font-medium text-white">Baixar uma cópia</h2>
        <p className="mt-1 text-base text-white/75">Um arquivo com tudo o que eu guardo sobre você, em texto que dá para ler. Senhas e chaves nunca entram.</p>
        <button type="button" onClick={() => void download()} className="jf-btn jf-focus mt-3 px-5 py-3 text-base">Baixar meus dados</button>
      </section>

      <section className={card} aria-labelledby="p-apagar">
        <h2 id="p-apagar" className="text-xl font-medium text-white">Apagar tudo</h2>
        <p className="mt-1 text-base text-white/75">
          Remove o seu nome, as conversas, o que aprendi, o diário, os estudos, os lembretes, as notas e memórias, o WhatsApp e as conexões com o Google. Não dá para desfazer.
        </p>
        {ask ? (
          <div className="mt-3">
            <label className="block text-base text-white/85">
              Para confirmar, digite <b>APAGAR</b>
              <input className="mt-1 w-full rounded-lg border border-white/20 bg-black/40 px-3 py-3 text-lg text-white" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="off" />
            </label>
            <div className="mt-3 flex gap-2">
              <button type="button" disabled={busy || confirm.trim().toUpperCase() !== "APAGAR"} onClick={() => void erase()} className="jf-focus rounded-lg border border-red-300/50 px-5 py-3 text-base text-red-100 hover:bg-red-400/10">
                Apagar tudo agora
              </button>
              <button type="button" onClick={() => { setAsk(false); setConfirm("") }} className="jf-btn jf-focus px-5 py-3 text-base">Não, manter</button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => setAsk(true)} className="jf-focus mt-3 rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">Apagar tudo…</button>
        )}
      </section>

      <section className={card} aria-labelledby="p-textos">
        <h2 id="p-textos" className="text-xl font-medium text-white">Ler os textos completos</h2>
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={() => setShow(show === "privacidade" ? "" : "privacidade")} className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5">Política de privacidade</button>
          <button type="button" onClick={() => setShow(show === "termos" ? "" : "termos")} className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5">Termos de uso</button>
        </div>
        {show && docs && <div className="mt-4"><DocView md={docs[show]} /></div>}
      </section>
    </div>
  )
}
