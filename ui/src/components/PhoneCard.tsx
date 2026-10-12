import { useEffect, useState } from "react"
import { expiresText, getPhone, newPairing, qrImageSrc, revokePhone, setPhoneEnabled, type PhonePairing, type PhoneState } from "@/lib/phone"

/** Falar com o Jefrey pelo celular, na mesma rede Wi-Fi. Desligado por padrao; so o computador gera o QR. */
export default function PhoneCard() {
  const [st, setSt] = useState<PhoneState | null>(null)
  const [pair, setPair] = useState<PhonePairing | null>(null)
  const [msg, setMsg] = useState("")

  useEffect(() => {
    void getPhone().then(setSt)
  }, [])

  async function toggle(on: boolean) {
    const r = await setPhoneEnabled(on)
    if (r.state) {
      setSt(r.state)
      if (!on) setPair(null)
      setMsg(on ? "Ligado. Se o Windows perguntar sobre a rede, escolha “Redes particulares”." : "Desligado. Os celulares pareados foram desconectados.")
    } else setMsg(r.error ?? "Não consegui agora.")
  }

  async function show() {
    const p = await newPairing()
    setPair(p)
    setMsg(p ? "" : "Não consegui gerar o QR agora.")
  }

  const img = pair ? qrImageSrc(pair.qr_svg) : null
  return (
    <div className="mt-3">
      <label className="flex items-start gap-3 text-base text-white/85">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={!!st?.enabled} onChange={e => void toggle(e.target.checked)} />
        <span>
          Falar com o Jefrey pelo celular
          <span className="block text-sm text-white/50">Só funciona no mesmo Wi-Fi, nunca pela internet. Coisas de risco (enviar mensagem, apagar) continuam pedindo sua aprovação aqui no computador.</span>
        </span>
      </label>
      {st?.enabled && (
        <div className="mt-2 pl-8">
          <button type="button" onClick={() => void show()} className="jf-focus rounded-lg border border-white/25 px-4 py-2 text-base text-white/85 hover:bg-white/5">
            Parear um celular (mostrar o QR)
          </button>
          {pair && img && (
            <div className="mt-2">
              <img src={img} alt="QR code para parear o celular" className="h-48 w-48 rounded-lg bg-white p-2" />
              <p className="text-sm text-white/60">Abra a câmera do celular e aponte para o QR. {expiresText(pair.expires_in)}</p>
            </div>
          )}
          {st.devices.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-white/70">
              {st.devices.map(d => (
                <li key={d.id}>
                  {d.name}{" "}
                  <button type="button" className="jf-focus underline" onClick={() => void revokePhone(d.id).then(ok => ok && void getPhone().then(setSt))}>
                    Desconectar
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {msg && <p role="status" className="mt-1 pl-8 text-sm text-cyan-200">{msg}</p>}
    </div>
  )
}
