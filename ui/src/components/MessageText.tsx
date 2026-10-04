import { useState } from "react"

type Part = { kind: "text" | "code"; text: string; lang?: string }

/** Separa blocos ```cercados``` do texto comum. Nunca usa innerHTML: React escapa tudo. */
export function splitParts(src: string): Part[] {
  const parts: Part[] = []
  const re = /```([\w+-]*)\n?([\s\S]*?)```/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) parts.push({ kind: "text", text: src.slice(last, m.index) })
    parts.push({ kind: "code", text: (m[2] ?? "").replace(/\n$/, ""), lang: m[1] || undefined })
    last = m.index + m[0].length
  }
  if (last < src.length) parts.push({ kind: "text", text: src.slice(last) })
  return parts
}

function CodeBlock({ text, lang }: { text: string; lang?: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* sem permissao de area de transferencia */
    }
  }
  return (
    <div className="my-2 overflow-hidden rounded-lg border border-white/10 bg-black/40">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1 text-xs text-white/50">
        <span>{lang || "código"}</span>
        <button type="button" onClick={copy} className="jf-focus rounded px-1 hover:text-white">
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-sm leading-relaxed">
        <code>{text}</code>
      </pre>
    </div>
  )
}

export function MessageText({ text }: { text: string }) {
  return (
    <>
      {splitParts(text).map((p, i) =>
        p.kind === "code" ? (
          <CodeBlock key={i} text={p.text} lang={p.lang} />
        ) : (
          <span key={i} className="whitespace-pre-wrap break-words">
            {p.text}
          </span>
        ),
      )}
    </>
  )
}
