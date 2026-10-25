/** Acessibilidade: tamanho da letra e alto contraste, alem do Modo Facil. Guardado so neste computador. */
import { useEffect, useState } from "react"

export type TextSize = "normal" | "grande" | "enorme"
export type Access = { text: TextSize; contrast: boolean }

const KEY = "jefrey_access_v1"
const EVT = "jefrey-access"
export const TEXT_SIZES: { id: TextSize; label: string }[] = [
  { id: "normal", label: "Normal" },
  { id: "grande", label: "Grande" },
  { id: "enorme", label: "Enorme" },
]

export function parseAccess(raw: string | null): Access {
  try {
    const v = JSON.parse(raw ?? "{}") as Partial<Access>
    const text: TextSize = v.text === "grande" || v.text === "enorme" ? v.text : "normal"
    return { text, contrast: v.contrast === true }
  } catch {
    return { text: "normal", contrast: false }
  }
}

export function getAccess(): Access {
  try {
    return parseAccess(localStorage.getItem(KEY))
  } catch {
    return { text: "normal", contrast: false }
  }
}

export function applyAccess(a: Access): void {
  const d = document.documentElement.dataset
  d.text = a.text
  d.contrast = a.contrast ? "alto" : "normal"
}

export function setAccess(a: Access): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(a))
  } catch {
    /* sem armazenamento: vale so ate recarregar */
  }
  applyAccess(a)
  window.dispatchEvent(new Event(EVT))
}

export function useAccess(): [Access, (a: Access) => void] {
  const [a, setA] = useState(getAccess)
  useEffect(() => {
    const h = () => setA(getAccess())
    window.addEventListener(EVT, h)
    return () => window.removeEventListener(EVT, h)
  }, [])
  return [a, setAccess]
}
