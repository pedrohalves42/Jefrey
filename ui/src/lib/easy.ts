/** Modo Fácil: letra grande, contraste alto e menu reduzido. Ligado por padrao (pensado para quem nao e tecnico). */
import { useEffect, useState } from "react"

const KEY = "jefrey_easy_mode_v1"
const EVT = "jefrey-easy"

export function getEasy(): boolean {
  try {
    const v = localStorage.getItem(KEY)
    return v === null ? true : v === "1"
  } catch {
    return true
  }
}

export function setEasy(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0")
  } catch {
    /* sem armazenamento: vale so ate recarregar */
  }
  applyEasy(on)
  window.dispatchEvent(new Event(EVT))
}

export function applyEasy(on: boolean): void {
  document.documentElement.dataset.easy = on ? "1" : "0"
}

export function useEasy(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(getEasy)
  useEffect(() => {
    const h = () => setOn(getEasy())
    window.addEventListener(EVT, h)
    return () => window.removeEventListener(EVT, h)
  }, [])
  return [on, setEasy]
}

export type NavItem = { to: string; label: string; end?: boolean; icon: string; easy?: boolean }

/** No modo Fácil so aparecem os itens marcados. */
export function visibleItems(items: NavItem[], easy: boolean): NavItem[] {
  return easy ? items.filter(i => i.easy) : items
}
