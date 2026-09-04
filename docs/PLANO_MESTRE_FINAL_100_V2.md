# PLANO MESTRE FINAL 100 V2 — JEFREY COMERCIAL — 2026-09-04 12:55
> **Base travada:** `main` aa253d9 SYNCED origin/main + `feat/final-100` (F0 criada) — deep 175/175 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x (9 panels) + verify_p7 54/54 2x + 68/68 linha-a-linha 0 BUG + pytest 40 + guard 6/6 + 7/7 healthy + promtool 7 rules
> **Tags:** v1.0.0 v1.0.0-p5-c v1.1.0 v1.2.0-ui v1.3.0-p1-voz — **Prioridade máxima:** F0 Trava + F1 Docker Sync `jefrey` sem vazamento (por que "nunca funciona nada")

---

## 0) DIRETRIZES CANÔNICAS (Axiom + CIPHER + Livros + Sites)

### Axioms 1-7 (FAIL-CLOSED)
| Axiom | Regra | Onde dói hoje |
|-------|-------|---------------|
| #1 FAIL-CLOSED | deny/false/raise, nunca `pass`/`allow` silencioso | Auth 401 correto mas UI sem wiring parece bug |
| #2 ISOLAMENTO | `user_id=None→guest`, `_build_filter` mandatory, `topic jefrey.events.{user_id}.{tool}`, DLQ `jefrey:dlq:{user_id}` | OK 21/21, mas compose `name: jarvis` (pasta) vaza naming |
| #3 SEM STUB EM PROD | `JEFREY_ENV=dev/prod` + `validate_for_production()` | OK HMAC `?required`, mas `JEFREY_VOICE__ENABLED=false` esconde voz |
| #4 PERSISTÊNCIA REAL | Redis `setex pipeline incr/expire`, `TTLCache` só dev | OK |
| #5 LEAST PRIVILEGE | `overwrite=False`, `:ro`, CORS explicit, `pool_pre_ping` | OK `:ro` + `read_only:true` + `tmpfs` |
| #6 OBSERVABILIDADE | `urlsafe_b64encode` sem padding, `RS256+kid`, `compare_digest`, `sort_keys` | OK jwks RS256 |
| #7 1 PROGRAMA 7 PEÇAS | Sem novo container à toa | OK P1 voz sem container novo (reuso `jefrey-api`) |

### CIPHER 025-035
- 025 dual-write, 026 rate_limit pipeline fail-closed, 028/029 policy deny_by_default, 031 OAuth JWKS/introspect, 032 Skill Risk, 033 HMAC kid v1/v2 dual-verify, 035 token refresh `valid_` só dev — **todos validados 175/175**

### 10 Livros (docs/REFERENCES.md)
1. **MCP Spec 2026-07-28** — `stateless_http`, `OAuth Resource Server`, tool injection (CIPHER-011)
2. **OpenAI Agents Cookbook** — `RunContextWrapper`, `handoff`, tracing → Prometheus
3. **Security Engineering (Anderson 3rd)** — modelo de ameaça, controle de acesso (PolicyEngine)
4. **Prometheus Up & Running 2nd** — cap5 Cardinality (sem `user_id` label), cap6 Histograms `by(le)`, cap10 Alerting, cap11 Grafana
5. **DDIA (Kleppmann)** — cap3 Persistence, cap5 Replication, cap6 Partitioning (network/volume), cap12 Tuning (HNSW, pool)
6. **SWE at Google** — cap8 Style, cap14 Testing (idempotente 2x, `pytest 40 + evals 6 = 46`)
7. **Fluent Python 19-21** — `WeakValueDictionary _PG_CACHE`, `lru_cache 1024`, descritores
8. **High Performance Python cap1-4** — `cProfile 7M calls 15s`, `orjson`, `bench p50 48ms p95 55ms`
9. **Building LLM Applications (O'Reilly 2024)** — RAG 6 tipos memória, 6 evals `test_memory_types.py`
10. **Pragmatic Programmer 20th** — broken windows, tracer bullets P0→P8

### Sites / Vídeos Referência
- https://www.youtube.com/watch?v=vTIq4pUR7o0 — Mark-LII build físico + wake word
- https://www.youtube.com/watch?v=iq0DlY0Sg-k — Mark-XXXIX voice pipeline
- https://moritz.ceogpt.de/jarvis-aufbau/ — **CEOGPT glassmorphism + HUD pulse + hue wheel + chime 2.4s + styles.css?v=6**
- https://www.instagram.com/reel/DcjTYTiCt6P/ — HUD reactor demo
- https://www.youtube.com/watch?v=x5ZIzhOqTzE — Mark-LII estetica

---

## 1) ONDE ESTAMOS — % HONESTO (linha-a-linha 68/68 + deep 175/175)

| Camada | % Código | % Usável (leigo abre localhost:8000 e conversa) | Gates |
|--------|----------|--------------------------------------------------|-------|
| **P0 Hardening** | 100% | 100% | 175/175, 6 greps 0 hits |
| **P1 Voz STT/TTS/Wake** | 100% | 60% (`ENABLED=false` + sem token wiring) | 68/68, 42 tools, 9 panels, faster-whisper small int8 |
| **P2-P5 Obs** | 100% | 95% (Grafana 401 cred) | 27/27, 7 alerts firing OK |
| **P6 Data pgvector HNSW** | 100% | 100% | 21/21 bench p95 52ms ef64 |
| **P7 Integração** | 100% | 95% (Ollama host) | 54/54, RBAC HITL |
| **UI Shell Vite+React** | 90% | 70% (auth wiring incompleto) | 5 chunks 633kB, code-split OK |
| **Docker/Infra** | 85% | 80% (`name: jarvis` + `jarvis_jefrey_*` mistura) | 7/7 healthy, `config -q RC0`, `:ro` OK |
| **E2E básico** | 92% global código | **72% produto usável** | Falta F1+F2 wiring |
| **GLOBAL** | **92%** | **72%** → 100% após F1-F4 | |

**Por que "nunca funciona nada" (3 fios, não lógica):**
1. **Auth 401 correto** mas UI não injeta `Bearer + X-User-Id` em todas rotas → parece quebrado (Axiom #1).
2. **`JefreyConfigInvalid firing`** (`jefrey_config_valid==0`) em dev + `qwen2:0.5b` sem Ollama host → `/chat 500` (não é bug, é infra).
3. **Docker naming** `jarvis_default` + `jarvis_jefrey_pgdata` mistura pasta+container → confusão "Gordão vazando".

---

## 2) COMPARATIVO MARK-LII / MARK-XXXIX-OR — ONDE ESTAMOS (faltou no plano anterior)

> Repo analisado: https://github.com/FatihMakes/Mark-LII.git (voz viva + HUD) e https://github.com/FatihMakes/Mark-XXXIX-OR.git (OR = Online Resources)

### O que ELES fazem que NÓS NÃO fazemos (GAPs)
| Feature deles | Status Jefrey | Gap | Prioridade |
|---------------|---------------|-----|------------|
| **Hardware HUD físico** (reactor LED + pulse real via GPIO/Arduino) | Só CSS `scale 1.0-1.6 neon cyan` + `AnalyserNode.getByteFrequencyData()` | Falta `navigator.serial` / `WebUSB` bridge ou mock HUD hardware | P3 |
| **Wake word offline 100% local (Porcupine C++ / snowboy)** | Web Speech `webkitSpeechRecognition` pt-BR interim (precisa internet) + porcupine só se `PICOVOICE_ACCESS_KEY` | Wake 100% offline ainda não | P1.4 parcial → P3 fechar |
| **Theming vivo (hue wheel hex, glassmorphism tokens `styles.css?v=6`)** | Tailwind 3.4 + shadcn, mas sem `hue wheel` nem `Live Theming` Mark-LII | CEOGPT tokens não copiados | P3 |
| **Boot chime 2.4s synthesized + easter eggs** | Sem chime | `AudioContext` chime faltante | P3 |
| **Plugins físicos** (file 500MB, browser_control playwright, send_message WhatsApp/Telegram via n8n) | Só `file_processor`, `web_search Tavily`, `automation` n8n | `browser_control`, `send_message` via `http://n8n:5678/webhook` | P2 |
| **Remote Dashboard QR AES-256-CBC + Morning Briefing + Hardware Monitoring** | `Observability.tsx` com 9 panels link, mas sem QR nem briefing | Backlog Mark-LII | P4 |
| **Clipboard Intelligence** | Não | — | P4 |

### O que NÓS fazemos que ELES NÃO fazem (Vantagem Jefrey)
| Feature nossa | Deles | Por que importa |
|---------------|-------|-----------------|
| **Fail-closed Axiom #1-7 + CIPHER 025-035 + 6 greps + 175/175 idempotente** | Scripts bash soltos, sem guard | Produção segura |
| **Multi-tenant isolamento `user_id=None→guest` + `jefrey.events.{user_id}.{tool}` + DLQ per user + Redis Streams XADD 10000 + XGROUP + XACK** | Single user | SaaS |
| **pgvector HNSW m=16 ef=64 `SET LOCAL hnsw.ef_search=int(ef)` + `pool_pre_ping` + bench p50 48ms** | Chroma local | Escala |
| **Observabilidade SRE 9 panels `by(le)` + 7 alerts `histogram_quantile by(le)` + `promtool` + `drill_alerts.py` 7 drills** | Logs soltos | SLO |
| **HITL approvals + PolicyEngine RBAC GUEST/USER/ADMIN + RiskLevel LOW/MED/HIGH/CRITICAL** | Sem HITL | Enterprise |
| **MCP stateless_http + OAuth JWKS RS256+kid + introspect + `compare_digest`** | MCP simples | MCP Spec 2026-07-28 |
| **Audit fallback `data/audit_fallback.jsonl` dual-write + `redact_pii`** | Sem audit | Compliance |
| **Vite code-split 5 chunks vendor 163kB + charts 383kB + `StaticFiles mount /`** | Flask simples | Perf |

**Conclusão equiparação:** Jefrey está **à frente em segurança/obs/escala**, **atrás em estetica viva + hardware + plugins físicos**. F2-F4 fecham usabilidade, P2/P3 fecham estetica/plugins para **superar** Mark-LII.

---

## 3) PLANO MESTRE FINAL 100 V2 — ORDEM IDEAL (Axiom #1, SWE cap14, DDIA cap6)

> **Ordem B (T3 P8 antes de T2 P7) já executada 11c864c. Agora F0/F1 são pré-requisito para qualquer P2/P3 — sem isolamento limpo, nada mais é confiável.**

### FASE F0 — TRAVA E BRANCH (15m) — PRIORIDADE MÁXIMA — SWE cap14, Axiom #7

**Objetivo:** Travar P0+P1 100% sem regressão, proteger `main`, alinhar docs.

| # | Ação | Comando | Gate | Livro |
|---|------|---------|------|-------|
| F0-1 | Branch `feat/final-100` (NÃO codar em main) | `git checkout -b feat/final-100` | `git branch --show-current == feat/final-100` | SWE cap8 |
| F0-2 | Status clean + tags sync | `git status --porcelain == ""` + `git tag --list` 5 tags | 5 tags SYNCED origin | DDIA cap5 |
| F0-3 | Validar CI local antes de tocar | `docker compose ps 7/7 healthy` + `compose config -q RC0` + `.env` existe | 7/7 RC0 | Axiom #7 |
| F0-4 | Revalidar gates 2x (idempotente) | `_validate_deep 175/175 2x` + `verify_p6_data 21/21 2x` + `verify_p6 27/27 2x` + `verify_p7 54/54 2x` + `validate_linha_a_linha 68/68` + `pytest 40` + `compileall -q` | 313 checks 2x | SWE cap14 |
| F0-5 | Sincronizar TODO.md | `TODO.md` base `aa253d9` (não 11c864c) | `TODO.md` data 2026-09-04 | Pragmatic cap5 |
| F0-6 | Commit F0 | `git commit -m "chore(f0): trava P0+P1 175/175 + branch feat/final-100"` | working tree clean | — |

**DoD F0:** `feat/final-100` criada, 313 checks 2x verdes, TODO.md sync, sem código alterado.

---

### FASE F1 — DOCKER SYNC `jefrey` SEM VAZAMENTO (45m) — PRIORIDADE MÁXIMA — Axiom #2/#5, DDIA cap6, CIPHER-032

**Problema raiz:** `docker-compose.yml` sem `name:` → Compose deriva `jarvis` da pasta `C:\Users\Pedro\jarvis` → `network jarvis_default` + `volumes jarvis_jefrey_*` (mistura) + confusão com `supabase_Gordao_Oficial`.

**Solução:** Fixar `name: jefrey` top-level (Compose Spec 2.24).

| # | Ação | Arquivo | Detalhe | Gate |
|---|------|---------|---------|------|
| F1-1 | `name: jefrey` linha 1 | `docker-compose.yml:1` | `name: jefrey` antes de `services:` | `docker compose config --format json \| jq .name == "jefrey"` |
| F1-2 | Volumes rename limpo | `docker-compose.yml` volumes | `jefrey_pgdata` `jefrey_redisdata` `jefrey_n8n_data` `jefrey_prometheus_data` `jefrey_grafana_data` (já estão `jefrey_*`, mas com prefixo `jarvis_` no engine → após `name: jefrey` viram `jefrey_*` puro) | `docker volume ls \| grep jefrey` sem `jarvis_` |
| F1-3 | Network rename | implícito | `jefrey_default` (não `jarvis_default`) | `docker network ls \| grep jefrey_default` |
| F1-4 | Prova isolamento vs Gordão | `docker network inspect jefrey_default` vs `supabase_network_Gordao_Oficial` | Redes distintas, sem `external:true` | `docker network ls` 2 redes isoladas |
| F1-5 | Recriar stack | `docker compose down && docker compose up -d --build` | `docker compose ls == jefrey running(7)` | 7/7 healthy 2x |
| F1-6 | Revalidar tudo 2x | `_validate_deep 175/175` + `verify_*` + `pytest 40` + `compose config -q` | 313 2x | SWE cap14 |
| F1-7 | Commit F1 | `git commit -m "fix(docker): name jefrey + sync network/volume sem vazamento (Axiom #2)"` | `git log --oneline -1` | DDIA cap6 |

**DoD F1:** `docker compose config` → `name: jefrey`, `network: jefrey_default`, `volumes: jefrey_*`, `docker volume ls` sem `jarvis_jefrey_*`, 7/7 healthy, 313 2x verdes, sem vazamento com `supabase_Gordao_Oficial`.

**Livros/Sites:** DDIA cap6 Partitioning, Security Engineering cap8 Least Privilege (`:ro` já ok), Compose Spec `name:`.

---

### FASE F2 — AUTH WIRING "BÁSICO FUNCIONA" (60m) — Axiom #1, CIPHER-031, MCP Spec

| # | Ação | Arquivo | Detalhe | Gate |
|---|------|---------|---------|------|
| F2-1 | Centralizar token | `ui/src/lib/api.ts` | `getToken()` + `getUserId()` + `authHeaders()` injeta `Authorization: Bearer` + `X-User-Id` em todas calls | `curl /chat 401 → curl -H "Bearer $DEV" /chat 200` |
| F2-2 | Dev token endpoint | `src/jefrey/api/auth.py` (novo) | `POST /auth/dev-token` só `JEFREY_ENV!=prod` (CIPHER-021), gera `JWT RS256` temporário, popula `localStorage` | `pytest` mock |
| F2-3 | UI wiring | `ui/src/pages/Chat.tsx` `useVoice.ts` `Memory.tsx` `Approvals.tsx` | Todas usam `authHeaders()` | Live Chat 200 |
| F2-4 | Docs leigo | `docs/GUIA_LEIGO_JEFREY.md` | "Sem token, /chat DEVE dar 401 (fail-closed)" | — |

**DoD F2:** `localhost:8000` abre, Chat envia mensagem e recebe `running` com `qwen2:0.5b`, sem 401 fantasma.

### FASE F3 — LLM E2E + VOZ ENABLE (30m) — DDIA cap12, HPP cap1-4

| # | Ação | Detalhe |
|---|------|---------|
| F3-1 | Ollama host check | `curl http://host.docker.internal:11434/api/tags` log no startup `jefrey-api` |
| F3-2 | Voz enable dev | `.env JEFREY_VOICE__ENABLED=true` + `JEFREY_VOICE__STT__MOCK=false` para demo real |
| F3-3 | Fallback mock visível | UI badge "LLM offline — modo mock" se Ollama ausente |

### FASE F4 — GRAFANA CRED SYNC + VOZ POLISH (30m) — Livro4 cap11

| # | Ação | Detalhe |
|---|------|---------|
| F4-1 | Grafana senha | `docker volume rm jefrey_grafana_data` ou `grafana-cli admin reset-admin-password BGl-LcTMp5NPTALZ` + `curl -u admin:... /api/dashboards/uid/jefrey-main 200` |
| F4-2 | `guard_grafana.sh` | `editable:false orgId:1 by(le)>=2` revalida |

### FASE F5 — REVALIDAÇÃO FINAL 2X + TAG v1.4.0-final-100 (30m) — SWE cap14

```bash
set PYTHONPATH=. && python scripts/_validate_deep.py          # 175/175 2x
set PYTHONPATH=. && python scripts/verify_p6_data.py          # 21/21 2x
set PYTHONPATH=. && python scripts/verify_p6.py               # 27/27 2x 9 panels
set PYTHONPATH=. && python scripts/verify_p7.py               # 54/54 2x
set PYTHONPATH=. && python scripts/validate_linha_a_linha_p0p1.py # 68/68 2x
set PYTHONPATH=. && python -m pytest -q                       # 40 2x
docker compose config -q && docker ps --format "{{.Names}} {{.Status}}" | grep jefrey
curl -s http://localhost:8000/health                          # 200
curl -s -H "Authorization: Bearer $DEV" http://localhost:8000/chat -d '{"message":"oi"}' # 200
curl -s -H "Authorization: Bearer $DEV" http://localhost:8000/stt/health # 200
curl -s http://localhost:3000/api/health                      # 200
curl -s http://localhost:9090/-/healthy                       # 200
```

- `git tag v1.4.0-final-100 && git push origin feat/final-100 && git push --tags` → merge `feat/final-100` → `main`

### FASE F6 — DOCS SYNC (15m)
- `TODO.md` + `CHANGELOG.md [1.4.0-final-100]` + `JEFREY-AUDIT/25_LINE_BY_LINE_SWEEP_P0-P7.md` alinhados.

---

## 4) CRONOGRAMA F0/F1 EXECUÇÃO IMEDIATA (HOJE)

```
12:55-13:10  F0 Trava (branch + 313 checks 2x + TODO sync)     ← AGORA
13:10-13:55  F1 Docker Sync (name: jefrey + down/up + 313 2x)
13:55-14:55  F2 Auth Wiring (dev-token + UI headers)
14:55-15:25  F3 LLM E2E + Voz Enable
15:25-15:55  F4 Grafana Cred
15:55-16:25  F5 Revalidação 2x + Tag v1.4.0
16:25-16:40  F6 Docs
```

---

## 5) RISCOS E MITIGAÇÕES (Pragmatic cap5)

| Risco | Mitigação | Axiom |
|-------|-----------|-------|
| `name: jefrey` quebra volumes existentes `jarvis_jefrey_*` | `docker compose down -v` só se backup `pg_dump` OK; senão `docker volume create jefrey_*` + `cp` | DDIA cap5 |
| Auth wiring quebra 401 esperado | Manter `TTLCache` + `compare_digest` + `fail-closed` | #1 |
| Ollama OOM `3.3GB` no host 6GB | Manter `qwen2:0.5b 352MB` + `keep_alive -1` | HPP cap1 |

---

## 6) PRÓXIMOS APÓS F1 (P2/P3 para superar Mark-LII)

- **P2 Mão Hand + Plugins 60m:** `src/jefrey/plugins/` + `browser_control` playwright + `send_message` WhatsApp/Telegram via `n8n:5678/webhook` + `Undo/Confirm CRITICAL`
- **P3 Estética CEOGPT 45m:** `hue wheel hex` + `glassmorphism styles.css?v=6` + `HUD reactor pulse full` + `chime 2.4s` + `npm audit fix --force`
- **P4 SRE 30m:** `Hardware Monitoring CPU/RAM` + `Morning Briefing` + `Remote Dashboard QR AES-256-CBC`

---

*Gerado em `feat/final-100` — F0 inicia agora. Cada fase só avança com 2x verde (SWE cap14).*
