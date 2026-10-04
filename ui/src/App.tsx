import { useEffect } from "react"
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

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } })

export default function App() {
  useEffect(() => {
    void ensureSession()
  }, [])
  return (
    <QueryClientProvider client={qc}>
      <AppearanceProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Conversa />} />
              <Route path="/memoria" element={<Memoria />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/configuracoes" element={<Configuracoes />} />
              <Route path="/avancado" element={<Avancado />} />
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
