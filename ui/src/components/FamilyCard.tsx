import { useEffect, useState } from "react"
import { canEnable, getFamily, setFamily } from "@/lib/family"

/** Resumo da semana para um familiar. Desligado por padrao; so com o seu consentimento e nunca envia sozinho. */
export default function FamilyCard() {
  const [on, setOn] = useState(false)
  const [contact, setContact] = useState("")
  const [msg, setMsg] = useState("")

  useEffect(() => {
    void getFamily().then(s => {
      if (s) {
        setOn(!!s.enabled)
        setContact(s.contact ?? "")
      }
    })
  }, [])

  async function save(enabled: boolean) {
    const s = await setFamily(enabled, contact)
    if (!s) return setMsg("Não consegui salvar agora.")
    setOn(s.enabled)
    setMsg(s.enabled ? `Certo. No domingo à noite eu pergunto se pode mandar o resumo para ${s.contact}.` : "Desligado. Nada é enviado para a família.")
  }

  return (
    <section className="jf-panel p-4" aria-labelledby="fam-title">
      <h2 id="fam-title" className="text-lg font-semibold text-white">Resumo da semana para a família</h2>
      <p className="text-sm text-white/55">Um familiar de confiança recebe um recado curto, só com números (nada das suas conversas). Eu sempre pergunto e peço a sua aprovação antes de enviar.</p>
      <label className="mt-3 block text-base text-white/85" htmlFor="fam-contact">Quem recebe (nome como está no seu WhatsApp)</label>
      <input id="fam-contact" value={contact} onChange={e => setContact(e.target.value)} maxLength={80} className="jf-focus mt-1 w-full rounded-lg border border-white/20 bg-transparent px-3 py-2 text-base text-white" />
      <label className="mt-3 flex items-start gap-3 text-base text-white/85">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={on} disabled={!canEnable(contact)} onChange={e => void save(e.target.checked)} />
        <span>Eu aceito que o Jefrey me ofereça esse resumo toda semana</span>
      </label>
      {msg && <p role="status" className="mt-2 text-sm text-cyan-200">{msg}</p>}
    </section>
  )
}
