import { lazy, Suspense, useEffect } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AppShell } from "@/components/AppShell"
import { AppearanceProvider } from "@/lib/appearance"
import { ensureSession } from "@/lib/session"
import Conversa from "@/pages/Conversa"
import Memoria from "@/pages/Memoria"
import Skills from "@/pages/Skills"
import Configuracoes from "@/pages/Configuracoes"
import Avancado from "@/pages/Avancado"
import BemVindo from "@/pages/BemVindo"
import PrimeiraVez from "@/pages/PrimeiraVez"
import Hoje from "@/pages/Hoje"
import Conexoes from "@/pages/Conexoes"
import Ajuda from "@/pages/Ajuda"
import Aprendi from "@/pages/Aprendi"
import Estudos from "@/pages/Estudos"
import Aprender from "@/pages/Aprender"
import Termos from "@/pages/Termos"
import Privacidade from "@/pages/Privacidade"
import { applyEasy, getEasy } from "@/lib/easy"
import { isDesktop } from "@/lib/shell"

const Orb = lazy(() => import("@/pages/Orb"))

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } })

export default function App() {
  useEffect(() => {
    applyEasy(getEasy())
    isDesktop() // guarda ?app=1 (janela propria do programa) antes de a rota mudar a URL
    void ensureSession()
  }, [])
  return (
    <QueryClientProvider client={qc}>
      <AppearanceProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/orb" element={<Suspense fallback={null}><Orb /></Suspense>} />
            <Route element={<AppShell />}>
              <Route path="/" element={<Conversa />} />
              <Route path="/memoria" element={<Memoria />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/configuracoes" element={<Configuracoes />} />
              <Route path="/avancado" element={<Avancado />} />
              <Route path="/bem-vindo" element={<BemVindo />} />
              <Route path="/primeira-vez" element={<PrimeiraVez />} />
              <Route path="/hoje" element={<Hoje />} />
              <Route path="/conexoes" element={<Conexoes />} />
              <Route path="/ajuda" element={<Ajuda />} />
              <Route path="/aprendi" element={<Aprendi />} />
              <Route path="/estudos" element={<Estudos />} />
              <Route path="/aprender" element={<Aprender />} />
              <Route path="/termos" element={<Termos />} />
              <Route path="/privacidade" element={<Privacidade />} />
              {/* enderecos antigos */}
              <Route path="/memory" element={<Navigate to="/memoria" replace />} />
              <Route path="/settings" element={<Navigate to="/configuracoes" replace />} />
              <Route path="/approvals" element={<Navigate to="/avancado" replace />} />
              <Route path="/observability" element={<Navigate to="/avancado" replace />} />
              <Route path="/knowledge" element={<Navigate to="/" replace />} />
              <Route path="/studio" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AppearanceProvider>
    </QueryClientProvider>
  )
}
