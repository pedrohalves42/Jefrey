import { authedFetch } from "@/lib/session"

export type PhoneState = { enabled: boolean; url: string | null; devices: { id: string; name: string; created: number }[] }
export type PhonePairing = { qr_svg: string; expires_in: number; url: string }

/** O QR vem do proprio Jefrey como SVG; vira imagem (data URL), nunca HTML solto na pagina. */
export function qrImageSrc(svg: string): string | null {
  return svg.trimStart().startsWith("<svg") ? "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg) : null
}

export function expiresText(seconds: number): string {
  const m = Math.max(1, Math.round(seconds / 60))
  return `O código vale por ${m} ${m === 1 ? "minuto" : "minutos"} e só uma vez.`
}

export async function getPhone(): Promise<PhoneState | null> {
  try {
    const r = await authedFetch("/phone")
    return r.ok ? ((await r.json()) as PhoneState) : null
  } catch {
    return null
  }
}

export async function setPhoneEnabled(enabled: boolean): Promise<{ state?: PhoneState; error?: string }> {
  try {
    const r = await authedFetch("/phone/enabled", { method: "PUT", body: JSON.stringify({ enabled }) })
    if (r.ok) return { state: (await r.json()) as PhoneState }
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    return { error: d.detail ?? "Não consegui agora." }
  } catch {
    return { error: "Não consegui agora." }
  }
}

export async function newPairing(): Promise<PhonePairing | null> {
  try {
    const r = await authedFetch("/phone/pairing", { method: "POST" })
    return r.ok ? ((await r.json()) as PhonePairing) : null
  } catch {
    return null
  }
}

export async function revokePhone(id: string): Promise<boolean> {
  try {
    return (await authedFetch(`/phone/devices/${encodeURIComponent(id)}`, { method: "DELETE" })).ok
  } catch {
    return false
  }
}
