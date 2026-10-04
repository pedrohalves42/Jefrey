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
