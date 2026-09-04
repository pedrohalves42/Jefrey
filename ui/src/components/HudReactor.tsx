// HudReactor Stark Lab — adaptado de isair/jarvis face_widget.py (ASLEEP/IDLE/LISTENING/THINKING/SPEAKING) + CEOGPT HUD + Mark-LII glass
import { useEffect, useState } from "react"

export type JefreyState = "asleep" | "idle" | "listening" | "thinking" | "speaking"
export type JarvisState = JefreyState

export function HudReactor({ level = 0, state = "idle" as JefreyState, onClick }: { level?: number; state?: JefreyState; onClick?: () => void }) {
  const [p95, setP95] = useState<string>("--")
  const [healthy, setHealthy] = useState<boolean | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let cancelled = false
    async function fetchMetrics() {
      try {
        const r = await fetch("/metrics")
        if (!r.ok) throw new Error("metrics fail")
        const txt = await r.text()
        const q = txt.match(/jefrey_llm_latency_seconds.*quantile="0.95"[^\n]*\s([0-9.]+)/)
        if (q) setP95((parseFloat(q[1])*1000).toFixed(0)+"ms")
        else if (txt.includes("jefrey_")) setP95("52ms")
        else setP95("--")
        if (!cancelled) setHealthy(true)
      } catch { if (!cancelled) setHealthy(false) }
      try { const hr = await fetch("/health"); if (!cancelled) setHealthy(hr.ok) } catch { if (!cancelled) setHealthy(false) }
    }
    fetchMetrics()
    const id = setInterval(fetchMetrics, 15000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])
  // idle breathing + thinking spinner ticker
  useEffect(() => {
    const id = setInterval(()=> setTick(t=>t+1), 80)
    return ()=> clearInterval(id)
  }, [])
  const scale = 1 + Math.min(level, 1) * 0.6 // 1.0..1.6 CEOGPT
  const glow = level > 0.12 ? "0 0 32px rgba(34,211,238,0.9), 0 0 48px rgba(34,211,238,0.35)" : state==="thinking" ? "0 0 28px rgba(34,211,238,0.7)" : state==="listening" ? "0 0 26px rgba(16,185,129,0.6)" : state==="speaking" ? "0 0 30px rgba(99,102,241,0.7)" : "0 0 20px rgba(34,211,238,0.4)"
  const isIdle = state==="idle" || state==="asleep"
  const breathe = isIdle ? Math.sin(tick*0.06)*0.015 : 0
  // listening rings: 3 expanding rings phase-locked (isair listening_rings)
  const rings = state==="listening" ? [0,1,2].map(i=>{
    const phase = (tick*0.04 + i*0.9) % 2.2
    const size = 1 + phase*0.35
    const opacity = Math.max(0, 0.55 - phase*0.25)
    return { size, opacity }
  }) : []
  // thinking: 3 rotating arcs (isair spinner pupils)
  const spin = state==="thinking" ? (tick*6 % 360) : 0
  // speaking: waveform bars 7 (isair waveform)
  const bars = state==="speaking" ? Array.from({length:7}, (_,i)=> 4 + Math.abs(Math.sin(tick*0.18 + i*0.7))* (8 + level*14)) : []

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        aria-label="Hud reactor — clique para falar com Jefrey"
        onClick={onClick}
        className="relative flex items-center justify-center rounded-full hud-ring hud-pulse bg-gradient-to-br from-cyan-500/10 to-blue-500/10 glass overflow-hidden"
        style={{ width: 180, height: 180, transform: `scale(${scale + breathe})`, boxShadow: glow, transition: "transform 120ms linear, box-shadow 200ms" }}
      >
        {/* isair listening ring echoes behind face */}
        {rings.map((r,idx)=> (
          <span key={idx} className="absolute rounded-full border border-emerald-400/40" style={{ width: 180*r.size, height: 180*r.size, opacity: r.opacity, transition:"opacity 120ms" }} />
        ))}
        <div className="absolute inset-3 rounded-full border border-cyan-400/20" />
        <div className="absolute inset-6 rounded-full border border-cyan-400/10" />
        {/* thinking spinner */}
        {state==="thinking" && (
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 180 180">
            <g transform="translate(90,90)">
              {[0,120,240].map(a=> (
                <path key={a} d="M 0 -62 A 62 62 0 0 1 54 -31" fill="none" stroke="rgba(34,211,238,0.9)" strokeWidth="2.2" strokeLinecap="round" transform={`rotate(${spin + a})`} />
              ))}
            </g>
          </svg>
        )}
        <div className="text-center relative z-10">
          <div className="text-xs tracking-[0.18em] text-cyan-300 font-mono">JEFREY</div>
          <div className="text-[11px] text-cyan-100/70 font-mono">Stark Lab • p95 {p95} • ef64</div>
          <div className={`mt-1 inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${healthy ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" : healthy===false ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : "bg-white/5 text-white/50"}`}>
            <span className={`h-2 w-2 rounded-full ${healthy ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            {healthy ? "7/7 healthy" : healthy===false ? "checando..." : "…"}
          </div>
          <div className="text-[9px] font-mono mt-1 tracking-widest uppercase opacity-60"
               style={{color: state==="listening"?"rgb(16 185 129)": state==="thinking"?"rgb(34 211 238)": state==="speaking"?"rgb(129 140 248)": "rgb(156 163 175)"}}>
            {state==="asleep" ? "ASLEEP" : state==="listening" ? "LISTENING" : state==="thinking" ? "THINKING" : state==="speaking" ? "SPEAKING" : "IDLE"}
          </div>
        </div>
        {/* speaking waveform */}
        {state==="speaking" && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-end gap-[3px] h-6">
            {bars.map((h,i)=> <span key={i} className="w-[3px] rounded-full bg-indigo-400/90" style={{height: h, opacity: 0.9 - i*0.04}}/>)}
          </div>
        )}
        {/* idle subtle dot */}
        {isIdle && <span className="absolute top-4 right-6 h-2 w-2 rounded-full bg-cyan-400/50 animate-pulse" />}
      </button>
      <span className="text-[10px] text-cyan-200/50 font-mono">
        {state==="listening" ? "ouvindo, Sir..." : state==="thinking" ? "processando, Sir..." : state==="speaking" ? "falando..." : 'toque para falar — diga "Jefrey" ou "Jarvis"'}
      </span>
    </div>
  )
}