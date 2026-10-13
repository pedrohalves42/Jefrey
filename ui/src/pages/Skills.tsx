import { useEffect, useState } from "react"
import { authedFetch } from "@/lib/session"

type Tool = { name: string; description: string; risk: string | null }
type Skill = { name: string; description: string; version: string; tags: string[]; requires_auth: boolean; enabled: boolean; tools: Tool[] }

const RISK: Record<string, { label: string; cls: string }> = {
  low: { label: "baixo", cls: "text-emerald-300" },
  medium: { label: "médio", cls: "text-amber-300" },
  high: { label: "alto: pede sua aprovação", cls: "text-orange-300" },
  critical: { label: "crítico: pede sua aprovação", cls: "text-red-300" },
  unknown: { label: "ainda não classificado", cls: "text-white/40" },
}

const NICE: Record<string, string> = {
  essentials: "Dia a dia (hora, conta, clima, arquivos)",
  computer: "Controlar o computador",
  alexa: "Alexa",
  reminders: "Lembretes",
  notes: "Notas",
  automation: "Automação",
  calendar: "Agenda",
  email: "E-mail",
  web_search: "Busca na web",
  drive: "Arquivos (Drive)",
}

/** O que dizer para usar cada skill (a voz ou o teclado, na Conversa). */
const EXAMPLES: Record<string, string[]> = {
  essentials: ["Que horas são?", "Quanto é 15% de 240?", "Como está o tempo em São Paulo?"],
  computer: ["Abre o Word", "Abre o YouTube", "Aumenta o volume", "Pausa a música", "Fecha o Chrome"],
  alexa: ["Fala na Alexa que o jantar está pronto", "Aciona a rotina boa noite"],
  reminders: ["Me lembra de beber água daqui a 30 minutos"],
  notes: ["Anota que a senha do wifi está na geladeira", "O que eu anotei sobre o médico?"],
  calendar: ["O que tenho amanhã na agenda?"],
  email: ["Tenho e-mail novo?"],
  web_search: ["Pesquisa o resultado do jogo de ontem"],
  drive: ["Procura meu currículo no Drive"],
}
const NEEDS: Record<string, { text: string; to: string }> = {
  alexa: { text: "Precisa ser conectada", to: "/conexoes?aba=alexa" },
  calendar: { text: "Precisa entrar com o Google", to: "/conexoes?aba=google" },
  email: { text: "Precisa entrar com o Google", to: "/conexoes?aba=google" },
  drive: { text: "Precisa entrar com o Google", to: "/conexoes?aba=google" },
}

export default function Skills() {
  const [skills, setSkills] = useState<Skill[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function toggle(name: string, enabled: boolean) {
    setBusy(name)
    setError(null)
    setSkills(prev => (prev ? prev.map(s => (s.name === name ? { ...s, enabled } : s)) : prev)) // otimista
    try {
      const r = await authedFetch(`/skills/${name}`, { method: "PUT", body: JSON.stringify({ enabled }) })
      if (!r.ok) throw new Error(String(r.status))
    } catch {
      setSkills(prev => (prev ? prev.map(s => (s.name === name ? { ...s, enabled: !enabled } : s)) : prev)) // desfaz
      setError("Não consegui salvar essa escolha. Tente de novo.")
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    let alive = true
    authedFetch("/skills")
      .then(async r => {
        if (!r.ok) throw new Error(String(r.status))
        const j = await r.json()
        if (alive) setSkills(Array.isArray(j.skills) ? j.skills : [])
      })
      .catch(() => alive && setError("Não consegui carregar as skills. Verifique se o Jefrey está rodando."))
    return () => {
      alive = false
    }
  }, [])

  const toolCount = skills?.reduce((n, s) => n + s.tools.length, 0) ?? 0

  return (
    <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto pb-4">
      <header>
        <h1 className="text-2xl font-semibold text-white">Skills</h1>
        <p className="text-sm text-white/55">
          O que o Jefrey sabe fazer{skills ? `: ${skills.length} skills, ${toolCount} ferramentas` : ""}. Ações de risco sempre pedem a sua aprovação.
        </p>
      </header>

      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}
      {!skills && !error && <p className="text-sm text-white/50">Carregando…</p>}
      {skills && skills.length === 0 && <p className="jf-panel p-4 text-sm text-white/60">Nenhuma skill carregada.</p>}

      <ul className="space-y-3">
        {skills?.map(s => (
          <li key={s.name} className={`jf-panel p-4 ${s.enabled ? "" : "opacity-60"}`}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 className="font-medium text-white">{NICE[s.name] ?? s.name}</h2>
              <button
                type="button"
                role="switch"
                aria-checked={s.enabled}
                aria-label={`${s.enabled ? "Desligar" : "Ligar"} ${NICE[s.name] ?? s.name}`}
                disabled={busy === s.name}
                onClick={() => void toggle(s.name, !s.enabled)}
                className={`jf-focus ml-auto inline-flex h-6 w-11 items-center rounded-full border transition-colors ${
                  s.enabled ? "border-emerald-400/50 bg-emerald-500/30" : "border-white/20 bg-white/5"
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${s.enabled ? "translate-x-6" : "translate-x-1"}`} />
              </button>
              <span className="text-xs text-white/40">v{s.version}</span>
              {s.requires_auth && <span className="rounded-full border border-amber-400/30 px-2 text-xs text-amber-200">precisa de login Google</span>}
              <span className="text-xs text-white/40">{s.tools.length} ferramentas</span>
            </div>
            <p className="mt-1 text-sm text-white/65">{s.description}</p>
            {EXAMPLES[s.name] && <p className="mt-1 text-sm text-white/55">Experimente dizer: {EXAMPLES[s.name].map(e => `“${e}”`).join(", ")}</p>}
            {NEEDS[s.name] && s.enabled && <p className="mt-1 text-sm text-amber-200/90">{NEEDS[s.name].text}: <a className="underline" href={NEEDS[s.name].to}>abrir Conexões</a></p>}
            {!s.enabled && <p className="mt-1 text-sm text-white/50">Desligada: o Jefrey não usa isso até você ligar.</p>}
            <button
              type="button"
              onClick={() => setOpen(open === s.name ? null : s.name)}
              aria-expanded={open === s.name}
              className="jf-focus mt-2 text-sm jf-accent hover:underline"
            >
              {open === s.name ? "Esconder ferramentas" : "Ver ferramentas"}
            </button>
            {open === s.name && (
              <ul className="mt-2 space-y-1.5 border-t border-white/10 pt-2">
                {s.tools.map(t => {
                  const risk = t.risk ? RISK[t.risk] : undefined
                  return (
                    <li key={t.name} className="text-sm">
                      <code className="text-white/90">{t.name}</code>
                      {risk && <span className={`ml-2 text-xs ${risk.cls}`}>risco {risk.label}</span>}
                      {t.description && <div className="text-xs text-white/50">{t.description}</div>}
                    </li>
                  )
                })}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
