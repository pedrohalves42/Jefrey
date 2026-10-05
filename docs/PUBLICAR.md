# Publicar o Jefrey: tirar do modo de teste, assinar e atualizar

Três coisas que só o dono do produto consegue fazer (precisam de contas e documentos seus). O código já está pronto para todas.

## 1. Tirar o Google do "modo de teste"
Hoje só os e-mails listados como **testadores** conseguem entrar com o Google (erro 403 `access_denied` para os outros).

1. Google Cloud Console → **APIs e serviços → Tela de permissão OAuth**.
2. Em **Status da publicação**, toque em **Publicar o app** (passa de "Em teste" para "Em produção").
3. O Google só deixa qualquer pessoa entrar sem aviso depois da **verificação do app**, porque Agenda, Gmail e Drive são escopos sensíveis.
   Para facilitar, peça só **Agenda** (leitura e criação de eventos) e deixe Gmail e Drive como opcionais.
   Precisa de: domínio próprio, página de privacidade pública (o texto está em `src/jefrey/legal`), vídeo curto mostrando o uso e o e-mail de suporte.
4. Enquanto não for verificado: até 100 usuários, com aviso "app não verificado" (dá para clicar em "Avançado → continuar").

Preencha também `[NOME DA EMPRESA]`, `[CNPJ]` e `[E-MAIL DE CONTATO]` nos textos legais antes de publicar.

## 2. Assinar o instalador
O Windows mostra "editor desconhecido" (SmartScreen) sem assinatura. Passos:

1. Comprar um certificado de assinatura de código (OV ou EV) de uma autoridade como DigiCert, Sectigo ou SSL.com. O EV tira o aviso na hora; o OV vai ganhando reputação.
2. Instalar o Windows SDK (traz o `signtool`).
3. Antes de gerar o instalador:
```
set JEFREY_SIGN_PFX=C:\caminho\certificado.pfx
set JEFREY_SIGN_PASS=senha
packaging\build_exe.bat C:\Users\Pedro\jv312\Scripts\python.exe
```
O `build_exe.bat` assina o `Jefrey.exe` e o `Jefrey-Setup.exe` sozinho. Nunca coloque o `.pfx` no Git (já está no `.gitignore`).

Um certificado "autoassinado" não adianta: o Windows continua avisando.

## 3. Atualização automática
Já funciona assim: o Jefrey procura versão nova ao abrir e a cada 6 horas, mostra um aviso com **Atualizar agora** (nunca instala sozinho), confere a assinatura, o tamanho e o SHA-256, faz backup dos dados e roda o instalador.

Já existe um par de chaves: a **pública** está em `packaging/defaults/update_public_key.txt` (vai no instalador) e a **privada** em `C:\Users\Pedro\Jefrey-chaves\update_private_key.txt`. **Guarde uma cópia da privada fora deste computador (pendrive ou cofre de senhas). Se perder, as cópias já instaladas não aceitam mais atualizações.**

Falta só um lugar para hospedar os dois arquivos (pode ser a página de downloads do site, ou os "Releases" do GitHub se o repositório for público):

1. Gere o instalador da nova versão (aumente `__version__` em `src/jefrey/__init__.py`).
2. Assine:
```
python scripts/sign_update.py --key C:\Users\Pedro\Jefrey-chaves\update_private_key.txt --installer packaging\Output\Jefrey-Setup.exe --version 1.0.1 --url https://SEU-SITE/Jefrey-Setup-1.0.1.exe --notes "O que mudou" --out manifest.json
```
3. Publique o instalador no endereço do `--url` e o `manifest.json` em um endereço fixo, por exemplo `https://SEU-SITE/atualizacoes/manifest.json`.
4. Uma única vez, coloque esse endereço em `packaging/defaults/update_url.txt` antes de gerar o instalador que você vai distribuir.

## 4. Docker (projetos mais complexos)
O caminho normal é o instalador do Windows (modo nativo). O Docker (`docker-compose.yml` e `docker-compose.prod.yml`) fica para quem quer rodar em servidor ou integrar com outros sistemas. Ele é opcional e não é o que o usuário comum usa.
