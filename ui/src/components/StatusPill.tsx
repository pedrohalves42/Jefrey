import { useState } from "react"
import { useStatus } from "@/lib/status"

const TEXT = { ok: "Tudo certo", degraded: "Funcionando, com avisos", offline: "Sem conexão" } as const
const DOT = { ok: "bg-emerald-400", degraded: "bg-amber-400", offline: "bg-red-400" } as const

/** Estado real dos servicos (vem de /api/status). Nada aqui e texto fixo. */
export function StatusPill() {
  const { data, isLoading } = useStatus()
  const [open, setOpen] = useState(false)
  if (isLoading || !data) {
    return <span className="text-xs text-white/50">Verificando…</span>
  }
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="jf-focus flex items-center gap-2 rounded-full border border-white/10 px-3 py-1 text-xs text-white/80 hover:bg-white/5"
      >
        <span className={`h-2 w-2 rounded-full ${DOT[data.summary]}`} aria-hidden="true" />
        {TEXT[data.summary]}
      </button>
      {open && (
        <div className="jf-panel absolute bottom-full left-0 z-30 mb-2 w-64 bg-[#0a1220]/95 p-3 text-xs">
          {data.reachable ? (
            <ul className="space-y-1.5">
              {data.services.map(s => (
                <li key={s.id} className="flex items-center justify-between gap-2">
                  <span className="text-white/75">{s.label}</span>
                  <span className={s.state === "ok" ? "text-emerald-300" : "text-red-300"}>{s.state === "ok" ? "ok" : "com problema"}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-white/70">Não consegui falar com o servidor do Jefrey. Verifique se ele está rodando.</p>
          )}
        </div>
      )}
    </div>
  )
}
