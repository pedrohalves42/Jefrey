import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
const links = [
  { to: "/", label: "Chat" },
  { to: "/memory", label: "Memoria" },
  { to: "/approvals", label: "Approvals" },
  { to: "/observability", label: "Observabilidade" },
  { to: "/settings", label: "Settings" }
]
export function Nav() {
  return (
    <nav className="flex gap-1 p-2 border-b bg-card">
      {links.map(l => (
        <NavLink key={l.to} to={l.to} className={({isActive})=> cn("px-3 py-2 rounded-md text-sm font-medium", isActive ? "bg-primary text-primary-foreground" : "hover:bg-secondary")}>
          {l.label}
        </NavLink>
      ))}
      <div className="ml-auto flex gap-2 text-xs items-center">
        <a href="/docs" target="_blank" className="px-2 py-1 rounded border">API /docs</a>
        <a href="http://localhost:3000" target="_blank" className="px-2 py-1 rounded border">Grafana</a>
        <a href="http://localhost:9090" target="_blank" className="px-2 py-1 rounded border">Prometheus</a>
      </div>
    </nav>
  )
}
