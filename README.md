# Jefrey

Assistente pessoal de IA que **roda no seu computador**. Conversa por texto e voz, lembra do que você
conta, usa ferramentas (notas, hora, contas, clima, arquivos, agenda e e-mail do Google) e **pede a sua
aprovação antes de qualquer ação de risco**. Funciona offline com modelos locais; se quiser respostas
mais fortes, conecta ao Claude, ao ChatGPT ou a outro provedor compatível.

## Começando (Windows)

Você precisa do [Docker Desktop](https://www.docker.com/products/docker-desktop) e de uns 8 GB de RAM livres.

1. Copie `.env.example` para `.env` e preencha os segredos (a chave da API: `python -c "import secrets; print(secrets.token_hex(32))"`).
2. Dê duplo clique em **`start_jefrey.bat`**. Ele abre o Docker se preciso, sobe o Jefrey e abre o navegador.
   - Na primeira vez os modelos são baixados (alguns GB). `start_jefrey.bat completo` sobe também o monitoramento.
3. Abra http://localhost:8000. No Edge/Chrome use **Instalar aplicativo** para usar o Jefrey como um programa do Windows.

Para parar: `stop_jefrey.bat`. Se algo não funcionar: `python -m src.jefrey.cli doctor` diagnostica e diz como resolver.

## O que ele faz hoje

| Área | Estado |
|---|---|
| Conversa | Streaming, histórico, parar/tentar de novo. Modelo local por padrão (`qwen3:1.7b`), nuvem opcional em **Configurações** |
| Memória | Busca por sentido em português, guardar/esquecer, **importar documentos** (txt, md, csv, json, html), isolada por usuário |
| Ferramentas | Notas, hora, calculadora segura, clima, arquivos numa pasta sua, agenda/e-mail/Drive do Google (exigem login Google) |
| Segurança | Ações de risco só com aprovação humana (na tela ou por WhatsApp); auditoria; resultados de ferramentas filtrados contra injeção de prompt |
| Voz | Ouvir (Whisper local) e falar (vozes do Windows); falar por cima interrompe; conversa contínua |
| Interface | Cérebro 3D em três formas (cérebro, orbe, reator), 100% personalizável; status e métricas reais |
| WhatsApp | Canal oficial da Meta, desligado por padrão ([guia](docs/WHATSAPP.md)); **ainda não testado com conta real** |
| Operação | `doctor`, `backup`/`restore`, modo leve (4 containers), app instalável |

Limitações conhecidas estão em [docs/PLANO_PRODUTO_COMPLETO.md](docs/PLANO_PRODUTO_COMPLETO.md) (seção "Estado real").

## Modelos

Veja [docs/MODELOS.md](docs/MODELOS.md): comparação medida e como escolher. Em resumo, `qwen3:1.7b` para
pouca memória e `qwen2.5:3b` para usar todas as ferramentas. A tela **Configurações → Modelo de IA**
mostra a memória livre e recomenda o maior modelo que cabe.

## Comandos úteis

```bash
python -m src.jefrey.cli doctor            # diagnóstico do ambiente
python -m src.jefrey.cli backup            # salva config, memórias, arquivos e banco em um .zip
python -m src.jefrey.cli restore ARQUIVO   # restaura (o que existe é guardado, nunca apagado)
python -m pytest tests -q                  # testes do servidor
python evals/run_evals.py                  # avalia o Jefrey rodando (acerto e latência)
cd ui && npm ci && npm test                # testes da interface
cd ui && npm run build:api                 # reconstrói a interface servida pelo servidor
```

## Estrutura

```
src/jefrey/
  api/        rotas (chat, memória, aprovações, skills, configurações, WhatsApp, voz)
  core/       agente, ferramentas e política de risco, memória, provedores de modelo, doctor, backup
  channels/   canais externos (WhatsApp)
  skills/     notas, essenciais, agenda, e-mail, web, Drive, automação
ui/           interface (React + three.js), testes com vitest
evals/        avaliação do produto rodando (34 casos)
docs/         modelos, WhatsApp, ameaças, runbooks, referências
```

## Documentação

- [Plano e estado real do produto](docs/PLANO_PRODUTO_COMPLETO.md)
- [Comparação com os projetos de referência](docs/COMPARACAO_REFERENCIAS.md)
- [Modelos locais](docs/MODELOS.md) · [WhatsApp](docs/WHATSAPP.md) · [Modelo de ameaças](docs/THREAT_MODEL.md)
- [Referências bibliográficas e projetos usados](docs/REFERENCES.md)

## Licença

MIT.
