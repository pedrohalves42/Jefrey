import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const links = [
  { to: "/", label: "Chat" },
  { to: "/studio", label: "Studio" },
  { to: "/memory", label: "Memória" },
  { to: "/approvals", label: "Approvals" },
  { to: "/observability", label: "Observabilidade" },
  { to: "/settings", label: "Settings" },
  { to: "/knowledge", label: "Conhecimento" }
]

export function Nav() {
  return (
    <nav className="flex gap-1 p-2 border-b glass border-cyan-500/20 bg-card/80 backdrop-blur">
      {links.map(l => (
        <NavLink key={l.to} to={l.to} className={({isActive})=> cn(
          "px-3 py-2 rounded-md text-sm font-medium transition-all duration-200",
          isActive 
            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-[0_0_8px_rgba(6,182,212,0.2)]" 
            : "hover:bg-cyan-500/10 text-cyan-200/60 hover:text-cyan-100"
        )}>
          {l.label}
        </NavLink>
      ))}
      <div className="ml-auto flex gap-2 text-xs items-center">
        <a href="/docs" target="_blank" className="px-2 py-1 rounded border border-cyan-500/30 hover:bg-cyan-500/10 text-cyan-200/60">API /docs</a>
        <a href="http://localhost:3000" target="_blank" className="px-2 py-1 rounded border border-cyan-500/30 hover:bg-cyan-500/10 text-cyan-200/60">Grafana</a>
        <a href="http://localhost:9090" target="_blank" className="px-2 py-1 rounded border border-cyan-500/30 hover:bg-cyan-500/10 text-cyan-200/60">Prometheus</a>
      </div>
    </nav>
  )
}