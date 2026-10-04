# Como o Jefrey funciona, por inteiro

Texto para entender o produto de ponta a ponta, como ele está **hoje** (04/10/2026, versão 0.9.0). Cada parte diz se foi **verificada
por testes automáticos** e o que **só você consegue testar** (conta, celular, microfone, outro PC).

## 1. A ideia em uma frase
Um assistente pessoal que mora no **seu computador**, conversa **por voz** e texto, **lembra** de você, **faz coisas** (lembretes, notas,
pesquisas, agenda), **estuda sozinho** os assuntos do seu interesse e pode **responder o seu WhatsApp** nas conversas que você liberar.
Pensado para que uma pessoa de **70 anos** instale, configure e use sozinha.

## 2. As peças
| Peça | O que faz | Onde fica |
|---|---|---|
| **Programa Jefrey** | Servidor local + tela + ícone perto do relógio (Abrir / Registros / Sair). Atalho **Ctrl+Alt+J** chama de qualquer programa | Seu PC; só aceita conexões do próprio computador |
| **Cérebro** | Entende e responde | **Nuvem** por padrão (OpenRouter, Claude ou ChatGPT) ou **local** (Ollama) se o PC aguentar |
| **Memória** | Notas, fatos, documentos, busca por sentido | Seu PC |
| **Banco local** | Lembretes, perfil, histórico, o que aprendeu, diário, estudos, resumos, WhatsApp | Seu PC (SQLite) |
| **Voz** | Ouve (Whisper local) e fala (vozes do Windows) | Seu PC; o áudio não vai para a internet |
| **Avatar** | Cérebro 3D, orbe, reator ou holograma com a sua imagem | Só no navegador |
| **Extensão do Chrome** | Liga o Jefrey ao WhatsApp Web | Chrome do seu PC, pareada por código |

## 3. O caminho de uma mensagem
1. Você **fala** (botão grande "Toque aqui e fale comigo") ou escreve. A tela só conversa com o servidor local (proteção contra sites maliciosos).
2. O Jefrey monta o **contexto**: persona informal, **seu nome**, data e hora, **que cérebro usa**, **que ferramentas tem agora** (e quais faltam, como
   "conta Google não conectada"), o que **aprendeu** sobre você e, **só quando ajuda**, memórias, diário e guias que estudou (o **portão de recordação**
   evita buscar à toa). Tudo que vem de fora entra dentro de `<dados>…</dados>`: é informação, nunca ordem.
3. **Atalhos sem IA** para o que é exato: hora, contas, lembretes, notas.
4. Para o resto o modelo responde e pode **chamar ferramentas**. Com cérebro de nuvem ele vê **todas**; com modelo local, só as relevantes. Ações de
   risco (enviar e-mail, apagar algo) **pedem a sua aprovação**.
5. A resposta chega aos poucos e é **falada**. Você pode falar por cima para interromper. Sob a resposta aparece **"Lembrei de…"** com o que foi usado.
6. A conversa fica gravada (90 dias) e continua depois de fechar o programa.

## 4. Como ele aprende (automático)
Depois de cada conversa, em segundo plano, o Jefrey extrai fatos (onde mora, gostos, família, projetos, datas) por regras e, com cérebro de nuvem, também por IA.
Fato novo **substitui** o antigo (o antigo vai para o histórico). **Nunca** guarda senhas, documentos, cartões ou chaves; saúde e dinheiro ficam marcados como
"delicado" e não entram nas respostas à toa. Em **O que aprendi** você vê, corrige, esquece ou manda **parar de aprender**. Um **diário** resume cada dia.

## 5. Como ele estuda sozinho
Escolhe assuntos pela sua **memória** (gostos, trabalho, projetos) e pela sua **curiosidade** (o que você pergunta mais de uma vez), até 5 por vez; você pode
incluir, pausar ou apagar. Cada ciclo: planeja buscas → busca na web → **lê as páginas com leitor protegido** (bloqueia endereços internos, limita tamanho)
→ escreve um **guia prático com as fontes e a data**, e sobe o **nível** do assunto (de "Começando" a "Especialista"). Só roda **com você ausente**, fora do
**horário de silêncio** e dentro do **teto diário (padrão US$ 0,10)**, e só com cérebro de nuvem. Na conversa ele usa esses guias quando têm a ver.

## 6. Proatividade
Um **resumo todas as manhãs** (lembretes do dia, o que ficou pendente, o que estudou, aniversário) aparece na Conversa e pode ser **ouvido**. **Lembretes avisam
no Windows** (balão perto do relógio) na hora, mesmo com a janela fechada. O avatar mostra "Estudando…" ou "Aprendendo…" e o ícone da bandeja também.

## 7. Conexões (botões que levam ao site)
- **Inteligência:** 1 clique (OpenRouter) ou o guia de 3 passos para Claude/ChatGPT, com o código validado na hora.
- **Google (Agenda/E-mail):** "Entrar com o Google"; os tokens ficam protegidos pelo Windows e dá para desconectar (o Google é avisado). Precisa do app no Google Cloud (`docs/GOOGLE.md`).
- **WhatsApp:** extensão do Chrome. Você libera conversa por conversa ("Perguntar antes" ou "Responder sozinho"); grupos nunca. Dinheiro, dados pessoais, links,
  emergência, compromisso, áudio/imagem ou dúvida do modelo **abrem um pop-up para você aprovar** (pode editar o texto). Há pausa geral, limites e aviso do risco de bloqueio do número.

## 8. Privacidade e segurança
- Seus dados ficam no PC. Com nuvem, **o texto da conversa vai ao serviço escolhido**; com modelo local, nada sai. Sem telemetria.
- Tela **Privacidade**: o que é guardado, **baixar uma cópia**, **apagar tudo**. Termos e política no primeiro uso.
- Chaves protegidas pelo Windows (DPAPI) e nunca voltam à tela; só a própria tela acessa o programa; `/metrics` pede login; aprovação para ações de risco;
  atualizações **assinadas** (Ed25519 + SHA-256), com backup antes e sem instalar sem você clicar.
- Mensagens de terceiros (WhatsApp) e páginas da web são **dados**: o modelo que as lê não tem ferramentas.

## 9. Modo Fácil
Ligado por padrão: letra grande, mais contraste, menu só com **Conversa, Conexões, O que aprendi e Ajuda**, botões "Ouvir" em cada tela, erros em português simples
(o que houve + o que fazer). Em **Ajuda** dá para mostrar mais opções.

## 10. O que foi verificado e o que falta
**Verificado automaticamente:** servidor (≈ 1.100 testes), interface (≈ 180) e a extensão do WhatsApp contra uma página simulada; navegação das telas no navegador.
**Só você consegue verificar:** voz com o seu microfone (e o download do modelo de voz na primeira vez); login do Google (precisa do app no Google Cloud); WhatsApp real
(celular); instalação em **PC limpo** e o alerta do Windows/antivírus; qualidade das respostas com **uma chave de nuvem** (`python evals/run_evals.py --only leigos`).
**Depende de decisões/contas suas:** certificado de assinatura, servidor de atualizações, textos legais revisados, licença, página de download e cobrança (`docs/DISTRIBUICAO.md`).
