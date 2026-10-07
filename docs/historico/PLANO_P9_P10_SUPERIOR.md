# PLANO P9/P10 — Jefrey Superior às Referências (10 Livros + 10 Repos)

> **Data:** 2026-09-11 13:12 -03:00 | **Commit base:** `99a65e3` + `b0c0e02` | **Infra validada:** P7 54/54, P6 27/27, CIPHER 32/32, P6-DATA 23/23, readiness 100/100/100 fator 1.0, 8/8 healthy, `jefrey_config_valid 1.0`
> **Honestidade:** `100/100/100` = infra. Produto fim-a-fim (microfone → STT → agente → TTS → áudio) ainda **~65%**. Este plano fecha **P9 (Auth/SSO/Performance) + P10 (Voz + GUI 3D)** para **>90% produto e >80% comercial** e deixa o Jefrey **superior a cada referência** nos quesitos que cada livro/repo ensina melhor.

---

## 1) Por que não é 100% (auditoria honesta validada agora)

| Prova shell | Resultado | Impacto |
|---|---|---|
| `Select-String getUserMedia frontend/*` | **0 hits** | Microfone não captura |
| `Select-String <audio Audio().play frontend/*` | **0 hits** | TTS não toca no browser |
| `POST /tts Bearer+ X-User-Id → 500 erro interno policy TTS` | `pyttsx3: No module named 'pyttsx3'` dentro de `jefrey-api` | TTS quebra sem `elevenlabs`/`pyttsx3` no `pyproject.toml`/`Dockerfile.api` |
| `pyproject.toml` grep `elevenlabs|pyttsx3|piper` | **0 hits** (só `faster-whisper 1.2.1 + av + onnxruntime`) | Fala indisponível sem rebuild |
| `VOICE.enabled False` (`src/jefrey/core/config.py: enabled=False`) | `JEFREY_VOICE__ENABLED` não setado | STT em mock/dev, não prod |
| `GET /tts/voices` sem Bearer → 401 (correto) | com Bearer+X-User-Id → 500 via `PolicyEngine.decide` | Bug de política bloqueia TTS mesmo autenticado |
| `frontend/main.js` só `console.log loaded` | `btnAvatar` só `alert()` | Avatar Three 0.165.0 carrega mas não troca tema/modelo |

**Conclusão:** infra é 100%; **produto voz é 0% utilizável por usuário leigo**. P9/P10 tornam voz utilizável **e** superam as referências.

---

## 2) Matriz — 10 livros × onde o Jefrey hoje empata e onde vai superar

| # | Livro / Repo | O que Jefrey já faz bem (empata) | GAP não usado | Como vamos superar (P9/P10) | Prova de superação |
|---|---|---|---|---|---|
| 1 | **DDIA — Kleppmann** | Postgres+pgvector HNSW m=16 ef=64, `pool_pre_ping`, `pool_recycle 3600`, `pg_dump 436 linhas` idempotente, 5 memórias | Sem **réplica lógica + failover drill + HNSW_TUNING bench** | P9: adicionar `scripts/verify_replica.sh` (lag <2s) + `HNSW_TUNING.md` ef 200 vs 64 benchmark latência p95 12ms → 8ms | `verify_p6_data 23/23` + `HNSW bench` artifact |
| 2 | **Building LLM Apps — Alto** | 6 camadas memória, `memory_search` tool, `PostgresSessionStore` | Sem **evals** de qualidade | P9: `scripts/eval_agent.py` 20 golden Q&A PT-BR + métricas `groundedness≥0.8` e `answer_relevancy≥0.85` (RAG) | `eval_agent 20/20 ≥ thresholds` |
| 3 | **Fluent Python — Ramalho** | `ToolDescriptor.__get__`, `@timed/@counted`, `stream()` async gen | `_RUNNING_TASKS` ainda `dict` não `WeakValueDictionary`; polling `sleep(2)` | P10: refator `executor.py` → `WeakValueDictionary` + `asyncio.wait_for(..., timeout=30)` robusto (cap.19-21) | `verify_p5 16/16` + sem leak |
| 4 | **OpenAI Agents SDK** | `Agent/Runner/function_tool/RunContextWrapper` | `_guarded_call` wrapper manual, `usage/model` não usado, tracing desabilitado sem opção | P9: migrar para **AgentHooks** nativos (`on_tool_start/on_tool_end`) + expor `usage` no `/chat` + `JEFREY_TRACING=1` liga tracing collector | `test_p4_*` + `AgentHooks` importado |
| 5 | **MCP Spec 2026-07-28** | `streamable-http 8001`, `stateless_http True`, `json_response True` | Falta **OAuth 2.0 Resource Server** por servidor MCP + `tool injection` CIPHER-011 parcial | P9: `MCPClientSettings` exige `Authorization` por server + `content_guard` 15 patterns no `MCPClient` | `verify_p7 P07-022` + `CIPHER-011` 100% |
| 6 | **High Performance Python** | `orjson`, `WeakValueDictionary` em `pg_memory` | Sem **profiling real** | P9: `scripts/profile_hotpaths.py` (`cProfile` + `line_profiler`) mede `_to_chroma_metadata` `json vs orjson` + `ToolExecutor sleep(2)` sob 50 conc. | `profile report p95 tool <300ms` |
| 7 | **Pragmatic Programmer** | `tracer bullets` P0→P8, `broken windows` 5 HIGH | Sem **Definition of Done** formal | P9: `docs/DEFINITION_OF_DONE.md` checklist 12 itens (code+test+metric+alert+runbook) | `DoD` assinado |
| 8 | **Prometheus Up & Running** | 18 metrics `<800 series` sem `user_id`, 7 alerts `for 1m/5m`, 9 panels `editable:false` | Buckets genéricos, sem **SLO burn rate** | P10: refinar buckets `stt 0.1/0.3/1/2/5` + panel **Burn Rate 30d** + `kid_legacy` SLI | `Grafana + promtool SUCCESS` |
| 9 | **Security Engineering — Anderson** | `THREAT_MODEL v1 P8` STRIDE T1-T7, `kid rotation v1/v2`, `HMAC fail-closed prod` | Sem **T8 voice injection via STT** e **T9 prompt injection via TTS replay** | P9: T8/T9 no Threat Model + `STT content_guard` + `TTS replay nonce 5min` | `THREAT_MODEL T1-T9` |
| 10 | **SWE@Google** | CI `guard-audit-pytest`, 12 testes, `SLO.md 7 SLIs`, runbooks 41 linhas | Sem **k6 load test** e **toil budget** | P9: `scripts/k6_load.js` (200 RPS, p95 memory <500ms) + `docs/TOIL_BUDGET.md` | `k6 pass` + CI |

**10 Repos onde vamos superar (o que não usamos):**

| Repo | Jefrey hoje | Superar em P9/P10 |
|---|---|---|
| `langgraph` | usa grafo `load_context→reasoning→execute→save` | + **checkpointer Postgres versionado** (time-travel debug) |
| `openai-agents-python 0.22` | usa `function_tool` | + **handoff entre agentes** (especialista calendar vs web_search) |
| `modelcontextprotocol/spec` | `streamable-http` | + **discovery cache + TTL 60s** para tools MCP |
| `faster-whisper` | `small int8` lazy load | + **vad_filter + word_timestamps** para barge-in |
| `piper-tts / elevenlabs` | `pyttsx3` fallback (quebrado) | + **streaming TTS chunked** (`/tts/stream` 128k) |
| `pgvector 0.5.1` | `HNSW cosine` | + **IVFFLAT fallback** documentado em `HNSW_TUNING.md` |
| `redis 7.2` | `Streams XADD maxlen 5000` | + **consumer group lag alert** `jefrey_stream_lag >1000` |
| `n8n` | workflow `jefrey-send-message` | + **versioned workflows JSON** no repo `workflows/` |
| `prometheus/grafana` | 9 panels | + **exemplars + tracing** (OpenTelemetry) |
| `supabase/postgres` | `ankane/pgvector` | + **Row Level Security (RLS) por `user_id`** em memórias |

---

## 3) P9 — Integrações, Auth/SSO, Performance (2.10.0 na tabela P7-P10)

### 3.1 Auth/SSO

- [ ] **OAuth Google** `calendar+ gmail+ drive`: refresh token `0o700` em `config/tokens/*.json`, `token_file` por `user_id`, `OAUTH_REFRESH_TOTAL{skill,status}` já existe
- [ ] **SSO OIDC**: `JWKS RS256 kid + aud/iss/exp + sismember revoked + TTLCache 1024/60 + hash(token)` (já em `auth_middleware`) + **MFA TOTP** opcional `pyotp` no `/auth/mfa/setup`
- [ ] **LGPD**: `DELETE /memory?user_id=...` já filtra, adicionar `GET /lgpd/export` zip JSONL + `audit_fallback.jsonl` dual-write já existe
- [ ] **Correção crítica TTS 500:** `src/jefrey/api/tts.py` `get_policy_engine().decide` está lançando `500` — trocar para `allow` quando `user_id` é `Bearer+ X-User-Id` válido e logar `policy reason`; teste: `POST /tts` com `JEFREY_API__SECRET_KEY` + `X-User-Id` deve retornar `200 audio/wav` sem eleven key (via `pyttsx3`).

### 3.2 Performance

- [ ] `faster-whisper base→small` já lazy load; adicionar `vad_filter=True` + `beam_size 5` já feito + `word_timestamps` para barge-in futuro
- [ ] `pyttsx3` → **piper** local (`pt_BR-faber-medium`) como fallback sem cloud; `elevenlabs` só se `ELEVENLABS_API_KEY` setada
- [ ] `orjson` já usado em `pg_memory`; medir e documentar `json vs orjson` 3× speedup
- [ ] `k6` load: `POST /chat` 50 VU × 5m p95 <500ms, `POST /stt` p95 <2s, `GET /health` p99 <50ms

**Critérios de aceite P9:** `POST /tts` 200 com Bearer (sem 500), `GET /tts/voices` 200, `eval_agent 20/20 ≥0.8`, `k6 p95 <300ms tool`, `THREAT_MODEL T8/T9`, `DoD` check.

---

## 4) P10 — GUI / Avatar 3D + Voz fim-a-fim (2.11.0)

### 4.1 Voz fim-a-fim (o que falta para o microfone funcionar)

1. **Deps:** adicionar em `pyproject.toml` `dependencies`: `elevenlabs>=1.0`, `pyttsx3>=2.90`, `piper-tts>=1.3` (opcional), manter `faster-whisper`, `av`, `onnxruntime`
2. **Docker:** `Dockerfile.api` instala `espeak`/`alsa` para `pyttsx3` (ou `piper` binary); env `JEFREY_VOICE__ENABLED=true`, `JEFREY_VOICE__STT__MODEL=small`, `JEFREY_VOICE__TTS__PROVIDER=piper` (default sem Eleven key)
3. **Backend:** corrigir `tts_engine.synthesize` para tentar ordem: `elevenlabs` (se key) → `piper` → `pyttsx3` → `raise RuntimeError` (fail-closed); `stt_engine.transcribe` já fail-closed
4. **Frontend — Microfone:** `frontend/index.html` + `frontend/main.js`:
   ```js
   // getUserMedia + MediaRecorder → POST /stt
   const btnMic = document.getElementById('btnMic');
   let rec, chunks=[];
   btnMic.onclick = async ()=>{
     const stream = await navigator.mediaDevices.getUserMedia({audio:true});
     rec = new MediaRecorder(stream, {mimeType:'audio/webm'});
     rec.ondataavailable = e=> chunks.push(e.data);
     rec.onstop = async ()=>{
       const blob = new Blob(chunks, {type:'audio/webm'}); chunks=[];
       const fd = new FormData(); fd.append('audio', blob, 'mic.webm');
       const r = await fetch('http://localhost:8000/stt', {method:'POST', headers:{Authorization:`Bearer ${TOKEN}`, 'X-User-Id': userId}, body: fd});
       const {transcript} = await r.json();
       // envia para /chat e depois TTS
       const chat = await fetch('/chat', {method:'POST', headers:{...}, body: JSON.stringify({message: transcript})});
       const {response} = await chat.json();
       const tts = await fetch('/tts', {method:'POST', headers:{...}, body: JSON.stringify({text: response, voice_id:'pt_BR-faber-medium', format:'wav'})});
       const audioBlob = await tts.blob();
       const url = URL.createObjectURL(audioBlob);
       new Audio(url).play();
       // avatar lip-sync pulse
       if(avatarMesh) avatarMesh.rotation.y += 0.2;
     };
     rec.start(); setTimeout(()=> rec.stop(), 5000);
   };
   ```
   - adicionar `<button id="btnMic">🎤 Falar</button>` + `<audio id="player" controls>` + `getUserMedia` error handling (permissão negada → toast)
   - `ws://localhost:8000/ws` já existe; manter 4 handlers `tool_start/memory_retrieved/approval_pending/security_alert`

### 4.2 Avatar 3D

- [ ] `Three 0.165.0` já ok + `OrbitControls` + `GLTFLoader` + `iron_man.glTF` → adicionar **troca de avatar** `JEFREY_AVATAR__MODEL` (select 3 modelos) + `auto_rotate` + `theme dark/light`
- [ ] **Lip-sync básico:** mapear `audioBlob` loudness (Web Audio `AnalyserNode`) → `avatarMesh.scale.y` pulse
- [ ] **Estados visuais:** `tool_start` → rotação, `approval_pending` → vermelho (já feito), `security_alert` → piscar

**Critério P10:** no `http://localhost:3001` clicar **🎤 Falar** → gravador 5s → `POST /stt 200 transcript` → `POST /chat 200` → `POST /tts 200 wav` → áudio toca no `<audio>` → avatar pulsa. Sem `500`.

---

## 5) Transversais — o que vamos roubar dos livros que ainda não usamos

- **DDIA cap.5:** `backup_restore.sh` já faz `pg_dump --no-owner` idempotente; falta **restore drill** documentado `docs/BACKUP_DRILL.md`
- **Fluent Python cap.19:** refator `src/jefrey/core/executor.py` `sleep(2)` → `asyncio.wait_for(wait_for_decision, timeout=ttl)` + `WeakValueDictionary` para `_RUNNING_TASKS`
- **HPP cap.1:** `scripts/profile_hotpaths.py` gera `profile.json` com p95s
- **Pragmatic cap.7:** `docs/DEFINITION_OF_DONE.md` 12 itens (lint, type, test, metric, alert, runbook, eval, backup, threat, docs, ci, demo)
- **SWE@Google cap.11:** `docs/TOIL_BUDGET.md` (toil < 30% sprint) + `scripts/k6_load.js`

---

## 6) Ordem de execução (sem quebrar o que está 100%)

**Passo 1 — Fix deps + voz backend (não quebra infra):**
1. `pyproject.toml` add `elevenlabs pyttsx3 piper-tts` + `pip install`
2. `src/jefrey/api/tts.py` fix `500` → `allow` + log (policy)
3. `.env` add `JEFREY_VOICE__ENABLED=true` (dev) — prod continua `false` até Eleven key
4. `Dockerfile.api` add `espeak-ng` para `pyttsx3`
5. `python -m compileall src` + `verify_p7 54/54`

**Passo 2 — Frontend voz (getUserMedia + audio):**
1. `frontend/index.html` add `btnMic + <audio>` + `getUserMedia` → `POST /stt` → `POST /chat` → `POST /tts` → `Audio.play()`
2. `frontend/main.js` extrair lógica para `initVoice({token, userId})`
3. `docker compose build --no-cache frontend` + `up -d`

**Passo 3 — Superior às refs (artefatos):**
1. `scripts/eval_agent.py` 20 golden
2. `docs/THREAT_MODEL.md` T8/T9
3. `docs/DEFINITION_OF_DONE.md` + `docs/BACKUP_DRILL.md` + `scripts/profile_hotpaths.py` + `scripts/k6_load.js`
4. `docker/grafana/dashboards/jefrey.json` panel **Burn Rate**

**Passo 4 — Rebuild total sem cache + validação fim-a-fim:**
```
docker compose build --no-cache jefrey-api mcp-server frontend
docker compose up -d --wait  # 8/8 healthy
python scripts/verify_p7.py  # 54/54
python scripts/verify_p6.py  # 27/27
python scripts/verify_cipher_fixes.py  # 32/32
curl -H "Authorization: Bearer $SECRET" -H "X-User-Id: u1" http://localhost:8000/tts/voices  # 200
curl -H "Authorization: Bearer $SECRET" -H "X-User-Id: u1" -H "Content-Type: application/json" -d '{"text":"ola","format":"wav"}' http://localhost:8000/tts --output /tmp/tts.wav && file /tmp/tts.wav  # RIFF
http://localhost:3001 → clicar 🎤 → falar 3s → ouvir resposta
```

---

## 7) Validação final (o que vamos rodar e deve ficar verde)

```
python -m compileall src -q                          # COMPILE_OK
python scripts/verify_p7.py                          # 54/54
python scripts/verify_p6.py                          # 27/27
python scripts/verify_cipher_fixes.py                # 32/32
python scripts/verify_p6_data.py                     # 23/23
python scripts/compute_readiness.py --json           # 100/100/100 fator 1.0 (infra)
python scripts/eval_agent.py                         # 20/20 ≥0.8 (Building LLM Apps)
docker ps --format table                             # 8/8 healthy (api 3.5GB mcp 2.2GB frontend 188MB)
curl http://localhost:8000/health                    # 200 ok
curl http://localhost:8000/metrics | grep jefrey_config_valid  # 1.0
promtool check rules /etc/prometheus/alerts.yml      # SUCCESS 7 rules
promtool check config /etc/prometheus/prometheus.yml # SUCCESS
docker exec jefrey-postgres pg_dump ... | wc -l      # 436 + CREATE EXTENSION vector
http://localhost:3001                                 # 200 + ws:// + Three 0.165.0 + 🎤 + <audio> + 4 handlers
POST /stt (webm 5s)                                   # 200 transcript pt-BR
POST /tts (texto)                                     # 200 audio/wav RIFF (não 500)
```

**Se falhar um, não é 100%.** Só com `tts.wav RIFF + transcript + audio.play()` o comercial vai de 56% → 85%+ (usuario leigo liga microfone e ouve).

---

## 8) Riscos e não-objetivos

- **Não vamos** trocar `llama3.1:8b ollama` por `gpt-4o` sem `OPENAI_API_KEY` — eval roda com ollama local
- **Não vamos** reintroduzir `secrets.token_bytes(32)` em `signing.py` — fail-closed permanece
- **Não vamos** voltar `3001:8080` para `8080:8080` — Grafana já ocupa 3000, conflito 8080 volta
- **ElevenLabs** é opcional; sem key o `piper/pyttsx3` deve **funcionar offline** (DDIA: disponibilidade)

---

*Gerado para P9/P10 superior — referências revisitadas: 10 livros (DDIA, Alto, Ramalho, Agents SDK, MCP Spec, HPP, Pragmatic, Prometheus, Anderson, SWE@Google) + 10 repos (langgraph, openai-agents, mcp, whisper, piper, pgvector, redis, n8n, prometheus, supabase). Próximo: Passo 1 fix deps+tts 500.*

