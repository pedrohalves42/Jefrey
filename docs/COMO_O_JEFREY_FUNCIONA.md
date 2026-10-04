# Como o Jefrey funciona, por inteiro

Texto para entender o produto de ponta a ponta. Marcamos o que **já funciona**, o que está **em construção** (sessões do plano) e o
que **ainda não existe**.

## 1. A ideia em uma frase
Um assistente pessoal que mora no **seu computador**, conversa por texto e voz, **lembra** de você, **faz coisas** (lembretes, notas,
pesquisas, agenda) e, aos poucos, **estuda sozinho** os assuntos do seu interesse para ajudar com mais autoridade. Você controla tudo
o que ele guarda e gasta.

## 2. As peças (o que roda e onde)
| Peça | O que faz | Onde fica |
|---|---|---|
| **Programa Jefrey** (`Jefrey.exe`) | Servidor local + tela. Ícone na bandeja (Abrir / Registros / Sair) | Seu PC, só aceita conexões do próprio computador |
| **Cérebro (modelo de IA)** | Entende e responde | **Nuvem** por padrão (OpenRouter, Claude ou ChatGPT, com a sua conta/chave) ou **local** (Ollama), se o PC tiver placa de vídeo |
| **Memória** | Notas, fatos, documentos, busca por sentido | Seu PC (`%LOCALAPPDATA%\Jefrey\data`). A busca usa Ollama, a nuvem ou um motor embutido |
| **Banco local** | Lembretes, perfil, histórico de conversas, aprovações | Seu PC (SQLite) |
| **Voz** | Ouvir (Whisper local) e falar (vozes do Windows) | Seu PC |
| **Avatar** | Cérebro 3D, orbe, reator ou **holograma com a sua imagem** | Só o navegador; a imagem não sai do PC |

## 3. O caminho de uma mensagem (já funciona)
1. Você escreve ou fala. A tela manda ao servidor local (com proteção contra sites maliciosos: só a própria tela fala com ele).
2. O Jefrey monta o **contexto**: persona informal, **como te chamar**, data e hora, **que cérebro está usando**, **que ferramentas tem agora**
   (e quais faltam, como "conta Google não conectada") e as **memórias relevantes**. Assim ele sabe quem ele é e o que pode.
3. **Atalhos sem IA** para o que é exato: hora, contas, lembretes ("me lembra de… amanhã às 8h"), notas ("guarda isso"), listar notas.
   São instantâneos e não erram.
4. Para o resto, o modelo responde e pode **chamar ferramentas** (clima, notas, lembretes, agenda…). Ferramentas de risco
   (enviar e-mail, apagar algo) **pedem a sua aprovação** antes. Texto vindo de ferramentas, páginas e memórias é tratado como
   **informação, nunca como ordem**.
5. A resposta chega aos poucos (streaming) e pode ser falada. A conversa é gravada no banco local, então **continua depois de fechar o programa**.

## 4. Como ele aprende (Sessões 3 e 4: em construção)
- **Automático:** depois de cada conversa, um passo em segundo plano extrai fatos, preferências, pessoas, projetos e datas.
  Fato novo **substitui** o antigo (com histórico). Nunca guarda senhas, documentos de identidade ou cartões.
- **Você revisa depois** em "O que aprendi": ver, corrigir, esquecer, desligar.
- **Diário e perfil:** um resumo por dia e um perfil curto que entra em toda resposta.
- **"Lembrei de…"**: sob a resposta, mostra de onde veio cada lembrança.

## 5. Como ele estuda sozinho (Sessão 5: em construção)
1. Escolhe **temas pela sua memória e curiosidade** (o que você pergunta e guarda).
2. Para cada tema faz um plano de estudo e roda um ciclo: **planeja perguntas → busca → lê páginas (leitor protegido) → resume com fonte e
   data → escreve um guia prático aplicável**, subindo o "nível" do tema.
3. Gasta no máximo o **teto diário** (padrão US$ 0,10; centavos com modelos baratos) e respeita o horário de silêncio.
4. Você vê tudo na tela **Estudos** e pode desligar quando quiser. O texto lido na web nunca vira instrução.

## 6. Proatividade (Sessão 6) e voz (Sessão 8)
Briefing da manhã (agenda, lembretes, clima, o que ele estudou), avisos úteis sem incomodar, atalho global e palavra de ativação.

## 7. Conexões (Sessão 3)
Botões que levam ao site, você entra na conta e volta: **assistente (OpenRouter, 1 clique)**, **Google** (agenda/e-mail), **WhatsApp**.
Onde o provedor só oferece chave, um guia em 3 passos.

## 8. Privacidade e segurança, resumidamente
- Dados, memórias e imagem do avatar ficam **no seu PC**. Com cérebro na nuvem, **o texto da conversa vai ao provedor escolhido**; no
  cérebro local nada sai.
- Chaves ficam **protegidas pelo Windows (DPAPI)** e nunca voltam à tela.
- Só o próprio navegador acessa o programa (proteção contra DNS rebinding e CSRF); aprovação humana para ações de risco; registros
  de suporte **sem chaves nem tokens**.
- Mensagens de terceiros (futuro WhatsApp) são **dados** e nunca acionam ferramentas.

## 9. O que ainda não existe
WhatsApp Web (Sessão 9), atualização automática assinada e assinatura do instalador (Sessão 12), verificação do Google (Sessão 12),
palavra de ativação (Sessão 8).
