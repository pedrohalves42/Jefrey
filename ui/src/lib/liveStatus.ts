/** Frase curta sobre o que o Jefrey esta fazendo agora (mostrada embaixo do avatar). Pura: o relogio entra por parametro. */

export type LiveTool = { tool: string; label: string }
export type LiveInput = { streaming: boolean; gotToken: boolean; approval: boolean; tool: LiveTool | null; elapsedS: number }

const DOING: Record<string, string> = {
  search: "Buscando na web…",
  search_news: "Procurando notícias…",
  news_brief: "Procurando notícias…",
  daily_summary: "Montando o resumo do seu dia…",
  list_events: "Olhando a sua agenda…",
  create_event: "Marcando na sua agenda…",
  read_emails: "Lendo os seus e-mails…",
  search_emails: "Procurando nos seus e-mails…",
  create_reminder: "Criando o lembrete…",
  list_reminders: "Vendo os seus lembretes…",
  undo_last: "Desfazendo…",
}

export function liveStatus(i: LiveInput): string | null {
  if (!i.streaming) return null
  if (i.approval) return "Aguardando sua aprovação"
  if (i.tool) return DOING[i.tool.tool] ?? `Fazendo: ${i.tool.label.toLowerCase()}…`
  if (i.gotToken) return "Escrevendo a resposta…"
  if (i.elapsedS >= 12) return "Está demorando mais que o normal. Continuo tentando…"
  if (i.elapsedS >= 5) return "Ainda pensando…"
  return "Pensando…"
}
