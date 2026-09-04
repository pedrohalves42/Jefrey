import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { isOnboarded, setOnboarded } from "@/lib/api"

export function OnboardingWizard({ onDone }: { onDone?: () => void }) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(1)
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      const tour = params.get("tour") === "1"
      if (tour) { setOpen(true); setStep(1); return }
      if (!isOnboarded()) setOpen(true)
    } catch {}
  }, [])
  function dismiss() {
    setOnboarded(true)
    setOpen(false)
    onDone?.()
  }
  function next() {
    if (step < 3) setStep(step + 1 as 1|2|3)
    else dismiss()
  }
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" role="dialog" aria-modal="true">
      <Card className="w-full max-w-md border-cyan-500/30 shadow-xl shadow-cyan-500/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {step === 1 && "Oi, sou o Jefrey"}
            {step === 2 && "Digite ou fale"}
            {step === 3 && "Pronto para usar"}
            <Badge variant="secondary">1 programa, 7 pecas</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 1 && (
            <div className="space-y-2 text-sm">
              <p>1 programa, 7 pecas — 175/175 validado. Postgres + Redis + LLM qwen2.5 + Voz + MCP + n8n + Grafana.</p>
              <p className="text-muted-foreground">Voce nao precisa entender token. Ja deixei tudo pronto.</p>
              <div className="rounded-md border bg-muted/20 p-2 text-xs font-mono">thread demo-1 pronta • 7/7 healthy</div>
            </div>
          )}
          {step === 2 && (
            <div className="space-y-2 text-sm">
              <p>Digite no Chat ou clique no microfone. Exemplos:</p>
              <ul className="list-disc ml-4 text-muted-foreground">
                <li>"oi, o que voce faz?"</li>
                <li>"salve uma memoria: meu projeto e Jarvis"</li>
              </ul>
              <p className="text-xs text-muted-foreground">Voz: STT small pt + TTS piper 6 vozes. Wake "Jefrey/Jarvis" em Settings.</p>
            </div>
          )}
          {step === 3 && (
            <div className="space-y-2 text-sm">
              <p>Tudo pronto. Nenhum manual.</p>
              <p className="text-muted-foreground">Se ver 401, clique em "Liberar acesso (1s)" — eu renovo sozinho.</p>
              <div className="rounded-md border border-cyan-500/20 bg-cyan-500/10 p-2 text-xs">Dica: use ?tour=1 para rever este guia.</div>
            </div>
          )}
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-muted-foreground">{step}/3</span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={dismiss}>Pular</Button>
              <Button onClick={next}>{step < 3 ? "Proximo →" : "Comecar →"}</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
