# GUIA LEIGO JEFREY — 1 programa, 7 pecas

> Como fazer o basico funcionar em 1 minuto (sem ser dev).

## Por que 401 nao e bug (Axiom #1 FAIL-CLOSED)

Jefrey e multi-tenant e fail-closed: sem Bearer token, `GET /chat` e `POST /chat` DEVEM dar 401 `{ok:false, error:"token nao fornecido"}`. E seguranca correta (Security Engineering cap4, CIPHER-031). Se der 200 sem token, seria vulnerabilidade.

## Passo a passo (Windows)

1. **Subir stack**: duplo clique em `start_jefrey.bat` OU `docker compose up -d --build` — aguarde `docker compose ps` 7/7 healthy.
2. **Abrir UI**: http://localhost:8000 — se ver HUD preto + menu Chat/Memoria/Approvals/Observabilidade/Settings, o `StaticFiles mount /` ja esta vivo (Axiom #7 sem container extra).
3. **Pegar token**:
   - Em dev (`JEFREY_ENV=dev`): va em **Settings -> Obter token dev** -> clique -> vera "Token dev obtido e salvo (dev). Agora Chat -> 200".
   - Em prod: cole seu JWT RS256 em Settings -> Bearer token -> Salvar.
4. **Testar Chat**: va em Chat, digite "oi" -> Enter. Deve voltar `status running|complete`. Sem token voltara 401 com CTA "Ir para Settings".
5. **Testar Memoria**: va em Memoria -> busque "teste" -> vera hits com score (HNSW m16 ef64).
6. **Testar Voz**: aperte mic -> fale -> vera transcript no input -> reply TTS toca (se `qwen2:0.5b` vivo). Sem token mic mostra erro "Sem token — va em Settings".

## Troubleshooting

| Sintoma | Causa | Fix |
|---------|-------|-----|
| `/chat 401` sempre | token nao salvo | Settings -> Obter token dev -> Salvar |
| `/chat 500 ProactorEventLoop` no TestClient Windows | psycopg async + Proactor | normal no docker (linux); nao e bug de codigo |
| `/memory 500 Ollama` | Ollama host off | `ollama serve` + `ollama pull nomic-embed-text` |
| `docker ps` sem jefrey-api healthy | `.env` sem `JEFREY_API__SECRET_KEY` | `python scripts/setup.py` gera `.env` |

## Stack (7 pecas, 1 programa)

- `jefrey-api:8000` (FastAPI + StaticFiles UI)
- `jefrey-mcp:8001`
- `postgres:5432` pgvector HNSW
- `redis:6379`
- `n8n:5678`
- `prometheus:9090`
- `grafana:3000`

SLO: `http://localhost:8000/health 200`, `http://localhost:8000/metrics` sem user_id label (Livro 4 cap5 cardinality), Grafana 9 panels editable false.

*Gerado F2 2026-09-04 — feat/final-100*
