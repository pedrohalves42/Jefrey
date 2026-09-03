# PLANO P7 — PERF (T2) V1.0 — 60m — 150→158 — pós T1 7/7 healthy 11:15
> **Base 11:15:** T1 100% FECHADO 5c54440 + 150/150 2x + 21/21 2x + 40 passed + 7/7 healthy (api/mcp/redis/pg/prom/grafana/n8n) + promtool 6/6 + grafana 8 panels by(le):2
> **Objetivo:** PERF sem quebrar nada (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #4 PERSISTENCIA, #6 LEAST PRIVILEGE + CIPHER 021/025/026/033 + DDIA cap12 + Livro4 cap5/6 + HPP cap1-4 + Fluent 19-21 + Building LLM Apps)
> **GO/NO-GO:** ganho p95 <5% → docs/PERF_TUNING.md e vai v1.1.0, NAO bloqueia P8 (SWE cap14). 158/158 só se ganho >=5% OU docs explica por que nao.

## 0) VALIDACAO COMPLETA 11:15 — O QUE FUNCIONA vs O QUE FALTA

### 100% provado (nao opiniao)
| Gate 11:15 | Resultado | Ref |
|---|---|---|
| verify_p6_data | 21/21 2x equal:true 100% DATA OK | DDIA cap3/6 |
| _validate_deep | 150/150 2x eq:true WARNS0 BUGS0 | SWE cap14 |
| pytest | 40 passed 4 warnings | CIPHER-032 |
| compileall | RC0 + py_compile OK | SWE cap8 |
| guard 6 greps | 6/6 PASS pre-commit | Axiom #6 |
| docker ps | 7/7 healthy api/mcp/redis/pg/prom/grafana/n8n | DDIA cap6 |
| compose config | RC0 | DDIA cap6 |
| promtool check | SUCCESS 6 rules | Livro4 cap10 |
| promtool test | SUCCESS | Livro4 cap10 |
| grafana | 8 panels by(le):2 editable:false orgId:1 | Livro4 cap6/11 |
| HNSW | CONCURRENTLY AUTOCOMMIT m16 ef64 | DDIA cap12 |
| Streams | maxlen10000 DLQ maxlen5000 XACK dual-verify v1/v2 | CIPHER-033 |
| cardinality | <800 sem user_id EVENTBUS_KID_LEGACY_TOTAL [] | Livro4 cap5 |
| git | CLEAN + hardening.log 13227 bytes | DDIA cap3 |
| GLOBAL | 99% (falta T2+T3 para 100%) | Axiom #1 |

### O QUE FALTA PARA 100% ATE T2 (P7 = 158/158) — 8 gates W
| Gap | W | Ref | Tempo |
|---|---|---|---|
| reports/p7-cprofile.prof inexistente | W1 cProfile | HPP cap1 | 15m |
| hot path nao perfilado (sleep2/json dumps/WeakValueDictionary) | W2 line/memory prof | HPP cap2-3 | 10m |
| otimizacao sem regressao nao feita | W3 otim | Fluent 19-21 Axiom #2 | 20m |
| evals 6 memory types inexistente | W4 evals | Building LLM Apps | 15m |
| bench p95 baseline nao salvo | W5 bench | DDIA cap12 Livro4 cap6 | incl W4 |
| re-valida idempotente pos-P7 | W6 guard/verify | SWE cap14 | 2m |
| deep 158/158 secao W | W7 deep | SWE cap14 | 5m |
| docs/PERF_TUNING.md | W8 docs | Pragmatic | 3m |
| D5 tag push pendente | v1.0.0-p5-c local | SWE cap14 | 2m (so P8) |

TOTAL T2: 60m. Sem T2 GLOBAL 99% → com T2 99.5% → com P8 162/162 = 100%.

## 1) PRINCIPIOS INEGOCIAVEIS

**Axiom 6 FAIL-CLOSED:** FAIL-CLOSED deny/false/raise | ISOLAMENTO user_id=None->guest + _build_filter mandatory + topic per-tenant + DLQ per-tenant + UNKNOWN deny | SEM STUB EM PROD JEFREY_ENV dev/prod + validate_for_production | PERSISTENCIA setex pipeline incr/expire pool_pre_ping 3600 TTLCache so dev | CRIPTO urlsafe_b64encode RS256+kid aud/iss/exp compare_digest kid v1->v2 | LEAST PRIVILEGE overwrite=False :ro CORS explicit allow_credentials False

**CIPHER:** 021 silent except nunca pass | 025 dual-write audit redact_pii 2 camadas | 026 rate limiting pipeline fail-closed | 033 HMAC kid v1/v2 + EVENTBUS_KID_LEGACY_TOTAL [] | 032 Skill Risk | 035 Token Refresh | 010 audit | 028/029 policy

**Livros T2:** HPP cap1-4 (cProfile/line_profiler/memory_profiler) + Fluent 19-21 (async) + Building LLM Apps (evals) + DDIA cap12 (tuning) + Livro4 cap5/6 (cardinality/hist)

**Qualidade SWE cap8:** py_compile + compileall + guard 6/6 + sem In-memory/overwrite/:-jefrey/.:/app sem :ro

## 2) MAPA DE GATES

| Gate | Total | Quando | Adiciona |
|---|---|---|---|
| 150/150 |150| P6-C + T1 5c54440 | ATUAL |
| 158/158 |158| P7 T2 | +8 W (cProfile+line_prof+otim+evals+bench+guard+deep+docs) |
| 162/162 |162| P8 T3 | +4 X (compose healthy+IdP real+CHANGELOG+tag) |

Regra: nunca 158 sem 150/150 2x + 7/7 healthy + 40 passed. Nunca 162 sem 158 ou docs PERF_TUNING <5%.

## 3) P7 DETALHADO — 4 SUB-TAREFAS (60m)

### T2.1 Profiling hot paths (15m, HPP cap1)
- T2.1a (5m) cProfile: python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py + pstats sort cumtime 20 linhas -> reports/p7-cprofile.txt. Gate W1.
- T2.1b (5m) Identificar hot paths: docs/PERF_TUNING.md sec1: ToolExecutor sleep(2), json dumps/_to_chroma_metadata, WeakValueDictionary. Medir % total. Nao editar codigo ainda.
- T2.1c (5m) Histograma baseline: python scripts/bench_hnsw.py ef 64 vs 200 -> reports/p7-bench.log p95 baseline (ex 56ms/86ms P6-A). Validar histogram_quantile(0.95, sum(rate(bucket[5m])) by (le)). Gate W5 parcial.

### T2.2 Otimizacao sem regressao (20m, HPP cap2-3 + Fluent 19-21 + Axiom #2)
- T2.2a (8m) Polling sleep(2) -> event-driven (asyncio.Event / XREADGROUP block 5000ms) OU documentar SLO 2s se quebrar HITL. Nunca quebrar PolicyEngine/thread_id/HITL/_build_filter.
- T2.2b (6m) json dumps memoize: functools.lru_cache 1024 ou orjson se ganho >10% pstats, mantendo redact_pii 2 camadas (CIPHER-025). Nunca user_id em labelnames (Livro4 cap5).
- T2.2c (6m) WeakValueDictionary cache se hot path >5% pstats. memory_profiler valida RAM. Gate W2+W3: py_compile+compileall+guard 6/6+verify 21/21 2x+deep 150/150 verdes apos cada micro-otim. Se falhar, revert.

### T2.3 Evals 6 memory types (15m, Building LLM Apps + awesome-llm-apps 135k)
- T2.3a (8m) Criar evals/test_memory_types.py: 6 tipos episodic/semantic/procedural + short_term/long_term/vector (src/jefrey/memory). Cada 20 casos, p95 <2x baseline + recall@5 >0.7. Usa awesome-llm-apps como ref pattern. Sem modelo pago, chroma local nomic-embed-text 768.
- T2.3b (4m) Rodar: python -m pytest evals/test_memory_types.py -q -> 6/6. Salvar reports/p7-evals.log p95 por tipo.
- T2.3c (3m) PERF_TUNING sec2: tabela 6 tipos x p95 x ganho vs baseline x custo (ollama 30B precisa placa dedicada vs API — lista 10 repos R$0 licenca != R$0 custo). Se <5% GO/NO-GO v1.1.0.

### T2.4 Gate 158/158 (10m, SWE cap14)
- T2.4a (5m) Deep +8 gates W em scripts/_validate_deep.py: W1 cProfile exists + W2 line_profiler ou docs + W3 bench p95 <1.05x ou docs <5% + W4 evals 6/6 + W5 cardinality <800 + W6 guard 6/6 + W7 verify 21/21 2x + W8 docs/PERF_TUNING exists. 150->158.
- T2.4b (3m) Re-valida final: verify 21/21 2x stdout igual + deep 158/158 2x WARNS0 BUGS0 + compileall + pytest 40 + evals 6/6 + promtool 6/6 + compose config RC0 + docker ps 7/7 healthy. Falha= revert.
- T2.4c (2m) Commit P7: git add -f reports/p7-* docs/PERF_TUNING.md evals/test_memory_types.py scripts/_validate_deep.py + commit feat(P7): perf 158/158 OU docs(P7): <5% adia v1.1.0

## 4) MELHOR ORDEM ATE P8 — 100% = 162/162

| Ordem | Sequencia | Tempo ate 100% | Risco | Recomendacao |
|---|---|---|---|---|
| A. Classica T2->T3 | T1 15m done -> T2 60m -> T3 60m | 120m | Baixo, Axiom #1 ok, mas T2 pode atrasar tag se <5% | Se quer 158 junto com tag |
| B. Tag primeiro | T1 done -> T3 60m TAG v1.0.0 (162/162 sem T2) -> T2 60m v1.1.0 | 60m ate v1.0.0 +60m v1.1.0 | Muito baixo, P8 nao depende PERF, P7 vira v1.1.0 se <5% | RECOMENDADA 11:15 — 7/7 healthy, promtool/grafana prontos, falta SLO_RUNBOOK+CHANGELOG+tag |
| C. Paralela T2+T3 | T1 -> T2 // T3 merge 162 | 60m | Alto dessync 150->158 vs 150->162, risco HNSW/cardinality | Evitar — Pragmatic proibe |

**Decisao 11:15: Ordem B e melhor:**
1. Axiom #1 satisfeito: T1 7/7 +150/150 prova fundacao, P8 pode ir sem P7 (P7 otimizacao, P8 deploy SWE cap11-14).
2. Economia real (lista 10 repos): T2 mede placa/memoria 1 semana (ollama 30B), mas T3 valida R$0 licenca != R$0 custo ja com compose prod ?required + free-for-dev.
3. Risco <5%: HPP cap1 preve ganho <5% polling 2s -> P7 documenta e adia, nao bloqueia v1.0.0.
4. Interface ja testavel: T1 healthy ja permite usar Jefrey (sec5), entao tag v1.0.0 libera usuario enquanto T2 roda background.

**Plano B detalhado (60m):**
```
HOJE 11:15 CLEAN:
 T3.1 15m compose up -d --wait ja healthy + valida prod ?required (JEFREY_ENV=prod validate_for_production)
 T3.2 15m IdP real + HMAC kid v1->v2 ADR-001 + 8 envs
 T3.3 15m SLO_RUNBOOK 1.3 + THREAT_MODEL + HNSW_TUNING sec5 + CHANGELOG git log bdcae44..5c54440 + P5_CONSOLIDATION freeze
 T3.4 15m deep 162/162 4 gates X + tag -a v1.0.0 + push --tags (inclui v1.0.0-p5-c D5) + verify 21/21 2x + deep 162/162 2x + pytest 40 + promtool 6/6
 => TAG v1.0.0 100% (162/162) — interface liberada
DEPOIS v1.1.0:
 T2.1->T2.4 60m 150->158 (ou 150+docs <5%)
```
Ordem A faz T2 60m ja ->158 ->T3 60m ->162 (mesma TAG +60m). Digo qual seguir no commit T3.

## 5) COMO USAR O JEFREY AGORA — INTERFACE VIVO POS T1 7/7 healthy

Tudo ja healthy, sem build. 4 jeitos:

### A) API REST + Swagger (30s)
```bash
curl http://localhost:8000/health
# {"status":"healthy","postgres":"ok","redis":"ok"}
open http://localhost:8000/docs
# FastAPI auto-doc: POST /chat, /memory, /tools/*, Try it out com thread_id
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -H "X-Thread-Id: demo-1" -d '{"message":"ola jefrey, lembra meu nome?","user_id":"demo-1"}'
curl http://localhost:8000/metrics | grep jefrey
```

### B) MCP Server streamable-http (P3a, :8001)
```bash
curl http://localhost:8001/health
# 200 OK (MCPServer 2.x)
python -c "
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
    async with streamablehttp_client('http://localhost:8001/mcp') as (r,w,_):
        async with ClientSession(r,w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print(len(tools.tools), [t.name for t in tools.tools[:5]])
            res = await s.call_tool('web_search', {'query':'teste jefrey'})
            print(res.content[0].text[:500])
asyncio.run(main())
"
```

### C) Observability — Grafana + Prometheus + n8n (Livro4 cap11, DDIA)
```bash
open http://localhost:9090        # Prometheus query: up{job="jefrey-api"} == 1
open http://localhost:3000        # Grafana admin / GRAFANA_PASSWORD .env -> Dashboard jefrey-main 8 panels: Config Valid, Service Up, Kid Legacy, API Error, RateLimit, Memory p95 by(le), Tools Blocked, Approvals HITL
open http://localhost:5678        # n8n workflow jefrey-events (Switch + MCP HTTP Request) -> webhook /webhook/jefrey-events
```

### D) Python direto (dev)
```bash
python -c "from src.jefrey.core.policy import get_policy_engine; print(get_policy_engine().autonomous)"
python scripts/bench_hnsw.py  # p95 ef=64 vs 200 -> reports/p6-bench.log
python scripts/drill_streams_two_processes.py  # XADD maxlen10000 + XREADGROUP + DLQ + HMAC dual-verify
```

**Troubleshooting (Axiom #6 FAIL-CLOSED):**
- docker logs jefrey-api --tail 80 -> onnx telemetry fail OK (chromadb), reloader WatchFiles OK
- docker logs jefrey-mcp --tail 80 -> web_search 3 ferramentas OK, gmail/calendar WARN sem credentials OK (FAIL-CLOSED)
- 401 em /chat -> JEFREY_ENV=prod precisa IdP real (T3.2), dev valid_* funciona (stub gated)
- redis NOAUTH -> ja fixado healthcheck redis-cli -a com password -> docker ps deve healthy

## 6) CHECKLIST T2 (SWE cap8 + Axiom)

- [ ] py_compile RC0
- [ ] compileall -q RC0
- [ ] guard 6/6 PASS
- [ ] verify 21/21 2x stdout igual RC0
- [ ] deep 158/158 WARNS0 BUGS0 2x (ou 150/150+docs <5%)
- [ ] compose config -q RC0
- [ ] pytest tests 40 passed + evals 6 passed
- [ ] promtool 6 rules + SUCCESS
- [ ] docker ps 7/7 healthy
- [ ] cardinality <800 sem user_id
- [ ] reports/p7-cprofile.prof + p7-bench.log + p7-evals.log + docs/PERF_TUNING.md
- [ ] git status vazio antes commit/tag

## 7) ENTREGAVEIS T2+P8

- reports/p7-cprofile.prof+.txt+p7-bench.log+p7-evals.log+p6-hardening.log 13227 bytes
- docs/PERF_TUNING.md (HPP+Fluent+awesome-llm-apps+ollama trade-off) + P5_CONSOLIDATION + HNSW_TUNING sec5
- evals/test_memory_types.py 6/6 + _validate_deep 158/158 + verify 21/21 2x
- docker-compose.yml 7/7 healthy + alerts.yml 6 alerts + jefrey.json 8 panels by(le):2
- TAG v1.0.0 + v1.0.0-p5-c pushadas (P8)

## 8) COMANDOS COPIAR-COLAR — T2 e USO

```bash
# T2.1 cProfile
python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py
python -m pstats reports/p7-cprofile.prof
python scripts/bench_hnsw.py > reports/p7-bench.log

# T2.2 re-valida
python -m compileall -q src && python scripts/verify_p6_data.py && python scripts/verify_p6_data.py && python scripts/_validate_deep.py

# T2.3 evals
mkdir -p evals && python -m pytest evals/test_memory_types.py -q

# T2.4 gate
python scripts/_validate_deep.py 2>&1 | tail -5  # deve 158/158
pytest tests -q && pytest evals -q

# USO jefrey agora (T1 ja healthy)
curl http://localhost:8000/health && curl http://localhost:8001/health
open http://localhost:8000/docs
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
open http://localhost:5678  # n8n
```

> Assinatura P7 V1.0 — 2026-09-03 11:15: T1 7/7 healthy +150/150 +21/21 +40 passed +promtool 6/6 provados. T2 60m 150->158 W1-W8 com GO/NO-GO <5% -> v1.1.0. Ordem B (T3->T2) recomendada 60m p/ v1.0.0, Ordem A 120m p/ v1.0.0 com perf. Interface ja testavel via :8000/docs, :8001/mcp, :3000, :9090, :5678.
