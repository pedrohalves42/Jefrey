import { useEffect, useState } from "react"
import { isDesktop } from "@/lib/shell"
import {
  POST_NETWORKS, PUBLISH_NETWORKS, THEMES, createCarousel, createPost, getNetworks, openCarouselFolder, openNetwork, publishPost, type CarouselResult, type Network,
} from "@/lib/social"

const card = "jf-panel p-5"
const field = "w-full rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white placeholder:text-white/30"
const big = "jf-btn jf-focus px-5 py-3 text-base"

type Msg = { ok: boolean; text: string } | null

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return <p role={msg.ok ? "status" : "alert"} className={`mt-3 rounded-lg border px-3 py-2 text-base ${msg.ok ? "border-emerald-400/40 text-emerald-100" : "border-red-400/40 text-red-100"}`}>{msg.text}</p>
}

/** Publicar de verdade: a pessoa escolhe a rede, ve o texto e confirma. O Jefrey limita o ritmo (5 por dia, 10 min entre posts). */
function PublishBox({ text, folder, networks }: { text: string; folder?: string; networks: { id: string; label: string }[] }) {
  const [net, setNet] = useState(networks[0]!.id)
  const [step, setStep] = useState<"idle" | "confirm" | "busy">("idle")
  const [msg, setMsg] = useState<Msg>(null)
  const label = networks.find(n => n.id === net)?.label ?? net
  async function go() {
    setStep("busy")
    setMsg(null)
    const r = await publishPost(net, text, folder ?? "")
    setStep("idle")
    setMsg(r.data?.ok ? { ok: true, text: r.data.message } : { ok: false, text: r.error || "Não consegui publicar agora." })
  }
  return (
    <div className="mt-4 rounded-xl border border-amber-300/30 p-4">
      <p className="text-base text-white/85">Publicar de verdade pelo Jefrey (a rede precisa estar aberta e com a sua conta em Conexões → Redes).</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <select className={`${field} max-w-[14rem]`} value={net} onChange={e => { setNet(e.target.value); setStep("idle") }} aria-label="Rede">
          {networks.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
        </select>
        {step === "idle" && <button type="button" className={big} onClick={() => setStep("confirm")}>Publicar no {label}</button>}
        {step === "busy" && <span className="text-base text-white/70">Publicando… acompanhe na janela do {label}.</span>}
      </div>
      {step === "confirm" && (
        <div className="mt-3 rounded-lg border border-white/15 p-3" role="alertdialog" aria-label="Confirmar publicação">
          <p className="text-base text-white">Vou publicar no <b>{label}</b>{folder ? ", com as imagens do carrossel" : ""}:</p>
          <p className="mt-1 whitespace-pre-wrap text-base text-white/85">“{text || "(só as imagens)"}”</p>
          <div className="mt-3 flex gap-3">
            <button type="button" className={big} onClick={() => void go()}>Sim, publicar</button>
            <button type="button" className={`${big} border-white/25`} onClick={() => setStep("idle")}>Cancelar</button>
          </div>
        </div>
      )}
      <Note msg={msg} />
    </div>
  )
}

function Janelas() {
  const [nets, setNets] = useState<Network[]>([])
  const [msg, setMsg] = useState<Msg>(null)
  useEffect(() => {
    const load = () => void getNetworks().then(r => r.data && setNets(r.data.networks))
    load()
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [])
  async function open(n: Network) {
    const r = await openNetwork(n.id)
    setMsg(r.ok ? { ok: true, text: `Abri o ${n.name}. Entre na sua conta uma vez; o login fica guardado.` } : { ok: false, text: "Isso só funciona no programa instalado do Jefrey." })
  }
  return (
    <section className={card} aria-labelledby="r-janelas">
      <h2 id="r-janelas" className="text-xl font-medium text-white">Suas redes aqui dentro</h2>
      <p className="mt-2 text-base text-white/70">Cada rede abre numa janela do Jefrey, sem navegador. Você entra uma vez e o login fica guardado. O Jefrey só conta o que há de novo; ele <b>não</b> responde nem posta sozinho (as redes bloqueiam contas que usam robô).</p>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {nets.map(n => (
          <li key={n.id} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 p-3">
            <span className="text-lg text-white">{n.name}{n.unread > 0 && <span className="ml-2 rounded-full bg-cyan-400/20 px-2 py-0.5 text-sm text-cyan-100">{n.unread} novas</span>}</span>
            <button type="button" className={`${big} py-2`} onClick={() => void open(n)} disabled={!isDesktop()}>Abrir</button>
          </li>
        ))}
      </ul>
      {!isDesktop() && <p className="mt-3 text-sm text-white/55">Abra o Jefrey pelo programa instalado para usar as janelas.</p>}
      <Note msg={msg} />
    </section>
  )
}

function Carrossel() {
  const [topic, setTopic] = useState("")
  const [slides, setSlides] = useState(6)
  const [theme, setTheme] = useState("escuro")
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<CarouselResult | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  async function go() {
    setBusy(true)
    setMsg(null)
    setRes(null)
    const r = await createCarousel(topic.trim(), slides, theme)
    setBusy(false)
    if (r.data) setRes(r.data)
    else setMsg({ ok: false, text: r.error })
  }
  return (
    <section className={card} aria-labelledby="r-carrossel">
      <h2 id="r-carrossel" className="text-xl font-medium text-white">Criar carrossel</h2>
      <p className="mt-2 text-base text-white/70">Diga o assunto. O Jefrey escreve os slides, desenha as imagens prontas e sugere a legenda. Você só publica.</p>
      <label className="mt-3 block text-base text-white/85">Assunto
        <input className={`${field} mt-1`} value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: 5 dicas para economizar na conta de luz" maxLength={300} />
      </label>
      <div className="mt-3 flex flex-wrap gap-4">
        <label className="text-base text-white/85">Slides
          <select className={`${field} mt-1`} value={slides} onChange={e => setSlides(Number(e.target.value))}>
            {[3, 4, 5, 6, 7, 8, 9, 10].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label className="text-base text-white/85">Cores
          <select className={`${field} mt-1`} value={theme} onChange={e => setTheme(e.target.value)}>
            {THEMES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </label>
      </div>
      <button type="button" className={`${big} mt-3`} onClick={() => void go()} disabled={busy || topic.trim().length < 3}>{busy ? "Criando… (leva uns segundos)" : "Criar carrossel"}</button>
      <Note msg={msg} />
      {res && (
        <div className="mt-4 rounded-xl border border-white/10 p-4">
          <h3 className="text-lg font-medium text-white">{res.title}</h3>
          <ol className="mt-2 list-decimal space-y-1 pl-6 text-base text-white/85">
            {res.slides.map((s, i) => <li key={i}><b>{s.title}</b>{s.body ? ` — ${s.body}` : ""}</li>)}
          </ol>
          {res.caption && <p className="mt-3 text-base text-white/80"><b>Legenda:</b> {res.caption} {res.hashtags.join(" ")}</p>}
          <p className="mt-3 break-all text-sm text-white/55">{res.files.length} imagens em {res.folder}</p>
          <button type="button" className={`${big} mt-3`} onClick={() => void openCarouselFolder(res.folder)}>Abrir a pasta das imagens</button>
          <PublishBox text={[res.caption, res.hashtags.join(" ")].join(" ").trim()} folder={res.folder} networks={PUBLISH_NETWORKS} />
        </div>
      )}
    </section>
  )
}

function Post() {
  const [net, setNet] = useState("instagram")
  const [topic, setTopic] = useState("")
  const [busy, setBusy] = useState(false)
  const [text, setText] = useState("")
  const [msg, setMsg] = useState<Msg>(null)
  async function go() {
    setBusy(true)
    setMsg(null)
    const r = await createPost(net, topic.trim())
    setBusy(false)
    if (r.data) setText(r.data.text)
    else setMsg({ ok: false, text: r.error })
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setMsg({ ok: true, text: "Copiado. É só colar na rede." })
    } catch {
      setMsg({ ok: false, text: "Não consegui copiar. Selecione o texto e copie." })
    }
  }
  return (
    <section className={card} aria-labelledby="r-post">
      <h2 id="r-post" className="text-xl font-medium text-white">Escrever um post</h2>
      <div className="mt-3 flex flex-wrap gap-4">
        <label className="text-base text-white/85">Rede
          <select className={`${field} mt-1`} value={net} onChange={e => setNet(e.target.value)}>
            {POST_NETWORKS.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </label>
        <label className="min-w-[16rem] flex-1 text-base text-white/85">Assunto
          <input className={`${field} mt-1`} value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: promoção de sábado na minha loja" maxLength={400} />
        </label>
      </div>
      <button type="button" className={`${big} mt-3`} onClick={() => void go()} disabled={busy || topic.trim().length < 3}>{busy ? "Escrevendo…" : "Escrever o post"}</button>
      {text && (
        <div className="mt-3">
          <textarea className={`${field} min-h-[8rem]`} value={text} onChange={e => setText(e.target.value)} aria-label="Texto do post" />
          <button type="button" className={`${big} mt-2`} onClick={() => void copy()}>Copiar o texto</button>
          {PUBLISH_NETWORKS.some(n => n.id === net) && <PublishBox key={net} text={text} networks={PUBLISH_NETWORKS.filter(n => n.id === net)} />}
        </div>
      )}
      <Note msg={msg} />
    </section>
  )
}

export default function Redes() {
  return (
    <div className="space-y-4">
      <Janelas />
      <Carrossel />
      <Post />
    </div>
  )
}
