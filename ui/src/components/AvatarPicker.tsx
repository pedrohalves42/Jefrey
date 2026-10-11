import { useState } from "react"
import { useAppearance } from "@/lib/appearance"
import { clearAvatarImage, PRESETS, processImageFile, saveAvatarImage } from "@/lib/avatarImage"

/** Escolha rapida do avatar, na propria Conversa: cerebro 3D, uma armadura/robo prontos, ou a imagem da pessoa (fica so neste computador). */
export default function AvatarPicker() {
  const { appearance, set } = useAppearance()
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const brain = appearance.shape !== "hologram"
  const btn = (on: boolean) => `jf-focus rounded-lg border px-2.5 py-1.5 text-xs ${on ? "border-white/45 bg-white/10 text-white" : "border-white/15 text-white/70 hover:bg-white/5"}`

  function usePreset(id: string) {
    const p = PRESETS.find(x => x.id === id)
    if (p && saveAvatarImage(p.url)) {
      set({ shape: "hologram" })
      setMsg({ ok: true, text: `Avatar: ${p.label}.` })
    } else setMsg({ ok: false, text: "Não consegui trocar agora." })
  }

  return (
    <fieldset className="space-y-1.5">
      <legend className="text-xs text-white/60">Avatar</legend>
      <div className="flex flex-wrap gap-1.5">
        <button type="button" className={btn(brain)} aria-pressed={brain} onClick={() => { clearAvatarImage(); set({ shape: "brain" }) }}>Cérebro</button>
        {PRESETS.map(p => (
          <button key={p.id} type="button" className={btn(false)} onClick={() => usePreset(p.id)}>{p.label}</button>
        ))}
        <label className={`${btn(false)} cursor-pointer`}>
          Minha imagem…
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="sr-only"
            aria-label="Escolher a imagem do avatar"
            onChange={e => {
              const f = e.target.files?.[0]
              e.target.value = ""
              if (!f) return
              void processImageFile(f)
                .then(url => {
                  if (saveAvatarImage(url)) {
                    set({ shape: "hologram" })
                    setMsg({ ok: true, text: "Pronto! Seu avatar foi aplicado." })
                  } else setMsg({ ok: false, text: "Não coube neste navegador. Tente uma imagem menor." })
                })
                .catch((err: unknown) => setMsg({ ok: false, text: err instanceof Error ? err.message : "Não consegui usar essa imagem." }))
            }}
          />
        </label>
      </div>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-xs ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>{msg.text}</p>}
    </fieldset>
  )
}
