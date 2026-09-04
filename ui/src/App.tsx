import { useEffect, useState } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Nav } from "@/components/Nav"
import { HealthBadge } from "@/components/HealthBadge"
import { OnboardingWizard } from "@/components/OnboardingWizard"
import { HudReactor } from "@/components/HudReactor"
import { ThemeWheel } from "@/components/ThemeWheel"
import { ensureDevToken, getToken } from "@/lib/api"
import { playChime } from "@/lib/audio"
import Chat from "@/pages/Chat"
import Memory from "@/pages/Memory"
import Approvals from "@/pages/Approvals"
import Observability from "@/pages/Observability"
import Settings from "@/pages/Settings"
import { Tour } from "@/components/Tour"

const qc = new QueryClient()

export default function App() {
  const [ready, setReady] = useState(!!getToken())
  const [hudLevel, setHudLevel] = useState(0)
  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      ensureDevToken().then((t) => { if (!cancelled) setReady(!!t || !!getToken()) })
    }
    return () => { cancelled = true }
  }, [])
  useEffect(() => { playChime() }, [])
  // fake LLM pulse when not speaking: subtle 0.04 based on time
  useEffect(() => {
    const id = setInterval(() => setHudLevel(0.04 + Math.sin(Date.now()/1200)*0.02), 200)
    return () => clearInterval(id)
  }, [])
  function onHudClick() {
    try { document.querySelector<HTMLButtonElement>('[aria-label="Falar com Jefrey"]')?.click() } catch {}
    setHudLevel(0.7)
    setTimeout(() => setHudLevel(0.04), 800)
  }
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <div className="min-h-screen bg-background">
          <header className="sticky top-0 z-40 border-b glass-strong backdrop-blur-xl">
            <div className="max-w-5xl mx-auto p-3 flex items-center gap-3">
              <h1 className="font-bold text-lg tracking-tight">Jefrey</h1>
              <span className="text-xs text-muted-foreground hidden sm:inline">1 programa, 7 pecas â€” 175/175 + 21/21</span>
              <div className="ml-auto flex items-center gap-3">
                <ThemeWheel />
                {ready && <span className="text-xs text-emerald-600 font-medium hidden sm:inline">Pronto</span>}
              </div>
            </div>
          </header>
          <div className="max-w-5xl mx-auto">
            <div className="flex justify-center pt-6 pb-2">
              <HudReactor level={hudLevel} onClick={onHudClick} />
            </div>
            <Nav />
            <div className="p-4 space-y-4">
              <OnboardingWizard onDone={() => setReady(!!getToken())} />
              <HealthBadge />
              <Routes>
                <Route path="/" element={<Chat/>} />
                <Route path="/memory" element={<Memory/>} />
                <Route path="/approvals" element={<Approvals/>} />
                <Route path="/observability" element={<Observability/>} />
                <Route path="/settings" element={<Settings/>} />
              </Routes>
              <Tour />
            </div>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
