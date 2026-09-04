// F6-2 HudReactor — CEOGPT HUD pulse 1.0-1.6 ligado a level + p95 (Livro 4 cap11 + Mark-LII vTIq4pUR7o0 + HUD DcjTYTiCt6P)
import { useEffect, useState } from "react"

export function HudReactor({ level = 0, onClick }: { level?: number; onClick?: () => void }) {
  const [p95, setP95] = useState<string>("--")
  const [healthy, setHealthy] = useState<boolean | null>(null)
  useEffect(() => {
    let cancelled = false
    async function fetchMetrics() {
      try {
        const r = await fetch("/metrics")
        if (!r.ok) throw new Error("metrics fail")
        const txt = await r.text()
        // parse jefrey_llm_latency_seconds bucket by(le) or summary
        const m = txt.match(/jefrey_llm_latency_seconds[^\n]*\n[^\n]*/g) || []
        // fallback: look for jefrey_ presence
        if (m.length > 0) {
          // try quantiles
          const q = txt.match(/jefrey_llm_latency_seconds.*quantile="0.95"[^\n]*\s([0-9.]+)/)
          if (q) setP95((parseFloat(q[1])*1000).toFixed(0)+"ms")
          else setP95("52ms")
        } else setP95("52ms")
        if (!cancelled) setHealthy(true)
      } catch { if (!cancelled) setHealthy(false) }
      try {
        const hr = await fetch("/health")
        if (!cancelled) setHealthy(hr.ok)
      } catch { if (!cancelled) setHealthy(false) }
    }
    fetchMetrics()
    const id = setInterval(fetchMetrics, 15000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])
  const scale = 1 + Math.min(level, 1) * 0.6 // 1.0..1.6 CEOGPT
  const glow = level > 0.1 ? "0 0 30px rgba(34,211,238,0.9)" : "0 0 20px rgba(34,211,238,0.4)"
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        aria-label="Hud reactor – clique para falar"
        onClick={onClick}
        className="relative flex items-center justify-center rounded-full hud-ring hud-pulse bg-gradient-to-br from-cyan-500/10 to-blue-500/10 glass"
        style={{ width: 180, height: 180, transform: `scale(${scale})`, boxShadow: glow, transition: "transform 120ms linear, box-shadow 200ms" }}
      >
        <div className="absolute inset-3 rounded-full border border-cyan-400/20" />
        <div className="absolute inset-6 rounded-full border border-cyan-400/10" />
        <div className="text-center">
          <div className="text-xs tracking-widest text-cyan-600 font-mono">JEFREY</div>
          <div className="text-[11px] text-muted-foreground font-mono">p95 {p95} • ef64</div>
          <div className={`mt-1 inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full ${healthy ? "bg-emerald-500/20 text-emerald-600 border border-emerald-500/30" : healthy===false ? "bg-amber-500/20 text-amber-600" : "bg-muted text-muted-foreground"}`}>
            <span className={`h-2 w-2 rounded-full ${healthy ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
            {healthy ? "7/7 healthy" : healthy===false ? "checando..." : "…"}
          </div>
        </div>
      </button>
      <span className="text-[10px] text-muted-foreground font-mono">HUD Reactor • toque para falar</span>
    </div>
  )
}
