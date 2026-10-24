import { useEffect, useRef } from "react"
import * as THREE from "three"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js"
import { MeshSurfaceSampler } from "three/examples/jsm/math/MeshSurfaceSampler.js"
import type { Appearance } from "@/lib/appearance"
import type { BrainState } from "./BrainScene"

/**
 * Holograma de uma cabeca humana REAL (escaneamento 3D de Lee Perry-Smith, CC BY 3.0, ver Ajuda > Creditos),
 * desenhada so com pontos e linhas de luz: bordas mais brilhantes, faixa de varredura, linhas finas, tremor raro,
 * pescoco que se dissolve em luz, respiracao e boca que acompanha a voz.
 */
type Props = { state: BrainState; level?: number; appearance: Appearance; onUnavailable?: () => void; points?: number; wire?: boolean }

export const HEAD_MODEL_URL = "/models/LeePerrySmith.glb"
const POINTS = 38_000
const APPROVAL_HUE = 38

const VERT = /* glsl */ `
uniform float uTime; uniform float uMouth; uniform float uSize; uniform float uPixel; uniform float uMinY; uniform float uScanSpeed;
attribute float aSeed;
varying float vFres; varying float vScan; varying float vFade; varying float vLines; varying float vSeed; varying float vLit;
void main() {
  vec3 p = position;
  // boca: o queixo desce e os labios abrem com a voz
  float jaw = smoothstep(-0.10, -0.55, p.y - 0.18) * step(0.0, p.z + 0.05);
  float lip = exp(-pow((p.y - 0.12) * 9.0, 2.0)) * step(0.05, p.z) * (1.0 - smoothstep(0.30, 0.55, abs(p.x)));
  p.y -= uMouth * (0.05 * jaw + 0.035 * lip);
  p.z += uMouth * 0.012 * lip;
  p.y += sin(uTime * 1.3) * 0.004; // respiracao
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vec3 n = normalize(normalMatrix * normal);
  vFres = pow(1.0 - abs(n.z), 1.6);
  vLit = abs(dot(n, normalize(vec3(-0.45, 0.55, 0.75)))); // luz de cima e da esquerda: olhos, nariz e boca aparecem
  float band = mod(uTime * uScanSpeed, 1.0) * 2.6 - 1.3;
  vScan = exp(-pow((p.y - band) * 5.5, 2.0));
  vFade = smoothstep(uMinY, uMinY + 0.55, p.y);
  vLines = 0.90 + 0.10 * sin(p.y * 170.0 - uTime * 2.4);
  vSeed = aSeed;
  gl_PointSize = uSize * uPixel * (0.6 + 0.8 * aSeed) / max(0.4, -mv.z);
  gl_Position = projectionMatrix * mv;
}`

const FRAG = /* glsl */ `
uniform vec3 uColor; uniform float uGain; uniform float uTime;
varying float vFres; varying float vScan; varying float vFade; varying float vLines; varying float vSeed; varying float vLit;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.0, d);
  float flicker = 1.0 - 0.10 * step(0.985, fract(sin(floor(uTime * 12.0) * 91.7) * 4375.5));
  float tw = 0.75 + 0.25 * sin(uTime * 3.0 + vSeed * 40.0); // cintilar de cada ponto
  float lum = (0.26 + 1.05 * vLit + 0.45 * vFres + 1.3 * vScan) * vLines * tw * flicker * uGain;
  vec3 col = uColor * lum + vec3(0.55, 0.8, 1.0) * vScan * 0.35; // varredura puxa para o branco
  gl_FragColor = vec4(col, soft * vFade * clamp(lum, 0.0, 1.0) * 0.8);
}`

function hsl(h: number, s: number, l: number): THREE.Color {
  return new THREE.Color().setHSL((((h % 360) + 360) % 360) / 360, s, l)
}

export default function HeadHologram({ state, level = 0, appearance, onUnavailable, points = POINTS, wire = true }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const live = useRef({ state, level, appearance })
  live.current = { state, level, appearance }

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
    const pr = Math.min(window.devicePixelRatio || 1, 2)
    renderer.setPixelRatio(pr)
    el.appendChild(renderer.domElement)
    renderer.domElement.style.display = "block"

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 30)
    camera.position.set(0, 0.05, 5.0)
    const group = new THREE.Group()
    scene.add(group)

    const uniforms = {
      uTime: { value: 0 }, uMouth: { value: 0 }, uSize: { value: 1.0 }, uPixel: { value: pr * 120 }, uMinY: { value: -1 },
      uScanSpeed: { value: 0.16 }, uColor: { value: hsl(live.current.appearance.hue, 0.95, 0.6) }, uGain: { value: 1 },
    }
    const material = new THREE.ShaderMaterial({ uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
    const lineMat = new THREE.LineBasicMaterial({ color: hsl(live.current.appearance.hue, 0.95, 0.55), transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false })
    const ringMat = new THREE.LineBasicMaterial({ color: hsl(live.current.appearance.hue, 0.95, 0.6), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false })

    let disposed = false
    const disposables: { dispose: () => void }[] = [material, lineMat, ringMat]
    new GLTFLoader().load(
      HEAD_MODEL_URL,
      gltf => {
        if (disposed) return
        let mesh: THREE.Mesh | null = null
        gltf.scene.traverse(o => {
          if (!mesh && (o as THREE.Mesh).isMesh) mesh = o as THREE.Mesh
        })
        if (!mesh) return onUnavailable?.()
        const src = (mesh as THREE.Mesh).geometry.clone()
        src.computeBoundingBox()
        const box = src.boundingBox!
        const size = new THREE.Vector3()
        box.getSize(size)
        const center = new THREE.Vector3()
        box.getCenter(center)
        const k = 2.3 / size.y
        src.translate(-center.x, -center.y, -center.z)
        src.scale(k, k, k)
        uniforms.uMinY.value = -size.y * k * 0.5
        // pontos sobre a superficie (mais denso que os vertices originais)
        const sampler = new MeshSurfaceSampler(new THREE.Mesh(src)).build()
        const pos = new Float32Array(points * 3)
        const nor = new Float32Array(points * 3)
        const seed = new Float32Array(points)
        const p = new THREE.Vector3()
        const n = new THREE.Vector3()
        for (let i = 0; i < points; i++) {
          sampler.sample(p, n)
          pos.set([p.x, p.y, p.z], i * 3)
          nor.set([n.x, n.y, n.z], i * 3)
          seed[i] = Math.random()
        }
        const g = new THREE.BufferGeometry()
        g.setAttribute("position", new THREE.BufferAttribute(pos, 3))
        g.setAttribute("normal", new THREE.BufferAttribute(nor, 3))
        g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1))
        group.add(new THREE.Points(g, material))
        disposables.push(g, src)
        if (wire) {
          const w = new THREE.LineSegments(new THREE.WireframeGeometry(src), lineMat)
          group.add(w)
          disposables.push(w.geometry)
        }
        // aneis do projetor, na altura do pescoco
        const y0 = -size.y * k * 0.5 - 0.02
        for (const r of [0.95, 0.72]) {
          const pts: THREE.Vector3[] = []
          for (let i = 0; i <= 96; i++) pts.push(new THREE.Vector3(Math.cos((i / 96) * Math.PI * 2) * r, 0, Math.sin((i / 96) * Math.PI * 2) * r))
          const rg = new THREE.BufferGeometry().setFromPoints(pts)
          const ring = new THREE.Line(rg, ringMat)
          ring.position.y = y0
          ring.scale.z = 0.35
          group.add(ring)
          disposables.push(rg)
        }
      },
      undefined,
      () => onUnavailable?.(),
    )

    function resize() {
      const w = el!.clientWidth || 1
      const h = el!.clientHeight || 1
      renderer.setSize(w, h, false)
      renderer.domElement.style.width = "100%"
      renderer.domElement.style.height = "100%"
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      uniforms.uPixel.value = pr * h * 0.021
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    let raf = 0
    let last = performance.now()
    let mouth = 0
    let hue = live.current.appearance.hue
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (document.hidden) return
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const { state: st, level: lv, appearance: ap } = live.current
      const moving = ap.motion
      uniforms.uTime.value += moving ? dt : 0
      // boca segue a voz (suavizada)
      const target = st === "responding" ? Math.min(1, lv * 1.6 + 0.12) : 0
      mouth += (target - mouth) * Math.min(1, dt * 14)
      uniforms.uMouth.value = mouth
      // cor: segue o tema do dia; aprovacao pendente fica ambar
      const wantHue = st === "approval" ? APPROVAL_HUE : ap.hue
      hue += (wantHue - hue) * Math.min(1, dt * 4)
      uniforms.uColor.value.copy(hsl(hue, 0.95, 0.6))
      lineMat.color.copy(hsl(hue, 0.95, 0.55))
      ringMat.color.copy(hsl(hue, 0.95, 0.6))
      uniforms.uGain.value = (0.7 + 0.6 * ap.intensity) * (st === "listening" ? 1.18 : st === "responding" ? 1.1 : 1)
      uniforms.uScanSpeed.value = st === "thinking" ? 0.55 : st === "listening" ? 0.28 : 0.16
      // movimento sutil de cabeca: balanco lento; pensando, vira um pouco mais
      const t = uniforms.uTime.value
      const sway = st === "thinking" ? 0.32 : st === "listening" ? 0.10 : 0.18
      group.rotation.y = moving ? Math.sin(t * 0.45) * sway : 0
      group.rotation.x = moving ? Math.sin(t * 0.31) * 0.035 + (st === "listening" ? 0.04 : 0) : 0
      group.position.y = moving ? Math.sin(t * 1.3) * 0.012 : 0
      renderer.render(scene, camera)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      ro.disconnect()
      disposables.forEach(d => d.dispose())
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [onUnavailable, points, wire])

  return <div ref={host} className="h-full w-full" aria-hidden="true" />
}
