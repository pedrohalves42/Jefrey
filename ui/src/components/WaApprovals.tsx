import { useEffect, useState } from "react"
import ListenButton from "@/components/ListenButton"
import { waDecide, waPending, waSetMode, whyText, type WaChat, type WaDraft, type WaMode } from "@/lib/wa"

/** Pop-up de aprovacao: aparece em qualquer tela quando uma resposta do WhatsApp precisa da sua decisao. */
export default function WaApprovals() {
  const [drafts, setDrafts] = useState<WaDraft[]>([])
  const [fresh, setFresh] = useState<WaChat[]>([])
  const [text, setText] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const r = await waPending()
      if (alive && r.data) {
        setDrafts(r.data.pending)
        setFresh(r.data.new_chats ?? [])
      }
    }
    void tick()
    const t = window.setInterval(() => void tick(), 4000)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [])

  const d = drafts[0]
  useEffect(() => {
    setText(d?.reply ?? "")
    setErr(null)
  }, [d?.id, d?.reply])

  async function choose(chat: WaChat, mode: WaMode) {
    const r = await waSetMode(chat.id, mode)
    if (r.ok) setFresh(prev => prev.filter(c => c.id !== chat.id))
  }

  async function chooseAll(mode: WaMode) {
    const all = [...fresh]
    for (const c of all) await waSetMode(c.id, mode)
    setFresh([])
  }

  const nc = fresh[0]
  if (!d && nc) {
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" role="alertdialog" aria-modal="true" aria-label="Nova conversa do WhatsApp">
        <div className="jf-panel w-full max-w-lg border border-cyan-300/40 bg-[#07141b] p-5">
          <p className="text-sm text-cyan-200">WhatsApp · conversa nova</p>
          <h2 className="mt-1 text-2xl font-semibold text-white">{nc.display || "Alguém"} te escreveu</h2>
          {fresh.length > 1 && <p className="mt-1 text-sm text-white/60">Tem mais {fresh.length - 1} conversa{fresh.length > 2 ? "s" : ""} nova{fresh.length > 2 ? "s" : ""} esperando.</p>}
          <p className="mt-2 text-base text-white/80">O que o Jefrey deve fazer nas conversas com essa pessoa? Enquanto você não escolher, ele <b>não responde</b>.</p>
          <div className="mt-4 flex flex-col gap-2">
            <button type="button" onClick={() => void choose(nc, "ask")} className="jf-btn jf-focus px-5 py-3 text-lg">Preparar a resposta e perguntar antes de enviar</button>
            <button type="button" onClick={() => void choose(nc, "auto")} className="jf-focus rounded-lg border border-white/30 px-5 py-3 text-lg text-white/90 hover:bg-white/5">Responder sozinho (só o que for simples)</button>
            <button type="button" onClick={() => void choose(nc, "off")} className="jf-focus rounded-lg border border-white/20 px-5 py-3 text-lg text-white/70 hover:bg-white/5">Ignorar essa pessoa</button>
          </div>
          {fresh.length > 1 && (
            <button type="button" onClick={() => void chooseAll("ask")} className="jf-focus mt-3 w-full rounded-lg border border-cyan-300/40 px-4 py-2.5 text-base text-cyan-100 hover:bg-cyan-400/10">
              Perguntar antes de enviar em todas as {fresh.length}
            </button>
          )}
          <p className="mt-3 text-sm text-white/50">Dinheiro, dados pessoais, compromissos e assuntos delicados sempre pedem a sua aprovação. Você muda isso depois em Conexões → WhatsApp.</p>
        </div>
      </div>
    )
  }
  if (!d) return null

  async function decide(decision: "approve" | "reject") {
    setBusy(true)
    const r = await waDecide(d!.id, decision, decision === "approve" ? text.trim() : undefined)
    setBusy(false)
    if (r.ok) setDrafts(prev => prev.filter(x => x.id !== d!.id))
    else {
      const detail = (r.data as { detail?: unknown } | null)?.detail
      setErr(typeof detail === "string" ? detail : "Não consegui agora. Tente de novo.")
      if (r.status === 404) setDrafts(prev => prev.filter(x => x.id !== d!.id))
    }
  }

  const speak = `${d.chat} escreveu: ${d.incoming}. ${whyText(d.why)}${d.reply ? ` Posso responder: ${d.reply}` : ""}`
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" role="alertdialog" aria-modal="true" aria-label="Aprovar resposta do WhatsApp">
      <div className="jf-panel max-h-[90dvh] w-full max-w-lg overflow-y-auto border border-amber-400/50 bg-[#07141b] p-5">
        <p className="text-sm text-amber-200">WhatsApp{drafts.length > 1 ? ` · ${drafts.length} esperando` : ""}</p>
        <h2 className="mt-1 text-2xl font-semibold text-white">{d.chat} escreveu</h2>
        <p className="mt-2 whitespace-pre-line rounded-lg border border-white/10 bg-black/30 p-3 text-lg text-white/90">{d.incoming || "(áudio, imagem ou outro tipo de mensagem)"}</p>
        <p className="mt-3 text-base text-amber-100">{whyText(d.why)}</p>
        <label className="mt-3 block text-base text-white/85">
          {d.reply ? "Posso responder assim (você pode mudar):" : "Escreva a resposta que devo enviar:"}
          <textarea
            className="mt-1 w-full rounded-lg border border-white/20 bg-black/40 p-3 text-lg text-white"
            rows={3}
            maxLength={600}
            value={text}
            onChange={e => setText(e.target.value)}
          />
        </label>
        {err && <p role="alert" className="mt-2 text-base text-red-200">{err}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" disabled={busy || text.trim().length < 1} onClick={() => void decide("approve")} className="jf-btn jf-focus px-6 py-3 text-lg">
            Enviar
          </button>
          <button type="button" disabled={busy} onClick={() => void decide("reject")} className="jf-focus rounded-lg border border-white/30 px-6 py-3 text-lg text-white/90 hover:bg-white/5">
            Não enviar
          </button>
          <ListenButton text={speak} />
        </div>
      </div>
    </div>
  )
}
