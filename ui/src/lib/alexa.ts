import { authedFetch } from "@/lib/session"

export type AlexaStatus = { configured: boolean; has_token: boolean; devices: string[]; routines: string[]; verified: boolean }
export type Row = { name: string; id: string }

type Res<T> = { ok: boolean; status: number; data: T | null }

async function json<T>(path: string, init?: RequestInit): Promise<Res<T>> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getAlexa = () => json<AlexaStatus>("/alexa")
export const saveAlexa = (token: string | null, devices: Record<string, string>, routines: Record<string, string>) =>
  json<AlexaStatus>("/alexa", { method: "PUT", body: JSON.stringify({ token, devices, routines }) })
export const testAlexa = () => json<{ ok: boolean; message: string }>("/alexa/test", { method: "POST" })
export const clearAlexa = () => json<AlexaStatus>("/alexa", { method: "DELETE" })

/** Linhas preenchidas viram {nome: codigo}; linhas vazias somem; meia linha e erro de preenchimento. */
export function rowsToMap(rows: Row[]): { map: Record<string, string>; problem: string | null } {
  const map: Record<string, string> = {}
  for (const r of rows) {
    const name = r.name.trim()
    const id = r.id.trim()
    if (!name && !id) continue
    if (!name || !id) return { map, problem: "Preencha o nome e o código de cada linha (ou apague a linha)." }
    map[name] = id
  }
  return { map, problem: null }
}

export const ALEXA_STEPS = [
  "Crie uma conta grátis no Voice Monkey (voicemonkey.io). É o serviço que liga o Jefrey à sua Alexa.",
  "No aplicativo da Alexa, ative a skill “Voice Monkey” e entre com a mesma conta.",
  "No Voice Monkey, crie um “monkey” (aparelho) para cada Echo e, se quiser, um para cada rotina da Alexa. Anote o código de cada um.",
  "Copie o seu token (código de acesso) do Voice Monkey e cole abaixo. Dê um nome fácil a cada aparelho, como “sala”.",
]
