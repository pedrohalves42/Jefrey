import { TEXT_SIZES, useAccess } from "@/lib/access"

/** Letra maior e alto contraste. Vale na hora e fica salvo neste computador. */
export default function AccessibilityPanel() {
  const [a, set] = useAccess()
  return (
    <section className="jf-panel p-4" aria-labelledby="acc-title">
      <h2 id="acc-title" className="text-lg font-semibold text-white">Ver melhor</h2>
      <p className="text-sm text-white/55">Deixe as letras maiores e as cores mais fortes. Vale em todas as telas.</p>
      <fieldset className="mt-3">
        <legend className="text-base text-white/85">Tamanho da letra</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {TEXT_SIZES.map(s => (
            <label key={s.id} className={`jf-focus cursor-pointer rounded-lg border px-4 py-2 text-base ${a.text === s.id ? "border-white/60 bg-white/10 text-white" : "border-white/20 text-white/75"}`}>
              <input type="radio" name="acc-text" className="sr-only" checked={a.text === s.id} onChange={() => set({ ...a, text: s.id })} />
              {s.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="mt-3 flex items-start gap-3 text-base text-white/85">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={a.contrast} onChange={e => set({ ...a, contrast: e.target.checked })} />
        <span>
          Alto contraste
          <span className="block text-sm text-white/55">Fundo bem escuro, letras brancas e bordas bem marcadas.</span>
        </span>
      </label>
    </section>
  )
}
