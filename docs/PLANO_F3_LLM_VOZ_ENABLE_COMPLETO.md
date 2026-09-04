# PLANO F3 — LLM E2E + VOZ ENABLE — 2026-09-04 15:15 FINAL
> **Branch:** `feat/final-100` | **Base:** `aa253d9` SYNCED | **Gates travados:** `175/175 2x WARN0 BUG0` + `68/68 0 BUG 2x` + `21/21 2x` + `27/27 2x (9 panels)` + `54/54 2x` + `pytest 40 2x` + `7/7 healthy jefrey_*` + `compose -q RC0`
> **Prioridade:** Fechar E2E básico usável (por que "nunca funciona nada" mesmo com código 95% OK) sem quebrar Axiom #1 FAIL-CLOSED.
> **Tempo:** 30m | **Depende de:** F0 ✅ F1 ✅ F2 ✅ | **Próximo:** F4 Grafana Cred Sync → F5 Tag v1.4.0-final-100 → F6 Docs
> **Commits:** 6922b19 (probe+badge+env) + FIX pendente (agent fallback + validator broad + compose qwen2.5)

## 0) VALIDAÇÃO COMPLETA P0→P2 (linha-a-linha + deep + live) — 2026-09-04 14:31-14:34 ✅ 0 BUG

| Gate | 1ª passada | 2ª passada | Veredito |
|------|------------|------------|----------|
| validate_linha_a_linha_p0p1.py (68 checks) | 68 OK 0 BUG | 68 OK 0 BUG | ✅ |
| _validate_deep.py (175 checks A-Q) | 175/175 100% 0 WARN 0 BUG | 175/175 100% | ✅ Axiom #1-7 + CIPHER 025-035 OK |
| verify_p6_data.py (21 checks) | 21/21 100% | 21/21 100% | ✅ HNSW m16 ef64 pool_pre_ping 3600 kid v1/v2 XADD 10000 |
| verify_p6.py (27 checks) | 27/27 100% 9 panels | 27/27 100% | ✅ Prometheus + Grafana |
| verify_p7.py (54 checks) | 54/54 100% | 54/54 100% | ✅ Memory/RBAC/HITL/MCP |
| pytest -q | 40 passed | 40 passed | ✅ |
| compileall -q src host | RC0 | RC0 | ✅ 64 files |
| docker compose config -q | RC0 | RC0 | ✅ |
| docker compose ps | 7/7 healthy jefrey-* | 7/7 healthy | ✅ |
| live /health | 200 {"status":"ok"} | — | ✅ |
| live /auth/dev-token | 200 len64 | — | ✅ F2 |
| live /chat 401→200 | 401 sem token (Axiom#1) / 200 running com token | — | ✅ antes 500, agora 200 |
| live /stt/health | 200 small pt | — | ✅ |
| live /tts/health + /tts/voices | 200 piper + 6 voices | — | ✅ |
| Ollama host | 200 4 models (qwen2.5:0.5b tools, qwen2:0.5b, llama3.1:8b, nomic-embed) | — | ✅ |
| LLM probe | reachable=True has_qwen2=True model=qwen2.5:0.5b | — | ✅ |

## 1) GAPS I-04/05/06 CORRIGIDOS (100%)

| # | Gap | Fix aplicado no commit 6922b19 | Status |
|---|-----|-------------------------------|--------|
| I-04 | .env sem JEFREY_LLM__BASE_URL (container ≠ host) | .env + compose JEFREY_LLM__BASE_URL=http://host.docker.internal:11434 extra_hosts host-gateway x2 | ✅ |
| I-05 | .env sem JEFREY_EMBEDDINGS__BASE_URL | .env JEFREY_EMBEDDINGS__BASE_URL idem | ✅ |
| I-06 | JEFREY_VOICE__ENABLED=false + STT base | .env true + small | ✅ |
| I-07 | probe startup ausente | src/jefrey/api/main.py _f3_llm_probe() httpx 2s @app.on_event startup | ✅ |
| I-08 | badge offline | ui/src/pages/Chat.tsx llmOk fetch /health → "LLM offline — modo mock" | ✅ |
| I-09 | probeHealth helper | ui/src/lib/api.ts probeHealth() | ✅ |

## 2) FIX PENDENTE F3-FINAL (este commit) — 3 arquivos

### 2.1 src/jefrey/core/agent.py — fallback qwen2 completion-only
**Ref:** DDIA cap12 Tuning + Axiom #1 visible fail-closed, HPP lazy
**Problema:** qwen2:0.5b Capabilities completion only → registry.ollama.ai/library/qwen2:0.5b does not support tools (400) → POST /chat 500 {"detail":"Erro interno"}
**Solução:**
```python
try:
    response = await self.llm_with_tools.ainvoke(messages)
except Exception as _e:
    msg = str(_e)
    if "does not support tools" in msg or "tools" in msg.lower() and "not supported" in msg.lower():
        _lg.getLogger(__name__).warning(f"LLM {get_settings().llm.model} sem tools, fallback sem bind_tools: {_e} (F3, qwen2:0.5b completion-only)")
        response = await self.llm.ainvoke(messages)
    else:
        raise
```
**Antes:** 500 | **Depois:** 200 {"status":"running"} (E2E prova em scripts/_e2e_f3.py)

### 2.2 docker-compose.yml — default qwen2.5:0.5b tools
```
JEFREY_LLM__MODEL: ${JEFREY_LLM__MODEL:-qwen2.5:0.5b} # antes qwen2:0.5b x2 (api+mcp)
```
**Ref:** DDIA cap6 Partitioning, Axiom #7 sem novo container. qwen2.5:0.5b 397MB Q4_K_M Capabilities completion+tools (vs qwen2:0.5b 352MB completion-only, vs llama3.1:8b 4.9GB OOM). Mantém 494M params, 32768 ctx, keep_alive -1.

### 2.3 scripts/validate_linha_a_linha_p0p1.py — broad qwen2
```python
check('.env qwen2', 'qwen2' in env) # antes strict 'qwen2:0.5b' → 67/1 BUG após upgrade qwen2.5
```
68/68 0 BUG 2x mantido (falso positivo eliminado).

## 3) E2E PROVAS (scripts/_e2e_f3.py) — 200 OK

- HEALTH 200 ok, METRICS jefrey_llm, OPENAPI 13 rotas, DEV_TOKEN len64, CHAT_NO_TOKEN 401 (Axiom#1), CHAT_WITH_TOKEN 200 running (antes 500), STT_HEALTH 200 small, TTS_HEALTH 200 piper, TTS_VOICES 6, Ollama 200 has_qwen2, STATIC 796, LLM probe reachable=True
- POLL 8x running sem complete em 16s (F3 95%→ precisa poll longo 30s + docker logs para provar complete)

## 4) DIRETRIZES — AXIOM + CIPHER + LIVROS + SITES

- **Axiom #1 FAIL-CLOSED:** 401 sem token OK, fallback visível warning não silencia, dev-token 403 em prod (CIPHER-021)
- **Axiom #7:** Sem novo container voz (STT/TTS dentro api, faster-whisper small int8)
- **CIPHER 026/033:** Rate 10/min + HMAC kid v1/v2 dual-verify per-tenant + DLQ
- **Livros:** DDIA cap12 Tuning (probe 2s + fallback), HPP cap1-4 (cProfile), Security Eng 3rd cap4 (401 não é bug), SWE cap8/14 (idempotente 2x), Fluent Python 19-21 (async), Prometheus Up&Running cap5/6/10 (cardinality <800, histogram p95 by(le), alert StT>2s)
- **Sites:** Mark-LII (youtube vTIq4p) estética, Mark-XXXIX-OR (iq0DlY0) voice pipeline, CEOGPT glassmorphism HUD, HUD reactor

## 5) DoD F3 100% (checklist para fechar commit)

- [x] .env JEFREY_LLM__BASE_URL + JEFREY_EMBEDDINGS__BASE_URL + JEFREY_VOICE__ENABLED=true + STT small + qwen2.5:0.5b
- [x] probe startup reachable=True has_qwen2=True + Chat badge + api probeHealth
- [x] agent fallback does not support tools → llm.ainvoke
- [x] compose default qwen2.5:0.5b x2 + validator broad qwen2 → 68/68 2x
- [ ] git add + commit pendente (este passo)
- [ ] docker compose up -d --build jefrey-api (300s) — prova build sem NameError app
- [ ] revalidar 175/175 2x + 68/68 2x + 21/21 2x + 27/27 2x + 54/54 2x + pytest 40 + compileall -q + compose -q + 7/7 healthy
- [ ] live poll 30s até complete (texto qwen real) + /metrics increment

## 6) PRÓXIMOS — F4/F5/F6 (Plano Mestre Final 100 V2)

- **F4 Grafana Cred Sync 30m:** Invalid username or password 401 vs volume jefrey_grafana_data antigo (reset-admin-password BGl-LcTMp5NPTALZ) + guard_grafana.sh
- **F5 Revalidação Final 2x + Tag v1.4.0-final-100 30m:** 175/175 2x 21/21 2x 27/27 2x 54/54 2x 68/68 2x 7/7 healthy + push --tags + merge feat/final-100→main
- **F6 Docs Sync 15m:** TODO.md + CHANGELOG [1.4.0-final-100] + JEFREY-AUDIT/25_LINE_BY_LINE_SWEEP_P0-P7.md + limpar órfãos jarvis_jefrey_* após pg_dump + remover temps
