# GUIA LEIGO — Jefrey como 1 so programa (v1.0.0)

> **Jefrey NAO sao 7 programas.** E 1 programa com 7 pecas que sobem juntas com 1 comando. Este guia e para quem nunca abriu Docker.

## 0) O que e cada peca (voce nao precisa decorar)

| Peca | Porta | O que faz | Voce ve onde |
|------|-------|-----------|--------------|
| **jefrey-api** | 8000 | Cerebro — /chat, /memory, /approvals | http://localhost:8000/docs |
| **jefrey-mcp** | 8001 | Ferramentas (web_search, notes, calendar) | http://localhost:8001/health |
| **postgres** | 5432 | Memoria longa (pgvector HNSW) | invisivel, mas precisa estar healthy |
| **redis** | 6379 | Memoria curta (cache) | invisivel |
| **prometheus** | 9090 | Observabilidade (6 alerts) | http://localhost:9090 |
| **grafana** | 3000 | Dashboard 8 paineis | http://localhost:3000 |
| **n8n** | 5678 | Automacao | http://localhost:5678 |

Todas falam entre si na rede `jefrey` do docker-compose. Voce so precisa subir TUDO de uma vez.

## 1) Primeira vez (5 min)

### Windows (recomendado)
1. Instale **Docker Desktop** (https://www.docker.com/products/docker-desktop/) e deixe rodando (icone baleia na bandeja).
2. Baixe o repo jefrey e abra a pasta `C:\Users\Pedro\jarvis`.
3. Duplo clique em `scripts\start_jefrey.bat` (ou clique direito > Executar).
   - Na primeira vez ele cria `.env` sozinho via `python scripts/setup.py --dev --non-interactive --force`.
   - Depois roda `docker compose up -d --wait` e abre as 4 paginas no navegador.
4. Aguarde "7/7 healthy" no terminal. Pronto — jefrey esta rodando como 1 programa.

### Alternativa manual (se o .bat nao abrir)
```bat
python scripts/setup.py --dev --non-interactive --force
docker compose up -d --wait
docker ps
```
Se ver `jefrey-api (healthy)` + `jefrey-mcp (healthy)` + `redis (healthy)` + `postgres (healthy)` = OK.

## 2) Como usar (sem codigo)

### A) Conversar com o jefrey (Swagger)
1. Abra http://localhost:8000/docs
2. Clique em `POST /chat` > Try it out
3. Cole:
```json
{"thread_id": "demo-1", "message": "ola jefrey, lembre que meu nome e Pedro", "user_id": "u-demo"}
```
4. Execute. A resposta vem com `thread_id` — use o mesmo para continuar a conversa (memoria).

### B) Ver o que ele lembrou
- http://localhost:8000/docs > `GET /memory` ou `POST /memory/search`

### C) Dashboard (ver se esta saudavel)
- http://localhost:3000 (login admin / senha do .env) — dashboard `jefrey-main` 8 paineis (Config Valid, Service Up, Kid Legacy, Error Rate, RateLimit, Memory p95, Tools Blocked, Approvals)
- http://localhost:9090 (Prometheus) — Alerts 6 rules.

### D) Automacao
- http://localhost:5678 (n8n) — workflows ja versionados em `n8n-workflows/`.

## 3) Como desligar / ligar de novo

- **Desligar sem apagar memoria:** `docker compose stop` (ou feche Docker Desktop)
- **Ligar de novo:** duplo clique em `scripts\start_jefrey.bat` ou `docker compose up -d --wait`
- **Desligar e apagar memoria (cuidado):** `docker compose down -v` — apaga postgres/redis volumes.

## 4) Deu problema? (FAIL-CLOSED — Axiom #1)

| Sintoma | O que fazer |
|---------|-------------|
| `api unhealthy` | `docker logs jefrey-api --tail 50` + `curl http://localhost:8000/health` |
| `redis unhealthy NOAUTH` | `docker compose up -d --force-recreate redis` — healthcheck usa `redis-cli -a $PASSWORD ping` |
| `mcp unhealthy NameError register_default_tools` | ja fixado em 98cd0da — `docker compose restart mcp-server` |
| `grafana sem by (le)` | ja fixado — 8 paineis com `by (le)` com espaco (Livro4 cap6) |
| `promtool FAIL` | `docker run --rm --entrypoint promtool -v "%cd%/docker/prometheus:/etc/prometheus" prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml` |
| Tudo "Restarting" | Docker Desktop > Restart + `docker compose up -d --wait` |

## 5) Onde fica sua memoria

- **Curta (Redis):** ultimas 20 msgs por thread — some se `down -v`.
- **Longa (Postgres pgvector HNSW m16 ef64):** embeddings 768 dims — persiste em volume `jefrey_pgdata`.
- **Backup (DDIA cap3):** `reports/p6-backup.log` prova `pg_dump RC0` + `BGSAVE ok`.

## 6) Custo (10 repos R$0 licenca != R$0 custo)

Jefrey usa ollama local (nomic-embed 768) = R$0 licenca, mas precisa placa/CPU para 30B. Alternativa API (OpenAI) paga por token. Awesome refs: public-apis 474k, awesome-mcp-servers 93k, free-for-dev 136k.

## 7) Atualizar

```bat
git pull
docker compose build jefrey-api mcp-server
docker compose up -d --wait
python scripts/verify_p6_data.py && python scripts/_validate_deep.py
```
Esperado: `21/21 100% DATA OK` + `167/167 WARNS0 BUGS0`.

---
**Refs:** Axiom #1-7 (FAIL-CLOSED), CIPHER-033 (kid v1/v2), DDIA cap6 (compose healthy), Livro4 cap11 (Grafana).
