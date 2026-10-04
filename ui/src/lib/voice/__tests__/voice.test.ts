import { describe, expect, it } from "vitest"
import { Endpointer } from "../vad"
import { SentenceBuffer, speakable } from "../sentences"

/** alimenta o detector com um nivel constante por `ms` milissegundos (passo de 50 ms). */
function feed(ep: Endpointer, level: number, from: number, ms: number): { t: number; ev: string | null } {
  let ev: string | null = null
  let t = from
  for (; t < from + ms; t += 50) {
    const e = ep.update(level, t)
    if (e && !ev) ev = e
  }
  return { t, ev }
}

describe("Endpointer", () => {
  it("detecta inicio e fim de uma fala", () => {
    const ep = new Endpointer({ threshold: 0.02, minSpeechMs: 150, endSilenceMs: 800 })
    let r = feed(ep, 0.003, 0, 500)
    expect(r.ev).toBeNull()
    r = feed(ep, 0.1, r.t, 600)
    expect(r.ev).toBe("speech_start")
    expect(ep.speaking).toBe(true)
    r = feed(ep, 0.002, r.t, 1000)
    expect(r.ev).toBe("speech_end")
    expect(ep.finished).toBe(true)
  })

  it("ignora estalos curtos (menos que minSpeechMs)", () => {
    const ep = new Endpointer({ minSpeechMs: 200 })
    expect(feed(ep, 0.003, 0, 300).ev).toBeNull()
    expect(feed(ep, 0.2, 300, 100).ev).toBeNull() // 100 ms de barulho
    expect(feed(ep, 0.003, 400, 400).ev).toBeNull()
    expect(ep.speaking).toBe(false)
  })

  it("pausa curta no meio da fala nao encerra", () => {
    const ep = new Endpointer({ endSilenceMs: 1000, minSpeechMs: 100 })
    let r = feed(ep, 0.1, 0, 400)
    expect(r.ev).toBe("speech_start")
    r = feed(ep, 0.002, r.t, 500) // pausa de meio segundo
    expect(r.ev).toBeNull()
    r = feed(ep, 0.1, r.t, 300)
    expect(r.ev).toBeNull()
    expect(ep.speaking).toBe(true)
  })

  it("desiste se ninguem falar (timeout)", () => {
    const ep = new Endpointer({ maxWaitMs: 2000 })
    expect(feed(ep, 0.003, 0, 2500).ev).toBe("timeout")
    expect(ep.update(0.5, 9999)).toBeNull() // depois de terminar nao reage mais
  })

  it("limita a duracao da fala", () => {
    const ep = new Endpointer({ maxSpeechMs: 1000, minSpeechMs: 50 })
    const r = feed(ep, 0.2, 0, 3000)
    expect(r.ev).toBe("speech_start")
    expect(ep.finished).toBe(true)
  })

  it("se adapta ao ruido de fundo alto", () => {
    const ep = new Endpointer({ threshold: 0.02, minSpeechMs: 100 })
    // ruido constante de 0.03 (acima do limiar fixo) durante muito tempo
    let r = feed(ep, 0.015, 0, 1000) // abaixo do limiar: aprende o piso
    expect(r.ev).toBeNull()
    r = feed(ep, 0.05, r.t, 400)
    expect(r.ev).toBe("speech_start")
  })

  it("entradas invalidas (NaN, negativo) nao quebram", () => {
    const ep = new Endpointer()
    expect(() => {
      ep.update(NaN, 0)
      ep.update(-1, 50)
      ep.update(Infinity, 100)
    }).not.toThrow()
  })
})

describe("speakable", () => {
  it("nao le codigo, links nem markdown", () => {
    expect(speakable("Veja:\n```py\nprint(1)\n```\nacabou")).toContain("trecho de código")
    expect(speakable("Veja:\n```py\nprint(1)\n```\nacabou")).not.toContain("print")
    expect(speakable("Acesse https://exemplo.com/x agora")).toBe("Acesse link agora")
    expect(speakable("**negrito** e `codigo` e *italico*")).toBe("negrito e codigo e italico")
    expect(speakable("# Titulo\n- item um\n- item dois")).toBe("Titulo\nitem um\nitem dois")
    expect(speakable("[texto](http://a.b)")).toBe("texto")
  })

  it("remove emojis e fecha bloco de codigo ainda aberto", () => {
    expect(speakable("Oi 😊 tudo bem?")).toBe("Oi tudo bem?")
    expect(speakable("antes ```codigo sem fim")).not.toContain("codigo sem")
  })
})

describe("SentenceBuffer", () => {
  const run = (chunks: string[], min = 10) => {
    const b = new SentenceBuffer(min)
    const out: string[] = []
    for (const c of chunks) out.push(...b.push(c))
    out.push(...b.flush())
    return out
  }

  it("entrega frases completas conforme chegam", () => {
    expect(run(["Olá, tudo bem? ", "Eu sou o Jefrey. ", "Como posso ajudar?"])).toEqual([
      "Olá, tudo bem?",
      "Eu sou o Jefrey.",
      "Como posso ajudar?",
    ])
  })

  it("junta frases curtas demais com a proxima", () => {
    expect(run(["Ok. ", "Vou salvar isso agora mesmo."], 20)).toEqual(["Ok. Vou salvar isso agora mesmo."])
  })

  it("funciona com pedacos minusculos (token a token)", () => {
    const text = "A capital da França é Paris. Ela fica no norte do país."
    expect(run(text.split(""))).toEqual(["A capital da França é Paris.", "Ela fica no norte do país."])
  })

  it("nao corta em numeros, abreviacoes nem enderecos", () => {
    expect(run(["O valor de pi é 3.14 aproximadamente. ", "Fale com o Sr. Silva amanhã cedo."])).toEqual([
      "O valor de pi é 3.14 aproximadamente.",
      "Fale com o Sr. Silva amanhã cedo.",
    ])
    expect(run(["Acesse exemplo.com.br para saber mais sobre o assunto."])).toEqual(["Acesse exemplo.com.br para saber mais sobre o assunto."])
  })

  it("quebra de linha encerra a frase (listas)", () => {
    expect(run(["1) primeiro item\n2) segundo item\n"])).toEqual(["1) primeiro item", "2) segundo item"])
  })

  it("espera mais texto quando a frase pode continuar e entrega o resto no flush", () => {
    const b = new SentenceBuffer(5)
    expect(b.push("Terminou aqui.")).toEqual([]) // pode vir "..." ou "5" depois
    expect(b.flush()).toEqual(["Terminou aqui."])
    expect(b.flush()).toEqual([])
  })

  it("reticencias e exclamacoes", () => {
    expect(run(["Hmm... deixa eu pensar um pouco! ", "Já sei a resposta."])).toEqual(["Hmm... deixa eu pensar um pouco!", "Já sei a resposta."])
  })
})

describe("speakable: contas e simbolos", () => {
  it("le contas em palavras e preserva o resultado", () => {
    expect(speakable("17 * 23 = 391")).toBe("17 vezes 23 igual a 391")
    expect(speakable("2 + 3 = 5")).toBe("2 mais 3 igual a 5")
    expect(speakable("10 - 4 = 6")).toBe("10 menos 4 igual a 6")
    expect(speakable("3×4")).toBe("3 vezes 4")
    expect(speakable("3*4*5")).toBe("3 vezes 4 vezes 5") // nao confunde com italico
  })

  it("nao estraga datas, nomes_com_underscore nem asteriscos soltos", () => {
    expect(speakable("Hoje e 2026-10-04")).toBe("Hoje e 2026-10-04")
    expect(speakable("variavel nome_do_arquivo ok")).toBe("variavel nome_do_arquivo ok")
    expect(speakable("nota*")).toBe("nota*")
  })
})

