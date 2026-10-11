import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }

/** Tira a marcacao (negrito, titulos, listas, codigo) para mostrar um resumo em texto corrido. */
export function plainText(src: string): string {
  return (src || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\*\*|__|`/g, "")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*[-*•]\s+/gm, "• ")
    .replace(/\s+/g, " ")
    .trim()
}
