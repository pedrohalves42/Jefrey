import { authedFetch } from "@/lib/session"

export type FeedbackValue = "up" | "down"
export const FEEDBACK_LABEL: Record<FeedbackValue, string> = { up: "Gostei da resposta", down: "Não gostei da resposta" }

/** Corpo do POST /feedback: so o id da mensagem, o valor e uma nota curta (nunca o texto da conversa). */
export type FeedbackBody = { message_id: string; value: FeedbackValue; note: string; question?: string; answer?: string }

export function feedbackPayload(messageId: string, value: FeedbackValue, note = "", question = "", answer = ""): FeedbackBody {
  const base: FeedbackBody = { message_id: messageId.slice(0, 120), value, note: note.slice(0, 300) }
  // so o 👎 leva o texto: ele vira um caso de teste local para a pessoa revisar; o 👍 nunca leva conversa
  return value === "down" && question && answer ? { ...base, question: question.slice(0, 500), answer: answer.slice(0, 2000) } : base
}

export async function sendFeedback(messageId: string, value: FeedbackValue, note = "", question = "", answer = ""): Promise<boolean> {
  try {
    const r = await authedFetch("/feedback", { method: "POST", body: JSON.stringify(feedbackPayload(messageId, value, note, question, answer)) })
    return r.ok
  } catch {
    return false
  }
}
