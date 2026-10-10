import { useEffect, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useSpeaker } from "@/hooks/useSpeaker"
import { useListener } from "@/hooks/useListener"
import { putProfile, skipWelcome } from "@/lib/llm"
import { setEasy } from "@/lib/easy"
import { initial, nextStep, script, type State } from "@/lib/primeiraVez"

const btn = "jf-btn jf-focus px-6 py-4 text-xl"
const soft = "jf-focus rounded-xl border border-white/25 px-6 py-4 text-xl text-white/90 hover:bg-white/5"

/** Primeira abertura conduzida por voz: o Jefrey pergunta, a pessoa responde falando (ou tocando). Nunca trava. */
export default function PrimeiraVez() {
  const nav = useNavigate()
  const speaker = useSpeaker()
  const [s, setS] = useState<State>(initial())
  const [typed, setTyped] = useState("")
  const [note, setNote] = useState("")
  const spokenFor = useRef<string>("")
  const said = useRef(false)

  const listener = useListener({
    onTranscript: text => answer(text),
    onUnclear: () => setNote("Não entendi. Pode repetir, ou toque em uma das opções?"),
  })

  function finish(goBrain: boolean) {
    skipWelcome()
    setEasy(true) // quem passa por aqui comeca com letras grandes e botoes grandes
    if (goBrain) nav("/conexoes?aba=cerebros", { replace: true }) // 9router ou Gemini: a pessoa cola a chave ali
    else nav("/", { replace: true })
  }

  function answer(text: string) {
    setNote("")
    const next = nextStep(s, text)
    if (s.step === "nome" && next.name && next.name !== s.name) void putProfile(next.name)
    setS(next)
    if (next.step === "experimente" && next.brain === "agora") {
      speaker.say("Vou abrir o site para você entrar. Depois é só voltar para cá.")
      window.setTimeout(() => finish(true), 3500)
      return
    }
    if (next.done) finish(false)
  }

  // fala a pergunta de cada passo uma vez
  useEffect(() => {
    const key = `${s.step}:${s.misses}`
    if (s.done || spokenFor.current === key) return
    spokenFor.current = key
    said.current = false
    speaker.say(s.misses > 0 ? "Desculpe, não entendi. " + script(s.step, s.name) : script(s.step, s.name))
  }, [s.step, s.misses, s.name, s.done])

  // quando ele termina de falar, passa a ouvir (sem precisar tocar em nada)
  useEffect(() => {
    if (speaker.speaking) said.current = true
    if (said.current && !speaker.speaking && !s.done && listener.state === "idle" && listener.supported) void listener.start()
  }, [speaker.speaking, s.done, listener.state, listener.supported])

  const text = s.done ? script("fim", s.name) : script(s.step, s.name)
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 p-4 text-center">
      <p className="text-3xl font-semibold leading-snug text-white" aria-live="polite">{text}</p>
      {note && <p role="status" className="text-lg text-amber-200">{note}</p>}
      <p className="text-lg text-white/70">
        {listener.state === "listening" || listener.state === "hearing" ? "Estou ouvindo…" : listener.state === "transcribing" ? "Entendendo…" : "Fale ou escolha abaixo."}
      </p>

      {s.step === "nome" && (
        <form className="flex w-full max-w-md gap-2" onSubmit={e => { e.preventDefault(); if (typed.trim()) answer(typed) }}>
          <input aria-label="Seu nome" className="min-w-0 flex-1 rounded-xl border border-white/20 bg-black/30 px-4 py-4 text-xl text-white" placeholder="Seu nome" value={typed} onChange={e => setTyped(e.target.value)} />
          <button type="submit" className={btn}>Pronto</button>
        </form>
      )}
      {s.step === "cerebro" && (
        <div className="flex flex-wrap justify-center gap-3">
          <button type="button" className={btn} onClick={() => answer("sim")}>Sim, ligar agora</button>
          <button type="button" className={soft} onClick={() => answer("depois")}>Depois</button>
        </div>
      )}
      {s.step === "experimente" && (
        <div className="flex flex-wrap justify-center gap-3">
          <button type="button" className={btn} onClick={() => answer("pronto")}>Entendi, vamos conversar</button>
        </div>
      )}

      {listener.supported && listener.state === "idle" && !s.done && (
        <button type="button" className={soft} onClick={() => void listener.start()}>Toque para falar</button>
      )}
      {listener.error && <p role="alert" className="text-lg text-red-200">{listener.error}</p>}
      <Link to="/bem-vindo" className="text-base text-white/60 underline" onClick={() => { speaker.cancel(); listener.stop() }}>Prefiro fazer sem voz</Link>
    </div>
  )
}

