import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Navigate, NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom"
import { getConfig, needsWelcome, welcomeSkipped } from "@/lib/llm"
import { StatusPill } from "@/components/StatusPill"
import { ReminderBanner } from "@/components/ReminderBanner"

const ITEMS = [
  { to: "/", label: "Conversa", end: true, icon: "M4 5h16v11H8l-4 4V5z" },
  { to: "/memoria", label: "Memória", icon: "M12 3a7 7 0 00-4 12.7V19h8v-3.3A7 7 0 0012 3zm-2 18h4" },
  { to: "/skills", label: "Skills", icon: "M13 2L4 14h6l-1 8 9-12h-6l1-8z" },
  { to: "/configuracoes", label: "Configurações", icon: "M12 8a4 4 0 100 8 4 4 0 000-8zm0-5v3m0 12v3M3 12h3m12 0h3" },
  { to: "/avancado", label: "Avançado", icon: "M4 6h16M4 12h16M4 18h10" },
]

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

function ConnectedNotice() {
  const [params, setParams] = useSearchParams()
  if (params.get("conectado") !== "openrouter") return null
  return (
    <div role="status" className="jf-panel fixed left-1/2 top-3 z-50 w-[min(92vw,26rem)] -translate-x-1/2 border border-emerald-400/40 p-3 text-sm text-emerald-100">
      Conectado! O Jefrey já pode usar a nuvem. É só conversar.
      <button type="button" className="jf-focus ml-3 underline" onClick={() => setParams({}, { replace: true })}>
        Ok
      </button>
    </div>
  )
}

export function AppShell() {
  const loc = useLocation()
  const cfg = useQuery({ queryKey: ["llm-config"], queryFn: async () => (await getConfig()).data, staleTime: 30_000, retry: 1 })
  if (loc.pathname !== "/bem-vindo" && needsWelcome(cfg.data, welcomeSkipped())) return <Navigate to="/bem-vindo" replace />
  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <ReminderBanner />
      <ConnectedNotice />
      {/* barra lateral (desktop) */}
      <nav className="jf-panel m-3 mr-0 hidden w-56 shrink-0 flex-col p-3 md:flex" aria-label="Principal">
        <div className="mb-5 flex items-center gap-2 px-2 pt-1">
          <span className="jf-orb !h-6 !w-6" aria-hidden="true" />
          <span className="text-lg font-semibold tracking-tight text-white">Jefrey</span>
        </div>
        <ul className="space-y-1">
          {ITEMS.map(i => (
            <li key={i.to}>
              <NavLink
                to={i.to}
                end={i.end}
                className={({ isActive }) =>
                  `jf-focus flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                    isActive ? "bg-white/10 text-white jf-accent" : "text-white/65 hover:bg-white/5 hover:text-white"
                  }`
                }
              >
                <Icon d={i.icon} />
                {i.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="mt-auto pt-4">
          <StatusPill />
        </div>
      </nav>

      <main className="min-h-0 min-w-0 flex-1 p-3">
        <Outlet />
      </main>

      {/* barra inferior (celular) */}
      <nav className="jf-panel m-2 mt-0 flex items-center justify-around p-1 md:hidden" aria-label="Principal">
        {ITEMS.map(i => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.end}
            aria-label={i.label}
            className={({ isActive }) => `jf-focus flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] ${isActive ? "jf-accent" : "text-white/55"}`}
          >
            <Icon d={i.icon} />
            {i.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
