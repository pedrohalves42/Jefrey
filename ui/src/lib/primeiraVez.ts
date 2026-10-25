/** Assistente de primeira vez, conduzido por voz: nome -> ligar a inteligencia -> experimentar. Logica pura (a tela so fala e escuta). */

export type StepId = "nome" | "cerebro" | "experimente" | "fim"
export type Brain = "agora" | "depois" | null
export type State = { step: StepId; name: string; brain: Brain; misses: number; done: boolean }

export const MAX_MISSES = 3 // depois de 3 respostas que nao deu para entender, segue sem travar a pessoa

export const STEPS: { id: StepId }[] = [{ id: "nome" }, { id: "cerebro" }, { id: "experimente" }, { id: "fim" }]

/** O que o Jefrey fala em cada passo (frases curtas, ate 20 palavras). */
export function script(step: StepId, name: string): string {
  switch (step) {
    case "nome":
      return "Oi! Eu sou o Jefrey. Como posso te chamar?"
    case "cerebro":
      return `Prazer, ${name || "amigo"}! Para eu pensar bem, preciso me ligar à internet. Posso fazer isso agora? Diga sim ou depois.`
    case "experimente":
      return "Pronto! Agora experimente falar comigo. Pergunte: que horas são?"
    default:
      return "Tudo certo! Pode falar comigo quando quiser."
  }
}

export function initial(): State {
  return { step: "nome", name: "", brain: null, misses: 0, done: false }
}

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim()

const NO = ["nao", "depois", "mais tarde", "agora nao", "deixa", "outra hora", "nem", "para depois", "pra depois"]
const YES = ["sim", "quero", "pode", "claro", "uhum", "ok", "okay", "vamos", "bora", "isso", "certo", "positivo", "com certeza"]

export function parseYesNo(text: string): "sim" | "nao" | null {
  const t = norm(text)
  if (!t) return null
  const words = t.split(" ")
  if (NO.some(n => (n.includes(" ") ? t.includes(n) : words.includes(n)))) return "nao" // "agora nao" e nao, apesar de ter "agora"
  if (YES.some(y => (y.includes(" ") ? t.includes(y) : words.includes(y)))) return "sim"
  return null
}

const NAME_LEAD = /^(?:oi|ola|bom dia|boa tarde|boa noite)?\s*(?:meu nome e|meu nome|me chamo|pode me chamar de|pode me chamar|me chama de|me chame de|eu sou o|eu sou a|eu sou|sou o|sou a|sou|aqui e o|aqui e a|aqui e)\s+/

/** Tira o nome de "meu nome e Pedro", "me chamo Ana", "Dona Lurdes"... Devolve "" se nao parece um nome. */
export function cleanName(text: string): string {
  const original = (text || "").trim()
  if (!original || original.length > 60) return ""
  const folded = norm(original)
  const lead = folded.match(NAME_LEAD)
  // acha onde o nome comeca no texto ORIGINAL (preserva acentos), contando palavras da introducao
  let rest = original
  if (lead) {
    const skip = lead[0].trim().split(" ").length
    rest = original.split(/\s+/).slice(skip).join(" ")
  }
  const words = rest
    .replace(/[.,!?;:]/g, " ")
    .split(/\s+/)
    .filter(w => /^[A-Za-zÀ-ÿ'-]{2,}$/.test(w) && !/^(?:h?m+|a+h*n*|e+h*|u+h*|o+h*|h+)$/.test(norm(w))) // "ééé", "hmm", "ahn": hesitacao, nao nome
    .slice(0, 3)
  if (!words.length) return ""
  return words.map(w => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" ")
}

/** Proximo estado dado o que a pessoa disse. Nunca trava: depois de MAX_MISSES erros, segue. */
export function nextStep(s: State, answer: string): State {
  switch (s.step) {
    case "nome": {
      const name = cleanName(answer)
      if (name) return { ...s, name, step: "cerebro", misses: 0 }
      return s.misses + 1 >= MAX_MISSES ? { ...s, step: "cerebro", misses: 0 } : { ...s, misses: s.misses + 1 }
    }
    case "cerebro": {
      const yn = parseYesNo(answer)
      if (yn === "sim") return { ...s, brain: "agora", step: "experimente", misses: 0 }
      if (yn === "nao") return { ...s, brain: "depois", step: "experimente", misses: 0 }
      return s.misses + 1 >= MAX_MISSES ? { ...s, brain: "depois", step: "experimente", misses: 0 } : { ...s, misses: s.misses + 1 }
    }
    case "experimente":
      return { ...s, step: "fim", done: true, misses: 0 }
    default:
      return { ...s, done: true }
  }
}
