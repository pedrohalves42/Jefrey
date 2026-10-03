import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { apiFetch, ensureDevToken, mapHttpError } from "@/lib/api"

type Cfg = { provider: string; model: string; base_url: string; has_key: boolean; is_cloud: boolean; temperature: number }
type Preset = { id: string; label: string; provider: string; base_url: string; models: string[]; needs_key: boolean }
type Option = { model: string; size_gb: number; needs_gb: number; quality: string; fits: boolean }
type Rec = {
  memory_total_gb: number
  memory_available_gb: number
  recommended: { model: string; quality: string; needs_gb: number }
  options: Option[]
  note: string
}

const field = "w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm"

export default function ModelSettings() {
  const [cfg, setCfg] = useState<Cfg | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [rec, setRec] = useState<Rec | null>(null)
  const [presetId, setPresetId] = useState("ollama-local")
  const [model, setModel] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const preset = presets.find(p => p.id === presetId)

  const load = useCallback(async () => {
    await ensureDevToken()
    try {
      const [a, b, c] = await Promise.all([
        apiFetch("/settings/llm"),
        apiFetch("/settings/llm/presets"),
        apiFetch("/settings/llm/recommend"),
      ])
      if (!a.ok) throw new Error(mapHttpError(a.status))
      const cur: Cfg = await a.json()
      const ps: Preset[] = (await b.json()).presets
      setCfg(cur)
      setPresets(ps)
      setModel(cur.model)
      setBaseUrl(cur.base_url)
      if (c.ok) setRec(await c.json())
      const match =
        ps.find(p => p.provider === cur.provider && (p.provider !== "openai" || p.base_url === cur.base_url)) ||
        ps.find(p => p.provider === cur.provider)
      if (match) setPresetId(match.id)
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Falha ao carregar a configuracao do modelo." })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  function pickPreset(id: string) {
    const p = presets.find(x => x.id === id)
    setPresetId(id)
    if (p) {
      setBaseUrl(p.base_url)
      if (p.models.length) setModel(p.models[0])
    }
    setMsg(null)
  }

  async function save() {
    if (!preset) return
    setBusy(true)
    setMsg(null)
    try {
      const body: Record<string, unknown> = {
        provider: preset.provider,
        model: model.trim(),
        base_url: baseUrl.trim() || null,
      }
      if (apiKey.trim()) body.api_key = apiKey.trim()
      const r = await apiFetch("/settings/llm", { method: "PUT", body: JSON.stringify(body) })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        setMsg({ ok: false, text: typeof j.detail === "string" ? j.detail : mapHttpError(r.status) })
        return
      }
      setCfg(j)
      setApiKey("")
      setMsg({ ok: true, text: "Modelo salvo. A proxima mensagem ja usa essa configuracao." })
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    setBusy(true)
    setMsg(null)
    try {
      const r = await apiFetch("/settings/llm/test", { method: "POST" })
      const j = await r.json().catch(() => ({}))
      setMsg({
        ok: !!j.ok,
        text: j.ok ? `Conectado: ${j.model} (${j.provider}).` : `Sem conexao: ${j.detail || mapHttpError(r.status)}`,
      })
    } finally {
      setBusy(false)
    }
  }

  async function removeKey() {
    setBusy(true)
    try {
      await apiFetch("/settings/llm", {
        method: "PUT",
        body: JSON.stringify({
          provider: "ollama",
          model: rec?.recommended.model || "qwen2.5:1.5b",
          base_url: "http://ollama:11434",
          api_key: "",
        }),
      })
      await load()
      setMsg({ ok: true, text: "Chave removida; voltou para o modelo local." })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Modelo de IA
          {cfg && <Badge variant={cfg.is_cloud ? "secondary" : "success"}>{cfg.is_cloud ? "nuvem" : "local"}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {cfg && (
          <p className="text-sm text-muted-foreground">
            Em uso: <b>{cfg.model}</b> via {cfg.provider}. Local por padrao: seus dados ficam no seu computador. Escolha
            um provedor de nuvem (Claude, ChatGPT) apenas se quiser respostas mais fortes.
          </p>
        )}

        {rec && (
          <div className="rounded-md border border-cyan-400/20 bg-cyan-400/5 p-3 text-sm">
            <div>
              Memoria livre agora: <b>{rec.memory_available_gb} GB</b> de {rec.memory_total_gb} GB. Recomendado para
              este computador: <b>{rec.recommended.model}</b> ({rec.recommended.quality}).
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {rec.options.map(o => (
                <button
                  key={o.model}
                  type="button"
                  disabled={!o.fits}
                  onClick={() => {
                    pickPreset("ollama-local")
                    setModel(o.model)
                  }}
                  className={`rounded-full border px-2 py-0.5 text-xs ${
                    o.fits ? "border-cyan-400/40 hover:bg-cyan-400/10" : "border-white/10 opacity-40"
                  }`}
                  title={`${o.quality} - precisa de ${o.needs_gb} GB livres`}
                >
                  {o.model}
                  {o.fits ? "" : " (nao cabe)"}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{rec.note}</p>
          </div>
        )}

        <label className="block text-sm">
          Provedor
          <select className={field} value={presetId} onChange={e => pickPreset(e.target.value)}>
            {presets.map(p => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          Modelo
          <Input list="model-options" value={model} onChange={e => setModel(e.target.value)} placeholder="ex.: qwen2.5:1.5b" />
          <datalist id="model-options">
            {preset?.models.map(m => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </label>

        {preset && preset.provider !== "ollama" && (
          <label className="block text-sm">
            Endereco da API
            <Input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
          </label>
        )}

        {preset?.needs_key && (
          <label className="block text-sm">
            Chave de API {cfg?.has_key && <Badge variant="secondary">chave salva</Badge>}
            <Input
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={cfg?.has_key ? "deixe em branco para manter a chave atual" : "cole sua chave aqui"}
            />
            <span className="text-xs text-muted-foreground">Guardada so neste computador e nunca exibida de volta.</span>
          </label>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={save} disabled={busy || !model.trim()}>
            Salvar
          </Button>
          <Button variant="outline" onClick={test} disabled={busy}>
            Testar conexao
          </Button>
          {cfg?.has_key && (
            <Button variant="outline" onClick={removeKey} disabled={busy}>
              Remover chave e voltar ao local
            </Button>
          )}
        </div>

        {msg && (
          <p role="status" className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>
            {msg.text}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
