# Arquitetura (hexagonal)

Regra única: **as dependências apontam para dentro**. O que é regra de negócio não conhece banco, rede, FastAPI, Windows nem Google.

```
        entrada (quem chama)                          saída (o que o Jefrey usa)
  api/ (rotas FastAPI)  native/ (janela, bandeja)    adapters/outbound/  (banco, Google, g1, Windows)
  extensão do Chrome    skills/ (ferramentas)                     ▲
            │                    │                              │ implementam
            ▼                    ▼                              │
        ┌───────────────────── application/ ─────────────────────┴──┐
        │ casos de uso: orquestram o dominio usando PORTAS           │
        │   ┌──────────────────── domain/ ───────────────────┐      │
        │   │ regras puras: lembretes, aprendizado, whatsapp, │      │
        │   │ assuntos, alertas, tarefas/contatos, persona…   │      │
        │   └─────────────────────────────────────────────────┘      │
        └──────────────────── ports/ (interfaces) ───────────────────┘
```

| Camada | Pode importar | Nunca importa |
|---|---|---|
| `domain/` | biblioteca padrão e o próprio domínio | qualquer outra camada, frameworks, rede, banco |
| `ports/` | domínio | tudo o mais |
| `application/` | domínio, portas | `adapters`, `api`, `core`, FastAPI, SQLAlchemy, httpx |
| `adapters/outbound/` | domínio, portas, bibliotecas de infraestrutura | `api`, `adapters/inbound` |
| `bootstrap.py` | tudo (é a **raiz de composição**) | — |

Os testes `tests/test_architecture.py` falham se alguém quebrar a regra. `python scripts/arch_report.py` mostra o que ainda está misturado.

## Já migrado
| Assunto | Domínio | Aplicação | Adaptador |
|---|---|---|---|
| Aviso de compromissos | `domain/event_alerts` | `application/event_alerts` | `adapters/outbound/system_adapters` (Google Agenda, balão do Windows) |
| Tarefas e Contatos do Google | `domain/google_data` | `application/google_data` | `adapters/outbound/google_rest` |
| Lembretes | `domain/reminders` | — | `adapters/outbound/sql_reminders` |
| Aprendizado ("Aprendi") | `domain/learning` | `application/learning` | `adapters/outbound/sql_facts` |
| WhatsApp | `domain/whatsapp` | `application/whatsapp` | `adapters/outbound/sql_whatsapp` |
| Assuntos de notícia | `domain/interests` | — | — |
| Persona, catálogo de ferramentas, palavra de ativação, recordação, importação, registro | `domain/*` | — | — |
| Eventos, atividade | — | `application/events`, `application/activity` | — |

Os caminhos antigos (`core/reminders.py`, `core/learning.py`, `core/wa_web.py`, `core/persona.py`…) continuam existindo como **atalhos finos**, para nada quebrar durante a migração. Quando ninguém mais os importar, apague o atalho.

## Como migrar o próximo módulo
1. `python scripts/arch_report.py` → escolha um módulo de `core/` (os "candidatos a domínio puro" saem primeiro).
2. Puro (sem I/O): `python scripts/move_pure.py domain nome` — move e deixa o atalho.
3. Misturado: separe (a) regra → `domain/`, (b) orquestração → `application/` usando uma porta nova em `ports/__init__.py`, (c) banco/rede → `adapters/outbound/`. Deixe `core/nome.py` como atalho que liga o adaptador padrão.
4. Rode `pytest tests -q` e `tests/test_architecture.py`. Se o número de desvios do `core/` cair, abaixe a catraca no teste.

## Ainda por migrar (ordem sugerida)
`core/today` (feeds e painel), `core/briefing`, `core/studies`, `core/memory` (+ `pg_memory`, `redis_memory`), `core/agent` e `agent_loop` (orquestração do modelo), `core/brains`/`llm_provider`, `core/google_oauth`, `core/updater`, `api/*` (rotas são adaptadores de entrada: devem só traduzir HTTP em chamadas de caso de uso), `skills/*` (idem, para ferramentas).

## Regras de dia a dia
- Código novo nasce na estrutura nova (domínio → porta → caso de uso → adaptador → raiz de composição).
- Teste de regra é rápido e sem rede: use portas falsas (veja `tests/test_event_alerts.py`).
- Segurança não muda: texto de terceiros é dado, nunca instrução; chaves nunca em log ou URL.
