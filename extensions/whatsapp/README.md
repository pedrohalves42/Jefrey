# Jefrey para WhatsApp (extensão do Chrome)

Deixa o Jefrey ler e responder, no **WhatsApp Web**, as conversas que a pessoa liberar. Não usa a API oficial do WhatsApp.

## Como instalar (por enquanto, modo desenvolvedor)
1. No Jefrey: **Conexões > WhatsApp > Abrir a pasta da extensão**.
2. No Chrome: `chrome://extensions`, ligue o **Modo do desenvolvedor**, **Carregar sem compactação**, escolha esta pasta.
3. No Jefrey: **Gerar código**. Clique no ícone do Jefrey no Chrome e digite o código de 6 números.
4. Abra `https://web.whatsapp.com`. No Jefrey, em **Conexões**, escolha o que fazer em cada conversa:
   **Perguntar antes** (recomendado no começo), **Responder sozinho** ou **Ignorar**.

> Para um clique só ("Adicionar ao Chrome"), a extensão precisa ser publicada na Chrome Web Store (Sessão 13 do plano).

## O que ela faz e o que NÃO faz
- Lê só a conversa **aberta** e só as mensagens **novas** (o histórico antigo nunca é respondido).
- Só responde conversas **liberadas**; **grupos são sempre ignorados**.
- **Nunca** abre conversas, inicia mensagens nem envia em massa; espera de 5 a 14 s antes de responder; no máximo uma mensagem a cada poucos segundos.
- Não envia se a pessoa estiver digitando ou se outra conversa estiver aberta.
- Dinheiro, dados pessoais, links, emergências, compromissos, áudio/imagem ou dúvida do modelo: **o Jefrey pede a aprovação** num pop-up.
- O texto de quem escreve é **dado**: o modelo que redige a resposta não tem ferramentas e ignora instruções dentro da mensagem.
- Fala só com o Jefrey em `127.0.0.1` (este computador). Guarda apenas o endereço e um token do aparelho (revogável no Jefrey).

## Riscos que a pessoa precisa saber
- O WhatsApp pode bloquear números que usam automação. Use primeiro **Perguntar antes** e, se puder, um número só para isso.
- As mensagens liberadas passam pela inteligência na nuvem escolhida (para escrever a resposta). Tudo fica guardado por 30 dias e dá para apagar.

## Teste
- Automático: `cd ui && npx vitest run src/__tests__/wa-extension.test.js` (página simulada do WhatsApp com todos os cenários).
- Real: só com o celular da pessoa (QR do WhatsApp Web). Os seletores do WhatsApp mudam de tempos em tempos: todos ficam em `core.js`.
