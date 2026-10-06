// @vitest-environment jsdom
// A extensao do WhatsApp contra uma pagina SIMULADA do WhatsApp Web (o teste real, com o celular, so a pessoa faz).
import { beforeEach, describe, expect, it, vi } from "vitest"
import fs from "node:fs"
import path from "node:path"

const DIR = path.resolve(__dirname, "../../../extensions/whatsapp")
const CORE_SRC = fs.readFileSync(path.join(DIR, "core.js"), "utf8")
const CONTENT_SRC = fs.readFileSync(path.join(DIR, "content.js"), "utf8")

function row(id, text, extra = "") {
  return `<div data-id="${id}">${text ? `<span class="selectable-text copyable-text">${text}</span>` : extra}</div>`
}

function sidebar(names) {
  const cells = names.map(n => `<div role="listitem" data-name="${n}"><span title="${n}">${n}</span></div>`).join("")
  return `<div id="side"><div contenteditable="true" data-tab="3"></div><div id="pane-side">${cells}</div></div>`
}

function page({ title = "Maria", group = false, rows = [], composer = "", chats = null } = {}) {
  const jid = group ? "120363@g.us" : "5511999999999@c.us"
  const body = rows.map(r => row(`${r.me ? "true" : "false"}_${jid}_${r.id}`, r.text, r.extra)).join("")
  document.body.innerHTML = `<div id="app">${chats ? sidebar(chats) : ""}<div id="main"><header><span dir="auto" title="${title}">${title}</span></header>
    <div class="messages">${body}</div>
    <footer><div contenteditable="true" data-tab="10">${composer}</div><button aria-label="Enviar"></button></footer></div></div>`
  // clicar em uma conversa da lista abre essa conversa (so troca o nome no cabecalho)
  document.querySelectorAll("#pane-side [role='listitem']").forEach(cell => {
    cell.addEventListener("click", () => {
      const h = document.querySelector("#main header span")
      h.textContent = cell.getAttribute("data-name")
      h.setAttribute("title", cell.getAttribute("data-name"))
    })
  })
  const send = document.querySelector('footer button[aria-label="Enviar"]')
  send.addEventListener("click", () => {
    const c = document.querySelector("footer div[contenteditable]")
    const me = document.createElement("div")
    me.setAttribute("data-id", `true_${jid}_ENVIADA${Date.now()}`)
    me.innerHTML = `<span class="selectable-text copyable-text">${c.textContent}</span>`
    document.querySelector(".messages").appendChild(me)
    c.textContent = "" // a mensagem saiu
  })
}

function addIncoming(id, text, extra = "") {
  const div = document.createElement("div")
  div.setAttribute("data-id", `false_5511999999999@c.us_${id}`)
  div.innerHTML = text ? `<span class="selectable-text copyable-text">${text}</span>` : extra
  document.querySelector(".messages").appendChild(div)
}

function loadCore() {
  delete globalThis.JefreyWACore
  window.eval(CORE_SRC)
  return globalThis.JefreyWACore
}

describe("leitura da pagina (core)", () => {
  let C
  beforeEach(() => {
    C = loadCore()
  })

  it("acha o nome da conversa e compara sem acento nem maiuscula", () => {
    page({ title: "José da Silva" })
    expect(C.chatTitle(document)).toBe("José da Silva")
    expect(C.sameChat("José da Silva", "jose da  SILVA")).toBe(true)
    expect(C.sameChat("José", "Maria")).toBe(false)
    expect(C.sameChat("", "")).toBe(false)
  })

  it("le as mensagens, quem enviou e o tipo (texto ou outro)", () => {
    page({ rows: [{ id: "A", text: "oi, tudo bem?" }, { id: "B", text: "tudo sim!", me: true }, { id: "C", text: "", extra: "<audio></audio>" }] })
    const r = C.parseRows(document)
    expect(r.map(x => [x.from_me, x.kind, x.text])).toEqual([[false, "text", "oi, tudo bem?"], [true, "text", "tudo sim!"], [false, "other", ""]])
  })

  it("reconhece grupo pelo identificador (@g.us)", () => {
    page({ group: true, rows: [{ id: "A", text: "bom dia" }] })
    expect(C.isGroup(document)).toBe(true)
    page({ rows: [{ id: "A", text: "bom dia" }] })
    expect(C.isGroup(document)).toBe(false)
  })

  it("so considera novas as mensagens recebidas que ainda nao foram vistas", () => {
    page({ rows: [{ id: "A", text: "antiga" }, { id: "B", text: "minha", me: true }, { id: "C", text: "nova" }] })
    const rows = C.parseRows(document)
    const seen = new Set([rows[0].id])
    expect(C.newIncoming(rows, seen).map(r => r.text)).toEqual(["nova"])
    expect(C.context(rows, 2).map(r => r.from_me)).toEqual([true, false])
  })

  it("digita no campo e confere o texto", () => {
    page()
    expect(C.typeText(document, "Oi! Tudo certo por aqui.")).toBe(true)
    expect(C.composerText(document)).toBe("Oi! Tudo certo por aqui.")
  })

  it("so envia no chat certo e com o campo vazio (nunca apaga o que a pessoa digita)", () => {
    page({ title: "Maria" })
    expect(C.canSendNow(document, "Maria")).toEqual({ ok: true, why: "" })
    expect(C.canSendNow(document, "João")).toEqual({ ok: false, why: "outro-chat" })
    page({ title: "Maria", composer: "estou escrevendo aqui" })
    expect(C.canSendNow(document, "Maria")).toEqual({ ok: false, why: "digitando" })
    document.body.innerHTML = '<div id="main"><header><span dir="auto" title="Maria">Maria</span></header></div>'
    expect(C.canSendNow(document, "Maria")).toEqual({ ok: false, why: "sem-campo" })
  })

  it("pausa humana entre 5 e 14 segundos", () => {
    expect(C.humanDelayMs(0)).toBe(5000)
    expect(C.humanDelayMs(0.999)).toBeLessThanOrEqual(14000)
    for (let i = 0; i < 50; i++) expect(C.humanDelayMs()).toBeGreaterThanOrEqual(5000)
  })
})

describe("extensao inteira na pagina simulada", () => {
  let calls, respostas, hooks

  function boot({ paired = true, paused = false, idleMs = 0 } = {}) {
    calls = []
    respostas = {}
    window.__jefreyWA = false
    document.documentElement.querySelectorAll("div[style*='position:fixed']").forEach(e => e.remove())
    window.__JEFREY_WA_TEST__ = { sleep: () => Promise.resolve(), idleMs }
    window.chrome = {
      runtime: {
        sendMessage: vi.fn(async msg => {
          calls.push(msg)
          if (msg.type === "status") return { paired, paused }
          if (msg.type === "setPaused") return { ok: true }
          if (msg.type === "api") {
            const r = respostas[msg.path]
            return typeof r === "function" ? r(msg) : r ?? { ok: true, status: 200, data: {} }
          }
          return { ok: true }
        }),
      },
    }
    loadCore()
    window.eval(CONTENT_SRC)
    hooks = window.__JEFREY_WA_TEST__.hooks
  }
  const api = path => calls.filter(c => c.type === "api" && c.path === path)

  it("nao responde o historico antigo: so avisa que a conversa existe", async () => {
    page({ rows: [{ id: "A", text: "mensagem antiga" }, { id: "B", text: "outra antiga" }] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    const inbound = api("/wa/device/inbound")
    expect(inbound).toHaveLength(1)
    expect(inbound[0].body).toMatchObject({ chat: "Maria", is_group: false, messages: [] })
    await hooks.readTick()
    await hooks.flush()
    expect(api("/wa/device/inbound")).toHaveLength(1) // nada novo: nada enviado ao Jefrey
  })

  it("manda ao Jefrey so a mensagem nova (e o contexto), uma vez", async () => {
    page({ rows: [{ id: "A", text: "antiga" }] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    addIncoming("NOVA1", "vamos almoçar amanhã?")
    await hooks.readTick()
    await hooks.flush()
    const inbound = api("/wa/device/inbound")
    expect(inbound).toHaveLength(2)
    const corpo = inbound[1].body
    expect(corpo.messages.map(m => m.text)).toEqual(["vamos almoçar amanhã?"])
    expect(corpo.context.map(c => c.text)).toEqual(["antiga"])
    await hooks.readTick()
    await hooks.flush()
    expect(api("/wa/device/inbound")).toHaveLength(2)
  })

  it("junta mensagens seguidas em um unico pedido", async () => {
    page({ rows: [] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    addIncoming("N1", "oi")
    await hooks.readTick()
    addIncoming("N2", "tudo bem?")
    await hooks.readTick()
    await hooks.flush()
    expect(api("/wa/device/inbound")[1].body.messages.map(m => m.text)).toEqual(["oi", "tudo bem?"])
  })

  it("audio vai marcado como outro tipo", async () => {
    page({ rows: [] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    addIncoming("AUD", "", "<audio></audio>")
    await hooks.readTick()
    await hooks.flush()
    expect(api("/wa/device/inbound")[1].body.messages[0]).toMatchObject({ kind: "other", text: "" })
  })

  it("envia o que foi aprovado: digita, clica em enviar e avisa o Jefrey", async () => {
    page({ title: "Maria", rows: [{ id: "A", text: "oi" }] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Oi! Tudo ótimo." }] } }
    await hooks.pollTick()
    const enviada = [...document.querySelectorAll("[data-id^='true_']")].map(e => e.textContent)
    expect(enviada).toContain("Oi! Tudo ótimo.")
    expect(api("/wa/device/sent")[0].body).toEqual({ id: "D1", ok: true })
    // a mensagem enviada aparece como "minha": nao e tratada como nova
    await hooks.readTick()
    await hooks.readTick()
    await hooks.flush()
    expect(api("/wa/device/inbound").every(c => c.body.messages.length === 0)).toBe(true)
  })

  it("nao envia em outra conversa nem por cima do que a pessoa esta digitando", async () => {
    page({ title: "João", rows: [{ id: "A", text: "oi" }] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Oi!" }] } }
    await hooks.pollTick()
    expect(api("/wa/device/sent")).toHaveLength(0)
    expect(document.querySelector("footer div[contenteditable]").textContent).toBe("")
    page({ title: "Maria", composer: "rascunho da pessoa" })
    await hooks.pollTick()
    expect(api("/wa/device/sent")).toHaveLength(0)
    expect(document.querySelector("footer div[contenteditable]").textContent).toBe("rascunho da pessoa")
  })

  it("abre sozinho a conversa certa da lista e envia o que a pessoa aprovou", async () => {
    page({ title: "João", rows: [{ id: "A", text: "oi" }], chats: ["João", "Maria Clara", "Maria"] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Chego às 8h!" }] } }
    await hooks.pollTick()
    expect(document.querySelector("#main header span").textContent).toBe("Maria") // abriu "Maria", nao "Maria Clara"
    expect(api("/wa/device/sent")[0].body).toEqual({ id: "D1", ok: true })
    expect([...document.querySelectorAll(".messages [data-id]")].some(d => d.textContent === "Chego às 8h!")).toBe(true)
  })

  it("nao troca de conversa enquanto a pessoa esta mexendo no WhatsApp", async () => {
    page({ title: "João", rows: [{ id: "A", text: "oi" }], chats: ["João", "Maria"] })
    boot({ idleMs: 60 * 60 * 1000 }) // acabou de mexer: nao esta parada
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Oi!" }] } }
    await hooks.pollTick()
    expect(document.querySelector("#main header span").textContent).toBe("João")
    expect(api("/wa/device/sent")).toHaveLength(0)
  })

  it("nao troca de conversa com rascunho digitado e nunca por uma conversa que nao existe; depois de algumas tentativas avisa que falhou", async () => {
    page({ title: "João", composer: "rascunho", chats: ["João", "Maria"] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Oi!" }] } }
    await hooks.pollTick()
    expect(document.querySelector("#main header span").textContent).toBe("João")
    page({ title: "João", chats: ["João", "Ana"] })
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D2", chat: "Zeca", text: "Oi!" }] } }
    for (let i = 0; i < 4; i++) await hooks.pollTick()
    expect(document.querySelector("#main header span").textContent).toBe("João")
    expect(api("/wa/device/sent").map(c => c.body)).toEqual([{ id: "D2", ok: false }])
  })

  it("pausado ou nao pareado: nao le e nao envia nada", async () => {
    page({ rows: [{ id: "A", text: "oi" }] })
    boot({ paired: true, paused: true })
    await hooks.refreshState()
    addIncoming("N1", "oi de novo")
    await hooks.readTick()
    await hooks.flush()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: false, send: [{ id: "D1", chat: "Maria", text: "Oi!" }] } }
    await hooks.pollTick()
    expect(api("/wa/device/inbound")).toHaveLength(0)
    expect(api("/wa/device/sent")).toHaveLength(0)
    boot({ paired: false })
    await hooks.refreshState()
    await hooks.readTick()
    await hooks.pollTick()
    expect(api("/wa/device/inbound")).toHaveLength(0)
    expect(api("/wa/device/poll")).toHaveLength(0)
  })

  it("se o Jefrey mandar pausar, nada e enviado", async () => {
    page({ title: "Maria", rows: [{ id: "A", text: "oi" }] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: true, status: 200, data: { paused: true, send: [{ id: "D1", chat: "Maria", text: "Oi!" }] } }
    await hooks.pollTick()
    expect(api("/wa/device/sent")).toHaveLength(0)
  })

  it("grupo: avisa que e grupo (o Jefrey ignora)", async () => {
    page({ group: true, rows: [{ id: "A", text: "bom dia grupo" }] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    expect(api("/wa/device/inbound")[0].body.is_group).toBe(true)
  })

  it("o codigo da extensao nao toca em nada fora do WhatsApp e nao guarda mensagens", () => {
    for (const src of [CORE_SRC, CONTENT_SRC]) {
      expect(src).not.toMatch(/localStorage|sessionStorage|indexedDB|document\.cookie|eval\(|new Function|innerHTML\s*=/)
    }
    const manifest = JSON.parse(fs.readFileSync(path.join(DIR, "manifest.json"), "utf8"))
    expect(manifest.content_scripts[0].matches).toEqual(["https://web.whatsapp.com/*"])
    expect(manifest.host_permissions.every(h => h.startsWith("http://127.0.0.1") || h.startsWith("http://localhost"))).toBe(true)
    expect(manifest.permissions).toEqual(["storage"])
  })
})
