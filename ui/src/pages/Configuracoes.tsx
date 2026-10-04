import ModelSettings from "@/components/ModelSettings"
import { AppearancePanel } from "@/components/AppearancePanel"
import FallbackSettings from "@/components/FallbackSettings"

export default function Configuracoes() {
  return (
    <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto pb-4">
      <header>
        <h1 className="text-2xl font-semibold text-white">Configurações</h1>
        <p className="text-sm text-white/55">Escolha o modelo de IA e o visual do Jefrey.</p>
      </header>
      <ModelSettings />
      <FallbackSettings />
      <AppearancePanel />
    </div>
  )
}
