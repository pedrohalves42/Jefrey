/** Acoes faceis da tela principal. A ordem acompanha o momento do dia; nenhuma some, so sobe a que faz mais sentido agora. */
export type Action = { id: string; icon: string; label: string; ask?: string; to?: string }

export const ALL_ACTIONS: Action[] = [
  { id: "resumo", icon: "☀️", label: "Resumo do dia" },
  { id: "whatsapp", icon: "💬", label: "Mensagens do WhatsApp", ask: "Tenho mensagem no WhatsApp?" },
  { id: "agenda", icon: "📅", label: "Minha agenda", ask: "O que tenho na agenda hoje?" },
  { id: "lembretes", icon: "🔔", label: "Meus lembretes", ask: "Quais são os meus lembretes?" },
  { id: "criar", icon: "⏰", label: "Criar lembrete", ask: "Quero criar um lembrete" },
  { id: "musica", icon: "🎵", label: "Tocar música", ask: "Toca uma música para mim" },
  { id: "tela", icon: "👀", label: "Olhar minha tela", ask: "Olha a minha tela e me explica o que aparece" },
  { id: "noticias", icon: "📰", label: "Notícias", to: "/hoje" },
  { id: "bolsa", icon: "📈", label: "Bolsa e dólar", to: "/hoje" },
  { id: "aprender", icon: "🎓", label: "Aprender algo", to: "/aprender" },
  { id: "sabe", icon: "🧠", label: "O que você sabe de mim?", ask: "O que você sabe sobre mim?" },
  { id: "pedir", icon: "💡", label: "O que posso pedir?", ask: "O que você consegue fazer por mim?" },
]

const FIRST: Record<string, string[]> = {
  manha: ["resumo", "noticias", "criar"],
  tarde: ["whatsapp", "agenda", "noticias"],
  noite: ["lembretes", "musica", "resumo"],
}

export function momentActions(hour: number): Action[] {
  const h = Number.isFinite(hour) ? ((Math.floor(hour) % 24) + 24) % 24 : 12
  const key = h >= 5 && h < 12 ? "manha" : h >= 12 && h < 18 ? "tarde" : "noite"
  const first = FIRST[key].map(id => ALL_ACTIONS.find(a => a.id === id)!)
  return [...first, ...ALL_ACTIONS.filter(a => !FIRST[key].includes(a.id))]
}
