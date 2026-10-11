import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { getLearned, newFacts } from "@/lib/learning"

/** Depois de cada conversa, mostra o que o Jefrey acabou de APRENDER sobre a pessoa (aprende entre conversas, e agora ela ve). */
export default function LearnedToast({ streaming }: { streaming: boolean }) {
  const known = useRef<Set<string> | null>(null)
  const was = useRef(false)
  const [text, setText] = useState("")

  useEffect(() => {
    let alive = true
    void getLearned().then(r => {
      if (alive) known.current = new Set((r.data?.facts ?? []).map(f => f.id))
    })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (was.current && !streaming && known.current) {
      const t = window.setTimeout(() => {
        void getLearned().then(r => {
          const fresh = newFacts(known.current ?? new Set(), r.data?.facts ?? [])
          if (!fresh.length) return
          fresh.forEach(f => known.current?.add(f.id))
          setText(fresh.slice(0, 2).map(f => f.text).join(" · "))
          window.setTimeout(() => setText(""), 9000)
        })
      }, 4500) // o aprendizado roda em segundo plano logo depois da resposta
      was.current = streaming
      return () => window.clearTimeout(t)
    }
    was.current = streaming
  }, [streaming])

  if (!text) return null
  return (
    <p role="status" className="jf-glass max-w-xl rounded-full px-4 py-1.5 text-center text-sm text-white/90">
      🧠 <span className="jf-accent">Aprendi:</span> {text} <Link to="/aprendi" className="ml-1 text-xs text-white/55 underline">ver tudo</Link>
    </p>
  )
}
