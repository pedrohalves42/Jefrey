import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import ListenButton from "@/components/ListenButton"
import NameField from "@/components/NameField"
import { getAdvice, getPullStatus, overallPercent, saveConfig, skipWelcome, startOpenRouter, startPull, type Advice, type PullStatus } from "@/lib/llm"

const INTRO = "Oi! Eu sou o Jefrey, o seu assistente. Para começar, me diga como você se chama e depois aperte o botão para me ligar à inteligência que me faz pensar."

export default function BemVindo() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const [advice, setAdvice] = useState<Advice | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [pull, setPull] = useState<PullStatus | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(
    params.get("erro") === "openrouter" ? { ok: false, text: "A conexão não foi concluída. Se você cancelou, está tudo bem: é só apertar o botão de novo." } : null,
  )

  useEffect(() => {
    void getAdvice().then(r => setAdvice(r.data))
  }, [])

  async function oneClick() {
    setBusy("oneclick")
    setMsg(null)
    const err = await startOpenRouter()
    if (err) {
      setMsg({ ok: false, text: err })
      setBusy(null)
    }
  }

  async function useLocal(m: string) {
    setBusy("local")
    setMsg(null)
    const saved = await saveConfig({ provider: "ollama", model: m, base_url: null })
    setBusy(null)
    if (!saved.ok) {
      setMsg({ ok: false, text: "Não consegui preparar isso agora. Tente de novo." })
      return
    }
    const started = await startPull([m, "embeddinggemma"])
    if (!started.ok) {
      const d = (started.data as unknown as { detail?: string } | null)?.detail
      setMsg({ ok: false, text: typeof d === "string" ? d : "Não consegui preparar o Jefrey no seu computador. A opção de 1 clique funciona sem isso." })
      return
    }
    setPull(started.data)
    await qc.invalidateQueries({ queryKey: ["llm-config"] })
  }

  useEffect(() => {
    if (!pull || pull.done) return
    const t = window.setInterval(() => {
      void getPullStatus().then(r => {
        if (!r.data) return
        setPull(r.data)
        if (r.data.done && !r.data.error) window.setTimeout(() => nav("/", { replace: true }), 800)
      })
    }, 1500)
    return () => window.clearInterval(t)
  }, [pull, nav])

  function skip() {
    skipWelcome()
    nav("/", { replace: true })
  }

  const card = "jf-panel p-5"
  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto pb-8">
      <h1 className="text-3xl font-semibold text-white">Bem-vindo! Vamos começar</h1>
      <p className="mt-1 text-base text-white/70">São só dois passos. Você pode mudar tudo depois.</p>
      <div className="mt-3">
        <ListenButton text={INTRO} label="Ouvir" />
      </div>

      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`mt-4 rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-200" : "border-red-400/40 text-red-200"}`}>
          {msg.text}
        </p>
      )}

      <section className={`${card} mt-5`} aria-labelledby="w-0">
        <h2 id="w-0" className="text-xl font-medium text-white">Passo 1: como posso te chamar?</h2>
        <div className="mt-3">
          <NameField compact />
        </div>
      </section>

      <section className={`${card} mt-4 border border-cyan-400/30`} aria-labelledby="w-1">
        <h2 id="w-1" className="text-xl font-medium text-white">Passo 2: ligar a inteligência do Jefrey</h2>
        <p className="mt-2 text-base text-white/75">
          Aperte o botão. O site abre, você entra (ou cria) uma conta e volta sozinho. O Jefrey nunca vê a sua senha. Você paga direto ao serviço, só pelo que usar.
        </p>
        <button type="button" onClick={() => void oneClick()} disabled={busy !== null} className="jf-btn jf-focus mt-3 px-5 py-3 text-base">
          {busy === "oneclick" ? "Abrindo o site…" : "Conectar com 1 clique"}
        </button>
        <p className="mt-4 text-base text-white/70">
          Já tem conta no Claude ou no ChatGPT? <Link className="underline" to="/conexoes">Veja como usar a sua conta</Link>.
        </p>
      </section>

      <section className={`${card} mt-4`} aria-labelledby="w-3">
        <h2 id="w-3" className="text-xl font-medium text-white">Ou use só no seu computador (sem internet)</h2>
        {advice ? (
          <>
            <p className="mt-2 text-base text-white/75">{advice.suggest_local ? "O seu computador aguenta. Fica mais privado e não gasta nada." : "Funciona, mas as respostas são mais simples neste computador."}</p>
            <button
              type="button"
              onClick={() => void useLocal(advice.suggest_local && advice.model ? advice.model : "qwen3:1.7b")}
              disabled={busy !== null}
              className="jf-focus mt-3 rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5"
            >
              Preparar no meu computador
            </button>
          </>
        ) : (
          <p className="mt-2 text-base text-white/60">Verificando o seu computador…</p>
        )}
      </section>

      {pull && (
        <section className="jf-panel mt-4 p-5" aria-live="polite">
          <h2 className="text-xl font-medium text-white">{pull.done ? (pull.error ? "Não terminou" : "Pronto!") : "Preparando o Jefrey…"}</h2>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-white/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={overallPercent(pull)}>
            <div className="h-full bg-cyan-400 transition-all" style={{ width: `${overallPercent(pull)}%` }} />
          </div>
          <p className="mt-2 text-base text-white/70">
            {pull.error ?? "Isso acontece só uma vez e pode levar alguns minutos. Pode deixar esta janela aberta."}
          </p>
        </section>
      )}

      <p className="mt-6 text-center text-base">
        <button type="button" onClick={skip} className="jf-focus text-white/60 underline hover:text-white/90">
          Fazer isso depois
        </button>
      </p>
    </div>
  )
}
