import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { BRIEFING_HOURS, getBriefing, putBriefingPrefs, type BriefingPrefs } from "@/lib/briefing"
import { useEasy } from "@/lib/easy"

const TOPICS: { title: string; text: string }[] = [
  { title: "Como falar com o Jefrey", text: "Aperte o botão do microfone na tela de Conversa e fale normalmente, como se falasse com uma pessoa. Quando você terminar, o Jefrey responde falando." },
  { title: "O que posso pedir", text: "Peça lembretes, como “me lembra de tomar o remédio às oito da noite”. Peça para guardar uma anotação. Pergunte as horas, o tempo, ou qualquer dúvida do dia a dia." },
  { title: "Se ele não entender", text: "Fale mais devagar e perto do microfone, ou escreva na caixa de texto. Se a resposta estiver errada, diga “não é isso” e explique de novo." },
  { title: "Conectar as suas contas", text: "Na tela de Conexões você liga o Jefrey à inteligência que responde e ao seu Google. Em cada uma é só apertar o botão, entrar na sua conta e voltar." },
  { title: "Para fechar o Jefrey", text: "Procure o ícone do Jefrey perto do relógio do Windows, clique com o botão direito e escolha Sair." },
]

function MorningSettings() {
  const [p, setP] = useState<BriefingPrefs | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    void getBriefing().then(r => setP(r.data?.prefs ?? null))
  }, [])
  async function save(change: Partial<BriefingPrefs>) {
    const r = await putBriefingPrefs(change)
    if (r.ok && r.data) {
      setP(r.data)
      setErr(null)
    } else setErr("Não consegui mudar isso agora. Tente de novo.")
  }
  if (!p) return null
  const field = "rounded-lg border border-white/15 bg-black/30 px-3 py-3 text-base text-white"
  return (
    <section className="jf-panel p-5" aria-labelledby="h-manha">
      <h2 id="h-manha" className="text-xl font-medium text-white">Resumo da manhã</h2>
      <p className="mt-2 text-base text-white/80">
        De manhã eu preparo um resumo com os seus lembretes do dia e o que eu estudei. Ele aparece na tela de Conversa.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-base text-white/85">
          <input type="checkbox" className="h-5 w-5" checked={p.enabled} onChange={e => void save({ enabled: e.target.checked })} />
          Preparar o resumo
        </label>
        <label className="text-base text-white/85">
          Horário
          <select className={`${field} ml-2`} value={p.hour} onChange={e => void save({ hour: Number(e.target.value) })}>
            {BRIEFING_HOURS.map(h => <option key={h} value={h}>{String(h).padStart(2, "0")}h</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-base text-white/85">
          <input type="checkbox" className="h-5 w-5" checked={p.notify} onChange={e => void save({ notify: e.target.checked })} />
          Avisar no Windows
        </label>
      </div>
      {err && <p role="alert" className="mt-2 text-base text-red-200">{err}</p>}
    </section>
  )
}

export default function Ajuda() {
  const [easy, setEasy] = useEasy()
  const all = TOPICS.map(t => `${t.title}. ${t.text}`).join(" ")
  return (
    <div className="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto pb-8">
      <header>
        <h1 className="text-3xl font-semibold text-white">Ajuda</h1>
        <p className="mt-1 text-base text-white/70">Respostas rápidas. Aperte “Ouvir” para o Jefrey ler para você.</p>
        <div className="mt-3">
          <ListenButton text={all} label="Ouvir toda a ajuda" />
        </div>
      </header>

      {TOPICS.map(t => (
        <section key={t.title} className="jf-panel p-5">
          <h2 className="text-xl font-medium text-white">{t.title}</h2>
          <p className="mt-2 text-base text-white/80">{t.text}</p>
          <div className="mt-3">
            <ListenButton text={`${t.title}. ${t.text}`} />
          </div>
        </section>
      ))}

      <MorningSettings />

      <section className="jf-panel p-5">
        <h2 className="text-xl font-medium text-white">Letra grande e menu simples</h2>
        <p className="mt-2 text-base text-white/80">
          {easy ? "Está ligado: letra grande e só o essencial no menu." : "Está desligado: aparecem mais opções no menu."}
        </p>
        <button type="button" onClick={() => setEasy(!easy)} aria-pressed={easy} className="jf-btn jf-focus mt-3 px-5 py-3 text-base">
          {easy ? "Mostrar mais opções" : "Voltar ao modo simples"}
        </button>
        {easy && (
          <p className="mt-3 text-sm text-white/60">
            Para mudar o seu nome ou a aparência do Jefrey, <Link className="underline" to="/configuracoes" onClick={() => setEasy(false)}>abra as Configurações</Link>.
          </p>
        )}
      </section>
    </div>
  )
}
