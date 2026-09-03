import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Nav } from "@/components/Nav"
import { HealthBadge } from "@/components/HealthBadge"
import { Chat } from "@/pages/Chat"
import { Memory } from "@/pages/Memory"
import { Approvals } from "@/pages/Approvals"
import { Observability } from "@/pages/Observability"
import { Settings } from "@/pages/Settings"

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <div className="min-h-screen bg-background">
          <header className="border-b bg-card/50">
            <div className="max-w-5xl mx-auto p-3 flex items-center gap-3">
              <h1 className="font-bold text-lg">Jefrey</h1>
              <span className="text-xs text-muted-foreground">1 programa, 7 pecas — 175/175 + 21/21</span>
            </div>
          </header>
          <div className="max-w-5xl mx-auto">
            <Nav />
            <div className="p-4 space-y-4">
              <HealthBadge />
              <Routes>
                <Route path="/" element={<Chat/>} />
                <Route path="/memory" element={<Memory/>} />
                <Route path="/approvals" element={<Approvals/>} />
                <Route path="/observability" element={<Observability/>} />
                <Route path="/settings" element={<Settings/>} />
              </Routes>
            </div>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
