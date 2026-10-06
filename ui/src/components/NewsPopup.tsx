import { useEffect, useState } from "react"
import { getTodayCached, type NewsItem } from "@/lib/today"

const OFF_KEY = "jefrey_news_off"
const SHOW_MS = 12000
const GAP_MS = 6000

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function offToday(): boolean {
  try {
    return localStorage.getItem(OFF_KEY) === today()
  } catch {
    return false
  }
}

/** Cartao de noticias que aparece, troca de manchete sozinho e some um instante, na tela principal. Primeiro os seus assuntos. */
export default function NewsPopup() {
  const [items, setItems] = useState<NewsItem[]>([])
  const [i, setI] = useState(0)
  const [visible, setVisible] = useState(false)
  const [off, setOff] = useState(offToday)

  useEffect(() => {
    let alive = true
    const load = async () => {
      const r = await getTodayCached()
      if (!alive || !r.data) return
      const s = r.data.sections
      setItems((s.foryou.items.length ? s.foryou.items : s.news.items).slice(0, 10))
    }
    void load()
    const id = window.setInterval(() => void load(), 10 * 60 * 1000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  useEffect(() => {
    if (off || !items.length) return
    let t: number
    const cycle = (show: boolean) => {
      setVisible(show)
      if (show) {
        t = window.setTimeout(() => cycle(false), SHOW_MS)
      } else {
        t = window.setTimeout(() => {
          setI(x => (x + 1) % items.length)
          cycle(true)
        }, GAP_MS)
      }
    }
    t = window.setTimeout(() => cycle(true), 4000) // espera a tela assentar antes da primeira
    return () => window.clearTimeout(t)
  }, [off, items.length])

  if (off || !items.length) return null
  const n = items[i % items.length]
  if (!n) return null
  return (
    <div
      className={`pointer-events-none absolute inset-x-0 bottom-9 z-20 flex justify-center px-3 transition-all duration-500 ${visible ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"}`}
      aria-live="polite"
    >
      <div className="jf-glass pointer-events-auto flex max-w-xl items-start gap-3 rounded-xl border border-cyan-300/30 px-4 py-2.5">
        <span className="mt-0.5 text-lg" aria-hidden="true">📰</span>
        <div className="min-w-0">
          <p className="text-xs text-cyan-200">{n.topic ?? "Agora nas notícias"}</p>
          <a href={n.link} target="_blank" rel="noopener noreferrer" tabIndex={visible ? 0 : -1} className="jf-focus line-clamp-2 text-sm leading-snug text-white hover:underline">{n.title}</a>
        </div>
        <button
          type="button"
          tabIndex={visible ? 0 : -1}
          aria-label="Não mostrar notícias hoje"
          title="Não mostrar notícias hoje"
          onClick={() => {
            try {
              localStorage.setItem(OFF_KEY, today())
            } catch {
              /* sem armazenamento: some so ate recarregar */
            }
            setOff(true)
          }}
          className="jf-focus -mr-1 shrink-0 rounded px-1.5 text-white/50 hover:text-white"
        >
          ×
        </button>
      </div>
    </div>
  )
}
