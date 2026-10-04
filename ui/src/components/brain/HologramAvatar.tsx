import { useEffect, useRef, useState } from "react"
import type { Appearance } from "@/lib/appearance"
import { AVATAR_EVENT, DEFAULT_AVATAR, loadAvatarImage } from "@/lib/avatarImage"
import { glitchBands, tintImageData } from "@/lib/holo"
import type { BrainState } from "./BrainScene"

const S = 512 // resolucao interna do canvas (a tela redimensiona)

function useAvatarSrc(): string {
  const [src, setSrc] = useState(() => loadAvatarImage() ?? DEFAULT_AVATAR)
  useEffect(() => {
    const refresh = () => setSrc(loadAvatarImage() ?? DEFAULT_AVATAR)
    window.addEventListener(AVATAR_EVENT, refresh)
    window.addEventListener("storage", refresh)
    return () => {
      window.removeEventListener(AVATAR_EVENT, refresh)
      window.removeEventListener("storage", refresh)
    }
  }, [])
  return src
}

function tinted(img: HTMLImageElement, hue: number, cut: number, invert: boolean): HTMLCanvasElement {
  const c = document.createElement("canvas")
  c.width = S
  c.height = S
  const ctx = c.getContext("2d", { willReadFrequently: true })
  if (!ctx) return c
  const iw = img.naturalWidth || 512
  const ih = img.naturalHeight || 512
  const k = Math.min(400 / iw, 400 / ih, 1.6)
  const w = iw * k
  const h = ih * k
  ctx.drawImage(img, (S - w) / 2, (S - h) / 2 + 10, w, h)
  const d = ctx.getImageData(0, 0, S, S)
  tintImageData(d.data, hue, cut, invert)
  ctx.putImageData(d, 0, 0)
  return c
}

function rings(ctx: CanvasRenderingContext2D, t: number, hue: number, intensity: number, pulse: number) {
  ctx.save()
  ctx.translate(S / 2, S / 2)
  const specs: [number, number, number[], number][] = [
    [238, 1.4, [3, 14], 1],
    [214, 1.0, [60, 18], -1.6],
    [190, 1.2, [2, 6], 2.2],
  ]
  for (const [r, w, dash, dir] of specs) {
    ctx.beginPath()
    ctx.setLineDash(dash)
    ctx.lineDashOffset = -t * 40 * dir
    ctx.lineWidth = w
    ctx.strokeStyle = `hsla(${hue},95%,65%,${0.18 + 0.42 * intensity})`
    ctx.arc(0, 0, r + pulse, 0, Math.PI * 2)
    ctx.stroke()
  }
  ctx.restore()
}

export default function HologramAvatar({ state, level, appearance }: { state: BrainState; level: number; appearance: Appearance }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const live = useRef({ state, level, appearance })
  live.current = { state, level, appearance }
  const src = useAvatarSrc()
  const [img, setImg] = useState<HTMLImageElement | null>(null)

  useEffect(() => {
    let alive = true
    const el = new Image()
    el.onload = () => alive && setImg(el)
    el.onerror = () => {
      if (!alive) return
      if (src !== DEFAULT_AVATAR) {
        const fb = new Image()
        fb.onload = () => alive && setImg(fb)
        fb.src = DEFAULT_AVATAR // imagem do usuario quebrada: volta para a silhueta
      }
    }
    el.src = src
    return () => {
      alive = false
    }
  }, [src])

  const a = appearance
  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext("2d")
    if (!img || !canvas || !ctx) return
    const frame = document.createElement("canvas")
    frame.width = S
    frame.height = S
    const f = frame.getContext("2d")
    if (!f) return
    const cache = new Map<string, { base: HTMLCanvasElement; l: HTMLCanvasElement; r: HTMLCanvasElement }>()
    const variants = (hue: number, cut: number, inv: boolean) => {
      const key = `${hue}|${cut}|${inv}`
      let v = cache.get(key)
      if (!v) {
        if (cache.size > 6) cache.clear()
        v = { base: tinted(img, hue, cut, inv), l: tinted(img, hue - 40, cut, inv), r: tinted(img, hue + 40, cut, inv) }
        cache.set(key, v)
      }
      return v
    }

    const draw = (t: number) => {
      const { state: st, level: lv, appearance: ap } = live.current
      const hue = st === "approval" ? 38 : ap.hue
      const v = variants(hue, ap.holoCut, ap.holoInvert)
      ctx.clearRect(0, 0, S, S)
      const speed = st === "thinking" ? 1.6 : st === "responding" ? 1.0 : st === "listening" ? 0.6 : 0.25
      rings(ctx, ap.motion ? t * speed : 0, hue, ap.intensity, st === "listening" ? lv * 16 : 0)

      f.clearRect(0, 0, S, S)
      const floatY = ap.motion ? Math.sin(t * 1.2) * 6 : 0
      const sc = 1 + (st === "responding" ? lv * 0.05 : 0) + (ap.motion ? Math.sin(t * 0.8) * 0.004 : 0)
      const flick = ap.motion ? 0.92 + 0.08 * Math.sin(t * 37) * Math.sin(t * 13) : 1
      f.globalCompositeOperation = "source-over"
      f.globalAlpha = flick * (0.6 + 0.4 * ap.intensity)
      f.save()
      f.translate(S / 2, S / 2 + floatY)
      f.scale(sc, sc)
      f.drawImage(v.base, -S / 2, -S / 2)
      if (ap.holoGlitch > 0) {
        f.globalCompositeOperation = "lighter"
        f.globalAlpha = 0.3 * ap.holoGlitch
        const off = 2 + 4 * ap.holoGlitch
        f.drawImage(v.l, -S / 2 - off, -S / 2)
        f.drawImage(v.r, -S / 2 + off, -S / 2)
      }
      f.restore()
      f.globalAlpha = 1
      if (ap.holoScan > 0) {
        f.globalCompositeOperation = "destination-out"
        f.fillStyle = `rgba(0,0,0,${0.55 * ap.holoScan})`
        for (let y = ap.motion ? (t * 18) % 4 : 0; y < S; y += 4) f.fillRect(0, y, S, 1.6)
      }
      f.globalCompositeOperation = "source-atop"
      const sy = (((ap.motion ? t : 0) * (st === "thinking" ? 0.9 : 0.35)) % 1.3 - 0.15) * S
      const g = f.createLinearGradient(0, sy - 36, 0, sy + 36)
      g.addColorStop(0, "rgba(255,255,255,0)")
      g.addColorStop(0.5, `hsla(${hue},100%,85%,${0.25 + 0.4 * ap.intensity})`)
      g.addColorStop(1, "rgba(255,255,255,0)")
      f.fillStyle = g
      f.fillRect(0, sy - 36, S, 72)
      f.globalCompositeOperation = "source-over"

      ctx.save()
      ctx.shadowColor = `hsla(${hue},100%,60%,${0.3 + 0.5 * ap.intensity})`
      ctx.shadowBlur = 16 + 30 * ap.intensity
      ctx.drawImage(frame, 0, 0)
      ctx.restore()
      if (ap.motion) {
        for (const b of glitchBands(Math.random, ap.holoGlitch, S)) ctx.drawImage(frame, 0, b.y, S, b.h, b.dx, b.y, S, b.h)
        ctx.fillStyle = `hsla(${hue},100%,80%,0.55)`
        for (let i = 0; i < 22; i++) {
          const x = (i * 97 + 31) % S
          const y = S - ((t * (14 + (i % 5) * 4) + i * 53) % S)
          ctx.fillRect(x, y, 1.5, 1.5)
        }
      }
    }

    let raf = 0
    let last = 0
    let stop = false
    const loop = (ts: number) => {
      if (stop) return
      raf = requestAnimationFrame(loop)
      if (document.hidden || ts - last < 33) return // ~30 quadros/s e pausa com a aba escondida
      last = ts
      draw(ts / 1000)
    }
    if (a.motion) raf = requestAnimationFrame(loop)
    else draw(0)
    return () => {
      stop = true
      cancelAnimationFrame(raf)
    }
  }, [img, a.motion, a.hue, a.holoCut, a.holoInvert, a.holoScan, a.holoGlitch, a.intensity])

  function tilt(e: React.PointerEvent<HTMLDivElement>) {
    const el = wrapRef.current
    if (!el || !a.motion) return
    const r = el.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width - 0.5) * 2
    const y = ((e.clientY - r.top) / r.height - 0.5) * 2
    el.style.transform = `perspective(900px) rotateY(${(x * 7).toFixed(2)}deg) rotateX(${(-y * 5).toFixed(2)}deg)`
  }

  return (
    <div
      className="flex h-full w-full items-center justify-center"
      onPointerMove={tilt}
      onPointerLeave={() => wrapRef.current && (wrapRef.current.style.transform = "")}
    >
      <div ref={wrapRef} className="h-full max-h-full transition-transform duration-200 ease-out" style={{ aspectRatio: "1 / 1" }}>
        <canvas ref={canvasRef} width={S} height={S} className="h-full w-full" aria-hidden="true" />
      </div>
    </div>
  )
}
