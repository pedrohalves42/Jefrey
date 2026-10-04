import { Link } from "react-router-dom"
import ListenButton from "@/components/ListenButton"
import { useEasy } from "@/lib/easy"

const TOPICS: { title: string; text: string }[] = [
  { title: "Como falar com o Jefrey", text: "Aperte o botão do microfone na tela de Conversa e fale normalmente, como se falasse com uma pessoa. Quando você terminar, o Jefrey responde falando." },
  { title: "O que posso pedir", text: "Peça lembretes, como “me lembra de tomar o remédio às oito da noite”. Peça para guardar uma anotação. Pergunte as horas, o tempo, ou qualquer dúvida do dia a dia." },
  { title: "Se ele não entender", text: "Fale mais devagar e perto do microfone, ou escreva na caixa de texto. Se a resposta estiver errada, diga “não é isso” e explique de novo." },
  { title: "Conectar as suas contas", text: "Na tela de Conexões você liga o Jefrey à inteligência que responde e ao seu Google. Em cada uma é só apertar o botão, entrar na sua conta e voltar." },
  { title: "Para fechar o Jefrey", text: "Procure o ícone do Jefrey perto do relógio do Windows, clique com o botão direito e escolha Sair." },
]

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
