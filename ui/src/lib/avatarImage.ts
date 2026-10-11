import { fitSize, MAX_STORED_CHARS, validateImageFile } from "@/lib/holo"

const KEY = "jefrey_avatar_image_v1"
export const AVATAR_EVENT = "jefrey-avatar"

/** Silhueta generica (busto) usada ate a pessoa escolher uma imagem. Nada de terceiros: desenho proprio. */
const BUST_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><defs>
<radialGradient id="g" cx="50%" cy="38%" r="60%"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#6b6b6b"/></radialGradient></defs>
<rect width="512" height="512" fill="#000"/>
<ellipse cx="256" cy="190" rx="80" ry="102" fill="url(#g)"/>
<rect x="226" y="270" width="60" height="64" rx="18" fill="#9a9a9a"/>
<path d="M70 500 Q84 340 256 326 Q428 340 442 500 Z" fill="url(#g)" opacity=".92"/>
<g stroke="#000" stroke-width="4" fill="none" opacity=".7">
<path d="M176 120 H336"/><path d="M172 146 H340"/><path d="M170 172 H342"/><path d="M172 198 H340"/><path d="M178 224 H334"/><path d="M190 250 H322"/>
<path d="M230 282 H282"/><path d="M230 306 H282"/>
<path d="M120 372 H392"/><path d="M104 404 H408"/><path d="M92 436 H420"/><path d="M82 468 H430"/>
<path d="M256 330 V500"/></g>
</svg>`

export const DEFAULT_AVATAR = "data:image/svg+xml;utf8," + encodeURIComponent(BUST_SVG)

export function loadAvatarImage(): string | null {
  try {
    const v = localStorage.getItem(KEY)
    return v && v.startsWith("data:image/") && v.length <= MAX_STORED_CHARS ? v : null
  } catch {
    return null
  }
}

export function saveAvatarImage(dataUrl: string): boolean {
  if (!dataUrl.startsWith("data:image/") || dataUrl.length > MAX_STORED_CHARS) return false
  try {
    localStorage.setItem(KEY, dataUrl)
    window.dispatchEvent(new Event(AVATAR_EVENT))
    return true
  } catch {
    return false // sem espaco ou armazenamento bloqueado
  }
}

export function clearAvatarImage(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nada a fazer */
  }
  window.dispatchEvent(new Event(AVATAR_EVENT))
}

/** Le a imagem escolhida, reduz (max 640 px) e devolve um texto data: pronto para guardar. Erros em portugues. */
export async function processImageFile(file: File, maxPx = 640): Promise<string> {
  const bad = validateImageFile(file)
  if (bad) throw new Error(bad)
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error("Não consegui abrir essa imagem."))
      el.src = url
    })
    const { w, h } = fitSize(img.naturalWidth, img.naturalHeight, maxPx)
    const canvas = document.createElement("canvas")
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext("2d")
    if (!ctx) throw new Error("Seu navegador não conseguiu processar a imagem.")
    ctx.drawImage(img, 0, 0, w, h)
    for (const [type, q] of [["image/webp", 0.85], ["image/jpeg", 0.85], ["image/png", undefined]] as const) {
      const out = canvas.toDataURL(type, q)
      if (out.startsWith(`data:${type}`) && out.length <= MAX_STORED_CHARS) return out
    }
    throw new Error("A imagem ficou grande demais mesmo reduzida. Escolha uma menor.")
  } finally {
    URL.revokeObjectURL(url)
  }
}


/** Desenhos PROPRIOS (nada de personagens de terceiros): a pessoa pode trocar por qualquer imagem sua. Fundo escuro, partes claras viram luz no holograma. */
const ARMOR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><defs>
<linearGradient id="m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset=".55" stop-color="#9aa0a6"/><stop offset="1" stop-color="#4a4f55"/></linearGradient></defs>
<rect width="512" height="512" fill="#000"/>
<path d="M256 40 C150 40 104 120 104 220 L104 330 C104 392 150 450 200 470 L256 486 L312 470 C362 450 408 392 408 330 L408 220 C408 120 362 40 256 40Z" fill="url(#m)"/>
<path d="M256 40 L256 150" stroke="#000" stroke-width="5" opacity=".55"/>
<path d="M132 214 L236 236 L236 268 L146 262 Z" fill="#fff"/><path d="M380 214 L276 236 L276 268 L366 262 Z" fill="#fff"/>
<path d="M200 330 H312 L292 384 H220 Z" fill="#2c3035" opacity=".75"/>
<g stroke="#000" stroke-width="4" opacity=".6" fill="none"><path d="M126 300 Q256 340 386 300"/><path d="M150 400 Q256 448 362 400"/><path d="M256 290 V330"/></g>
<circle cx="256" cy="440" r="20" fill="#fff" opacity=".9"/></svg>`

const ROBOT_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><defs>
<radialGradient id="r" cx="50%" cy="40%" r="65%"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#6b7075"/></radialGradient></defs>
<rect width="512" height="512" fill="#000"/>
<rect x="118" y="110" width="276" height="250" rx="52" fill="url(#r)"/>
<rect x="240" y="60" width="32" height="56" rx="8" fill="#b9bec4"/><circle cx="256" cy="52" r="16" fill="#fff"/>
<circle cx="204" cy="224" r="42" fill="#000"/><circle cx="308" cy="224" r="42" fill="#000"/>
<circle cx="204" cy="224" r="26" fill="#fff"/><circle cx="308" cy="224" r="26" fill="#fff"/>
<rect x="190" y="304" width="132" height="24" rx="12" fill="#000" opacity=".7"/><path d="M206 316 H306" stroke="#fff" stroke-width="5" stroke-dasharray="14 10"/>
<rect x="198" y="360" width="116" height="44" rx="14" fill="#9aa0a6"/><path d="M96 440 Q256 392 416 440 L430 500 H82 Z" fill="url(#r)" opacity=".92"/></svg>`

const toUrl = (svg: string) => "data:image/svg+xml;utf8," + encodeURIComponent(svg)

export const PRESETS: { id: string; label: string; url: string }[] = [
  { id: "armadura", label: "Armadura", url: toUrl(ARMOR_SVG) },
  { id: "robo", label: "Robô", url: toUrl(ROBOT_SVG) },
]
