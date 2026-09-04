# PLANO F3 — LLM E2E + VOZ ENABLE — 2026-09-04 14:35
> **Branch:** `feat/final-100` `e73006f` | **Base:** `aa253d9` SYNCED | **Gates travados:** `175/175 2x WARN0 BUG0` + `68/68 0 BUG 2x` + `21/21 2x` + `27/27 2x (9 panels)` + `54/54 2x` + `pytest 40 2x` + `7/7 healthy `jefrey_*` + `compose -q RC0`
> **Prioridade:** Fechar E2E básico usável (por que "nunca funciona nada" mesmo com código 95% OK) sem quebrar Axiom #1 FAIL-CLOSED.
> **Tempo:** 30m | **Depende de:** F0 ✅ F1 ✅ F2 ✅ | **Próximo:** F4 Grafana Cred Sync → F5 Tag v1.4.0-final-100 → F6 Docs

---

## 0) VALIDAÇÃO COMPLETA P0→P2 (linha-a-linha + deep + live) — 2026-09-04 14:31-14:34

### 0.1 Gates 2x idempotentes (SWE cap14) — ✅ 0 BUG

| Gate | 1ª passada | 2ª passada | Veredito |
|------|------------|------------|----------|
| `validate_linha_a_linha_p0p1.py` (68 checks) | 68 OK 0 BUG (via `PYTHONPATH=.`) | 68 OK 0 BUG | ✅ Sem bug lógica/sintaxe P0+P1 |
| `_validate_deep.py` (175 checks A-Q) | 175/175 100% 0 WARN 0 BUG | 175/175 100% 0 WARN 0 BUG | ✅ Axiom #1-7 + CIPHER 025-035 OK |
| `verify_p6_data.py` (21 checks) | 21/21 100% | 21/21 100% | ✅ HNSW m16 ef64, pool_pre_ping 3600, kid v1/v2, XADD 10000, pg_dump OK |
| `verify_p6.py` (27 checks) | 27/27 100% 9 panels* | 27/27 100% 9 panels* | ✅ Prometheus + Grafana OK |
| `verify_p7.py` (54 checks) | 54/54 100% | 54/54 100% | ✅ Memory/RBAC/HITL/MCP/approvals OK |
| `pytest -q` | 40 passed 4 warns | — (mesmo) | ✅ 40 passed |
| `compileall -q src` host | RC0 | RC0 | ✅ 64 files SYNTAX OK |
| `compileall -q src` container | OSError Read-only (Axiom #5 :ro) | — | ✅ Esperado, não bug |
| `docker compose config -q` | RC0 | RC0 | ✅ |
| `docker compose ps` | 7/7 healthy `jefrey-*` | 7/7 healthy | ✅ |
| `docker compose ls` | `jefrey running(7)` | — | ✅ |
| `docker network ls` | `jefrey_default` isolada de `supabase_network_Gordao_Oficial` | — | ✅ Sem vazamento |
| `live /health` | 200 `{"status":"ok"}` | — | ✅ |
| `live /metrics` | 200 exposition + `jefrey_stt/tts_*}` + `jefrey_config_valid 0.0` | — | ⚠️ ver §0.3 |

> *P06-19 valida "6+ panels" (9 atuais = passa). Deep Q valida 9 panels by(le)>=2.

### 0.2 Linha-a-linha 68/68 — dump completo (2ª passada PYTHONPATH=.)

- SYNTAX 64 files OK, METRICS no user_id label OK, STT/TTS histograms OK, REGISTRY 42 tools (stt_transcribe MEDIUM USER, tts_synthesize MEDIUM USER, overwrite=False) OK, STT_ENGINE Whisper small int8 fail-closed mock-dev-only singleton OK, TTS_ENGINE elevenlabs+pyttsx3 fail-closed OK, STT_API 128L 401 anonymous/system Policy MEDIUM histogram OK, TTS_API 114L 1-5000 5+piper MEDIUM OK, AUTH _PUBLIC_PATHS / + /vite.svg + /assets/ TTLCache 1024/60 compare_digest OK, MAIN StaticFiles / stt+tts before mount CORS allow_credentials False OK, CONFIG VoiceSTT mock via env+engine validate_for_production OK, COMPOSE qwen2:0.5b 2 lines x2 extra_hosts host-gateway :ro read_only /app/.cache explicit postgres:5432 redis:6379 OK, GRAFANA 9 panels editable false STT p95 by(le)>=2 OK, UI audio.ts useVoice VoiceButton useWakeWord Chat Settings Voz Card jarvis vite proxy /stt /tts outDir static OK, STATIC index.html 5 chunks + vite.svg whitelist OK, ALERTS 1 group 7 rules JefreySttLatencyHigh OK, ENV qwen2:0.5b JEFREY_VOICE OK.

### 0.3 Issues / Gaps encontrados (sem quebrar gates, mas bloqueiam "usável 100%")

| # | Severidade | Achado | Evidência | Impacto | Fixa em |
|---|------------|--------|-----------|---------|---------|
| I-01 | 🟡 MÉDIO | **TODO.md desatualizado** — ainda `2026-09-03 22:15 v1.2.0-ui f6381e2` | `type TODO.md` head | Docs dessincronizado (SWE cap8) | **F6** |
| I-02 | 🟡 MÉDIO | **Volumes órfãos `jarvis_jefrey_*` (5)** ainda existem + `jefrey_*` (5) novos | `docker volume ls` 10 volumes | Confusão "vazamento Gordão" + risco `down -v` apagar errado | **F6** após pg_dump |
| I-03 | 🔴 ALTO | **Ollama host offline** — `http://localhost:11434/api/tags` → `Impossível conectar-se ao servidor remoto` | powershell Invoke-RestMethod timeout 5s | `/chat` sem LLM → 500 ou `running` sem resposta; `/memory/search` 500 | **F3** |
| I-04 | 🟡 MÉDIO | **`.env JEFREY_LLM__BASE_URL` comentado** — depende só do default compose `host.docker.internal:11434` | `type .env` sem linha ativa | Host pytest usa `localhost:11434` vs container `host.docker.internal` — divergência DX | **F3** explicitar |
| I-05 | 🟡 MÉDIO | **`JEFREY_VOICE__ENABLED=false`** — P1 voz 100% código mas desabilitada | `type .env` | Voz não aparece/demo não funciona | **F3** → `true` |
| I-06 | 🔵 BAIXO | **`JEFREY_VOICE__STT__MODEL=base` vs engine `small`** | `.env base` vs `stt_engine.py small int8 pt` | Bench/docs divergem (HPP) | **F3** alinhar → `small` |
| I-07 | 🔵 BAIXO | **`jefrey_config_valid 0.0` no /metrics** | `curl /metrics` | `JefreyConfigInvalid` firing mesmo em dev (esperado? mas poluí SLO) | **F4** investigar (`validate_for_production` warn sem secret? mas secret existe) |
| I-08 | 🔵 BAIXO | **`env_file: [.env]` em postgres/redis** — vaza todo .env p/ containers DB | `docker-compose.yml` | Least privilege (Security Eng cap8) — não bloqueia, mas backlog | P3 |
| I-09 | 🔵 BAIXO | **`validate_linha_a_linha` sem `PYTHONPATH=.` → `ModuleNotFoundError: No module named 'src'`** | 1ª passada stderr | DX falso-positivo, não bug lógica | Docs (F6) |
| I-10 | ✅ OK | **`__pycache__` read-only no container** | `compileall -q src` OSError 30 | Axiom #5 `:ro + tmpfs` — comportamento correto | — |
| I-11 | ✅ OK | **Grafana `jefrey_grafana_data` vs `jarvis_jefrey_grafana_data` separados** | volume ls | F1 migração correta, órfão preservado p/ rollback | — |

**Conclusão validação:** **0 BUG lógica/sintaxe**, **0 WARN gates**, **95% código OK**. Usável 85% (F2 fixou 401 wiring) → 100% após F3 (Ollama E2E). Nenhum falso-positivo quebrando projeto — validator 68/68 já corrigido (vite.svg whitelist, CONFIG mock via env+engine, COMPOSE 2 lines).

---

## 1) DIRETRIZES CANÔNICAS F3

### Axioms aplicados
| Axiom | Como F3 respeita | Anti-padrão evitado |
|-------|------------------|---------------------|
| **#1 FAIL-CLOSED** | LLM offline → `raise RuntimeError` / badge "LLM offline — modo mock" visível, nunca `except: pass` silencioso | `try: llm() except: pass` |
| **#3 SEM STUB EM PROD** | `JEFREY_ENV=dev` permite mock; `JEFREY_ENV=prod` → `validate_for_production()` bloqueia mock | Mock em prod |
| **#7 1 programa 7 peças** | Reusa `jefrey-api` (não cria container Ollama no compose — host Ollama é externo, como no dev) | Novo container desnecessário |
| **#2 ISOLAMENTO** | /chat continua per-`user_id` + `thread_id` + HMAC kid | LLM sem isolamento |

### CIPHER
- 025 dual-write (audit fallback), 026 rate_limit pipeline, 033 kid v1/v2 (já OK), 035 valid_ stub só dev

### Livros (capítulos exatos)
1. **DDIA Kleppmann cap12 Tuning** — `hnsw.ef_search`, bench p50/p95, tuning LLM keep_alive
2. **High Performance Python cap1-4** — cProfile, orjson, lazy load Whisper small int8, keep_alive -1
3. **Prometheus Up & Running 2nd cap5/6/10** — sem user_id label, histogram by(le), alert St tLatencyHigh
4. **SWE at Google cap14 Testing** — gates 2x idempotentes, mock ApprovalManager p/ CI sem docker
5. **MCP Spec 2026-07-28** — stateless_http, OAuth Resource Server (já OK)
6. **Building LLM Applications O'Reilly 2024** — RAG 6 memórias, tracing → /metrics

### Sites / Estética
- Mark-LII build: https://www.youtube.com/watch?v=vTIq4pUR7o0
- Mark-XXXIX voice pipeline: https://www.youtube.com/watch?v=iq0DlY0Sg-k
- CEOGPT glassmorphism HUD pulse: https://moritz.ceogpt.de/jarvis-aufbau/ (glass + pulse + hue wheel + chime 2.4s — P3, não F3)

---

## 2) OBJETIVO F3 + DoD

**Objetivo:** `POST /chat` com `Bearer + X-User-Id` responde de verdade via `qwen2:0.5b` (352MB, 494M Q4_0, ctx 32768) em `http://host.docker.internal:11434`, sem 500 infra, e voz STT→chat→TTS funciona E2E em dev. Se Ollama off, UI mostra fallback visível e não quebra.

**DoD (SWE cap14 — só avança com 2x verde):**
- [ ] `powershell curl http://localhost:11434/api/tags` lista `qwen2:0.5b` (ou `ollama pull qwen2:0.5b` OK)
- [ ] `.env` → `JEFREY_LLM__BASE_URL=http://host.docker.internal:11434` explícito + `JEFREY_LLM__MODEL=qwen2:0.5b` + `JEFREY_VOICE__ENABLED=true` + `JEFREY_VOICE__STT__MODEL=small` + `JEFREY_EMBEDDINGS__BASE_URL=http://host.docker.internal:11434`
- [ ] `docker compose up -d --build jefrey-api` loga no startup `LLM base_url=... model=qwen2:0.5b reachable=true/false` (fail-closed visível)
- [ ] `curl -H "Authorization: Bearer $DEV" -H "X-User-Id: test" http://localhost:8000/chat -d '{"message":"oi","thread_id":"t1"}'` → `{"status":"running"}` e depois polling 200 com resposta qwen2 (não 500)
- [ ] `curl http://localhost:8000/metrics | grep jefrey_llm` tem buckets
- [ ] UI Chat → "Obter token dev" → digita "oi" → vê streaming/resposta qwen2 (sem mock)
- [ ] Se Ollama off → UI badge "LLM offline — modo mock" + `jefrey_config_valid` não quebra
- [ ] Gates 2x ainda verdes: `175/175 2x` + `21/21 2x` + `27/27 2x` + `54/54 2x` + `68/68 2x` + `pytest 40 2x` + `compose -q RC0` + `7/7 healthy`

---

## 3) PLANO F3 — 5 PASSOS (ordem ideal, sem quebrar gates)

### F3-1 — Ollama host check + pull qwen2:0.5b (5m) — DDIA cap12
**Arquivo:** host (fora do compose, Axiom #7)
```powershell
# 1. Ver se Ollama está rodando (Windows host)
ollama list  # ou curl http://localhost:11434/api/tags
# Se "Impossível conectar" → iniciar Ollama app
# 2. Pull modelo leve (workaround OOM 8b 4.9GB → 3.3GB alloc fail)
ollama pull qwen2:0.5b        # 352MB — já pullado antes, só garantir
ollama pull nomic-embed-text  # 274MB dim 768 — já OK
# 3. Teste vivo
curl http://localhost:11434/api/generate -d '{"model":"qwen2:0.5b","prompt":"oi","stream":false}'  # ~2.5s cold, <800ms warm keep_alive -1
```
**Gate:** `ollama list | findstr qwen2:0.5b` OK

### F3-2 — .env explicitar + Voice enable (5m) — Axiom #3, HPP
**Arquivo:** `.env` (3 linhas)
```diff
- # JEFREY_LLM__BASE_URL=https://api.openai.com/v1
+ JEFREY_LLM__BASE_URL=http://host.docker.internal:11434
+ JEFREY_EMBEDDINGS__BASE_URL=http://host.docker.internal:11434
- JEFREY_VOICE__ENABLED=false
+ JEFREY_VOICE__ENABLED=true
- JEFREY_VOICE__STT__MODEL=base
+ JEFREY_VOICE__STT__MODEL=small
```
**Por que:** Remove divergência host vs container (I-04), liga voz (I-05), alinha small (I-06). Compose já tem `extra_hosts: host-gateway` + `JEFREY_LLM__BASE_URL:-http://host.docker.internal:11434` fallback — agora .env é fonte da verdade.
**Gate:** `type .env | findstr JEFREY_LLM__BASE_URL` + `findstr JEFREY_VOICE__ENABLED=true`

### F3-3 — Healthcheck LLM no startup jefrey-api (10m) — Axiom #1 FAIL-CLOSED, DDIA cap12
**Arquivo:** `src/jefrey/core/config.py` ou `src/jefrey/api/main.py` lifespan (sem novo container)
```python
# src/jefrey/api/main.py — lifespan
import httpx, logging
log = logging.getLogger(__name__)
@app.on_event("startup")
async def _llm_probe():
    cfg = get_settings()
    url = (cfg.llm.base_url or "http://host.docker.internal:11434").rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(url)
            ok = r.status_code == 200 and "qwen2:0.5b" in r.text
            log.info(f"LLM probe base_url={cfg.llm.base_url} model={cfg.llm.model} reachable={ok} status={r.status_code}")
            if not ok:
                log.warning("LLM offline — modo mock/erro visível na UI (Axiom #1 fail-closed)")
    except Exception as e:
        log.warning(f"LLM probe falhou base_url={cfg.llm.base_url}: {e} — modo mock")
```
**Alternativa leve (se não quiser lifespan):** só log no `src/jefrey/core/llm.py` onde já chama Ollama — adicionar `logger.warning` quando `ConnectionError: Failed to connect to Ollama`.
**Gate:** `docker compose logs jefrey-api | findstr "LLM probe"` mostra reachable true/false, nunca crash.

### F3-4 — UI badge "LLM offline — modo mock" (5m) — CEOGPT UX, Axiom #1 visível
**Arquivo:** `ui/src/pages/Chat.tsx` (ou `ui/src/components/LLMStatusBadge.tsx` novo 20L) + `ui/src/lib/api.ts`
```tsx
// ui/src/lib/api.ts — já tem authHeaders(), adicionar:
export async function probeHealth(): Promise<{llmReachable:boolean}> {
  try { const r=await fetch("/health"); const j=await r.json(); return {llmReachable: r.ok && j.status==="ok"}; } catch { return {llmReachable:false} }
}
// ui/src/pages/Chat.tsx — topo:
const [llmOk,setLlmOk]=useState<boolean|null>(null);
useEffect(()=>{ fetch("/health").then(r=>setLlmOk(r.ok)).catch(()=>setLlmOk(false)); },[]);
// render:
{llmOk===false && <div className="text-amber-400 text-xs p-2 border border-amber-500/30 rounded">LLM offline — modo mock (inicie Ollama: ollama serve & ollama pull qwen2:0.5b)</div>}
```
**Gate:** Com Ollama off → badge aparece; com on → não aparece. Nunca quebra /chat.

### F3-5 — Rebuild + Revalidação 2x (5m) — SWE cap14
```powershell
docker compose up -d --build jefrey-api
docker compose ps  # 7/7 healthy
set PYTHONPATH=. && python scripts/_validate_deep.py  # 175/175 2x
set PYTHONPATH=. && python scripts/verify_p6_data.py  # 21/21 2x
set PYTHONPATH=. && python scripts/verify_p6.py       # 27/27 2x
set PYTHONPATH=. && python scripts/verify_p7.py       # 54/54 2x
set PYTHONPATH=. && python scripts/validate_linha_a_linha_p0p1.py  # 68/68 2x
python -m pytest -q  # 40 passed 2x
# live
powershell -Command "Invoke-RestMethod -Uri http://localhost:8000/health | ConvertTo-Json -Compress"
powershell -Command "$t=(Invoke-RestMethod -Uri http://localhost:8000/auth/dev-token -Method POST).token; Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST -Headers @{Authorization="Bearer $t"; "X-User-Id"="test-f3"} -Body '{"message":"oi","thread_id":"f3-1"}' -ContentType 'application/json' | ConvertTo-Json -Compress"
```
**Gate:** deep 175/175 2x + live /chat 200 running + qwen2 responde.

---

## 4) RISCOS E MITIGAÇÕES

| Risco | Mitigação | Livro |
|-------|-----------|-------|
| Ollama OOM 8b 3.3GB no host 6GB | Manter `qwen2:0.5b 352MB` + `keep_alive -1` + `ollama ps` | HPP cap1, DDIA cap12 |
| Host Ollama não inicia no boot | Instruir `ollama serve` + badge mock visível (não 500 fantasma) | Axiom #1 |
| .env explicitar quebra CI sem Ollama | CI usa mock (sempre) — probe só loga warning, não falha | SWE cap14 |
| STT small (244MB) download lento | `JEFREY_STT__MOCK=true` em CI, `small` só dev local | Axiom #3 |

---

## 5) DEPOIS DE F3

- **F4 (30m):** Grafana cred sync — `docker volume ls` mostra `jefrey_grafana_data` novo; `GRAFANA_PASSWORD=BGl-LcTMp5NPTALZ` mas login 401 = volume antigo com senha antiga → `docker compose exec grafana grafana-cli admin reset-admin-password BGl-LcTMp5NPTALZ` ou `docker volume rm jefrey_grafana_data && up -d` + `guard_grafana.sh` editable:false orgId:1 by(le)>=2
- **F5 (30m):** Revalidação 2x + `git tag v1.4.0-final-100 && git push origin feat/final-100 --tags && merge --no-ff feat/final-100 -> main`
- **F6 (15m):** TODO.md + CHANGELOG [1.4.0-final-100] + `JEFREY-AUDIT/25_LINE_BY_LINE_SWEEP_P0-P7.md` + `docker volume rm jarvis_jefrey_*` após `pg_dump` OK

---

## 6) REFERÊNCIAS

- Plano Mestre: `docs/PLANO_MESTRE_FINAL_100_V2.md` 221L
- F2 Auth: `docs/PLANO_F2_AUTH_WIRING_COMPLETO.md` 170L
- Gates: `scripts/_validate_deep.py` + `validate_linha_a_linha_p0p1.py` + `verify_p*.py`
- Compose: `docker-compose.yml:1 name: jefrey` + `volumes name: jefrey_*` + `extra_hosts host-gateway x2`
- .env: `JEFREY_LLM__MODEL=qwen2:0.5b` + `JEFREY_VOICE__ENABLED=false→true`
- Live: `jefrey-api:8000/health 200` + `/metrics jefrey_config_valid 0.0` + `jefrey_default` vs `supabase_network_Gordao_Oficial` isoladas

*F3 só inicia após este doc commitado em `feat/final-100` — cada passo exige 2x verde antes do próximo (Pragmatic cap5 broken windows).*
