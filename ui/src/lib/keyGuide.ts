/** Guia de chave para quem nao e tecnico: onde clicar, como reconhecer a chave certa e mensagens humanas. */

export type KeyProviderId = "anthropic" | "openai" | "openrouter"

export type KeyGuide = {
  id: KeyProviderId
  /** Como a pessoa conhece. */
  name: string
  /** Pagina oficial onde a chave e criada (abre em outra aba). */
  url: string
  steps: string[]
}

export const KEY_GUIDES: KeyGuide[] = [
  {
    id: "anthropic",
    name: "Claude",
    url: "https://console.anthropic.com/settings/keys",
    steps: [
      "Clique no botão abaixo. O site do Claude abre em outra aba.",
      "Entre na sua conta e clique em “Create Key” (criar chave). Dê o nome “Jefrey”.",
      "Copie o código que aparece (um botão de copiar fica ao lado) e volte aqui.",
    ],
  },
  {
    id: "openai",
    name: "ChatGPT",
    url: "https://platform.openai.com/api-keys",
    steps: [
      "Clique no botão abaixo. O site do ChatGPT abre em outra aba.",
      "Entre na sua conta e clique em “Create new secret key” (criar nova chave). Dê o nome “Jefrey”.",
      "Copie o código que aparece e volte aqui.",
    ],
  },
]

export const KEY_COST_NOTE =
  "Importante: a assinatura que você paga para conversar no site (Plus, Pro, Max) é separada. A chave tem cobrança própria, só pelo que usar, e você acompanha o gasto no site do provedor."

/** Remove espacos, aspas e quebras que costumam vir junto ao copiar. */
export function cleanKey(text: string): string {
  return (text || "").trim().replace(/^["'`]+|["'`]+$/g, "").trim()
}

/** Descobre de qual servico e o codigo colado, pelo comeco dele. */
export function detectKeyProvider(text: string): KeyProviderId | null {
  const k = cleanKey(text)
  if (k.startsWith("sk-ant-")) return "anthropic"
  if (k.startsWith("sk-or-")) return "openrouter"
  if (k.startsWith("sk-")) return "openai"
  return null
}

/** Texto de erro humano, ou null se o codigo parece certo para o servico escolhido. */
export function keyProblem(expected: KeyProviderId, text: string): string | null {
  const k = cleanKey(text)
  if (!k) return "Cole aqui o código que você copiou."
  if (/\s/.test(k)) return "O código não pode ter espaços no meio. Copie de novo, o código inteiro."
  const found = detectKeyProvider(k)
  if (!found) return "Esse código não parece uma chave. Ela começa com “sk-”. Copie de novo, no botão de copiar do site."
  if (found !== expected) {
    const name = (id: KeyProviderId) => (id === "anthropic" ? "do Claude" : id === "openai" ? "do ChatGPT" : "do OpenRouter")
    return `Esse código parece ser ${name(found)}, mas você escolheu ${name(expected).replace("do ", "o ")}. Escolha o serviço certo acima.`
  }
  if (k.length < 24) return "O código parece cortado. Copie de novo, o código inteiro."
  return null
}

export function guideFor(id: KeyProviderId): KeyGuide | undefined {
  return KEY_GUIDES.find(g => g.id === id)
}
