import { authedFetch } from "@/lib/session"

export type Briefing = { day: string; text: string; seen: boolean }
export type BriefingPrefs = { enabled: boolean; hour: number; notify: boolean }
export type Activity = { studying: boolean; learning: boolean; topic: string | null }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getBriefing = () => json<{ briefing: Briefing | null; prefs: BriefingPrefs }>("/briefing")
export const makeBriefing = () => json<{ briefing: Briefing }>("/briefing/now", { method: "POST" })
export const markBriefingSeen = () => json<{ ok: boolean }>("/briefing/seen", { method: "POST" })
export const putBriefingPrefs = (p: Partial<BriefingPrefs>) => json<BriefingPrefs>("/briefing/prefs", { method: "PUT", body: JSON.stringify(p) })
export const getActivity = () => json<Activity>("/system/activity")

/** Texto sob o avatar quando o Jefrey faz algo sozinho; null se esta quieto. */
export function ambientLabel(a: Activity | null): string | null {
  if (!a) return null
  if (a.studying) return a.topic ? `Estudando ${a.topic}…` : "Estudando em segundo plano…"
  if (a.learning) return "Aprendendo com a conversa…"
  return null
}

/** O resumo so aparece quando existe e a pessoa ainda nao deu ciente. */
export function shouldShowBriefing(b: Briefing | null | undefined): b is Briefing {
  return !!b && !b.seen && b.text.trim().length > 0
}

export const BRIEFING_HOURS = [5, 6, 7, 8, 9, 10, 11, 12]
