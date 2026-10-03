import { useEffect, useState } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Nav } from "@/components/Nav"
import { HealthBadge } from "@/components/HealthBadge"
import { OnboardingWizard } from "@/components/OnboardingWizard"
import { HudReactor, type JefreyState, type JarvisState } from "@/components/HudReactor"
import { useWakeWord } from "@/hooks/useWakeWord"
import { ThemeWheel } from "@/components/ThemeWheel"
import { ensureDevToken, getToken } from "@/lib/api"
import { playChime } from "@/lib/audio"
import Chat from "@/pages/Chat"
import ChatStudio from "@/pages/ChatStudio"
import MemoryStudio from "@/pages/MemoryStudio"
import AutomationStudio from "@/pages/AutomationStudio"
import Memory from "@/pages/Memory"
import Approvals from "@/pages/Approvals"
import Observability from "@/pages/Observability"
import Settings from "@/pages/Settings"
import Knowledge from "@/pages/KnowledgePage"
import { Tour } from "@/components/Tour"
import { SkillManager } from "@/components/SkillManager"
import { AuthButton } from "@/components/AuthButton"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

const qc = new QueryClient()

function StudioRouter() {
  return (
    <Tabs defaultValue="chat" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="chat" className="data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-300">
          Chat Studio
        </TabsTrigger>
        <TabsTrigger value="memory" className="data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-300">
          Memory Studio
        </TabsTrigger>
        <TabsTrigger value="automation" className="data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-300">
          Automation Studio
        </TabsTrigger>
      </TabsList>
      <TabsContent value="chat">
        <ChatStudio />
      </TabsContent>
      <TabsContent value="memory">
        <MemoryStudio />
      </TabsContent>
      <TabsContent value="automation">
        <AutomationStudio />
      </TabsContent>
    </Tabs>
  )
}

export default function App() {
  const [ready, setReady] = useState(!!getToken())
  const [hudLevel, setHudLevel] = useState(0)
  const [hudState, setHudState] = useState<JefreyState>("idle")
  const [wakeEnabled, setWakeEnabled] = useState(false)
  const wake = useWakeWord({ enabled: wakeEnabled, onWake: () => { setHudState("listening"); setHudLevel(0.6); try { document.querySelector<HTMLButtonElement>('[aria-label="Falar com Jefrey"]')?.click() } catch {} } })
  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      ensureDevToken().then((t) => { if (!cancelled) setReady(!!t || !!getToken()) })
    }
    return () => { cancelled = true }
  }, [])
  useEffect(() => { playChime() }, [])
  // isair face_widget idle breathing + state wiring (listening via wake, thinking via chat, speaking via TTS)
  useEffect(() => {
    const id = setInterval(() => {
      if (hudState==="idle") setHudLevel(0.04 + Math.sin(Date.now()/1200)*0.02)
    }, 200)
    return () => clearInterval(id)
  }, [hudState])
  // expose global hook for Chat/Voice to drive HUD (Stark lab)
  useEffect(()=>{ (window as any).__setHudState = (s:JefreyState)=> setHudState(s); (window as any).__setHudLevel = (v:number)=> setHudLevel(v); return ()=>{ delete (window as any).__setHudState; delete (window as any).__setHudLevel }},[])
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
              <h1 className="font-bold text-lg tracking-tight text-cyan-100">Jefrey</h1>
              <span className="text-xs text-muted-foreground hidden sm:inline text-cyan-200/60">1 programa, 7 pecas — 175/175 + 21/21</span>
              <div className="ml-auto flex items-center gap-3">
                <button onClick={()=> setWakeEnabled(v=>!v)} title={wake.supported ? (wakeEnabled ? "Desativar wake Jefrey" : "Ativar wake Jefrey") : "Wake nao suportado neste browser"} className={`text-[10px] px-2 py-1 rounded-full font-mono border transition-all ${wakeEnabled ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30" : "bg-white/5 text-white/50 border-white/10 hover:bg-white/10"}`}>{wakeEnabled ? "WAKE ON" : "WAKE OFF"}</button>
                <AuthButton />
                <ThemeWheel />
                {ready && <span className="text-xs text-emerald-400 font-medium hidden sm:inline">Pronto</span>}
              </div>
            </div>
          </header>
          <div className="max-w-5xl mx-auto">
            <div className="flex justify-center pt-6 pb-2">
              <HudReactor level={hudLevel} state={hudState} onClick={onHudClick} />
            </div>
            <Nav />
            <div className="p-4 space-y-4">
              <OnboardingWizard onDone={() => setReady(!!getToken())} />
              <HealthBadge />
              <SkillManager />
              <Routes>
                <Route path="/" element={<Chat/>} />
                <Route path="/studio" element={<StudioRouter />} />
                <Route path="/memory" element={<Memory/>} />
                <Route path="/approvals" element={<Approvals/>} />
                <Route path="/observability" element={<Observability/>} />
                <Route path="/settings" element={<Settings/>} />
                <Route path="/knowledge" element={<Knowledge/>} />
              </Routes>
              <Tour />
            </div>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}