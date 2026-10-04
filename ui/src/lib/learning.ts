import { authedFetch } from "@/lib/session"

export type Fact = { id: string; kind: string; key: string; text: string; sensitive: boolean; active: boolean; created_at: string }

async function json<T>(path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: T | null }> {
  try {
    const r = await authedFetch(path, init)
    return { ok: r.ok, status: r.status, data: (await r.json().catch(() => null)) as T | null }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export const getLearned = () => json<{ enabled: boolean; facts: Fact[] }>("/learning")
export const setLearning = (enabled: boolean) => json<{ enabled: boolean }>("/learning", { method: "PUT", body: JSON.stringify({ enabled }) })
export const correctFact = (id: string, text: string) => json<Fact>(`/learning/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ text }) })
export const forgetFact = (id: string) => json<{ ok: boolean }>(`/learning/${encodeURIComponent(id)}`, { method: "DELETE" })
export const forgetAll = () => json<{ ok: boolean; removed: number }>("/learning", { method: "DELETE" })

const KIND_LABEL: Record<string, string> = {
  pessoa: "Sobre você",
  familia: "Família e amigos",
  gosto: "Gostos",
  trabalho: "Trabalho",
  projeto: "Projetos",
  data: "Datas",
  saude: "Saúde",
  dinheiro: "Dinheiro",
  outro: "Outras coisas",
}
const ORDER = ["pessoa", "familia", "gosto", "trabalho", "projeto", "data", "saude", "dinheiro", "outro"]

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? KIND_LABEL.outro!
}

/** Agrupa os fatos por assunto, na ordem em que a pessoa espera ver. */
export function groupFacts(facts: Fact[]): { kind: string; label: string; items: Fact[] }[] {
  const by = new Map<string, Fact[]>()
  for (const f of facts) {
    const k = ORDER.includes(f.kind) ? f.kind : "outro"
    by.set(k, [...(by.get(k) ?? []), f])
  }
  return ORDER.filter(k => by.has(k)).map(k => ({ kind: k, label: kindLabel(k), items: by.get(k)! }))
}

/** Mensagem humana para o erro de uma correcao. */
export function correctionError(status: number): string {
  if (status === 422) return "Esse texto não pode ser guardado (parece conter senha ou número de documento)."
  if (status === 404) return "Não encontrei mais isso. A lista foi atualizada."
  return "Não consegui salvar agora. Tente de novo."
}
