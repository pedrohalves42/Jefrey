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

  it("digita no campo e confere o texto", async () => {
    page()
    expect(await C.typeText(document, "Oi! Tudo certo por aqui.", () => Promise.resolve())).toBe(true)
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
        id: "jefrey-test",
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

  it("extensao recarregada com a aba aberta: para sozinho, avisa para recarregar e nao enche o console de erros", async () => {
    page({ title: "Maria", rows: [{ id: "A", text: "oi" }] })
    boot()
    await hooks.refreshState()
    window.chrome.runtime.id = undefined // o contexto antigo morreu
    window.chrome.runtime.sendMessage = vi.fn(async () => {
      throw new Error("Extension context invalidated.")
    })
    await expect(hooks.refreshState()).resolves.toBeUndefined()
    await expect(hooks.pollTick()).resolves.toBeUndefined()
    expect([...document.querySelectorAll("div[title^='Clique para pausar']")].some(b => b.textContent.includes("Recarregue a página"))).toBe(true)
    expect(window.chrome.runtime.sendMessage).not.toHaveBeenCalled() // depois de morto nem tenta falar com a extensao
  })

  it("o Jefrey nao conhece mais este aparelho (401): para de insistir e mostra nao pareado", async () => {
    page({ title: "Maria", rows: [{ id: "A", text: "oi" }] })
    boot()
    await hooks.refreshState()
    respostas["/wa/device/poll"] = { ok: false, status: 401, data: null }
    await hooks.pollTick()
    expect(hooks.state().paired).toBe(false)
    expect([...document.querySelectorAll("div[title^='Clique para pausar']")].some(b => b.textContent.includes("não pareado"))).toBe(true)
    const antes = api("/wa/device/poll").length
    await hooks.pollTick() // pareamento desfeito: nem tenta de novo
    expect(api("/wa/device/poll").length).toBe(antes)
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

describe("lista de conversas, historico e conversa comigo mesmo", () => {
  let C
  beforeEach(() => {
    C = loadCore()
  })

  const cell = (name, preview, unread = 0, time = "10:32", icon = "") =>
    `<div role="listitem"><span title="${name}">${name}</span><span dir="ltr">${time}</span><span dir="ltr" title="${preview}">${preview}</span>${
      unread ? `<span aria-label="${unread} mensagens não lidas">${unread}</span>` : ""
    }${icon}</div>`

  it("le quem escreveu, a previa e as nao lidas sem abrir nada", () => {
    document.body.innerHTML = `<div id="side"><div id="pane-side">${cell("Maria", "vamos jantar?", 2)}${cell("José", "ok, valeu", 0, "ontem")}${cell("Família", "foto", 5, "09:00", '<span data-icon="default-group"></span>')}</div></div>`
    const items = C.parseSidebar(document)
    expect(items.map(i => [i.title, i.preview, i.unread, i.group])).toEqual([
      ["Maria", "vamos jantar?", 2, false],
      ["José", "ok, valeu", 0, false],
      ["Família", "foto", 5, true],
    ])
  })

  it("grupo pela previa 'Fulano: texto' e pelo marcador do WhatsApp de hoje", () => {
    expect(C.looksLikeGroupPreview("Ana: bom dia")).toBe(true)
    expect(C.looksLikeGroupPreview("Você: bom dia")).toBe(false)
    expect(C.looksLikeGroupPreview("You: ok")).toBe(false)
    expect(C.looksLikeGroupPreview("bom dia, tudo bem?")).toBe(false)
    document.body.innerHTML = `<div id="side"><div id="pane-side">
      <div data-testid="cell-frame-container"><span title="Promo"></span><div data-testid="last-msg-status"><span dir="ltr">Loja X: oferta de hoje</span></div><span data-testid="icon-unread-count" aria-label="3 mensagens não lidas">3</span></div>
      <div data-testid="cell-frame-container"><span title="Arnaldo"></span><div data-testid="last-msg-status"><span dir="ltr">chego às 8</span></div></div></div></div>`
    const items = C.parseSidebar(document)
    expect(items.map(i => [i.title, i.group, i.unread])).toEqual([["Promo", true, 3], ["Arnaldo", false, 0]])
    expect(items[1].preview).toBe("chego às 8")
  })

  it("reconhece a conversa comigo mesmo e as respostas do proprio Jefrey", () => {
    expect(C.isSelfChat("Pedro (Você)")).toBe(true)
    expect(C.isSelfChat("Pedro (You)")).toBe(true)
    expect(C.isSelfChat("Pedro")).toBe(false)
    expect(C.isBotText("🤖 São 10 horas")).toBe(true)
    expect(C.isBotText("São 10 horas")).toBe(false)
    page({ title: "Pedro (Você)", rows: [{ id: "A", text: "que horas são?", me: true }, { id: "B", text: "🤖 São 10 horas", me: true }, { id: "C", text: "oi", me: false }] })
    const rows = C.parseRows(document)
    expect(C.newCommands(rows, new Set()).map(r => r.text)).toEqual(["que horas são?"])
  })
})

describe("extensao: caixa de entrada, historico e comandos", () => {
  let calls, hooks
  function boot() {
    calls = []
    window.__jefreyWA = false
    window.__JEFREY_WA_TEST__ = { sleep: () => Promise.resolve(), idleMs: 0 }
    window.chrome = {
      runtime: {
        id: "jefrey-test",
        sendMessage: vi.fn(async msg => {
          calls.push(msg)
          if (msg.type === "status") return { paired: true, paused: false }
          if (msg.type === "api") return { ok: true, status: 200, data: msg.path === "/wa/device/command" ? { action: "working" } : {} }
          return { ok: true }
        }),
      },
    }
    loadCore()
    window.eval(CONTENT_SRC)
    hooks = window.__JEFREY_WA_TEST__.hooks
  }
  const api = path => calls.filter(c => c.type === "api" && c.path === path)

  it("manda a lista de conversas uma vez e de novo so quando muda", async () => {
    page({ chats: ["Maria", "José"], rows: [] })
    document.querySelector("#pane-side").innerHTML =
      '<div role="listitem"><span title="Maria">Maria</span><span dir="ltr" title="oi">oi</span><span aria-label="1 mensagem não lida">1</span></div>'
    boot()
    await hooks.refreshState()
    await hooks.inboxTick()
    await hooks.inboxTick()
    expect(api("/wa/device/inbox")).toHaveLength(1)
    expect(api("/wa/device/inbox")[0].body.items[0]).toMatchObject({ title: "Maria", unread: 1, preview: "oi" })
    document.querySelector("#pane-side span[aria-label]").setAttribute("aria-label", "3 mensagens não lidas")
    await hooks.inboxTick()
    expect(api("/wa/device/inbox")).toHaveLength(2)
  })

  it("manda o historico da conversa aberta (nao de grupo)", async () => {
    page({ rows: [{ id: "A", text: "bom dia" }, { id: "B", text: "bom dia!", me: true }] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    await Promise.resolve()
    const h = api("/wa/device/history")
    expect(h).toHaveLength(1)
    expect(h[0].body.messages.map(m => m.text)).toEqual(["bom dia", "bom dia!"])
    page({ group: true, title: "Família", rows: [{ id: "G", text: "oi grupo" }] })
    await hooks.readTick()
    await Promise.resolve()
    expect(api("/wa/device/history")).toHaveLength(1)
  })

  it("conversa comigo mesmo: o que antes ja estava la e ignorado; o pedido novo vai ao Jefrey uma vez", async () => {
    page({ title: "Pedro (Você)", rows: [{ id: "A", text: "pedido antigo", me: true }] })
    boot()
    await hooks.refreshState()
    await hooks.readTick()
    expect(api("/wa/device/command")).toHaveLength(0)
    const div = document.createElement("div")
    div.setAttribute("data-id", "true_5511999999999@c.us_NOVA")
    div.innerHTML = '<span class="selectable-text copyable-text">que horas são?</span>'
    document.querySelector(".messages").appendChild(div)
    await hooks.readTick()
    await hooks.readTick()
    const cmds = api("/wa/device/command")
    expect(cmds).toHaveLength(1)
    expect(cmds[0].body).toMatchObject({ chat: "Pedro (Você)", text: "que horas são?" })
    expect(api("/wa/device/inbound").every(c => c.body.messages.length === 0)).toBe(true) // nunca "responde como a pessoa" a si mesma
  })
})

describe("editor do WhatsApp que atualiza o texto um instante depois (Lexical)", () => {
  let C
  beforeEach(() => {
    C = loadCore()
  })

  function lexicalPage() {
    document.body.innerHTML = `<div id="main"><header><span dir="auto" title="ph">ph</span></header>
      <footer><div contenteditable="true" data-tab="10"><p><br></p></div><button aria-label="Enviar"></button></footer></div>`
    return document.querySelector("footer div[contenteditable]")
  }
  const showAfter = (el, text, ms) =>
    setTimeout(() => {
      el.innerHTML = `<p><span data-lexical-text="true">${text.replace("🙂", "")}</span><span data-lexical-text="true">🙂</span></p>`
    }, ms)

  it("espera o editor mostrar o texto e NAO digita duas vezes", async () => {
    const el = lexicalPage()
    let chamadas = 0
    document.execCommand = () => {
      chamadas++
      showAfter(el, "Oi, tudo bem? 🙂", 120) // o editor so mostra depois
      return true
    }
    expect(await C.typeText(document, "Oi, tudo bem? 🙂")).toBe(true)
    expect(chamadas).toBe(1)
    expect(C.readText(el)).toBe("Oi, tudo bem? 🙂") // so uma vez, mesmo com o emoji repetido dentro do span
  })

  it("se o texto nunca aparece, limpa o campo e devolve falso (nao deixa rascunho)", async () => {
    const el = lexicalPage()
    document.execCommand = () => true // diz que digitou, mas nada aparece
    Object.defineProperty(el, "textContent", { get: () => "", set: () => {}, configurable: true }) // e o editor ignora a troca direta do texto
    expect(await C.typeText(document, "Oi", () => Promise.resolve())).toBe(false)
    expect(C.readText(el)).toBe("")
  })

  it("leitura do campo ignora o texto de dica e conta so o que a pessoa ve", () => {
    const el = lexicalPage()
    el.innerHTML = '<p><span data-lexical-text="true">abc</span></p><span>Digite uma mensagem</span>'
    expect(C.readText(el)).toBe("abc")
    expect(C.composerText(document)).toBe("abc")
  })
})
