// @vitest-environment node
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

type Listener = (event: any) => void

/** Carrega public/sw.js com um `self`, `caches` e `fetch` falsos e devolve os ouvintes registrados. */
function loadSw() {
  const code = readFileSync(resolve(__dirname, "../../public/sw.js"), "utf-8")
  const listeners: Record<string, Listener> = {}
  const store = new Map<string, Map<string, unknown>>()
  const cacheOf = (name: string) => {
    if (!store.has(name)) store.set(name, new Map())
    const m = store.get(name) as Map<string, unknown>
    return {
      match: async (req: any) => m.get(typeof req === "string" ? req : req.url),
      put: async (req: any, resp: unknown) => void m.set(typeof req === "string" ? req : req.url, resp),
      addAll: async (urls: string[]) => urls.forEach(u => m.set(u, { cached: u })),
    }
  }
  const caches = {
    open: async (n: string) => cacheOf(n),
    match: async (req: any) => {
      for (const m of store.values()) {
        const hit = m.get(typeof req === "string" ? req : req.url)
        if (hit) return hit
      }
      return undefined
    },
    keys: async () => [...store.keys()],
    delete: async (n: string) => store.delete(n),
  }
  const calls: string[] = []
  const fakeFetch = async (req: any) => {
    calls.push(req.url)
    return { ok: true, status: 200, clone() { return this }, url: req.url }
  }
  const self = { location: { origin: "http://localhost:8000" }, addEventListener: (t: string, l: Listener) => (listeners[t] = l), skipWaiting() {}, clients: { claim() {} } }
  new Function("self", "caches", "fetch", "Response", code)(self, caches, fakeFetch, { error: () => ({ error: true }) })
  return { listeners, caches, store, calls }
}

/** Dispara o evento fetch e diz se o service worker assumiu a resposta (respondWith). */
function intercepted(listeners: Record<string, Listener>, url: string, init: { method?: string; mode?: string } = {}) {
  let handled = false
  const event = { request: { url, method: init.method ?? "GET", mode: init.mode ?? "cors" }, respondWith: () => void (handled = true) }
  listeners.fetch?.(event)
  return handled
}

const O = "http://localhost:8000"

describe("service worker: nunca mexe na API", () => {
  const { listeners } = loadSw()

  it.each([
    "/chat", "/chat/stream", "/chat/status/t1", "/memory/search?q=x", "/memory/recent", "/approvals/pending",
    "/stt", "/tts", "/settings/llm", "/settings/llm/recommend", "/skills", "/metrics", "/health", "/api/status",
    "/auth/dev-token", "/channels/whatsapp/webhook", "/docs", "/openapi.json", "/ws",
  ])("GET %s segue direto para a rede", path => {
    expect(intercepted(listeners, O + path)).toBe(false)
  })

  it.each(["POST", "PUT", "DELETE", "PATCH"])("%s nunca e interceptado, nem em arquivo estatico", method => {
    expect(intercepted(listeners, O + "/chat/stream", { method })).toBe(false)
    expect(intercepted(listeners, O + "/assets/index-abc.js", { method })).toBe(false)
  })

  it("outras origens nao sao interceptadas", () => {
    expect(intercepted(listeners, "https://exemplo.com/assets/x.js")).toBe(false)
    expect(intercepted(listeners, "http://localhost:11434/api/chat")).toBe(false)
  })

  it("navegar para um caminho de API nao cai na casca do app", () => {
    expect(intercepted(listeners, O + "/approvals/pending", { mode: "navigate" })).toBe(false)
    expect(intercepted(listeners, O + "/memory/search", { mode: "navigate" })).toBe(false)
  })
})

describe("service worker: casca do app", () => {
  it("arquivos estaticos e paginas do app sao tratados", () => {
    const { listeners } = loadSw()
    expect(intercepted(listeners, O + "/assets/index-abc123.js")).toBe(true)
    expect(intercepted(listeners, O + "/images/icon-192.png")).toBe(true)
    expect(intercepted(listeners, O + "/manifest.json")).toBe(true)
    for (const p of ["/", "/memoria", "/skills", "/configuracoes", "/avancado"]) {
      expect(intercepted(listeners, O + p, { mode: "navigate" })).toBe(true)
    }
  })

  it("instalacao guarda a casca e a ativacao apaga caches de versoes antigas", async () => {
    const { listeners, store } = loadSw()
    store.set("jefrey-shell-v0", new Map())
    let p1: Promise<unknown> = Promise.resolve()
    listeners.install?.({ waitUntil: (p: Promise<unknown>) => (p1 = p) })
    await p1
    expect(store.get("jefrey-shell-v1")?.has("/")).toBe(true)
    let p2: Promise<unknown> = Promise.resolve()
    listeners.activate?.({ waitUntil: (p: Promise<unknown>) => (p2 = p) })
    await p2
    expect(store.has("jefrey-shell-v0")).toBe(false)
    expect(store.has("jefrey-shell-v1")).toBe(true)
  })
})

describe("manifesto", () => {
  const m = JSON.parse(readFileSync(resolve(__dirname, "../../public/manifest.json"), "utf-8"))

  it("e instalavel: nome, escopo, modo janela e icones PNG 192 e 512 (+ maskable)", () => {
    expect(m.name).toBe("Jefrey")
    expect(m.display).toBe("standalone")
    expect(m.start_url).toBe("/")
    const sizes = m.icons.filter((i: any) => i.type === "image/png").map((i: any) => i.sizes)
    expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]))
    expect(m.icons.some((i: any) => i.purpose === "maskable")).toBe(true)
  })

  it("nao carrega mais textos de status falsos", () => {
    expect(JSON.stringify(m)).not.toMatch(/175|7 pecas|1 programa/i)
  })

  it("os icones declarados existem no disco", () => {
    for (const i of m.icons) {
      expect(() => readFileSync(resolve(__dirname, "../../public" + i.src))).not.toThrow()
    }
  })
})
