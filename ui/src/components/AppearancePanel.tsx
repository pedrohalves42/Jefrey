import { useState } from "react"
import { BrainStage } from "@/components/brain/BrainStage"
import { PRESETS, useAppearance, type BrainShape } from "@/lib/appearance"
import { clearAvatarImage, loadAvatarImage, processImageFile, saveAvatarImage } from "@/lib/avatarImage"

const SHAPES: { id: BrainShape; label: string; hint: string }[] = [
  { id: "brain", label: "Cérebro", hint: "dois hemisférios com neurônios e sinapses" },
  { id: "orb", label: "Orbe", hint: "esfera de neurônios" },
  { id: "reactor", label: "Reator", hint: "anéis concêntricos estilo Homem de Ferro" },
  { id: "hologram", label: "Holograma", hint: "qualquer imagem sua, em estilo holograma animado" },
]

function Slider(props: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; display?: string; style?: React.CSSProperties }) {
  return (
    <label className="block text-sm">
      <span className="flex justify-between text-white/80">
        {props.label}
        <span className="text-white/45">{props.display ?? Math.round(props.value * 100) + "%"}</span>
      </span>
      <input
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        onChange={e => props.onChange(Number(e.target.value))}
        className="jf-focus mt-1 w-full"
        style={props.style}
      />
    </label>
  )
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 text-sm">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="jf-focus mt-1 h-4 w-4" />
      <span>
        <span className="text-white/85">{label}</span>
        <span className="block text-xs text-white/45">{hint}</span>
      </span>
    </label>
  )
}

export function AppearancePanel() {
  const { appearance: a, set, reset, exportJson, importJson } = useAppearance()
  const [msg, setMsg] = useState<string | null>(null)
  const [pasted, setPasted] = useState("")
  const [imgMsg, setImgMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [hasImg, setHasImg] = useState(() => loadAvatarImage() !== null)

  async function copy() {
    try {
      await navigator.clipboard.writeText(exportJson())
      setMsg("Perfil copiado. Cole em outro computador para repetir este visual.")
    } catch {
      setPasted(exportJson())
      setMsg("Copie o texto abaixo.")
    }
  }

  return (
    <section className="jf-panel p-4" aria-labelledby="ap-title">
      <h2 id="ap-title" className="text-lg font-semibold text-white">
        Aparência
      </h2>
      <p className="mb-3 text-sm text-white/55">Deixe o Jefrey com a sua cara. Tudo muda na hora e fica salvo neste computador.</p>

      <div className="grid gap-4 lg:grid-cols-[minmax(220px,1fr)_1.2fr]">
        <div className="jf-panel h-56 lg:h-auto lg:min-h-[260px]">
          <BrainStage state="thinking" className="h-full" />
        </div>

        <div className="space-y-4">
          <div>
            <div className="mb-1 text-sm text-white/80">Estilos prontos</div>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map(p => (
                <button key={p.id} type="button" onClick={() => set(p.value)} className="jf-btn jf-focus px-3 py-1 text-xs">
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <fieldset>
            <legend className="mb-1 text-sm text-white/80">Forma</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {SHAPES.map(s => (
                <label
                  key={s.id}
                  title={s.hint}
                  className={`jf-focus cursor-pointer rounded-lg border px-3 py-2 text-center text-sm ${
                    a.shape === s.id ? "border-white/40 bg-white/10 text-white" : "border-white/10 text-white/60 hover:bg-white/5"
                  }`}
                >
                  <input type="radio" name="shape" className="sr-only" checked={a.shape === s.id} onChange={() => set({ shape: s.id })} />
                  {s.label}
                </label>
              ))}
            </div>
          </fieldset>

          {a.shape === "hologram" && (
            <div className="space-y-3 rounded-lg border border-white/10 p-3">
              <div className="text-sm text-white/80">Sua imagem</div>
              <p className="text-xs text-white/50">
                Escolha qualquer foto, desenho ou personagem. Fundo escuro funciona melhor; ela fica só neste computador e o Jefrey a
                transforma em holograma na cor do tema.
              </p>
              <div className="flex flex-wrap gap-2">
                <label className="jf-btn jf-focus cursor-pointer px-3 py-1.5 text-sm">
                  Escolher imagem
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    className="sr-only"
                    onChange={e => {
                      const f = e.target.files?.[0]
                      e.target.value = ""
                      if (!f) return
                      void processImageFile(f)
                        .then(url => {
                          const ok = saveAvatarImage(url)
                          setHasImg(ok)
                          setImgMsg(ok ? { ok: true, text: "Imagem aplicada." } : { ok: false, text: "Não consegui guardar essa imagem (sem espaço no navegador)." })
                        })
                        .catch((err: unknown) => setImgMsg({ ok: false, text: err instanceof Error ? err.message : "Não consegui usar essa imagem." }))
                    }}
                  />
                </label>
                {hasImg && (
                  <button
                    type="button"
                    className="jf-focus rounded-lg border border-white/15 px-3 py-1.5 text-sm text-white/80 hover:bg-white/5"
                    onClick={() => {
                      clearAvatarImage()
                      setHasImg(false)
                      setImgMsg({ ok: true, text: "Voltou para a silhueta padrão." })
                    }}
                  >
                    Voltar à silhueta
                  </button>
                )}
              </div>
              {imgMsg && (
                <p role={imgMsg.ok ? "status" : "alert"} className={`text-xs ${imgMsg.ok ? "text-emerald-300" : "text-red-300"}`}>
                  {imgMsg.text}
                </p>
              )}
              <Slider label="Linhas de varredura" value={a.holoScan} min={0} max={1} step={0.05} onChange={v => set({ holoScan: v })} />
              <Slider label="Falhas e cor dividida" value={a.holoGlitch} min={0} max={1} step={0.05} onChange={v => set({ holoGlitch: v })} />
              <Slider label="Apagar fundo escuro" value={a.holoCut} min={0} max={0.9} step={0.02} onChange={v => set({ holoCut: v })} />
              <Toggle label="Imagem de fundo claro" hint="Inverte o brilho para fotos com fundo branco." checked={a.holoInvert} onChange={v => set({ holoInvert: v })} />
            </div>
          )}

          <Slider
            label="Cor"
            value={a.hue}
            min={0}
            max={360}
            step={1}
            display={`${a.hue}°`}
            onChange={v => set({ hue: v })}
            style={{ accentColor: `hsl(${a.hue} 90% 60%)` }}
          />
          <Slider label="Brilho e energia" value={a.intensity} min={0} max={1} step={0.05} onChange={v => set({ intensity: v })} />
          <Slider
            label="Quantidade de neurônios"
            value={a.particles}
            min={0}
            max={1}
            step={0.05}
            display={`${Math.round(80 + 820 * a.particles)}`}
            onChange={v => set({ particles: v })}
          />

          <div className="space-y-2">
            <Toggle label="Animações" hint="Desligue para economizar bateria ou se movimento incomoda." checked={a.motion} onChange={v => set({ motion: v })} />
            <Toggle label="Visualização 3D" hint="Desligada, só o chat aparece (mais leve em computadores fracos)." checked={a.visual} onChange={v => set({ visual: v })} />
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-white/10 pt-3">
            <button type="button" onClick={reset} className="jf-focus rounded-lg border border-white/15 px-3 py-1.5 text-sm text-white/80 hover:bg-white/5">
              Restaurar padrão
            </button>
            <button type="button" onClick={() => void copy()} className="jf-focus rounded-lg border border-white/15 px-3 py-1.5 text-sm text-white/80 hover:bg-white/5">
              Copiar perfil
            </button>
          </div>
          <div>
            <label className="block text-xs text-white/55">
              Importar perfil (cole aqui)
              <textarea
                value={pasted}
                onChange={e => setPasted(e.target.value)}
                rows={2}
                className="jf-focus mt-1 w-full rounded-md border border-white/10 bg-black/30 p-2 font-mono text-xs"
                placeholder='{"hue":191,"shape":"reactor",...}'
              />
            </label>
            <button
              type="button"
              disabled={!pasted.trim()}
              onClick={() => setMsg(importJson(pasted) ? "Perfil aplicado." : "Esse texto não é um perfil válido.")}
              className="jf-btn jf-focus mt-1 px-3 py-1 text-xs"
            >
              Aplicar
            </button>
          </div>
          {msg && (
            <p role="status" className="text-sm text-emerald-300">
              {msg}
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
