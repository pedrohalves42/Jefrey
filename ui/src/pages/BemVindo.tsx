import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import NameField from "@/components/NameField"
import {
  getAdvice, getPresets, getPullStatus, overallPercent, saveConfig, skipWelcome, startOpenRouter, startPull, testConfig,
  testMessage, type Advice, type PullStatus, type Preset,
} from "@/lib/llm"

const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/30"

export default function BemVindo() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const [presets, setPresets] = useState<Preset[]>([])
  const [advice, setAdvice] = useState<Advice | null>(null)
  const [presetId, setPresetId] = useState("openrouter")
  const [model, setModel] = useState("")
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [pull, setPull] = useState<PullStatus | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(
    params.get("erro") === "openrouter" ? { ok: false, text: "A conexão com o OpenRouter não foi concluída. Tente de novo ou cole uma chave." } : null,
  )

  useEffect(() => {
    void (async () => {
      const [p, a] = await Promise.all([getPresets(), getAdvice()])
      const list = p.data?.presets ?? []
      setPresets(list)
      setAdvice(a.data)
      const first = list.find(x => x.id === "openrouter") ?? list[0]
      if (first?.models.length) setModel(first.models[0] as string)
    })()
  }, [])

  const preset = presets.find(p => p.id === presetId)
  const cloudPresets = presets.filter(p => p.needs_key)

  function pick(id: string) {
    setPresetId(id)
    const p = presets.find(x => x.id === id)
    if (p?.models.length) setModel(p.models[0] as string)
    setMsg(null)
  }

  async function oneClick() {
    setBusy("oneclick")
    setMsg(null)
    const err = await startOpenRouter()
    if (err) {
      setMsg({ ok: false, text: err })
      setBusy(null)
    }
  }

  async function saveKey() {
    if (!preset || !key.trim() || !model.trim()) {
      setMsg({ ok: false, text: "Cole a chave e escolha o modelo." })
      return
    }
    setBusy("key")
    setMsg(null)
    const saved = await saveConfig({ provider: preset.provider, model: model.trim(), base_url: preset.base_url, api_key: key.trim() })
    if (!saved.ok) {
      const d = (saved.data as unknown as { detail?: string } | null)?.detail
      setMsg({ ok: false, text: typeof d === "string" ? d : "Não consegui salvar. Confira os dados." })
      setBusy(null)
      return
    }
    setKey("")
    const t = testMessage(await testConfig())
    setMsg(t)
    setBusy(null)
    if (t.ok) {
      await qc.invalidateQueries({ queryKey: ["llm-config"] })
      setTimeout(() => nav("/", { replace: true }), 900)
    }
  }

  async function useLocal(m: string) {
    setBusy("local")
    setMsg(null)
    const saved = await saveConfig({ provider: "ollama", model: m, base_url: null })
    setBusy(null)
    if (!saved.ok) {
      setMsg({ ok: false, text: "Não consegui salvar o modelo local." })
      return
    }
    // baixa o modelo (e o de memoria) com barra de progresso; avisa se o Ollama nao estiver instalado
    const started = await startPull([m, "embeddinggemma"])
    if (!started.ok) {
      const d = (started.data as unknown as { detail?: string } | null)?.detail
      setMsg({ ok: false, text: typeof d === "string" ? d : "Não consegui preparar o modelo local." })
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
      <h1 className="text-2xl font-semibold text-white">Vamos conectar o cérebro do Jefrey</h1>
      <p className="mt-1 text-sm text-white/60">Escolha como ele vai pensar. Você pode mudar depois, em Configurações.</p>

      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`mt-4 rounded-lg border px-3 py-2 text-sm ${msg.ok ? "border-emerald-400/40 text-emerald-200" : "border-red-400/40 text-red-200"}`}>
          {msg.text}
        </p>
      )}

      <div className="mt-5">
        <NameField />
      </div>

      <section className={`${card} mt-4 border border-cyan-400/30`} aria-labelledby="w-1">
        <p className="text-xs uppercase tracking-wide text-cyan-300">Recomendado</p>
        <h2 id="w-1" className="mt-1 text-lg font-medium text-white">Conectar com 1 clique</h2>
        <p className="mt-1 text-sm text-white/65">
          Você entra (ou cria) uma conta no OpenRouter, que dá acesso a vários modelos de IA, e autoriza o Jefrey. O Jefrey
          nunca vê a sua senha. Você paga direto ao provedor, só o que usar, e pode acompanhar o gasto por lá.
        </p>
        <button type="button" onClick={() => void oneClick()} disabled={busy !== null} className="jf-btn jf-focus mt-3 px-4 py-2 text-sm">
          {busy === "oneclick" ? "Abrindo…" : "Conectar com OpenRouter"}
        </button>
      </section>

      <section className={`${card} mt-4`} aria-labelledby="w-2">
        <h2 id="w-2" className="text-lg font-medium text-white">Já tenho uma chave de API</h2>
        <p className="mt-1 text-sm text-white/65">Cole a chave do Claude, do ChatGPT ou do OpenRouter. Ela fica guardada protegida neste computador e não aparece de volta na tela.</p>
        <div className="mt-3 grid gap-3">
          <label className="text-sm text-white/80">
            Provedor
            <select className={field} value={presetId} onChange={e => pick(e.target.value)}>
              {cloudPresets.map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </label>
          <label className="text-sm text-white/80">
            Modelo
            <input className={field} list="w-models" value={model} onChange={e => setModel(e.target.value)} />
            <datalist id="w-models">{preset?.models.map(m => <option key={m} value={m} />)}</datalist>
          </label>
          <label className="text-sm text-white/80">
            Chave de API
            <input className={field} type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} placeholder="cole aqui" />
          </label>
          <button type="button" onClick={() => void saveKey()} disabled={busy !== null} className="jf-btn jf-focus justify-self-start px-4 py-2 text-sm">
            {busy === "key" ? "Testando…" : "Testar e salvar"}
          </button>
        </div>
      </section>

      <section className={`${card} mt-4`} aria-labelledby="w-3">
        <h2 id="w-3" className="text-lg font-medium text-white">No meu computador (sem enviar nada para a nuvem)</h2>
        {advice ? (
          <>
            <p className="mt-1 text-sm text-white/65">{advice.reason}</p>
            {advice.suggest_local && advice.model ? (
              <button type="button" onClick={() => void useLocal(advice.model as string)} disabled={busy !== null} className="jf-btn jf-focus mt-3 px-4 py-2 text-sm">
                Usar {advice.model}
              </button>
            ) : (
              <button type="button" onClick={() => void useLocal("qwen3:1.7b")} disabled={busy !== null} className="jf-focus mt-3 rounded-lg border border-white/20 px-4 py-2 text-sm text-white/80 hover:bg-white/5">
                Usar mesmo assim o modelo leve (respostas simples)
              </button>
            )}
          </>
        ) : (
          <p className="mt-1 text-sm text-white/50">Verificando o seu computador…</p>
        )}
      </section>

      {pull && (
        <section className="jf-panel mt-4 p-5" aria-live="polite">
          <h2 className="text-lg font-medium text-white">{pull.done ? (pull.error ? "Não terminou" : "Pronto!") : "Baixando o modelo…"}</h2>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={overallPercent(pull)}>
            <div className="h-full bg-cyan-400 transition-all" style={{ width: `${overallPercent(pull)}%` }} />
          </div>
          <p className="mt-2 text-sm text-white/60">
            {pull.error ?? "Isso acontece só uma vez e pode levar alguns minutos, dependendo da internet. Pode deixar esta janela aberta."}
          </p>
        </section>
      )}

      <p className="mt-5 text-center text-sm">
        <button type="button" onClick={skip} className="jf-focus text-white/50 underline hover:text-white/80">
          Pular por enquanto
        </button>
      </p>
    </div>
  )
}
