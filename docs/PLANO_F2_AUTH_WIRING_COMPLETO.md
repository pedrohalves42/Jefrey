# PLANO F2 — AUTH WIRING BÁSICO FUNCIONA — 2026-09-04 13:57
> Branch `feat/final-100` | Base `aa253d9` + `49eb801`(F0) + `3d84d58`(F1 docker `jefrey`) | Gates 175/175 2x + 21/21 2x + 27/27 2x 9 panels + 54/54 2x + 68/68 + 40 passed + 7/7 healthy

> Prioridade máxima pós-F0/F1. Resolve o "nunca funciona nada" (401 fantasma) sem quebrar Axiom #1 FAIL-CLOSED.

---

## 0) DIRETRIZES CANÔNICAS

### Axiom 1-7 — onde F2 dói
| Axioma | Regra F2 | Gate |
|--------|----------|------|
| #1 FAIL-CLOSED | Sem token => 401 JSON {ok:false}. Nunca 200 vazio, nunca `except: pass`. UI mostra CTA Settings. | _validate_deep 175/175 P0-003, guard C2/C1b |
| #2 ISOLAMENTO | Todo request leva `X-User-Id` + body `user_id`. `request.state.user_id` nunca default `system` em /chat. Topic `jefrey.events.{user_id}.{tool}`. | verify_p6_data 21/21, verify_p7 54/54 |
| #3 SEM STUB EM PROD | `POST /auth/dev-token` SÓ `JEFREY_ENV!=prod`. Em prod => 403 fail-closed, sem auto-key. | guard C1a, validate_for_production() |
| #4 PERSISTÊNCIA REAL | Token nunca em URL `?token=`, só header + localStorage. TTLCache 1024/60 com hash(token) nunca raw. | auth_middleware TTLCache |
| #5 LEAST PRIVILEGE | CORS `allow_credentials False`, `allow_headers` explicito Authorization+X-User-Id. Sem `overwrite=True`. | config CORS |
| #6 OBSERVABILIDADE | 401 log warning com hash[:12] nunca token raw (CIPHER-010 redact_pii). | audit_fallback.jsonl |
| #7 1 PROGRAMA 7 PEÇAS | Sem novo container. Reuso `jefrey-api:8000` + StaticFiles mount /. | compose 7 peças |

### CIPHER 025-035 aplicados
- 025 dual-write audit preservado
- 026 rate_limit pipeline fail-closed
- 028/029 deny_by_default RBAC guest/user/admin
- 031 OAuth2 JWKS/introspect + TTLCache hash + compare_digest + kid v1/v2
- 032 Skill Risk MEDIUM stt/tts
- 033 HMAC kid per-tenant
- 035 Token Refresh stub só dev

### 10 Livros — mapeamento F2
1. MCP Spec 2026-07-28 stateless_http + OAuth Resource Server — Bearer em header nunca query
2. OpenAI Agents Cookbook RunContextWrapper user_id
3. Security Engineering (Anderson 3rd) cap4-8 modelo ameaça, least privilege, nunca token URL
4. Prometheus Up & Running 2nd cap5 cardinality sem user_id label
5. DDIA Kleppmann cap5/6 Replication + Partitioning — X-User-Id partição tenant
6. SWE at Google cap8 Style + cap14 Testing — idempotente 2x, DRY authHeaders único ponto
7. Fluent Python 19-21
8. High Performance Python cap1-4
9. Building LLM Applications O'Reilly 2024
10. Pragmatic Programmer 20th broken windows

### Sites / Vídeos
- https://www.youtube.com/watch?v=vTIq4pUR7o0 — Mark-LII build
- https://www.youtube.com/watch?v=iq0DlY0Sg-k — Mark-XXXIX voice pipeline
- https://moritz.ceogpt.de/jarvis-aufbau/ — CEOGPT glassmorphism HUD pulse hue wheel chime 2.4s
- https://www.instagram.com/reel/DcjTYTiCt6P/ — HUD reactor
- https://www.youtube.com/watch?v=x5ZIzhOqTzE — Mark-LII estetica

---

## 1) % HONESTO — ONDE PARAMOS (pós-F1)

| Camada | % Código | % Usável leigo | Gates |
|--------|----------|----------------|-------|
| P0 Hardening | 100% | 100% | 175/175 |
| P1 Voz STT/TTS/Wake | 100% | 60% ENABLED=false + sem wiring | 68/68, 42 tools, 9 panels |
| UI Shell Vite+React | 90% | 70% authHeaders incompleto | 5 chunks 633kB |
| Docker Infra | 100% pós-F1 | 95% grafana 401 pendente F4 | name: jefrey, 7/7 |
| E2E básico | 92% | 72% produto (401 parece bug) | /chat 401 correto |
| GLOBAL | 92% | 72% -> 85% após F2 | |

Por que parece quebrado: 401 é correto (Axiom #1), mas UI não injeta X-User-Id em todas rotas e não tem fluxo dev-token.

---

## 2) ESCOPO F2 — O QUE ENTRA / NÃO ENTRA

ENTRA (60m):
- F2-1 `ui/src/lib/api.ts` authHeaders = Authorization + X-User-Id + apiFetch DRY
- F2-2 `src/jefrey/api/auth.py` POST /auth/dev-token só JEFREY_ENV!=prod
- F2-3 `src/jefrey/api/main.py` include router
- F2-4 wiring `useVoice` + Settings botão dev
- F2-5 `docs/GUIA_LEIGO_JEFREY.md`
- F2-6 validação 175/175 2x + 68/68 2x + 40 passed 2x + live 401->200

NÃO ENTRA: LLM Ollama host, voz enable, grafana reset, glassmorphism (F3/F4/P3)

---

## 3) ESPECIFICAÇÃO LINHA-A-LINHA

### F2-1 ui/src/lib/api.ts (DRY único ponto — SWE cap8)
- `getToken(): string|null` try localStorage jefrey_token
- `getUserId(): string` fallback "demo"
- `authHeaders(): Record<string,string>` retorna `{Authorization: Bearer <t>, "X-User-Id": getUserId()}` se token existe
- `apiFetch(path, init)` SEMPRE `Content-Type json + ...authHeaders() + ...(init.headers)` — nunca loga token, nunca envia em URL
- Gate: `tsc --noEmit` passa, vite build sem erro

### F2-2 src/jefrey/api/auth.py (CIPHER-021, Axiom #3)
- APIRouter prefix="/auth"
- `POST /auth/dev-token` só JEFREY_ENV!=prod — dupla guarda `cfg.is_prod` + `cfg.debug`
- Sem auto-key, sem `except: pass`, sem `b64encode` sem urlsafe
- `token = cfg.api.secret_key` valida len>=16 e sem CHANGE_ME
- Gate: `python -m py_compile` RC0, guard 6/6 PASS

### F2-3 src/jefrey/api/main.py
- `from src.jefrey.api.auth import router as auth_router` + `app.include_router(auth_router)`
- CORS already `allow_headers=[Authorization,Content-Type,X-User-Id]` OK
- StaticFiles mount "/" último

### F2-4 UI wiring
- `useVoice.ts`: trocar fetch manual por `authHeaders()` + `getUserId()`
- `Settings.tsx`: botão "Obter token dev" POST /auth/dev-token

### F2-5 docs/GUIA_LEIGO_JEFREY.md
- Passo a passo leigo com 401 explicado

---

## 4) QUALIDADE — ANTI-QUEBRA

Regras duras (guard 6 greps = 0):
- C1a HMAC auto-key => 0
- C1b rate_limit allow => 0
- C2 except: pass => 0
- A1 b64encode sem urlsafe => 0
- A4 token em URL => 0
- M5 overwrite=True => 0

Checklist antes commit:
1. `python -m py_compile src/jefrey/api/auth.py && python -m compileall -q src/`
2. `npx tsc --noEmit`
3. guard 6/6 PASS
4. `_validate_deep 175/175` não cair
5. `docker compose config -q RC0 && docker ps 7/7`
6. live `curl /health 200 + /chat 401 + -H Bearer /chat 200`

Se falhar => não avança F3.

---

## 5) PLANO EXECUÇÃO (60m)

| # | Min | Ação | DoD |
|---|-----|------|-----|
| F2-1 | 10 | api.ts authHeaders + X-User-Id | tsc OK |
| F2-2 | 15 | auth.py dev-token fail-closed | py_compile OK |
| F2-3 | 5 | main.py include router | openapi lista /auth/dev-token |
| F2-4 | 15 | wiring useVoice + Settings | vite build OK |
| F2-5 | 5 | docs GUIA_LEIGO | doc existe |
| F2-6 | 10 | revalidação 2x + live | 175/175 2x, 7/7 |

---

## 6) RISCOS E MITIGAÇÕES

| Risco | Mitigação | Livro |
|-------|-----------|-------|
| dev-token vaza prod | dupla guarda is_prod + debug | Security Eng cap4 |
| X-User-Id spoofing | middleware valida token antes | MCP Spec |
| quebra 175/175 | só adicionar router overwrite=False | SWE cap14 |
| vite quebra | sem import circular | HPP |

---

## 7) VALIDAÇÃO FINAL F2

- [ ] authHeaders inclui X-User-Id nunca loga token
- [ ] auth.py prod=>403 dev=>200 sem auto-key sem except:pass
- [ ] main.py include auth_router openapi lista /auth/dev-token
- [ ] useVoice usa authHeaders/getUserId
- [ ] Settings botão dev-token
- [ ] GUIA_LEIGO existe explica 401
- [ ] compileall -q RC0 + tsc --noEmit RC0
- [ ] guard 6/6 PASS 175/175 2x 68/68 2x 54/54 40 passed 2x 7/7
- [ ] curl /health 200 + /chat 401 + -H Bearer /chat 200 + POST /auth/dev-token 200 dev

DoD F2: leigo localhost:8000 -> Settings Obter token dev -> Chat 200 + STT/TTS via useVoice. 401 sem token correto.

*Gerado F2 13:57 feat/final-100 — cada passo com py_compile + guard antes commit.*
