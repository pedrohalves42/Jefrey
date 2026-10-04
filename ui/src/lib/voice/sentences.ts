/** Texto como deve ser FALADO: sem codigo, links, markdown nem emojis; contas viram palavras. */
export function speakable(text: string): string {
  return text
    .replace(/```[\s\S]*?(```|$)/g, " trecho de código. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // link markdown: le so o texto (antes das URLs soltas)
    .replace(/https?:\/\/\S+/g, " link ")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "") // titulos
    .replace(/^\s*>\s?/gm, "") // citacao
    .replace(/^\s*[-*•]\s+/gm, "") // marcadores de lista
    .replace(/(?<!\d)(\*{1,3}|~~)(\S(?:[^\n]*?\S)?)\1/g, "$2") // **negrito**, *italico*, ~~riscado~~ (nao apos digito: 3*4*5)
    .replace(/(^|\s)_(\S(?:[^\n]*?\S)?)_(?=\s|$|[.,;:!?])/g, "$1$2") // _italico_ (snake_case fica)
    .replace(/(\d)\s*[*×]\s*(?=\d)/g, "$1 vezes ") // lookahead: "3*4*5" nao perde o digito do meio
    .replace(/(\d)\s+\+\s+(?=\d)/g, "$1 mais ")
    .replace(/(\d)\s+-\s+(?=\d)/g, "$1 menos ")
    .replace(/\s=\s/g, " igual a ")
    .replace(/\|/g, ", ")
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\s*\n\s*/g, "\n")
    .trim()
}

const ABBREV = /\b(sr|sra|srta|dr|dra|prof|profa|etc|vs|obs|ex|av|pág|págs|cap|art|nº|n)\.$/i

/**
 * Corta o texto que chega aos pedacos (streaming) em frases completas, para comecar a falar
 * antes de a resposta terminar. Nao corta em "3.14", "Sr. Silva", "etc." nem em frases curtas demais.
 */
export class SentenceBuffer {
  private buf = ""
  constructor(private minLen = 24) {}

  push(chunk: string): string[] {
    this.buf += chunk
    return this.drain(false)
  }

  flush(): string[] {
    return this.drain(true)
  }

  private drain(final: boolean): string[] {
    const out: string[] = []
    for (;;) {
      const cut = this.findCut()
      if (cut < 0) break
      const sentence = this.buf.slice(0, cut).trim()
      this.buf = this.buf.slice(cut)
      if (sentence) out.push(sentence)
    }
    if (final) {
      const rest = this.buf.trim()
      this.buf = ""
      if (rest) out.push(rest)
    }
    return out
  }

  /** indice logo apos o fim da proxima frase completa, ou -1 */
  private findCut(): number {
    const s = this.buf
    for (let i = 0; i < s.length; i++) {
      const c = s[i] as string
      if (c === "\n") {
        if (s.slice(0, i).trim().length >= 1) return i + 1
        continue
      }
      if (!".!?…".includes(c)) continue
      let j = i
      while (j + 1 < s.length && ".!?…".includes(s[j + 1] as string)) j++
      const next = s[j + 1]
      if (next === undefined) return -1 // pode vir mais texto: espera
      if (!/\s/.test(next)) {
        i = j
        continue // "3.14", "site.com"
      }
      const head = s.slice(0, j + 1)
      if (c === "." && j === i && ABBREV.test(head.trimEnd())) {
        i = j
        continue
      }
      if (head.trim().length < this.minLen) {
        i = j
        continue // curta demais: junta com a proxima
      }
      return j + 1
    }
    return -1
  }
}
