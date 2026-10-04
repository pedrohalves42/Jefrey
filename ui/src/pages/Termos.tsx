import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import ListenButton from "@/components/ListenButton"
import { acceptLegal, getLegalDocs, parseDoc, plain, type DocBlock, type LegalDocs } from "@/lib/legal"

export function DocView({ md }: { md: string }) {
  const blocks: DocBlock[] = parseDoc(md)
  return (
    <div className="space-y-2">
      {blocks.map((b, i) => {
        if (b.type === "h1") return <h2 key={i} className="text-2xl font-semibold text-white">{b.text}</h2>
        if (b.type === "h2") return <h3 key={i} className="pt-3 text-lg font-medium text-white">{b.text}</h3>
        if (b.type === "li") return <p key={i} className="pl-3 text-base text-white/85">• {plain(b.text)}</p>
        if (b.type === "table")
          return (
            <ul key={i} className="space-y-2">
              {b.rows.map((r, j) => (
                <li key={j} className="rounded-lg border border-white/10 p-3 text-base text-white/85">
                  {r.map((c, k) => (
                    <p key={k}>
                      <span className="text-white/55">{b.header[k]}: </span>
                      {plain(c)}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          )
        return <p key={i} className="text-base text-white/85">{plain(b.text)}</p>
      })}
    </div>
  )
}

/** Primeira tela: termos e privacidade em linguagem simples, com um botao grande para aceitar. */
export default function Termos() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [docs, setDocs] = useState<LegalDocs | null>(null)
  const [tab, setTab] = useState<"termos" | "privacidade">("privacidade")
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void getLegalDocs().then(r => setDocs(r.data))
  }, [])

  async function accept() {
    setBusy(true)
    const r = await acceptLegal()
    setBusy(false)
    if (r.ok) {
      await qc.invalidateQueries({ queryKey: ["legal"] })
      nav("/", { replace: true })
    } else setErr("Não consegui registrar o aceite agora. Tente de novo.")
  }

  const resumo =
    "Antes de começar: o Jefrey roda no seu computador e o que ele aprende fica aqui. Para pensar, ele usa a inteligência na nuvem que você escolher, e o texto da conversa vai para esse serviço. " +
    "Ele pode errar, então confira o que for importante. Você pode ver, baixar e apagar os seus dados quando quiser."
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Antes de começar</h1>
        <p className="mt-2 text-base text-white/80">{resumo}</p>
        <div className="mt-3"><ListenButton text={resumo} label="Ouvir" /></div>
      </header>

      <div className="flex gap-2">
        {(["privacidade", "termos"] as const).map(t => (
          <button
            key={t}
            type="button"
            aria-pressed={tab === t}
            onClick={() => setTab(t)}
            className={`jf-focus rounded-lg border px-4 py-2 text-base ${tab === t ? "border-cyan-300 bg-cyan-400/10 text-white" : "border-white/25 text-white/80 hover:bg-white/5"}`}
          >
            {t === "privacidade" ? "Privacidade" : "Termos de uso"}
          </button>
        ))}
      </div>

      <section className="jf-panel p-5" aria-label={tab === "termos" ? "Termos de uso" : "Política de privacidade"}>
        {docs ? <DocView md={docs[tab]} /> : <p className="text-base text-white/70">Carregando…</p>}
      </section>

      {err && <p role="alert" className="text-base text-red-200">{err}</p>}
      <div className="sticky bottom-0 bg-gradient-to-t from-[#050b10] to-transparent pb-2 pt-4">
        <button type="button" onClick={() => void accept()} disabled={busy || !docs} className="jf-btn jf-focus w-full rounded-xl px-6 py-4 text-xl font-medium">
          {busy ? "Registrando…" : "Li e aceito"}
        </button>
      </div>
    </div>
  )
}
