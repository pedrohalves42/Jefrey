import { describe, expect, it } from "vitest"
import { SseParser } from "../sse"

const ev = (o: object) => `data: ${JSON.stringify(o)}\n\n`

describe("SseParser", () => {
  it("le tokens e fim em um unico pedaco", () => {
    const p = new SseParser()
    const out = p.push(ev({ type: "token", content: "Ol" }) + ev({ type: "token", content: "a" }) + ev({ type: "done", thread_id: "t1" }))
    expect(out).toEqual([
      { type: "token", content: "Ol" },
      { type: "token", content: "a" },
      { type: "done", thread_id: "t1" },
    ])
  })

  it("junta um evento partido em varios pedacos", () => {
    const p = new SseParser()
    const full = ev({ type: "token", content: "Olá, mundo" })
    const a = p.push(full.slice(0, 10))
    const b = p.push(full.slice(10, 25))
    const c = p.push(full.slice(25))
    expect([...a, ...b, ...c]).toEqual([{ type: "token", content: "Olá, mundo" }])
  })

  it("aceita CRLF", () => {
    const p = new SseParser()
    expect(p.push('data: {"type":"token","content":"x"}\r\n\r\n')).toEqual([{ type: "token", content: "x" }])
  })

  it("ignora lixo e JSON invalido sem quebrar", () => {
    const p = new SseParser()
    const out = p.push("data: {nao e json}\n\n: comentario\n\ndata: [1,2]\n\n" + ev({ type: "token", content: "ok" }))
    expect(out).toEqual([{ type: "token", content: "ok" }])
  })

  it("ignora tipos desconhecidos e token sem texto", () => {
    const p = new SseParser()
    expect(p.push(ev({ type: "xyz" }) + ev({ type: "token" }))).toEqual([])
  })

  it("entrega erro e aprovacao pendente", () => {
    const p = new SseParser()
    expect(p.push(ev({ type: "error", message: "falhou" }) + ev({ type: "pending_approval", approval_id: "a1", thread_id: "t" }))).toEqual([
      { type: "error", message: "falhou" },
      { type: "pending_approval", approval_id: "a1", thread_id: "t" },
    ])
  })

  it("flush recupera o ultimo evento sem linha em branco final", () => {
    const p = new SseParser()
    expect(p.push('data: {"type":"done"}')).toEqual([])
    expect(p.flush()).toEqual([{ type: "done", thread_id: undefined }])
    expect(p.flush()).toEqual([])
  })

  it("preserva acentos e quebras de linha no token", () => {
    const p = new SseParser()
    expect(p.push(ev({ type: "token", content: "ação\nnova" }))).toEqual([{ type: "token", content: "ação\nnova" }])
  })

  it("entende eventos de ferramenta e de aprovacao", () => {
    const p = new SseParser()
    const out = p.push(
      ev({ type: "tool_start", tool: "save_note", label: "Salvar nota", risk: "low" }) +
        ev({ type: "approval_required", approval_id: "a1", tool: "delete_note", label: "Apagar nota", risk: "high" }) +
        ev({ type: "tool_end", tool: "save_note", ok: true, status: "ok", summary: "salvo" }),
    )
    expect(out).toEqual([
      { type: "tool_start", tool: "save_note", label: "Salvar nota", risk: "low" },
      { type: "approval_required", approval_id: "a1", tool: "delete_note", label: "Apagar nota", risk: "high" },
      { type: "tool_end", tool: "save_note", ok: true, status: "ok", summary: "salvo" },
    ])
  })

  it("descarta eventos de ferramenta malformados", () => {
    const p = new SseParser()
    expect(p.push(ev({ type: "tool_start" }) + ev({ type: "approval_required", tool: "x" }) + ev({ type: "tool_end", ok: true }))).toEqual([])
  })

  it("entende 'Lembrei de' e descarta itens ruins, sem confiar no formato", () => {
    const p = new SseParser()
    const out = p.push(
      ev({ type: "recall", items: [{ kind: "fato", text: "Mora em Curitiba." }, { kind: "hacker", text: "x" }, { kind: "diario", text: "  " }, 5, null, { kind: "lembranca", text: "a".repeat(500) }] }),
    )
    expect(out).toHaveLength(1)
    const items = (out[0] as { items: { kind: string; text: string }[] }).items
    expect(items.map(i => i.kind)).toEqual(["fato", "lembranca"])
    expect(items[1]!.text.length).toBe(160)
    expect(p.push(ev({ type: "recall", items: "nada" }) + ev({ type: "recall" }))).toEqual([])
  })

  it("tool_end so e ok quando ok === true (nao confia em valores truthy)", () => {
    const p = new SseParser()
    expect(p.push(ev({ type: "tool_end", tool: "x", ok: "true", status: "ok", summary: "" }))).toEqual([
      { type: "tool_end", tool: "x", ok: false, status: "ok", summary: "" },
    ])
  })
})
