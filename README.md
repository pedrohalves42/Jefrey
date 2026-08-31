# Jefrey – Assistente Pessoal de IA Avançado

> **P1.1 READY 2026-08-31 - docs/JEFREY-AUDIT/acceptance_p1.1.md - 92.0%/67.2%/60.4% - Skills READY (drive.file + web_search fallback + OAuth hardening)**

> **P0 Accepted 2026-08-31 - docs/JEFREY-AUDIT/acceptance_p0_to_p1.md - 86.0%/62.8%/56.5% - gate P0->P1 PASS**

## Visão Geral

**Jefrey** é um assistente pessoal de IA projetado para profissionais e empreendedores que precisam de um agente inteligente capaz de:
- Conversar em linguagem natural (texto ou voz)
- Manter memória de curto e longo prazo com buscas semânticas
- Executar tarefas automatizadas via *tools* (notas, buscas na web, calendário, e‑mail, workflows)
- Integrar facilmente com serviços externos (Google Calendar, Gmail, Notion, Composio, etc.)
- Ser extensível via um registro de *skills* plug‑and‑play

O projeto está estruturado para **escalabilidade**, **performance** e **facilidade de implantação** (Docker, CI/CD). Ideal para ser comercializado como SaaS ou como solução on‑premise.

---

## Principais Funcionalidades

| Área | Funcionalidade |
|------|----------------|
| **Conversação** | Interface CLI com streaming, suporte a voz (opcional) via Whisper/Porcupine |
| **Memória** | Curto‑prazo (buffer de mensagens) + longo prazo (ChromaDB + embeddings cache) |
| **Skills** | Notas, Busca Web (Tavily), Calendário (Google), E‑mail (Gmail), Automação (workflows) |
| **Orquestração** | LangGraph State Machine com checkpoints, tracing via `langsmith` |
| **Eventos** | Bus de eventos assíncrono para logging, hooks e extensibilidade |
| **Deploy** | Docker multi‑stage, `docker‑compose`, CI básico (GitHub Actions) |

---

## Instalação Rápida

> **Requisitos**: Python 3.11+, `git`, Docker (opcional)

1. **Clone o repositório**
   ```bash
   git clone https://github.com/pedro/jefrey.git
   cd jefrey
   ```
2. **Instale dependências**
   ```bash
   # Ambiente virtual opcional
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt   # produção
   pip install -r requirements-dev.txt   # desenvolvimento
   ```
3. **Configure variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite .env e adicione suas chaves (OpenAI, Tavily, Google, etc.)
   ```
4. **Suba a infra e valide - Tracer Bullet 6.4 (fresh machine)**
   ```bash
   python scripts/setup.py --dev --non-interactive --force
   docker compose up -d --wait
   python scripts/run_tests.py --quick   # 2 PASS ~40s (smoke)
   # ou completo:
   python scripts/run_tests.py --ci      # 5 PASS ~115s
   python scripts/compute_readiness.py   # 86.0% impl (P0) / 92.0% com --status '{"Skills":"READY"}' (P1.1) / 62.8% prod / 56.5% comercial
   ```
   > Aceite: `docs/JEFREY-AUDIT/acceptance_p0_to_p1.md` - gate P0->P1 PASS
5. **Inicie o assistente**
   ```bash
   jefrey chat   # comando instalado pelo pyproject
   # ou
   python -m src.jefrey.interfaces.cli chat
   ```

---

## Configuração detalhada

O arquivo principal de configuração é `config/settings.yaml`. Ele pode ser customizado ou sobrescrito via variáveis de ambiente (`JEFREY_...`).

- **LLM** – escolha entre `openai`, `anthropic` ou `ollama`.
- **Memória** – `chromadb` (persistente) ou `sqlite-vec`.
- **Voice** – habilite STT/TTS e *wake word*.
- **Integrações** – habilite Google Calendar e Gmail (necessita OAuth, veja o script `setup.py`).

---

## Uso Básico (CLI)

```text
/jefrey> Olá, quem é você?
🤖 Jefrey: Você é o Jefrey, um assistente pessoal avançado...

/jefrey> Salva nota: título 'Reunião', conteúdo 'Discutir Q4', tags ['#trabalho']
✅ Nota salva com ID: a1b2c3d4...

/jefrey> Busca na web: últimas novidades IA generativa
[resposta da busca] ...

/jefrey> /skills   # lista skills e ferramentas disponíveis

/jefrey> /health   # verifica saúde do LLM e da memória
```

---

## Arquitetura do Projeto

```
 jefrey/
 ├─ config/                 # YAML de settings + prompts
 ├─ data/
 │   ├─ chroma_db/          # Persistência da memória vetorial
 │   └─ workflows/          # JSON de workflows de automação
 ├─ logs/                    # Logs estruturados (JSON opcional)
 ├─ src/
 │   ├─ jefrey/
 │   │   ├─ core/          # Config, memória, eventos, agente
 │   │   ├─ skills/        # Implementação de skills
 │   │   └─ interfaces/    # CLI, (futuro: UI, API)
 ├─ scripts/                # setup, smoke_test, CI helpers
 ├─ Dockerfile               # Build multi‑stage
 ├─ docker-compose.yml       # Orquestração simples
 ├─ pyproject.toml           # Build system + dependências
 └─ README.md                # Este documento
```

---

## Roadmap de Funcionalidades Pagas

| Versão | Feature | Descrição |
|--------|---------|-----------|
| **1.0** | **Assistente Comercial** | Interface web com autenticação SSO, multi‑usuário e billing por token. |
| **1.1** | **Integrações Premium** | Notion, Asana, Zapier (via Composio). |
| **1.2** | **Voice Premium** | TTS via ElevenLabs, wake‑word avançado com modelo customizado. |
| **2.0** | **Fine‑tuning** | Fine‑tune modelo LLM interno (Ollama) por cliente. |

---

## Licença

Este projeto está licenciado sob a **MIT License** – veja o arquivo `LICENSE` para detalhes.
