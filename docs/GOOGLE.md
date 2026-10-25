# Ligar o botão "Entrar com o Google" (para quem publica o Jefrey)

O Jefrey já traz o fluxo pronto (PKCE, `state` de uso único, tokens protegidos pelo Windows). Falta só **uma vez** criar o "app" do
Jefrey no Google e colocar as credenciais. Quem usa o Jefrey não faz isto: só aperta o botão.

## Passo a passo (uma vez, por quem distribui o programa)
1. Entre em <https://console.cloud.google.com/> e crie um projeto (nome: Jefrey).
2. **APIs e serviços > Biblioteca**: ative **Google Calendar API** e **Gmail API** (e **Google Drive API**, se for usar).
3. **Tela de permissão OAuth**: tipo "Externo"; nome do app "Jefrey"; e-mail de suporte; adicione os escopos
   `calendar.events`, `gmail.modify` (e `drive.file`).
4. **Credenciais > Criar credenciais > ID do cliente OAuth** com tipo **Aplicativo para computador (Desktop)**.
   Esse tipo aceita o retorno em `http://localhost` / `http://127.0.0.1` em qualquer porta, que é o que o Jefrey usa.
5. Baixe o JSON e salve como `config/google_oauth.json` (no instalador, na pasta de dados), ou defina as variáveis
   `JEFREY_OAUTH__CLIENT_ID` e `JEFREY_OAUTH__CLIENT_SECRET`.

## Limites do Google que você precisa saber
- Enquanto o app estiver em **"Teste"**, só entram os e-mails que você cadastrar como testadores (até 100) e a autorização expira
  em 7 dias.
- Para qualquer pessoa usar: **publicar o app** e passar pela **verificação do Google**. O escopo do Gmail (`gmail.modify`) é
  "restrito" e exige verificação mais rigorosa (e, em geral, avaliação de segurança anual). A **Agenda** é mais simples de liberar.
- Alternativa para lançar rápido: liberar primeiro só **Agenda** (e/ou Drive `drive.file`) e deixar o Gmail para depois.

## Se o Google mostrar "Erro 400: redirect_uri_mismatch"
O Google só aceita o endereço de retorno que você **registrou** no app (clientes do tipo "Aplicativo da Web"). Duas saídas:
1. **Recomendado:** crie o cliente como **"Aplicativo para computador"** (Desktop). Aceita qualquer porta local, então o botão funciona
   mesmo quando o Jefrey sobe numa porta diferente da 8000.
2. Se já tem um cliente "Aplicativo da Web": em **Credenciais > seu cliente > URIs de redirecionamento autorizados**, adicione
   `http://localhost:8000/auth/google/callback` (e, se quiser, `http://127.0.0.1:8000/connections/google/callback`).
   Se o endereço registrado estiver em `JEFREY_OAUTH__REDIRECT_URIS` e na mesma porta do Jefrey, o botão usa exatamente esse.
   Se o Jefrey abrir em outra porta (8001, 8002…), o cliente "Web" não serve: use o tipo "Computador".

## Se o Google mostrar "Acesso bloqueado ... Erro 403: access_denied"
Significa que o app está em **fase de testes** e a conta que entrou **não está na lista de testadores** (visto na prática com `pedrohalves42@gmail.com`;
o Jefrey chegou ao Google normalmente e o endereço de retorno registrado foi aceito). Para liberar:
1. Google Cloud Console > **APIs e serviços > Tela de permissão OAuth** (ou **Google Auth Platform > Público-alvo**).
2. Em **Usuários de teste**, clique em **Add users** e inclua o e-mail da pessoa (até 100). O dono do projeto também precisa estar na lista.
3. Tente de novo no Jefrey. Aparece o aviso "O Google não verificou este app": **Avançado > Acessar jefrey (não seguro)** (normal em teste).
Limites do modo de testes: a autorização **vence em 7 dias** (a pessoa precisa conectar de novo) e só os testadores entram. Para qualquer pessoa usar,
é preciso **publicar** o app e passar pela **verificação** (Agenda é simples; **Gmail é escopo restrito** e pode exigir avaliação de segurança paga).
Dica para lançar mais rápido: oferecer só **Agenda** no início (desmarque E-mail no botão) e deixar o Gmail para depois da verificação.

## O que o Jefrey guarda
Tokens de acesso e de renovação, protegidos pelo Windows (DPAPI), no banco local, por pessoa. Nada vai a terceiros.
O botão **Desconectar** apaga os tokens e avisa o Google para revogá-los.
