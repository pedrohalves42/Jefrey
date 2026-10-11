import { useEffect, useRef, useState, type ReactNode } from "react"
import type { Activity } from "@/lib/briefing"
import type { Message } from "@/lib/chat"
import { brainLine, buildLog, fmtUptime, gauges, getTelemetry, logTime, waveBars, type Telemetry } from "@/lib/hud"

function Panel({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`jf-hudpanel jf-glass ${className}`} aria-label={title}>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-[hsl(var(--hue)_55%_72%)]">{title}</h3>
      {children}
    </section>
  )
}

/** Onda de voz: nivel real do microfone, ou onda suave enquanto o Jefrey fala. */
export function Wave({ level, speaking, className = "" }: { level: number; speaking: boolean; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const live = useRef({ level, speaking })
  live.current = { level, speaking }
  useEffect(() => {
    const cv = ref.current
    const ctx = cv?.getContext("2d")
    if (!cv || !ctx) return
    let raf = 0
    const draw = (t: number) => {
      const w = cv.width
      const h = cv.height
      ctx.clearRect(0, 0, w, h)
      const hue = getComputedStyle(document.documentElement).getPropertyValue("--hue").trim() || "191"
      ctx.fillStyle = `hsl(${hue} 90% 62%)`
      const bars = waveBars(64, live.current.level, live.current.speaking, t)
      const bw = w / bars.length
      bars.forEach((v, i) => {
        const bh = Math.max(2, v * h)
        ctx.globalAlpha = 0.3 + 0.7 * v
        ctx.fillRect(i * bw + 1, (h - bh) / 2, bw - 2, bh)
      })
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={ref} width={640} height={40} className={`h-8 w-full ${className}`} aria-hidden="true" />
}

/** Paineis pequenos sobre o avatar: medidores reais (esquerda) e registro de atividade (direita). So em telas largas. */
export function HudOverlay({ messages, activity }: { messages: Message[]; activity: Activity | null }) {
  const [tele, setTele] = useState<Telemetry | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      if (document.hidden) return
      const t = await getTelemetry()
      if (alive) setTele(t)
    }
    void tick()
    const id = window.setInterval(() => void tick(), 5000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])
  const log = buildLog(messages, activity, Date.now(), 6)
  return (
    <>
      <Panel title="Registro" className="pointer-events-none absolute bottom-3 left-3 z-10 hidden w-56 2xl:block">
        {log.length === 0 ? (
          <p className="text-xs text-white/50">Tudo quieto.</p>
        ) : (
          <ul className="space-y-1" aria-live="polite">
            {log.map((l, i) => (
              <li key={i} className={`text-xs leading-snug ${l.tone === "ok" ? "text-emerald-200" : l.tone === "bad" ? "text-red-300" : l.tone === "warn" ? "text-amber-200" : "text-white/70"}`}>
                <span className="mr-1.5 tabular-nums text-white/35">{logTime(l.at)}</span>
                {l.text}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  )
}
