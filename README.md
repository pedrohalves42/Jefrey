# Jefrey

Assistente pessoal de IA que **roda no seu computador (Windows)**, feito para que **uma pessoa de 70 anos** instale, configure e use sozinha.
Conversa **por voz** (um botão grande: toque, fale, ouça), lembra de você, faz lembretes que avisam no Windows, **aprende** o que é importante
(você revisa), **estuda sozinho** os assuntos do seu interesse e pode **ler e responder o seu WhatsApp** (janela própria dentro do app) nas conversas que você liberar. Também lê e publica nas redes sociais (X, Facebook, Instagram) com a sua aprovação.
Para pensar, usa até **10 cérebros** ao mesmo tempo (9router, Gemini, Groq, OpenAI, Claude e outros, cada um com uma função, trabalhando em equipe) ou um **modelo local**.

> Estado, o que foi verificado e o que só você pode testar: [docs/COMO_O_JEFREY_FUNCIONA.md](docs/COMO_O_JEFREY_FUNCIONA.md) e [docs/PLANO_EXECUCAO_SESSOES.md](docs/PLANO_EXECUCAO_SESSOES.md).

## Instalar (para quem usa)
Baixe e execute **Jefrey-Setup.exe** (não precisa de administrador, nem de Docker). Leia e aceite os termos, diga o seu nome, aperte **Conectar com 1 clique** e fale.
Atalho para chamar de qualquer programa: **Ctrl+Alt+J**.

## Rodar em desenvolvimento
Python **3.12** (`C:\Users\Pedro\jv312` neste projeto) e Node 20+.

```bash
python -m src.jefrey.native                 # servidor + tela + bandeja (http://127.0.0.1:8000)
cd ui && npm ci && npm run build:api        # reconstrói a tela servida pelo programa
```

## Testes
```bash
python -m pytest tests -q --ignore=tests/e2e --ignore=tests/smoke     # servidor (hermético: SQLite + Redis em memória)
cd ui && npm test && npx tsc --noEmit -p .                             # interface e extensão do WhatsApp (página simulada)
python evals/run_evals.py --only leigos                                # bateria de 17 pedidos de pessoa comum (precisa de cérebro de nuvem)
```

## Gerar o instalador
`packaging\build_exe.bat C:\caminho\python3.12.exe` (assina se `JEFREY_SIGN_PFX`/`JEFREY_SIGN_PASS` existirem). Veja [docs/DISTRIBUICAO.md](docs/DISTRIBUICAO.md).

## Estrutura
```
src/jefrey/
  api/        rotas (chat, conexões, aprendizado, estudos, resumo, WhatsApp, privacidade, atualizações, voz)
  core/       agente, persona, aprendizado, recordação, estudos, leitor protegido, WhatsApp, atualização assinada, privacidade
  native/     lançador, bandeja, atalho global
  legal/      termos de uso e política de privacidade (rascunhos para revisão)
  skills/     notas, essenciais, agenda, e-mail, web, Drive, automação
extensions/whatsapp/   leitura e envio no WhatsApp Web (injetada na janela do app; também serve como extensão do Chrome)
ui/           interface (React), testes com vitest
evals/        avaliação do produto rodando (inclui a bateria de leigos)
packaging/    PyInstaller + Inno Setup
site/         página de apresentação (a preencher)
n8n/          fluxo opcional de eventos
```

## Documentação
[Como funciona](docs/COMO_O_JEFREY_FUNCIONA.md) · [Plano por sessões](docs/PLANO_EXECUCAO_SESSOES.md) · [Auditoria de 10/10/2026](docs/AUDITORIA_2026-10-10.md) · [Distribuição e venda](docs/DISTRIBUICAO.md) ·
[Google](docs/GOOGLE.md) · [Extensão do WhatsApp](extensions/whatsapp/README.md) · [Auditoria de segurança](docs/AUDITORIA_CIPHER_2026-10.md) ·
[Licenças de terceiros](docs/LICENCAS_TERCEIROS.md) · [Modelos locais](docs/MODELOS.md) · [Modelo de ameaças](docs/THREAT_MODEL.md)

## Licença
O repositório está sob MIT; **a decisão de licença para a venda é do dono** (ver [docs/DISTRIBUICAO.md](docs/DISTRIBUICAO.md), item 5).
