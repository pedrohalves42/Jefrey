# Falar com o Jefrey pelo WhatsApp

O Jefrey usa a **API oficial do WhatsApp (Cloud API, da Meta)**. Fica **desligado por padrão** e só
conversa com os números que você autorizar. Ações de risco (enviar e-mail, apagar algo) pedem a sua
aprovação **no próprio WhatsApp**.

> Estado: o código do canal está pronto e testado (assinatura, lista de autorizados, aprovação por
> código, limites). **Ainda não foi testado com uma conta real do WhatsApp**: isso depende dos passos
> abaixo, que só você pode fazer (conta Meta e número de telefone).

## O que você precisa fazer (uma vez)

1. **Conta de desenvolvedor da Meta**: https://developers.facebook.com → criar um app do tipo *Business*
   e adicionar o produto **WhatsApp**.
2. Em *WhatsApp → API Setup*, anote:
   - **Phone number ID** (o número de teste da Meta serve para começar);
   - **Token de acesso** (o temporário dura 24 h; para uso contínuo crie um *System User* com token permanente);
   - em *App settings → Basic*, o **App Secret**.
3. Adicione o **seu número** em *To* (destinatários permitidos no modo de teste) e confirme o código.
4. **Endereço público HTTPS** para o webhook (a Meta precisa alcançar o seu computador). Opções gratuitas:
   `cloudflared tunnel --url http://localhost:8000` ou `ngrok http 8000`.
5. Em *WhatsApp → Configuration → Webhook*:
   - **Callback URL**: `https://SEU-ENDERECO/channels/whatsapp/webhook`
   - **Verify token**: invente um texto longo e aleatório (o mesmo que vai no `.env`)
   - assine o campo **messages**.

## Configuração (`.env`)

```env
JEFREY_WHATSAPP__ENABLED=true
JEFREY_WHATSAPP__VERIFY_TOKEN=um-texto-longo-e-aleatorio
JEFREY_WHATSAPP__APP_SECRET=o-app-secret-da-meta
JEFREY_WHATSAPP__ACCESS_TOKEN=o-token-de-acesso
JEFREY_WHATSAPP__PHONE_NUMBER_ID=123456789012345
# quem pode falar com o Jefrey: numero com DDI (so digitos), opcionalmente =usuario
JEFREY_WHATSAPP__ALLOWED=5511999990000=demo
```

Depois: reinicie o Jefrey. Mande "oi" para o número do WhatsApp do seu app.

## Segurança (o que o Jefrey faz por você)

- **Sem App Secret ou sem lista de autorizados o canal fica fechado** (responde 404).
- Cada mensagem recebida tem a **assinatura HMAC** conferida; assinatura inválida é recusada.
- **Números fora da lista são ignorados em silêncio**: o Jefrey não vira um repetidor de spam.
- Reenvios do webhook são processados **uma única vez**; há limite de 20 mensagens por minuto por pessoa.
- Pedidos de aprovação usam um **código curto** (`SIM 7F3A` / `NÃO 7F3A`) que só vale para quem recebeu o
  pedido e expira em 30 minutos. A resposta de aprovação **não passa pelo modelo de IA**, então ninguém
  consegue "convencer" a IA a aprovar sozinha.
- O token e o texto das mensagens nunca vão para os logs.

## Limitações atuais

- Só mensagens de **texto** (áudio e imagem recebem um aviso; transcrição de áudio é o próximo passo).
- No modo de teste da Meta só dá para falar com os números cadastrados; para uso amplo é preciso
  verificar o negócio na Meta.
- A Meta só permite respostas livres dentro de **24 h** depois da sua última mensagem.
