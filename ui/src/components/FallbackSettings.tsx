import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getFallbacks, getPresets, putFallbacks, type Fallback, type Preset } from "@/lib/llm"

const field = "w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm"

/** Provedor de reserva: se o principal falhar (limite, queda, chave recusada), o Jefrey tenta o proximo sozinho. */
export default function FallbackSettings() {
  const [items, setItems] = useState<Fallback[]>([])
  const [max, setMax] = useState(3)
  const [presets, setPresets] = useState<Preset[]>([])
  const [presetId, setPresetId] = useState("openrouter")
  const [model, setModel] = useState("")
  const [key, setKey] = useState("")
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const [f, p] = await Promise.all([getFallbacks(), getPresets()])
    if (f.data) {
      setItems(f.data.fallbacks)
      setMax(f.data.max)
    }
    const list = (p.data?.presets ?? []).filter(x => x.needs_key)
    setPresets(list)
    const first = list.find(x => x.id === "openrouter") ?? list[0]
    if (first?.models.length) setModel(first.models[0] as string)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const preset = presets.find(p => p.id === presetId)

  function toPayload(rows: Fallback[]) {
    return rows.map(r => ({ id: r.id, provider: r.provider, model: r.model, base_url: r.base_url })) // chave existente fica (null = manter)
  }

  async function add() {
    if (!preset || !key.trim() || !model.trim()) {
      setMsg({ ok: false, text: "Escolha o provedor, o modelo e cole a chave." })
      return
    }
    setBusy(true)
    setMsg(null)
    const id = `r${Date.now().toString(36)}`
    const res = await putFallbacks([...toPayload(items), { id, provider: preset.provider, model: model.trim(), base_url: preset.base_url, api_key: key.trim() }])
    setBusy(false)
    if (!res.ok) {
      const d = (res.data as unknown as { detail?: string } | null)?.detail
      setMsg({ ok: false, text: typeof d === "string" ? d : "Não consegui salvar a reserva." })
      return
    }
    setKey("")
    setMsg({ ok: true, text: "Reserva adicionada." })
    await load()
  }

  async function remove(id: string) {
    setBusy(true)
    const res = await putFallbacks(toPayload(items.filter(i => i.id !== id)))
    setBusy(false)
    if (res.ok) await load()
    else setMsg({ ok: false, text: "Não consegui remover." })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reserva (se o principal falhar)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Se o provedor principal estiver fora do ar, no limite de uso ou recusar a chave, o Jefrey tenta automaticamente os
          abaixo, em ordem, antes de a resposta começar. Até {max} reservas.
        </p>
        {items.length > 0 && (
          <ul className="space-y-1 text-sm">
            {items.map((i, n) => (
              <li key={i.id} className="flex items-center justify-between rounded-md border border-white/10 px-3 py-1.5">
                <span>
                  {n + 1}. {i.model} <span className="opacity-50">({i.provider})</span>
                  {!i.has_key && <span className="ml-2 text-amber-300">sem chave</span>}
                </span>
                <button type="button" className="jf-focus text-xs text-red-300 underline" disabled={busy} onClick={() => void remove(i.id)}>
                  Remover
                </button>
              </li>
            ))}
          </ul>
        )}
        {items.length < max && (
          <div className="grid gap-2">
            <select className={field} value={presetId} onChange={e => { setPresetId(e.target.value); const p = presets.find(x => x.id === e.target.value); if (p?.models.length) setModel(p.models[0] as string) }} aria-label="Provedor da reserva">
              {presets.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <input className={field} list="fb-models" value={model} onChange={e => setModel(e.target.value)} aria-label="Modelo da reserva" />
            <datalist id="fb-models">{preset?.models.map(m => <option key={m} value={m} />)}</datalist>
            <input className={field} type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} placeholder="chave de API da reserva" aria-label="Chave da reserva" />
            <button type="button" onClick={() => void add()} disabled={busy} className="jf-btn jf-focus justify-self-start px-4 py-1.5 text-sm">
              Adicionar reserva
            </button>
          </div>
        )}
        {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>{msg.text}</p>}
      </CardContent>
    </Card>
  )
}
