import ModelSettings from "@/components/ModelSettings"
import { AppearancePanel } from "@/components/AppearancePanel"
import FallbackSettings from "@/components/FallbackSettings"
import NameField from "@/components/NameField"

export default function Configuracoes() {
  return (
    <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto pb-4">
      <header>
        <h1 className="text-2xl font-semibold text-white">Configurações</h1>
        <p className="text-sm text-white/55">Escolha o modelo de IA e o visual do Jefrey.</p>
      </header>
      <section className="jf-panel p-4" aria-label="Seu nome">
        <h2 className="text-lg font-semibold text-white">Seu nome</h2>
        <p className="text-sm text-white/55">É assim que o Jefrey vai te chamar.</p>
        <NameField compact />
      </section>
      <ModelSettings />
      <FallbackSettings />
      <AppearancePanel />
    </div>
  )
}
