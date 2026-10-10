import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Navigate, NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom"
import { getConfig, needsWelcome, welcomeSkipped } from "@/lib/llm"
import { useEasy, visibleItems, type NavItem } from "@/lib/easy"
import { getLegalStatus } from "@/lib/legal"
import { StatusPill } from "@/components/StatusPill"
import VersionLabel from "@/components/VersionLabel"
import { ReminderBanner } from "@/components/ReminderBanner"
import WaApprovals from "@/components/WaApprovals"
import WindowControls from "@/components/WindowControls"
import WaLinkBanner from "@/components/WaLinkBanner"
import { UpdateBanner } from "@/components/UpdateBanner"

// easy: aparece no modo Fácil (padrao): so o essencial para quem nao e tecnico
const ITEMS: NavItem[] = [
  { to: "/", label: "Conversa", end: true, icon: "M4 5h16v11H8l-4 4V5z", easy: true },
  { to: "/hoje", label: "Hoje", icon: "M12 3v2m0 14v2M5 12H3m18 0h-2M6.3 6.3L5 5m14 0l-1.3 1.3M6.3 17.7L5 19m14 0l-1.3-1.3M12 8a4 4 0 100 8 4 4 0 000-8z", easy: true },
  { to: "/conexoes", label: "Conexões", icon: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1", easy: true },
  { to: "/aprender", label: "Aprender", icon: "M12 3l9 5-9 5-9-5 9-5zM7 11v5c0 1.5 2.2 3 5 3s5-1.5 5-3v-5", easy: true },
  { to: "/aprendi", label: "O que aprendi", icon: "M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5L12 3z", easy: true },
  { to: "/estudos", label: "Estudos", icon: "M4 19V6a2 2 0 012-2h12v15H6a2 2 0 00-2 2m0 0h14M8 8h6M8 12h6" },
  { to: "/memoria", label: "Memória", icon: "M12 3a7 7 0 00-4 12.7V19h8v-3.3A7 7 0 0012 3zm-2 18h4" },
  { to: "/skills", label: "Skills", icon: "M13 2L4 14h6l-1 8 9-12h-6l1-8z" },
  { to: "/configuracoes", label: "Configurações", icon: "M12 8a4 4 0 100 8 4 4 0 000-8zm0-5v3m0 12v3M3 12h3m12 0h3", easy: true },
  { to: "/privacidade", label: "Privacidade", icon: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z", easy: true },
  { to: "/avancado", label: "Avançado", icon: "M4 6h16M4 12h16M4 18h10" },
  { to: "/ajuda", label: "Ajuda", icon: "M9.5 9a2.5 2.5 0 115 0c0 1.7-2.5 2-2.5 4M12 17h.01M12 3a9 9 0 100 18 9 9 0 000-18z", easy: true },
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
  const [easy] = useEasy()
  const items = visibleItems(ITEMS, easy)
  const cfg = useQuery({ queryKey: ["llm-config"], queryFn: async () => (await getConfig()).data, staleTime: 30_000, retry: 1 })
  const legal = useQuery({ queryKey: ["legal"], queryFn: async () => (await getLegalStatus()).data, staleTime: 60_000, retry: 1 })
  // primeira tela: termos e privacidade (so depois do aceite o resto abre)
  if (legal.data && !legal.data.accepted && loc.pathname !== "/termos") return <Navigate to="/termos" replace />
  if (loc.pathname !== "/bem-vindo" && loc.pathname !== "/primeira-vez" && loc.pathname !== "/termos" && needsWelcome(cfg.data, welcomeSkipped())) return <Navigate to="/primeira-vez" replace />
  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <WindowControls />
      <ReminderBanner />
      <WaApprovals />
      <WaLinkBanner />
      <UpdateBanner />
      <ConnectedNotice />
      {/* barra lateral (desktop) */}
      <nav className="jf-panel m-3 mr-0 hidden w-56 shrink-0 flex-col p-3 md:flex" aria-label="Principal">
        <div className="mb-5 flex items-center gap-2 px-2 pt-1">
          <span className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--hue)_70%_62%)] shadow-[0_0_14px_hsl(var(--hue)_70%_55%/0.7)]" aria-hidden="true" />
          <span className="jf-brand text-2xl text-white">Jefrey</span>
        </div>
        <ul className="space-y-1">
          {items.map(i => (
            <li key={i.to}>
              <NavLink
                to={i.to}
                end={i.end}
                className={({ isActive }) =>
                  `jf-focus flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] ${
                    isActive ? "bg-[hsl(var(--hue)_40%_28%/0.38)] text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
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
          <VersionLabel className="mt-1 px-1" />
        </div>
      </nav>

      <main className="min-h-0 min-w-0 flex-1 p-3">
        <Outlet />
      </main>

      {/* barra inferior (celular) */}
      <nav className="jf-panel m-2 mt-0 flex items-center justify-around p-1 md:hidden" aria-label="Principal">
        {items.map(i => (
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
