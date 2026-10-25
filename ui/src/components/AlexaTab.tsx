import { useEffect, useState } from "react"
import ListenButton from "@/components/ListenButton"
import { ALEXA_STEPS, clearAlexa, getAlexa, rowsToMap, saveAlexa, testAlexa, type AlexaStatus, type Row } from "@/lib/alexa"

const big = "jf-btn jf-focus px-5 py-3 text-base"
const soft = "jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/35"

function RowsEditor({ title, hint, rows, onChange }: { title: string; hint: string; rows: Row[]; onChange: (r: Row[]) => void }) {
  return (
    <div className="mt-4">
      <h3 className="text-lg font-medium text-white">{title}</h3>
      <p className="text-sm text-white/60">{hint}</p>
      <ul className="mt-2 space-y-2">
        {rows.map((r, i) => (
          <li key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <input className={field} aria-label="Nome" placeholder="Nome (ex.: sala)" value={r.name} maxLength={30} onChange={e => onChange(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
            <input className={field} aria-label="Código" placeholder="Código no Voice Monkey" value={r.id} maxLength={60} onChange={e => onChange(rows.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)))} />
            <button type="button" aria-label="Apagar linha" onClick={() => onChange(rows.filter((_, j) => j !== i))} className="jf-focus rounded-lg border border-white/20 px-3 text-white/70 hover:bg-white/5">×</button>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => onChange([...rows, { name: "", id: "" }])} className={`${soft} mt-2`}>+ Incluir</button>
    </div>
  )
}

/** Aba Alexa: o Jefrey fala nos seus Echo e aciona rotinas (pelo Voice Monkey). */
export default function AlexaTab() {
  const [st, setSt] = useState<AlexaStatus | null>(null)
  const [token, setToken] = useState("")
  const [devs, setDevs] = useState<Row[]>([{ name: "", id: "" }])
  const [rout, setRout] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function load() {
    const r = await getAlexa()
    if (r.data) {
      setSt(r.data)
      if (r.data.devices.length && devs.every(d => !d.name && !d.id)) setDevs(r.data.devices.map(n => ({ name: n, id: "" })))
    }
  }
  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function detail(res: { data: unknown }, fallback: string) {
    const d = (res.data as { detail?: unknown } | null)?.detail
    return typeof d === "string" ? d : fallback
  }

  async function save() {
    const d = rowsToMap(devs)
    const r2 = rowsToMap(rout)
    if (d.problem || r2.problem) return setMsg({ ok: false, text: (d.problem || r2.problem) as string })
    if (!Object.keys(d.map).length && !Object.keys(r2.map).length) return setMsg({ ok: false, text: "Inclua pelo menos um aparelho ou uma rotina." })
    setBusy(true)
    const r = await saveAlexa(token.trim() || null, d.map, r2.map)
    setBusy(false)
    if (r.ok && r.data) {
      setSt(r.data)
      setToken("")
      setMsg({ ok: true, text: "Salvo. Agora toque em “Testar” para a Alexa falar." })
    } else setMsg({ ok: false, text: detail(r, "Não consegui salvar agora.") })
  }

  async function test() {
    setBusy(true)
    const r = await testAlexa()
    setBusy(false)
    setMsg(r.ok ? { ok: true, text: "Pedi para a Alexa falar. Ela falou?" } : { ok: false, text: detail(r, "Não consegui falar com a Alexa agora.") })
  }

  async function remove() {
    const r = await clearAlexa()
    if (r.data) setSt(r.data)
    setDevs([{ name: "", id: "" }])
    setRout([])
    setMsg({ ok: true, text: "Desconectado. O token foi apagado deste computador." })
  }

  const listen = ALEXA_STEPS.join(" ")
  return (
    <section className="jf-panel p-5" aria-labelledby="c-alexa">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="c-alexa" className="text-xl font-medium text-white">Alexa</h2>
        <span className={`rounded-full px-3 py-1 text-sm ${st?.configured ? "bg-emerald-400/15 text-emerald-200" : "bg-white/10 text-white/60"}`}>{st?.configured ? "Conectada" : "Ainda não conectada"}</span>
      </div>
      <p className="mt-2 text-base text-white/75">
        O Jefrey pode fazer a sua Alexa <b>falar um aviso</b> (“o jantar está pronto”) e <b>acionar rotinas</b> dela (como “boa noite”). Acionar uma rotina pede a sua aprovação.
      </p>
      <p className="mt-1 text-sm text-amber-100/90">A conexão usa o serviço Voice Monkey, de terceiros. Esta parte ainda não foi testada com uma conta real: use “Testar” e me conte se funcionou.</p>
      <ol className="mt-3 list-decimal space-y-1.5 pl-6 text-base text-white/85">{ALEXA_STEPS.map(s => <li key={s}>{s}</li>)}</ol>
      <div className="mt-2"><ListenButton text={listen} /></div>

      <label className="mt-4 block text-base text-white/85">
        Token do Voice Monkey {st?.has_token && <span className="text-sm text-emerald-300">(já guardado; deixe em branco para manter)</span>}
        <input className={`${field} mt-1`} type="password" autoComplete="off" spellCheck={false} value={token} onChange={e => setToken(e.target.value)} placeholder="cole aqui" />
      </label>
      <RowsEditor title="Aparelhos (Echo)" hint="Um nome fácil e o código do monkey correspondente." rows={devs} onChange={setDevs} />
      <RowsEditor title="Rotinas (opcional)" hint="Ex.: nome “boa noite” e o código do monkey que aciona essa rotina." rows={rout} onChange={setRout} />

      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={() => void save()} disabled={busy} className={big}>Salvar</button>
        <button type="button" onClick={() => void test()} disabled={busy || !st?.configured} className={soft}>Testar</button>
        {st?.has_token && <button type="button" onClick={() => void remove()} className="jf-focus rounded-lg border border-red-300/40 px-4 py-2 text-base text-red-100 hover:bg-red-400/10">Desconectar</button>}
      </div>
      {st && st.devices.length > 0 && <p className="mt-3 text-sm text-white/60">Aparelhos guardados: {st.devices.join(", ")}{st.routines.length ? ` · Rotinas: ${st.routines.join(", ")}` : ""}. Por segurança, os códigos não voltam para a tela.</p>}
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-3 rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>{msg.text}</p>}
    </section>
  )
}
