import { useState } from "react"
import { waCompose, waSend, type WaChat } from "@/lib/wa"

/** "Escrever mensagem": a pessoa diz a ideia, o Jefrey escreve, ela revisa e manda para a fila. Nada sai sem o toque dela. */
export default function WaCompose({ chat, onQueued }: { chat: WaChat; onQueued: () => void }) {
  const [open, setOpen] = useState(false)
  const [idea, setIdea] = useState("")
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function write() {
    setBusy(true)
    setMsg(null)
    const r = await waCompose(chat.id, idea)
    setBusy(false)
    if (r.ok && r.data?.text) setText(r.data.text)
    else setMsg({ ok: false, text: ((r.data as { detail?: string } | null)?.detail) || "Não consegui escrever agora. Você pode digitar a mensagem." })
  }

  async function send() {
    setBusy(true)
    const r = await waSend(chat.id, text)
    setBusy(false)
    if (r.ok) {
      setMsg({ ok: true, text: `Na fila! Abra a conversa com ${chat.display} no WhatsApp Web (no Chrome) e eu envio sozinho em instantes.` })
      setText("")
      setIdea("")
      onQueued()
    } else {
      setMsg({ ok: false, text: ((r.data as { detail?: string } | null)?.detail) || "Não consegui colocar na fila." })
    }
  }

  const line = "jf-focus w-full rounded-lg border border-white/20 bg-black/40 px-3 py-2 text-base text-white"
  return (
    <div className="mt-2">
      {!open ? (
        <button type="button" onClick={() => setOpen(true)} className="jf-focus rounded-lg border border-cyan-300/40 px-4 py-2 text-base text-cyan-100 hover:bg-cyan-400/10">
          ✍ Escrever mensagem para {chat.display}
        </button>
      ) : (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3">
          <label className="block text-sm text-white/70">O que você quer dizer? (pode ser só a ideia)
            <input className={`${line} mt-1`} value={idea} onChange={e => setIdea(e.target.value)} placeholder="Ex.: avisa que chego às 8h" maxLength={600} />
          </label>
          <button type="button" disabled={busy || idea.trim().length < 2} onClick={() => void write()} className="jf-btn jf-focus mt-2 px-4 py-2 text-base">
            {busy ? "Escrevendo…" : "Escrever com o Jefrey"}
          </button>
          <label className="mt-3 block text-sm text-white/70">Mensagem (você pode mudar):
            <textarea className={`${line} mt-1 min-h-[5rem]`} value={text} onChange={e => setText(e.target.value)} maxLength={1000} placeholder="Escreva aqui, ou peça ao Jefrey acima." />
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" disabled={busy || !text.trim()} onClick={() => void send()} className="jf-btn jf-focus px-5 py-2 text-base">Enviar</button>
            <button type="button" onClick={() => { setOpen(false); setMsg(null) }} className="jf-focus rounded-lg border border-white/20 px-4 py-2 text-base text-white/75 hover:bg-white/5">Fechar</button>
          </div>
          {msg && <p role="status" className={`mt-2 text-sm ${msg.ok ? "text-emerald-200" : "text-red-200"}`}>{msg.text}</p>}
        </div>
      )}
    </div>
  )
}
