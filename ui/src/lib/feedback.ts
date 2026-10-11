import { authedFetch } from "@/lib/session"

export type FeedbackValue = "up" | "down"
export const FEEDBACK_LABEL: Record<FeedbackValue, string> = { up: "Gostei da resposta", down: "Não gostei da resposta" }

/** Corpo do POST /feedback: so o id da mensagem, o valor e uma nota curta (nunca o texto da conversa). */
export function feedbackPayload(messageId: string, value: FeedbackValue, note = "") {
  return { message_id: messageId.slice(0, 120), value, note: note.slice(0, 300) }
}

export async function sendFeedback(messageId: string, value: FeedbackValue, note = ""): Promise<boolean> {
  try {
    const r = await authedFetch("/feedback", { method: "POST", body: JSON.stringify(feedbackPayload(messageId, value, note)) })
    return r.ok
  } catch {
    return false
  }
}
