# CONTRIBUTING — Jefrey — Padrões Fail-Closed (FASE 0)

> **Você é um senior staff engineer. Stack: Python 3.14 runtime / 3.12 spec, FastAPI:8000+Starlette, SQLAlchemy, Postgres 16+pgvector, Redis 7.2, MCP:8001, n8n:5678, Prometheus:9090/Grafana:3000. Sem frontend (`ui/components` vazio → Cat 2 e 5 = N/A).**
> **Veredito RESUMO_JARVIS_PESSIMISTA.md: Corroborado.** `audit_pessimista.py:58-72` + `_get_hmac_key() dev-auto-generated-key` + 44=28+16 bola de neve → 45 linhas (C1→C1a/C1b). Prod-ready 60-65% pessimista.

---

## 0. PRINCÍPIOS — Sempre (trancados antes de qualquer código/commit) — FASE 0

1. **FAIL-CLOSED (Axiom #6, Security Eng ch.4):** se env var ausente/inválida → `raise RuntimeError/ValueError`, **nunca** `auto-key`, `fallback allow`, `default system/user`, `:-jefrey`, `0.1.0` warn. Reprodução C1a: `JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c "from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()"` → `RuntimeError` (não `UserWarning`).
2. **ISOLAMENTO (Axiom #2, DDIA):** toda query/fila/cache/session **DEVE** filtrar `user_id` explícito. Default `user_id=None` (não `"system"`), `user_role="guest"` (não `"user"`). Tenant A nunca lê checkpoint/cache/evento de B.
3. **SEM STUB EM PROD (Pragmatic Programmer):** `valid_`, `stub`, `placeholder`, `TODO` → se `JEFREY_ENV=prod` → `NotImplementedError` + `grep` 0 em `src/` + `docker-compose.yml`.
4. **PERSISTÊNCIA REAL (DDIA):** nunca `dict`/`list` in-memory para revogação/token/broker. Use **Redis com TTL** + `pool_pre_ping=True` + `retry`. `_introspection_cache` e `_jwks_cache` sem bound → `TTLCache(maxsize=1024, ttl=60)` ou `redis.setex`.
5. **CRIPTO CORRETA (Security Eng ch.8, MCP Spec, CIPHER-033/031):** HMAC inclui `kid + user_id + timestamp + canonical` com `json.dumps(..., sort_keys=True, separators=(",",":"))` + `hmac.compare_digest`; JWKS `urlsafe_b64encode(...).decode().rstrip("=")` sem padding + `alg:RS256` + `kid` versionado para rotação sem quebrar Redis Streams; JWT valida `aud/iss/exp/kid/alg` com `PyJWT` + `leeway`.
6. **LEAST PRIVILEGE (Axiom #5, Security Eng):** `registry.register(overwrite=False)`, volume `.:/app:ro` + `read_only:true` + `tmpfs:/tmp`, CORS allowlist explícita (`allow_origins` de `JEFREY_API__CORS_ORIGINS`, `allow_methods`/`allow_headers` enumerados, `allow_credentials=False` salvo allowlist — Starlette>0.36 dá `ValueError` com `allow_credentials=True` + wildcard).

---

## 1. ANTI-PATTERNS PROIBIDOS — 6 greps exatos (grep deve dar 0)

```bash
# GREP-1 C1a HMAC fail-closed: dev-auto-generated-key / auto-key fallback
grep -rn "dev-auto-generated-key\|auto-key" src/jefrey/eventbus/  # 0
# GREP-2 C1b rate_limit fail-open: return "allow" sem Redis
grep -rn 'return "allow"' src/jefrey/core/rate_limit.py  # 0 (deve raise/deny)
# GREP-3 silent except
grep -rn -E "except.*:[[:space:]]*pass" src/  # 0
# GREP-4 str(dict) nao deterministico (audit.py:83 json.dumps default=str OK só com redact_pii)
grep -rn -E "str\(.*dict|str\(.*canonical|str\(.*payload" src/jefrey/eventbus/ src/jefrey/core/audit.py | grep -v "default=str"  # 0
# GREP-5 b64encode proibido (usar urlsafe_b64encode sem padding) — grep -v urlsafe_b64encode
grep -rn "b64encode" src/jefrey/oauth2/ | grep -v "urlsafe_b64encode"  # 0
# GREP-6 overwrite/valid/In-memory/fallback/creds
grep -rn "overwrite=True" src/  # 0 (A4)
grep -rn "valid_" src/jefrey/oauth2/  # 0 em prod (stub)
grep -rn "In-memory" src/  # 0
grep -rn ":-jefrey" docker-compose.yml  # 0 (usar ${VAR:?required})
grep -rn ".:/app" docker-compose.yml | grep -v ":ro"  # 0 (volume :ro)
```

**Script único:** `bash scripts/guard_anti_patterns.sh` roda os 6 greps acima e falha (exit 1) se qualquer hit >0. Rodar antes de commit e no pre-commit hook.

---

## 2. CHECKLIST ANTES DE COMMIT (obrigatório — copiar no PR description)

- [ ] **GREP-1** `grep -rn "dev-auto-generated-key\|auto-key" src/jefrey/eventbus/` = 0 — Reprodução C1a: `JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c "from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()"` → `RuntimeError` não `warn`
- [ ] **GREP-2** `grep -rn 'return "allow"' src/jefrey/core/rate_limit.py` = 0 — Sem Redis deve `raise RuntimeError` / `deny` não `allow` (C1b, CIPHER-026)
- [ ] **GREP-3** `grep -rn "except.*: pass" src/` = 0 — CIPHER-021
- [ ] **GREP-4** `grep -rn -E "str\(.*dict|str\(.*canonical" src/jefrey/eventbus/ src/jefrey/core/audit.py | grep -v "default=str"` = 0 — C2 `json.dumps(..., sort_keys=True, separators=(",",":"))` + `kid.user_id.timestamp` no HMAC; `audit.py` com `redact_pii` antes de `json.dumps`
- [ ] **GREP-5** `grep -rn "b64encode" src/jefrey/oauth2/ | grep -v "urlsafe_b64encode"` = 0 — A1 RFC7517 `urlsafe_b64encode(...).decode().rstrip("=")` + `alg:RS256` + `kid`
- [ ] **GREP-6** `grep -rn "overwrite=True" src/; grep -rn "valid_" src/jefrey/oauth2/; grep -rn "In-memory" src/; grep -rn ":-jefrey" docker-compose.yml; grep -rn ".:/app" docker-compose.yml | grep -v ":ro"` = 0 — A4 + stub + persistência + env fallback + volume :ro
- [ ] `grep -rn "user_id.*system" src/jefrey/core/` só em `Column server_default` comentado ou migration; `PolicyContext.user_id=None` + `user_role="guest"` (A3, least privilege)
- [ ] `docker compose config` sem `:-jefrey` e sem `HMAC`/`OAUTH` faltante; volumes com `:ro` + `read_only:true` + `tmpfs:/tmp`
- [ ] `JEFREY_ENV=prod python audit_pessimista.py` → 0 CRÍTICO (inclui GREP-5 e GREP-6 com `JEFREY_ENV=prod` fail-closed)
- [ ] `JEFREY_ENV=prod python audit_v2_falsos_verdes.py` → 0 CRÍTICO/ALTO
- [ ] `p3_validate.py` passa com tools **REAIS** (`save_note`, `calendar_create` — não `social_post_create` fake) sem `UNKNOWN`
- [ ] e2e 2 processos Redis Streams cruza mensagem assinada (publisher A → subscriber B) com `kid` versionado

---

## 3. LIVROS BASE — 10 Referências (REFERÊNCIAS_MAPPING.md)

| # | Livro | Uso no plano |
|---|-------|--------------|
| 1 | **MCP Spec 2026-07-28** modelcontextprotocol.io | OAuth2 Resource Server, `aud/iss/kid/alg`, `stateless_http`, JWKS |
| 2 | **OpenAI Agents SDK Cookbook** | SDK hooks, `RunContextWrapper`, tool Pydantic schemas |
| 3 | **Security Engineering — Ross Anderson 3ª ed.** | fail-closed, HMAC, timing-safe, PII redaction, threat model |
| 4 | **Prometheus: Up & Running — Brian Brazil** | sem `user_id` label, Counter/Gauge/Histogram, alerts |
| 5 | **DDIA — Kleppmann** | HNSW, `pool_pre_ping`, partição `user_id`, Streams |
| 6 | **SWE at Google — Winters et al** | CI/CD, SLOs, policy as code, versionamento |
| 7 | **Fluent Python — Ramalho 2ª ed. cap 19-21** | `__get__`, `WeakValueDictionary` |
| 8 | **High Performance Python — Gorelick/Ozsvald** | serialização, batch |
| 9 | **Building LLM Applications — Valentina Alto O Reilly 2024** | LLM app patterns |
| 10 | **The Pragmatic Programmer — Hunt/Thomas 20th** | pragmático, DRY |

**Ordem leitura:** AGORA 1,2,3 → DURANTE P8 4,5,6 → DEPOIS 7,8,9,10 (`REFERENCES.md:98`)
**Stack model:** `langgraph>=0.2 + langchain + openai-agents>=0.1 + pgvector>=0.2 + chromadb>=0.5 + prometheus-client>=0.20 + mcp>=1.19,<3` (`pyproject.toml:27`)

---

## 4. HMAC rotação com kid versionado (C2)

Incluir `user_id` no HMAC quebra assinaturas antigas no Redis Stream. Use `kid` versionado:

- `signed["kid"] = os.getenv("JEFREY_EVENTBUS__HMAC_KID","v1")`, HMAC = `hmac.new(keys[kid], f"{kid}.{user_id}.{timestamp}.{canonical}".encode(), sha256).hexdigest()`
- `verify_message` extrai `kid` e seleciona `keys[kid]` (suporte a 2 kids simultâneos). Mensagens sem `kid` → `v0` compat + `DeprecationWarning` + métrica `eventbus_kid_legacy_total`.
- Chaves: `JEFREY_EVENTBUS__HMAC_KEYS_JSON='{"v1":"<hex32>","v2":"<hex32>"}'` ou `JEFREY_EVENTBUS__HMAC_KEY` (v1) + `JEFREY_EVENTBUS__HMAC_KEY_V2`.
- Plano: 1) deploy dual-verify (aceita v1 e v2), 2) publisher assina com v2, 3) após TTL max (5min + retention), remover v1. e2e deve cruzar v1→v2.

---

## 5. Fluxo de contribuição

1. **Este plano é o padrão** (`PLANO_MESTRE_44_ISSUES.md` v1.1) — nenhum código/commit sem passar no checklist §0 (6 greps) e `scripts/guard_anti_patterns.sh`.
2. **FASE 0 guardrails** (este commit): `scripts/guard_anti_patterns.sh` + `pre-commit` hook + `JEFREY_ENV Literal["dev","prod"]` em `core/config.py` + `audit_pessimista.py` regras 5/6 + `CONTRIBUTING.md`.
3. **FASE 1 C1a/C1b/C2** — 3 diffs isolados (fail-closed cripto + authz + HMAC determinístico com `kid`), cada um com `comando de reprodução` no PR body.
4. Repetir A1-A6 → M1-M7 → B1 — nunca batch de 44 em 1 commit (bola de neve controlada).
5. **Gere diff + comando de reprodução. Não alegue "já verificado".**

---

## 6. Comandos de verificação (gerar diff + reprodução)

```bash
# Anti-patterns (6 greps)
bash scripts/guard_anti_patterns.sh
grep -rn "dev-auto-generated-key\|return \"allow\" # fail-open\|str(.*dict\|b64encode" src/jefrey/ || echo "0 anti-patterns"
grep -rn 'overwrite=True' src/ || echo "0 overwrite"
grep -rn '.:/app' docker-compose.yml

# Env
grep -E "JEFREY_EVENTBUS__HMAC_KEY|JEFREY_OAUTH|JEFREY_REDIS__PASSWORD|JEFREY_ENV" .env.example
docker compose config | grep -E "JEFREY_|GRAFANA_PASSWORD"

# Prod audits (fail-closed)
JEFREY_ENV=prod python audit_pessimista.py 2>&1 | grep CRITICO
JEFREY_ENV=prod python audit_v2_falsos_verdes.py 2>&1 | grep -E "CRITICO|ALTO"
# Reprodução C1a deve dar RuntimeError não warn:
JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c "from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()"

# P3 real tools
python p3_validate.py 2>&1 | grep -E "UNKNOWN|PASS|FAIL"

# e2e EventBus Redis (após FASE 1)
python -m src.jefrey.eventbus.e2e_two_processes  # a criar: XADD jefrey.events.u1.test

# Diff
git diff --stat
git diff src/jefrey/eventbus/signing.py src/jefrey/core/rate_limit.py
```
