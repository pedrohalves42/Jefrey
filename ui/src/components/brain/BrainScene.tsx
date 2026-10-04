import { useEffect, useRef } from "react"
import * as THREE from "three"
import type { Appearance } from "@/lib/appearance"
import { buildGraph, generatePoints, neuronCount } from "./geometry"

export type BrainState = "idle" | "listening" | "thinking" | "responding" | "approval"

type Props = {
  state: BrainState
  /** nivel de audio/energia 0-1 (voz) */
  level?: number
  appearance: Appearance
  onUnavailable?: () => void
  onSlow?: () => void
}

const APPROVAL_HUE = 38

function hueFor(state: BrainState, base: number): number {
  return state === "approval" ? APPROVAL_HUE : base
}

/**
 * Cerebro/orbe/reator 3D. Neuronios (pontos) ligados por sinapses (linhas); os disparos
 * viajam de vizinho em vizinho e o ritmo muda conforme o estado do assistente.
 */
export default function BrainScene({ state, level = 0, appearance, onUnavailable, onSlow }: Props) {
  const host = useRef<HTMLDivElement>(null)
  // valores lidos a cada frame sem recriar a cena
  const live = useRef({ state, level, appearance })
  live.current = { state, level, appearance }

  const { shape, particles } = appearance

  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" })
    } catch {
      onUnavailable?.()
      return
    }
    renderer.setClearColor(0x000000, 0)
    let pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
    renderer.setPixelRatio(pixelRatio)
    el.appendChild(renderer.domElement)
    renderer.domElement.style.display = "block"
    renderer.domElement.style.touchAction = "none"

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 20)
    camera.position.set(0, 0, 3.2)
    const group = new THREE.Group()
    scene.add(group)

    // ---- geometria ----
    const n = neuronCount(particles)
    const pts = generatePoints(shape, n)
    const graph = buildGraph(pts, shape === "reactor" ? 2 : 3)

    const act = new Float32Array(n) // ativacao 0-1 de cada neuronio
    const nColors = new Float32Array(n * 3)
    const pGeo = new THREE.BufferGeometry()
    pGeo.setAttribute("position", new THREE.BufferAttribute(pts, 3))
    pGeo.setAttribute("color", new THREE.BufferAttribute(nColors, 3))
    const pMat = new THREE.PointsMaterial({
      size: 0.034,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    })
    const points = new THREE.Points(pGeo, pMat)
    group.add(points)

    const e = graph.edges
    const linePos = new Float32Array(e.length * 3)
    for (let i = 0; i < e.length; i++) {
      const idx = e[i] as number
      linePos[i * 3] = pts[idx * 3] as number
      linePos[i * 3 + 1] = pts[idx * 3 + 1] as number
      linePos[i * 3 + 2] = pts[idx * 3 + 2] as number
    }
    const lineColors = new Float32Array(e.length * 3)
    const lGeo = new THREE.BufferGeometry()
    lGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3))
    lGeo.setAttribute("color", new THREE.BufferAttribute(lineColors, 3))
    const lMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    group.add(new THREE.LineSegments(lGeo, lMat))

    // ---- tamanho ----
    const resize = () => {
      const w = Math.max(1, el.clientWidth)
      const h = Math.max(1, el.clientHeight)
      renderer.setSize(w, h, false)
      renderer.domElement.style.width = "100%"
      renderer.domElement.style.height = "100%"
      camera.aspect = w / h
      // em janelas estreitas afasta a camera para a forma caber inteira na largura
      camera.position.z = Math.max(3.2, 2.9 / camera.aspect)
      camera.updateProjectionMatrix()
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    // ---- arrastar para girar ----
    let dragging = false
    let lastX = 0
    let lastY = 0
    let yaw = 0
    let pitch = 0
    const down = (ev: PointerEvent) => {
      dragging = true
      lastX = ev.clientX
      lastY = ev.clientY
      renderer.domElement.setPointerCapture(ev.pointerId)
    }
    const move = (ev: PointerEvent) => {
      if (!dragging) return
      yaw += (ev.clientX - lastX) * 0.01
      pitch = Math.max(-1.1, Math.min(1.1, pitch + (ev.clientY - lastY) * 0.01))
      lastX = ev.clientX
      lastY = ev.clientY
      if (!live.current.appearance.motion) draw()
    }
    const up = () => {
      dragging = false
    }
    renderer.domElement.addEventListener("pointerdown", down)
    renderer.domElement.addEventListener("pointermove", move)
    renderer.domElement.addEventListener("pointerup", up)
    renderer.domElement.addEventListener("pointercancel", up)

    // ---- animacao ----
    const queue: { i: number; at: number }[] = []
    const color = new THREE.Color()
    const white = new THREE.Color(1, 1, 1)
    let last = performance.now()
    let spin = 0
    let raf = 0
    let slowTime = 0
    let reportedSlow = false
    let running = false

    const fire = (i: number, strength = 1) => {
      act[i] = Math.max(act[i] as number, strength)
      const nb = graph.neighbors[i] ?? []
      for (const j of nb) if (Math.random() < 0.55) queue.push({ i: j, at: performance.now() + 90 + Math.random() * 110 })
    }

    const rates: Record<BrainState, number> = { idle: 0.02, listening: 0.1, thinking: 0.4, responding: 0.22, approval: 0.08 }

    const step = (now: number, dt: number) => {
      const { state: st, level: lv, appearance: ap } = live.current
      const motion = ap.motion
      if (motion) {
        const speed = st === "thinking" ? 0.5 : st === "idle" ? 0.12 : 0.25
        spin += dt * speed
      }
      // novos disparos
      let rate = rates[st] * (0.4 + ap.intensity)
      if (st === "responding") rate *= 0.6 + 0.4 * Math.abs(Math.sin(now / 160))
      if (st === "listening") rate *= 0.5 + lv * 2
      const tries = motion ? Math.max(1, Math.round(n / 120)) : 0
      for (let t = 0; t < tries; t++) {
        if (Math.random() < rate) {
          let i = Math.floor(Math.random() * n)
          if (st === "listening") {
            // prefere a periferia: reage como se "ouvisse" de fora
            for (let k = 0; k < 4; k++) {
              const c = Math.floor(Math.random() * n)
              if (Math.abs(pts[c * 3] as number) + Math.abs(pts[c * 3 + 2] as number) > Math.abs(pts[i * 3] as number) + Math.abs(pts[i * 3 + 2] as number)) i = c
            }
          }
          fire(i)
        }
      }
      // propaga a fila
      for (let q = queue.length - 1; q >= 0; q--) {
        const item = queue[q]!
        if (now >= item.at) {
          queue.splice(q, 1)
          if ((act[item.i] as number) < 0.5) fire(item.i, 0.85)
        }
      }
      if (queue.length > 4000) queue.length = 0
      // decaimento + cores
      const decay = Math.pow(0.0025, dt) // ~ cai a 0.25% em 1s
      const baseHue = hueFor(st, ap.hue) / 360
      const bright = 0.25 + 0.75 * ap.intensity
      for (let i = 0; i < n; i++) {
        const a = (act[i] as number) * decay
        act[i] = a < 0.01 ? 0 : a
        color.setHSL(baseHue, 0.9, 0.35 + 0.2 * ap.intensity)
        color.lerp(white, a * 0.7)
        const f = bright * (0.35 + 0.65 * a)
        nColors[i * 3] = color.r * f * 1.6
        nColors[i * 3 + 1] = color.g * f * 1.6
        nColors[i * 3 + 2] = color.b * f * 1.6
      }
      for (let i = 0; i < e.length; i++) {
        const idx = e[i] as number
        const a = act[idx] as number
        color.setHSL(baseHue, 0.9, 0.3)
        color.lerp(white, a * 0.5)
        const f = bright * (0.08 + 0.7 * a)
        lineColors[i * 3] = color.r * f
        lineColors[i * 3 + 1] = color.g * f
        lineColors[i * 3 + 2] = color.b * f
      }
      ;(pGeo.getAttribute("color") as THREE.BufferAttribute).needsUpdate = true
      ;(lGeo.getAttribute("color") as THREE.BufferAttribute).needsUpdate = true
      pMat.size = 0.03 + 0.012 * ap.intensity
    }

    const draw = () => {
      if (shape === "reactor") {
        group.rotation.set(0.35 * Math.sin(spin * 0.7) + pitch, yaw, spin)
      } else {
        group.rotation.set(pitch, spin + yaw, 0)
      }
      renderer.render(scene, camera)
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now
      step(now, dt)
      draw()
      // se ficar abaixo de ~24 fps por 3 s: reduz resolucao e avisa
      slowTime = dt > 1 / 24 ? slowTime + dt : Math.max(0, slowTime - dt)
      if (slowTime > 3) {
        slowTime = 0
        if (pixelRatio > 1) {
          pixelRatio = 1
          renderer.setPixelRatio(1)
          resize()
        } else if (!reportedSlow) {
          reportedSlow = true
          onSlow?.()
        }
      }
    }

    const start = () => {
      if (running || !live.current.appearance.motion) return
      running = true
      last = performance.now()
      raf = requestAnimationFrame(frame)
    }
    const stop = () => {
      running = false
      cancelAnimationFrame(raf)
    }
    const onVis = () => (document.hidden ? stop() : start())
    document.addEventListener("visibilitychange", onVis)

    if (live.current.appearance.motion) start()
    else {
      // sem animacao: um quadro estatico com alguns neuronios acesos
      for (let i = 0; i < n; i += 9) act[i] = 0.7
      step(performance.now(), 0.0001)
      draw()
    }

    // reage a ligar/desligar animacao sem recriar a cena
    const poll = window.setInterval(() => {
      if (live.current.appearance.motion && !running) start()
      else if (!live.current.appearance.motion && running) {
        stop()
        draw()
      }
    }, 400)

    return () => {
      stop()
      window.clearInterval(poll)
      document.removeEventListener("visibilitychange", onVis)
      ro.disconnect()
      renderer.domElement.removeEventListener("pointerdown", down)
      renderer.domElement.removeEventListener("pointermove", move)
      renderer.domElement.removeEventListener("pointerup", up)
      renderer.domElement.removeEventListener("pointercancel", up)
      pGeo.dispose()
      lGeo.dispose()
      pMat.dispose()
      lMat.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
    // a cena e recriada apenas quando a forma ou a quantidade de neuronios muda
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shape, particles])

  return <div ref={host} className="h-full w-full" aria-hidden="true" />
}
