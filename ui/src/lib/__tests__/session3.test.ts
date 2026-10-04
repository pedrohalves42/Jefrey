import { describe, expect, it, beforeEach, vi } from "vitest"
import { cleanKey, detectKeyProvider, guideFor, KEY_GUIDES, keyProblem } from "../keyGuide"
import { googleReturnMessage } from "../connections"
import { getEasy, setEasy, visibleItems, type NavItem } from "../easy"
import { speechChunks } from "../speak"

describe("guia de chave", () => {
  it("reconhece o servico pelo comeco do codigo", () => {
    expect(detectKeyProvider("sk-ant-api03-abcdefghijklmnopqrstuvwxyz")).toBe("anthropic")
    expect(detectKeyProvider("sk-or-v1-abcdefghijklmnopqrstuvwxyz")).toBe("openrouter")
    expect(detectKeyProvider("sk-proj-abcdefghijklmnopqrstuvwxyz")).toBe("openai")
    expect(detectKeyProvider("oi tudo bem")).toBeNull()
  })

  it("limpa espacos e aspas ao colar", () => {
    expect(cleanKey('  "sk-abc"  ')).toBe("sk-abc")
  })

  it("aceita um codigo certo e explica os errados em portugues simples", () => {
    const ok = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    expect(keyProblem("anthropic", ok)).toBeNull()
    expect(keyProblem("anthropic", "")).toMatch(/Cole aqui/)
    expect(keyProblem("anthropic", "sk-ant- com espaco no meio")).toMatch(/espaços/)
    expect(keyProblem("anthropic", "qualquercoisa")).toMatch(/sk-/)
    expect(keyProblem("openai", ok)).toMatch(/Claude/)
    expect(keyProblem("anthropic", "sk-ant-curto")).toMatch(/cortado/)
  })

  it("nenhum texto do guia usa jargao tecnico", () => {
    const todo = KEY_GUIDES.flatMap(g => g.steps).join(" ").toLowerCase()
    for (const palavra of ["api", "token", "endpoint", "provedor", "modelo"]) expect(todo).not.toContain(palavra)
    expect(guideFor("anthropic")?.url.startsWith("https://")).toBe(true)
  })
})

describe("volta do Google", () => {
  it("mostra mensagens humanas", () => {
    expect(googleReturnMessage("ok")?.ok).toBe(true)
    expect(googleReturnMessage("erro")?.ok).toBe(false)
    expect(googleReturnMessage(null)).toBeNull()
    expect(googleReturnMessage("x")).toBeNull()
  })
})

describe("modo Facil", () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, v),
    })
    vi.stubGlobal("document", { documentElement: { dataset: {} as Record<string, string> } })
    vi.stubGlobal("window", { dispatchEvent: () => true })
  })
  const items: NavItem[] = [
    { to: "/", label: "Conversa", icon: "", easy: true },
    { to: "/skills", label: "Skills", icon: "" },
    { to: "/ajuda", label: "Ajuda", icon: "", easy: true },
  ]
  it("vem ligado por padrao e lembra a escolha", () => {
    expect(getEasy()).toBe(true)
    setEasy(false)
    expect(getEasy()).toBe(false)
    expect(document.documentElement.dataset.easy).toBe("0")
    setEasy(true)
    expect(document.documentElement.dataset.easy).toBe("1")
  })
  it("no modo Facil mostra so o essencial", () => {
    expect(visibleItems(items, true).map(i => i.label)).toEqual(["Conversa", "Ajuda"])
    expect(visibleItems(items, false)).toHaveLength(3)
  })
})

describe("fala", () => {
  it("quebra em frases curtas, sem links nem simbolos", () => {
    const c = speechChunks("**Oi!** Veja https://exemplo.com agora. Tudo bem? " + "palavra ".repeat(80))
    expect(c[0]).toBe("Oi!")
    expect(c.join(" ")).not.toContain("http")
    expect(c.join(" ")).not.toContain("*")
    expect(c.every(x => x.length <= 220)).toBe(true)
    expect(speechChunks("   ")).toEqual([])
  })
})
