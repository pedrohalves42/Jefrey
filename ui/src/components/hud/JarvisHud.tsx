import { useEffect, useRef, useState, type ReactNode } from "react"
import type { Activity } from "@/lib/briefing"
import type { Message } from "@/lib/chat"
import { brainLine, buildLog, fmtUptime, gauges, getTelemetry, logTime, waveBars, type Telemetry } from "@/lib/hud"

function Panel({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`jf-hudpanel ${className}`} aria-label={title}>
      <h3 className="mb-2 text-[11px] uppercase tracking-[0.25em] text-[hsl(var(--hue)_80%_72%)]">{title}</h3>
      {children}
    </section>
  )
}

function Wave({ level, speaking }: { level: number; speaking: boolean }) {
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
      const bars = waveBars(48, live.current.level, live.current.speaking, t)
      const bw = w / bars.length
      bars.forEach((v, i) => {
        const bh = Math.max(2, v * h)
        ctx.globalAlpha = 0.35 + 0.65 * v
        ctx.fillRect(i * bw + 1, (h - bh) / 2, bw - 2, bh)
      })
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={ref} width={480} height={36} className="h-9 w-full" aria-hidden="true" />
}

/** Painel estilo Jarvis: medidores reais a esquerda, a esfera no centro, registro de atividade a direita e a onda de voz embaixo. */
export default function JarvisHud({ children, messages, activity, level, speaking }: {
  children: ReactNode
  messages: Message[]
  activity: Activity | null
  level: number
  speaking: boolean
}) {
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
  const log = buildLog(messages, activity)
  return (
    <div className="grid gap-2 lg:grid-cols-[210px_minmax(0,1fr)_250px]" data-testid="jarvis-hud">
      <Panel title="Sistema" className="hidden lg:block">
        <ul className="space-y-3">
          {gauges(tele).map(g => (
            <li key={g.label}>
              <div className="flex justify-between text-xs text-white/70"><span>{g.label}</span><span className={g.warn ? "text-amber-300" : ""}>{g.text}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded bg-white/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={g.value ?? 0} aria-label={g.label}>
                <div className={`h-full ${g.warn ? "bg-amber-400" : "bg-[hsl(var(--hue)_90%_60%)]"}`} style={{ width: `${g.value ?? 0}%` }} />
              </div>
            </li>
          ))}
          <li className="text-xs text-white/70">Cérebro<span className="block text-sm text-white">{brainLine(tele)}</span></li>
          <li className="text-xs text-white/70">Ligado há<span className="block text-sm text-white">{tele ? fmtUptime(tele.uptime_s) : "—"}</span></li>
        </ul>
      </Panel>

      <div className="min-w-0">
        {children}
        <div className="mt-1 px-2"><Wave level={level} speaking={speaking} /></div>
      </div>

      <Panel title="Registro" className="hidden lg:block">
        {log.length === 0 ? (
          <p className="text-xs text-white/55">Tudo quieto. Quando eu fizer ou lembrar algo, aparece aqui.</p>
        ) : (
          <ul className="space-y-1.5" aria-live="polite">
            {log.map((l, i) => (
              <li key={i} className={`text-xs leading-snug ${l.tone === "ok" ? "text-emerald-200" : l.tone === "bad" ? "text-red-300" : l.tone === "warn" ? "text-amber-200" : "text-white/75"}`}>
                <span className="mr-1.5 tabular-nums text-white/40">{logTime(l.at)}</span>
                {l.text}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}
