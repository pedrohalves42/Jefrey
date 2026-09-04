// F6-2 ThemeWheel — hue wheel 0-360 (CEOGPT styles.css?v=6)
import { useEffect, useState } from "react"

export function ThemeWheel() {
  const [hue, setHue] = useState<number>(() => {
    try { const v = localStorage.getItem("jefrey_hue"); return v ? parseInt(v,10) : 191 } catch { return 191 }
  })
  useEffect(() => {
    try {
      document.documentElement.style.setProperty("--hue", String(hue))
      localStorage.setItem("jefrey_hue", String(hue))
    } catch {}
  }, [hue])
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-muted-foreground">Cor</label>
      <input
        aria-label="hue wheel"
        type="range" min={0} max={360} value={hue}
        onChange={(e) => setHue(parseInt(e.target.value,10))}
        className="h-2 w-24 accent-cyan-500"
        style={{ background: `linear-gradient(to right, hsl(0 90% 60%), hsl(60 90% 60%), hsl(120 90% 60%), hsl(180 90% 60%), hsl(240 90% 60%), hsl(300 90% 60%), hsl(360 90% 60%))` }}
      />
      <span className="text-xs font-mono w-8">{hue}°</span>
      <span className="h-4 w-4 rounded-full border" style={{ background: `hsl(${hue} 90% 60%)` }} />
    </div>
  )
}
