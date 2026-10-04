import { useState } from "react"
import Saude from "@/pages/Saude"
import Aprovacoes from "@/pages/Aprovacoes"
import { getUserId } from "@/lib/api"
import { refreshToken } from "@/lib/session"

const TABS = [
  { id: "saude", label: "Saúde" },
  { id: "aprovacoes", label: "Aprovações" },
  { id: "conta", label: "Conta" },
] as const
type TabId = (typeof TABS)[number]["id"]

function Conta() {
  const [msg, setMsg] = useState<string | null>(null)
  async function renew() {
    const t = await refreshToken()
    setMsg(t ? "Sessão renovada." : "Não consegui renovar a sessão.")
  }
  return (
    <section className="jf-panel space-y-2 p-4" aria-labelledby="ct-t">
      <h2 id="ct-t" className="text-lg font-semibold text-white">
        Conta
      </h2>
      <p className="text-sm text-white/70">
        Usuário atual: <b>{getUserId()}</b>
      </p>
      <p className="text-xs text-white/45">A sessão é renovada sozinha quando expira. Use o botão se algo parecer travado.</p>
      <button type="button" onClick={() => void renew()} className="jf-btn jf-focus px-4 py-1.5 text-sm">
        Renovar sessão
      </button>
      {msg && (
        <p role="status" className="text-sm text-emerald-300">
          {msg}
        </p>
      )}
    </section>
  )
}

export default function Avancado() {
  const [tab, setTab] = useState<TabId>("saude")
  return (
    <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto pb-4">
      <header>
        <h1 className="text-2xl font-semibold text-white">Avançado</h1>
        <p className="text-sm text-white/55">Para quem quer ver o que está acontecendo por baixo.</p>
      </header>
      <div role="tablist" aria-label="Seções avançadas" className="flex gap-2">
        {TABS.map(t => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`jf-focus rounded-lg px-4 py-1.5 text-sm ${tab === t.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{tab === "saude" ? <Saude /> : tab === "aprovacoes" ? <Aprovacoes /> : <Conta />}</div>
    </div>
  )
}
