import { authedFetch } from "@/lib/session"

/** "Parar tudo": o servidor recusa qualquer acao no computador por alguns segundos. Nunca lanca erro. */
export async function haltComputer(): Promise<boolean> {
  try {
    const r = await authedFetch("/computer/halt", { method: "POST" })
    return r.ok
  } catch {
    return false
  }
}
