# PLANO F4 — GRAFANA CRED SYNC + VOZ POLISH — 2026-09-04 15:30
> **Branch:** `feat/final-100` `584e04a` SYNCED origin | **Base:** `aa253d9` | **Gates travados:** `175/175 2x WARN0 BUG0` + `68/68 2x` + `21/21 2x` + `27/27 2x 9 panels` + `54/54 2x` + `pytest 40 2x` + `7/7 healthy jefrey_*` + `compose -q RC0` + `promtool 7 rules SUCCESS`
> **Prioridade:** Fechar "Grafana 401 Invalid username or password" e provar Voz STT/TTS 100% sem quebrar Axiom #1 FAIL-CLOSED. Destranca F5 Tag v1.4.0-final-100.
> **Tempo:** 30m (15m cred sync + 15m voz polish) | **Depende de:** F0 ✅ F1 ✅ F2 ✅ F3 ✅ (584e04a) | **Próximo:** F5 Revalidação 2x + Tag → F6 Docs
> **Refs:** Axiom #1-7 + CIPHER 025-035 + 10 Livros (MCP Spec 2026-07-28, OpenAI Agents Cookbook, Security Eng 3rd, Prometheus Up&Running 2nd cap5/6/10/11, DDIA cap3/5/6/12, SWE cap8/14, Fluent 19-21, HPP cap1-4, LLM Apps 2024, Pragmatic 20th) + Sites Mark-LII/XXXIX/CEOGPT/HUD + PLANO MESTRE FINAL 100 V2

## 0) VALIDAÇÃO COMPLETA P0→F3 (linha-a-linha + deep + live) — 2026-09-04 15:15-15:30 ✅ 0 BUG

| Gate | 1ª | 2ª | Veredito |
|------|----|----|----------|
| validate_linha_a_linha_p0p1.py | 68 OK 0 BUG | 68 OK 0 BUG | ✅ |
| _validate_deep.py | 175/175 WARN0 BUG0 | 175/175 | ✅ Axiom #1-7 + CIPHER 025-035 |
| verify_p6_data.py | 21/21 | 21/21 | ✅ HNSW m16 ef64 pool_pre_ping 3600 kid v1/v2 XADD 10000 pg_dump |
| verify_p6.py | 27/27 9 panels | 27/27 | ✅ Prometheus + Grafana |
| verify_p7.py | 54/54 | 54/54 | ✅ Memory/RBAC/HITL/MCP |
| pytest -q | 40 passed 4 warns | 40 passed | ✅ |
| compileall -q src | RC0 | — | ✅ 64 files |
| docker compose config -q | RC0 | RC0 | ✅ |
| docker compose ps | 7/7 healthy jefrey-* | 7/7 healthy | ✅ |
| live /health | 200 ok | — | ✅ |
| live /auth/dev-token | 200 len64 | — | ✅ F2 |
| live /chat 401→200 | 401 sem token (Axiom#1) / 200 running com token | — | ✅ F3 fallback qwen2.5 |
| live /stt/health | 200 small pt | — | ✅ |
| live /tts/health + /tts/voices | 200 piper + 6 voices | — | ✅ |
| live Ollama /api/tags | 200 4 models has_qwen2 True qwen2.5:0.5b tools | — | ✅ |
| live /metrics | 200 jefrey_llm_* | — | ✅ |
| promtool check rules | SUCCESS 7 rules | — | ✅ |
| grafana dashboard | editable:false orgId:1 by(le)>=2 | — | ✅ fix CI 100711632864 |

> Commit F3 584e04a push origin/feat/final-100 SYNCED + tags SYNCED + working tree clean. Poll /chat/status ainda running sem complete em 16s (F3 95% — prova qwen texto real pendente F4-3).

## 1) GAPS F4 — DIAGNÓSTICO HONESTO

| # | Severidade | Achado | Evidência | Impacto | Fixa em |
|---|------------|--------|-----------|---------|---------|
| I-10 | 🔴 ALTA | **Grafana Login 401 Invalid username or password** | Volume jefrey_grafana_data antigo (criado antes de F1 name: jefrey) guarda admin antigo vs .env GF_SECURITY_ADMIN_PASSWORD atual | /3000 login e /api/dashboards 401 mesmo com .env correto — parece "nunca funciona" mas é estado do volume (DDIA cap3 Persistence) | **F4-1** |
| I-11 | 🟡 MÉDIO | **Volumes órfãos jarvis_jefrey_grafana_data (5)** | docker volume ls 10 volumes (5 jarvis_* órfãos + 5 jefrey_* novos) | Confusão vazamento Gordão_Oficial + risco down -v | F6 após pg_dump |
| I-12 | 🟡 MÉDIO | **Guard Grafana não no CI local** | scripts/guard_grafana.sh existe mas não revalidado 2x pós-F1 | Regressão editable:true | **F4-2** |
| I-13 | 🟢 BAIXO | **Poll /chat running sem complete** | POST /chat 200 running mas GET /status 8x running em 16s | E2E não prova texto qwen2.5 completo (precisa 30s + logs) | **F4-3** |
| I-14 | 🟢 BAIXO | **.env tem senhas em claro (GF_SECURITY_ADMIN_PASSWORD, N8N_BASIC_AUTH, POSTGRES_PASSWORD)** | grep .env 7 secrets | Vazamento se commitado (Axiom #5 LEAST PRIVILEGE) — mas .env gitignored ✅ | F4 lista segmentada sem vazar (Security Eng cap4) |

## 2) SENHAS — LISTA SEGMENTADA (Axiom #5 + Security Eng 3rd cap8 + CIPHER-031 + DDIA cap5)

> **Princípio:** .env é gitignored, nunca commitado. Listar POR CATEGORIA + LOCAL + REDE, sem expor valores em claro (redacted 3***3). Prova compose usa ${VAR} + volumes jefrey_* isolados de supabase_*_Gordao_Oficial.

| # | Serviço | Variável .env | Container | Volume | Porta | Uso | Estado |
|---|---------|---------------|-----------|--------|-------|-----|--------|
| 1 | Grafana | GF_SECURITY_ADMIN_USER=admin / GF_SECURITY_ADMIN_PASSWORD=BGl***ALZ | jefrey-grafana | jefrey_grafana_data | 3000:3000 | Login /3000 + datasource provisioning orgId:1 | ⚠️ volume antigo divergente — fix F4-1 |
| 2 | n8n | N8N_BASIC_AUTH_USER / N8N_BASIC_AUTH_PASSWORD | jefrey-n8n | jefrey_n8n_data | 5678:5678 | Workflow webhook /webhook + send_message futuro P2 | ✅ healthy |
| 3 | Postgres | POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB + JEFREY_DATABASE__URL=...@postgres:5432 | jefrey-postgres | jefrey_pgdata | 5432:5432 | pgvector HNSW 768dim pool_pre_ping 3600 | ✅ healthy |
| 4 | Redis | REDIS_PASSWORD / JEFREY_REDIS__URL=redis://:***@redis:6379 | jefrey-redis | jefrey_redisdata | 6379:6379 | Streams XADD 10000 + DLQ 5000 + rate_limit pipeline | ✅ healthy |
| 5 | API | JEFREY_API__SECRET_KEY=7da***946 (64 hex) | jefrey-api | — (:ro) | 8000:8000 | HMAC kid v1/v2 + JWT RS256 jwks.json + TTLCache 1024/60 compare_digest | ✅ /health 200 |
| 6 | LLM | JEFREY_LLM__API_KEY=sk-***qui (placeholder local) | — (host Ollama) | — | host 11434 | Ollama qwen2.5:0.5b tools fallback (Axiom #1 visible) | ✅ host 200 |
| 7 | Voz | JEFREY_VOICE__WAKE_WORD__ACCESS_KEY=sua***ice (placeholder) | jefrey-api (sem container novo Axiom#7) | — | 8000 /stt /tts | Porcupine C++ quando key real (Mark-LII) | ✅ small/piper 200 |
| 8 | Prometheus | — (sem senha, rete 30d) | jefrey-prometheus | jefrey_prometheus_data | 9090:9090 | 7 alerts SLO + StT>2s | ✅ healthy |
| 9 | Gordão_Oficial | supabase_*_Gordao_Oficial (rede/volume/container separados) | supabase_* | supabase_* | — | Prova isolamento: docker network ls jefrey_default vs supabase_network_Gordao_Oficial | ✅ isolado |

**Isolamento Docker (DDIA cap6 Partitioning + Axiom #2 ISOLAMENTO):** compose project name: jefrey (Compose Spec 2.24) + volumes explicit name: jefrey_* evita double prefix jefrey_jefrey_* e vazamento jarvis. Networks: jefrey_default vs Gordao_Oficial_default vs jarvis_default (órfão) — docker network ls prova. Containers prefix jefrey-* vs supabase_*_Gordao_Oficial.

## 3) PLANO EXECUÇÃO F4 — 3 PASSOS (15m cred + 15m voz)

### F4-1 Grafana Cred Sync (10m) — DDIA cap3 + Axiom #1 + Security Eng cap8
**Ref:** Prometheus Up&Running 2nd cap11 Grafana provisioning, DDIA cap3 Persistence (volume state), SWE cap14 idempotente 2x
```bash
# Diagnóstico sem vazar senha
docker logs jefrey-grafana --tail 20 | grep -i "admin|password|auth"
docker volume ls | grep grafana  # 2 volumes: jefrey_grafana_data (novo) + jarvis_jefrey_grafana_data (órfão)
docker compose ps | grep grafana
cat .env | grep GF_SECURITY_ADMIN_PASSWORD # redacted

# Fix fail-closed sem apagar dados à toa (Axiom #1): reset password dentro do volume atual
docker exec jefrey-grafana grafana-cli admin reset-admin-password "${GF_SECURITY_ADMIN_PASSWORD}"
# alternativa idempotente se grafana-cli falhar: docker volume rm jefrey_grafana_data (só se provisioning recria datasource+dashboard — DDIA cap3 backup)
docker compose restart grafana && sleep 8 && docker compose ps | grep grafana

# Prova 200 com auth
curl -s -u admin:${GF_SECURITY_ADMIN_PASSWORD} http://localhost:3000/api/health # 200
curl -s -u admin:${GF_SECURITY_ADMIN_PASSWORD} http://localhost:3000/api/dashboards/uid/jefrey-main # 200 + editable:false
curl -s http://localhost:3000/api/dashboards/uid/jefrey-main # 401 (Axiom #1 fail-closed sem auth)
```
**DoD F4-1:** login /3000 com senha .env 200 + /api/dashboards 200 editable:false + 401 sem auth provado.

### F4-2 Guard Grafana 2x (5m) — SWE cap14 + Prometheus cap11 + Axiom #6
```bash
sh scripts/guard_anti_patterns.sh  # 6 greps 0 hits
# guard_grafana.sh (se existir) ou grep inline:
grep -q '"editable": false' docker/grafana/dashboards/jefrey.json && echo PASS editable false || echo FAIL
grep -q '"orgId": 1' docker/grafana/provisioning/datasources/datasource.yml && echo PASS orgId 1 || echo FAIL
grep -q 'by (le)' docker/grafana/dashboards/jefrey.json && echo PASS "by(le)>=2" || echo FAIL # L4 cap6 histogram_quantile
promtool check rules docker/prometheus/alerts.yml # SUCCESS 7 rules
# revalidar 2x
```
**DoD F4-2:** editable:false + orgId:1 + by(le) + promtool SUCCESS + guard 6/6.

### F4-3 Voz Polish + Poll Complete 30s (15m) — HPP cap1-4 + DDIA cap12 + Axiom #7
```bash
# Prova STT/TTS já 200 (F3)
curl -s -H "Authorization: Bearer $DEV" http://localhost:8000/stt/health # 200 small
curl -s http://localhost:8000/tts/voices # 6 voices
# Poll longo até complete com qwen2.5 tools (fallback já no api 584e04a)
DEV=$(curl -s -X POST http://localhost:8000/auth/dev-token | jq -r '.access_token // .token')
curl -s -X POST http://localhost:8000/chat -H "Authorization: Bearer $DEV" -H "X-User-Id: test-f4" -d '{"message":"oi, diga oi em 1 frase","thread_id":"f4-final","user_id":"test-f4"}' # 200 running
for i in 1..15; do sleep 2; curl -s -H "Authorization: Bearer $DEV" http://localhost:8000/chat/status/f4-final; done # deve virar complete com texto
docker logs jefrey-api --tail 40 | grep -i "fallback|qwen2|does not support|LLM probe"
ollama list | grep qwen2.5 # 397MB Q4_K_M tools
```
**DoD F4-3:** /stt/health 200 + /tts/voices 6 + /chat poll 30s complete com texto qwen + logs sem "does not support tools" error (fallback warning OK).

## 4) DIRETRIZES — AXIOM + CIPHER + LIVROS + SITES + PROJETOS

- **Axiom #1 FAIL-CLOSED:** Grafana 401 sem auth OK (não é bug), 401 com senha errada OK, dev-token 403 em prod (CIPHER-021). Nunca silenciar com except:pass (guard GREP-3).
- **Axiom #2 ISOLAMENTO:** per-tenant jefrey.events.{user_id}.{tool} + DLQ jefrey:dlq:{user_id} + HMAC kid v1/v2 dual-verify (CIPHER-033) — Grafana orgId:1 isolado de supabase.
- **Axiom #5 LEAST PRIVILEGE:** :ro volume ./:/app:ro + read_only tmpfs /app/.cache + crawl_brute_force overwrite=False + CORS explicit + pool_pre_ping.
- **CIPHER 025/026/031/033:** dual-write, rate_limit pipeline fail-closed, OAuth2 JWKS RS256+kid, HMAC EventBus kid rotation.
- **Livros:** Security Eng 3rd cap4/8 (authz + cred sync), Prometheus cap5 cardinality (<800 sem user_id label), cap6 histogram by(le), cap10 alert StT>2s 5m, cap11 Grafana datasource httpMethod POST, DDIA cap3 persistence (volume vs down -v), cap5 replication, cap6 partitioning (network/volume), cap12 tuning (HNSW m=16 ef64 48ms p95), SWE cap8 Style cap14 Testing 2x, HPP cap1-4 cProfile orjson lru_cache, LLM Apps 2024 RAG 6 memory types.
- **Sites:** Mark-LII youtube vTIq4pUR7o0 (estética hardware + wake), Mark-XXXIX iq0DlY0Sg-k (voice pipeline opus/webm 16k → faster-whisper small int8 → qwen2.5 → elevenlabs/piper → audio autoplay + HUD AnalyserNode), CEOGPT moritz.ceogpt.de/jarvis-aufbau (glassmorphism styles.css?v=6 + HUD pulse + hue wheel + chime 2.4s), HUD reactor instagram DcjTYTiCt6P.
- **Projetos ref:** Mark-LII (FatihMakes) — ahead: estetica viva/hardware, behind: 175/175 segurança; Mark-XXXIX-OR — ahead: voice pipeline pyttsx3, behind: obs/escala. Jefrey equipara com HUD pulse + chime + wake porcupine em P3.

## 5) DoD F4 100% (checklist para fechar commit + push)

- [ ] F4-1 Grafana login 200 com .env + /api/dashboards 200 editable:false + 401 sem auth
- [ ] F4-2 guard_grafana editable:false orgId:1 by(le) + promtool 7 rules SUCCESS + guard 6/6 2x
- [ ] F4-3 STT 200 small + TTS 6 voices + /chat poll 30s complete texto qwen2.5 + logs fallback OK
- [ ] revalidar gates 2x: 175/175 2x + 68/68 2x + 21/21 2x + 27/27 2x + 54/54 2x + pytest 40 2x + compileall -q + compose -q + 7/7 healthy
- [ ] git commit -m "feat(f4): grafana cred sync reset-admin-password + guard + voz poll complete" + push origin feat/final-100

## 6) PRÓXIMOS — F5 + F6 + P2/P3

- **F5 Revalidação Final 2x + Tag v1.4.0-final-100 (30m):** 175/175 2x +21/21 2x +27/27 2x +54/54 2x +68/68 2x + pytest 40 2x + docker 7/7 + live /health /chat Bearer /stt/health /tts/voices + git push --tags + merge feat/final-100→main.
- **F6 Docs Sync (15m):** TODO.md + CHANGELOG [1.4.0-final-100] + JEFREY-AUDIT/25_LINE_BY_LINE_SWEEP_P0-P7.md + limpar órfãos jarvis_jefrey_* após pg_dump + remover temps.
- **P2 Hand+Plugins 60m / P3 Estética CEOGPT 45m / P4 SRE 30m** — backlog pós-final-100.
