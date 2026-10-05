// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import axe from "axe-core"
import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import PrimeiraVez from "../pages/PrimeiraVez"
import Skills from "../pages/Skills"
import Aprender from "../pages/Aprender"
import Conexoes from "../pages/Conexoes"
import VoiceDownload from "../components/VoiceDownload"
import { UpdateBanner } from "../components/UpdateBanner"
import ReportProblem from "../components/ReportProblem"

let root: Root | null = null
let box: HTMLDivElement

beforeEach(() => {
  box = document.createElement("div")
  document.body.appendChild(box)
  // todas as chamadas a API devolvem um JSON vazio e simples: o que importa aqui e a estrutura da tela
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ skills: [], catalog: [], brains: [], sources: [], topics: [], engines: [], devices: [], routines: [] }), { status: 200, headers: { "content-type": "application/json" } })))
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }))
})

afterEach(() => {
  act(() => root?.unmount())
  root = null
  box.remove()
  vi.unstubAllGlobals()
})

async function mount(el: ReactElement) {
  root = createRoot(box)
  await act(async () => {
    root!.render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>{el}</MemoryRouter>
      </QueryClientProvider>,
    )
  })
  await act(async () => {
    await new Promise(r => setTimeout(r, 30))
  })
}

async function violations() {
  // jsdom nao calcula layout: contraste e regioes dependem de renderizacao real e ficam para a revisao manual
  const r = await axe.run(box, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } })
  return r.violations.filter(v => v.impact === "serious" || v.impact === "critical").map(v => `${v.id}: ${v.nodes[0]?.html.slice(0, 120)}`)
}

describe("acessibilidade (axe, sem violacoes serias ou criticas)", () => {
  const screens: [string, () => ReactElement][] = [
    ["Primeira vez", () => <PrimeiraVez />],
    ["Skills", () => <Skills />],
    ["Aprender", () => <Aprender />],
    ["Conexoes", () => <Conexoes />],
    ["Voz natural", () => <VoiceDownload />],
    ["Aviso de atualizacao", () => <UpdateBanner />],
    ["Algo deu errado", () => <ReportProblem />],
  ]
  for (const [name, el] of screens) {
    it(name, async () => {
      await mount(el())
      expect(await violations()).toEqual([])
    })
  }

  it("todo botao e campo tem nome para o leitor de tela", async () => {
    await mount(<PrimeiraVez />)
    const semNome = [...box.querySelectorAll("button, input, select, textarea, a[href]")].filter(e => {
      const label = (e.getAttribute("aria-label") || e.textContent || "").trim()
      const labelled = e.id && box.querySelector(`label[for="${e.id}"]`)
      return !label && !labelled && !e.getAttribute("placeholder") && !e.closest("label")
    })
    expect(semNome.map(e => e.outerHTML.slice(0, 80))).toEqual([])
  })
})

describe("o proprio teste enxerga problemas (prova de que nao e um teste vazio)", () => {
  it("botao sem nome e imagem sem texto alternativo sao apanhados", async () => {
    await mount(
      <div>
        <button type="button" />
        <img src="x.png" />
      </div>,
    )
    const v = await violations()
    expect(v.some(x => x.startsWith("button-name"))).toBe(true)
    expect(v.some(x => x.startsWith("image-alt"))).toBe(true)
  })
})
