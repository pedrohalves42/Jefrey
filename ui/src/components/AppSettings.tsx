import { useEffect, useState } from "react"
import { getAutostart, isDesktop, restartApp, setAutostart, showOrb, type Autostart } from "@/lib/shell"

/** O Jefrey como programa do computador: iniciar com o Windows e a bolinha (orbe) na tela. So aparece no programa instalado. */
export default function AppSettings() {
  const [auto, setAuto] = useState<Autostart | null>(null)
  const [msg, setMsg] = useState("")
  const desktop = isDesktop()

  useEffect(() => {
    void getAutostart().then(setAuto)
  }, [])

  if (!desktop && !auto?.available) return null

  async function toggle(on: boolean) {
    const r = await setAutostart(on)
    if (r) {
      setAuto(r)
      setMsg(on ? "Pronto. O Jefrey vai abrir sozinho quando você ligar o computador." : "Certo. O Jefrey não abre mais sozinho.")
    } else {
      setMsg("Não consegui mudar agora. Tente de novo.")
    }
  }

  return (
    <section className="jf-panel p-4" aria-label="O Jefrey no computador">
      <h2 className="text-lg font-semibold text-white">O Jefrey no computador</h2>
      <p className="text-sm text-white/55">Ele fica no relógio do Windows (perto da hora) e continua te avisando, mesmo com a janela fechada.</p>
      {auto?.available && (
        <label className="mt-3 flex items-start gap-3 text-base text-white/85">
          <input type="checkbox" className="mt-1 h-5 w-5" checked={auto.enabled} onChange={e => void toggle(e.target.checked)} />
          <span>
            Abrir o Jefrey quando eu ligar o computador
            <span className="block text-sm text-white/50">Ele abre escondido, no relógio. Para falar com ele: Ctrl + Alt + J.</span>
          </span>
        </label>
      )}
      {desktop && (
        <div className="mt-3">
          <button type="button" onClick={() => void showOrb()} className="jf-btn jf-focus px-5 py-3 text-base">
            Mostrar a bolinha (orbe) na tela
          </button>
          <p className="mt-1 text-sm text-white/50">Uma bolinha que fica sempre à vista. Clique nela para abrir o Jefrey.</p>
          <button type="button" onClick={() => void window.pywebview?.api?.toggle_fullscreen?.()} className="jf-focus mt-4 rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">
            Alternar tela cheia (sem bordas) e janela comum
          </button>
          <p className="mt-1 text-sm text-white/50">Também funciona com a tecla F11. Em tela cheia, os botões de minimizar e esconder ficam no canto de cima, à direita.</p>
        </div>
      )}
      <div className="mt-4">
        <button type="button" onClick={() => { setMsg("Reiniciando… a janela fecha e abre de novo em instantes."); void restartApp() }} className="jf-focus rounded-lg border border-white/25 px-5 py-3 text-base text-white/85 hover:bg-white/5">
          Reiniciar o Jefrey
        </button>
        <p className="mt-1 text-sm text-white/50">Fecha e abre de novo. Também há “Reiniciar o Jefrey” no menu Iniciar e no ícone do relógio.</p>
      </div>
      <p role="status" className="mt-2 text-sm text-cyan-200">{msg}</p>
    </section>
  )
}
