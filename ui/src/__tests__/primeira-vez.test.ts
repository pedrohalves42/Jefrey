import { describe, expect, it } from "vitest"
import { cleanName, initial, nextStep, parseYesNo, script, STEPS } from "../lib/primeiraVez"

describe("primeira vez: entender a resposta falada", () => {
  it("sim e nao em linguagem do dia a dia", () => {
    for (const t of ["sim", "Sim, quero", "pode ser", "claro", "uhum", "vamos lá", "quero sim"]) expect(parseYesNo(t)).toBe("sim")
    for (const t of ["não", "Nao obrigado", "depois", "agora não", "deixa pra depois", "mais tarde"]) expect(parseYesNo(t)).toBe("nao")
    expect(parseYesNo("banana")).toBeNull()
    expect(parseYesNo("")).toBeNull()
  })
  it("'agora nao' e nao, mesmo tendo a palavra 'agora'", () => expect(parseYesNo("agora não")).toBe("nao"))
  it("extrai o nome de frases comuns", () => {
    expect(cleanName("meu nome é Pedro")).toBe("Pedro")
    expect(cleanName("Me chamo Ana Maria.")).toBe("Ana Maria")
    expect(cleanName("pode me chamar de Zé")).toBe("Zé")
    expect(cleanName("eu sou o João")).toBe("João")
    expect(cleanName("Dona Lurdes")).toBe("Dona Lurdes")
    expect(cleanName("  carlos  ")).toBe("Carlos")
  })
  it("nome vazio, muito longo ou so ruido nao serve", () => {
    expect(cleanName("")).toBe("")
    expect(cleanName("ééé hmm")).toBe("")
    expect(cleanName("a".repeat(80))).toBe("")
  })
})

describe("primeira vez: passos", () => {
  it("percorre tudo so com respostas de voz simuladas", () => {
    let s = initial()
    expect(s.step).toBe("nome")
    s = nextStep(s, "meu nome é Dona Lurdes")
    expect(s.name).toBe("Dona Lurdes")
    expect(s.step).toBe("cerebro")
    s = nextStep(s, "sim")
    expect(s.brain).toBe("agora")
    expect(s.step).toBe("experimente")
    s = nextStep(s, "que horas são")
    expect(s.step).toBe("fim")
    expect(s.done).toBe(true)
  })
  it("resposta que nao entendi repete a pergunta e nunca trava", () => {
    let s = nextStep(initial(), "")
    expect(s.step).toBe("nome")
    expect(s.misses).toBe(1)
    s = nextStep(s, "hmm")
    s = nextStep(s, "hmm")
    expect(s.step).toBe("cerebro") // depois de 3 tentativas segue sem nome
    expect(s.name).toBe("")
  })
  it("'depois' no cerebro pula sem travar", () => {
    let s = nextStep(initial(), "Ana")
    s = nextStep(s, "depois")
    expect(s.brain).toBe("depois")
    expect(s.step).toBe("experimente")
  })
  it("cada fala tem ate 20 palavras", () => {
    for (const st of STEPS) expect(script(st.id, "Dona Lurdes").split(/\s+/).length).toBeLessThanOrEqual(20)
  })
  it("a fala do cerebro usa o nome", () => expect(script("cerebro", "Ana")).toContain("Ana"))
})
