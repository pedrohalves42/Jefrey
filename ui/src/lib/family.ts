import { authedFetch } from "@/lib/session"

export type FamilyState = { enabled: boolean; contact: string }

/** Liga so com um nome para receber: sem contato, fica desligado (o servidor tambem exige). */
export function canEnable(contact: string): boolean {
  return contact.trim().length > 0
}

export async function getFamily(): Promise<FamilyState | null> {
  try {
    const r = await authedFetch("/family")
    return r.ok ? ((await r.json()) as FamilyState) : null
  } catch {
    return null
  }
}

export async function setFamily(enabled: boolean, contact: string): Promise<FamilyState | null> {
  try {
    const r = await authedFetch("/family", { method: "PUT", body: JSON.stringify({ enabled, contact }) })
    return r.ok ? ((await r.json()) as FamilyState) : null
  } catch {
    return null
  }
}
