# 13 — Validação PRÉ-P3 (camadas locais sob condições de rede/concorrência)

**Data:** 2026-08-28 · **Autor:** AXIOM · **Status:** ✅ 6/6 pontos validados (sem quebra silenciosa)

Validação das camadas construídas para uso local/single-thread sob as condições que
**P3 (MCP gateway + n8n bridge)** introduz: chamadas externas, concorrência real,
thread_id vindo de fora, timeout de rede e Redis caindo em deploy.

**Harness:** `scripts/verify_p3_pre.py` (pontos 1–5) + `scripts/cmp_p1p2.py` (ponto 6, idempotência).
Ambiente: Windows 11, Python 3.14.7, `jefrey-redis`/`jefrey-postgres` (docker, healthy),
sem `JEFREY_POLICY_*` no `.env` (defaults: `mode=enforce`, `autonomous=True`).

---

## Resultado por ponto

| # | Item | Resultado | Evidência |
|---|------|-----------|-----------|
| 1 | PolicyEngine concorrente | ✅ PASS | 5 threads simultâneas (3 LOW + 2 HIGH, `threading.Barrier`); 5/5 resolvidas, 5 linhas auditadas, 2 approvals HIGH com UUID únicos (sem duplicado), LOW=allow/HIGH=deny, 2/2 persistidos no Postgres; 0 deadlock |
| 2 | RedisWorkingMemory thread_id externo | ✅ PASS | `n8n:workflow:abc123:exec:456`, thread_id longo (300+ chars), thread_id com espaços/unicode `ção`; add/get/list_sessions/clear OK; chave `jefrey:wm:<tid>` binary-safe |
| 3 | Checkpointer gap > 5s (timeout n8n) | ✅ PASS | persist → `sleep(6)` → persist → `4 msgs`; `aget_tuple` re-lido íntegro; `pool_pre_ping=True` + `SelectorEventLoop` mantêm conexão após ociosidade |
| 4 | PolicyEngine audit vs enforce | ✅ PASS (com NUANCE) | ver abaixo |
| 5 | health_check com Redis DOWN | ✅ PASS | `docker stop` → `degraded` + `redis=error` (sem crash); `docker start` → `healthy` sem reiniciar agente |
| 6 | Idempotência verify_p1/p2 (3×) | ✅ PASS | após normalizar UUIDs: saída lógica idêntica; p2 estável em `4 msgs` (BUG-P2-01 resolvido) |

---

## Ponto 4 — Nuance de design (decisão necessária antes de P3)

Validação empírica do `PolicyEngine.decide()`:

| Config | Ferramenta LOW | Ferramenta HIGH/CRITICAL | Audit log |
|--------|----------------|--------------------------|-----------|
| `mode=enforce` (default), `autonomous=True` | ALLOW | **DENY** (bloqueado) | sim |
| `mode=audit`, `autonomous=True` | ALLOW | **DENY** (bloqueado) | sim |
| `mode=audit`, `autonomous=False` | ALLOW | **HITL** (EXECUTA, pendente) | sim |
| `mode=off` | ALLOW | ALLOW | sim (sempre emitido pela runtime) |

**Achado:** o medo específico ("audit tratado como `off`, log de auditoria não sai") **NÃO se confirma** —
`audit()` é chamado pela runtime separadamente de `decide()`, então o log de auditoria **sempre** sai,
independentemente do modo. Porém a expectativa "audit mode não bloqueia chamadas do n8n" **só é verdadeira
com `autonomous=False`**: com `autonomous=True` (default, pois não há `JEFREY_POLICY__AUTONOMOUS` no `.env`),
audit mode AINDA BLOQUEIA HIGH/CRITICAL em `_hitl()` (`if self._autonomous or self._mode == "enforce": DENY`).

**Recomendação para P3-dev:** para deixar o n8n executar ferramentas HIGH em modo observação, usar
`JEFREY_POLICY__MODE=audit` **+** `JEFREY_POLICY__AUTONOMOUS=false`. Se o objetivo for bloquear por padrão,
manter `enforce` (default). ← *Decisão de semântica a confirmar com o usuário antes de P3.*

## Ponto 5 — Nuance de status

- Redis cai em **runtime** (cliente já existente, `ping` falha): `MemoryManager.health_check` → `degraded`, `redis={"status":"error"}`.
- Redis **indisponível no init** (fallback local): `redis={"status":"local_fallback"}` e o agregado reporta `healthy`
  (pois a memória local ainda opera). Ou seja: init-down → `healthy`; runtime-down → `degraded`.
- n8n deve tratar `error` como `degraded` (correto) e `local_fallback` como "capacidade reduzida porém operacional".
- Risco menor: se Redis cair **durante** um `add()`, `RedisWorkingMemory._save` faz `self._redis.set(...)` sem try/except
  e propaga — `health_check` em si não crasha, mas a escrita falha. Aceitável para P3 (MCP pode retornar erro),
  mitigar em P4 com retry/fallback.

---

## Conclusão AXIOM

Nenhuma das 6 camadas quebra **silenciosamente** sob as condições de P3. As únicas divergências são:
1. **Decisão de design** (Ponto 4) — como interpretar `audit` + `autonomous` (perguntar ao usuário).
2. **Status `local_fallback`=healthy** (Ponto 5) — documentar contrato de health para o n8n.

Pré-requisitos para P3 atendidos: PolicyEngine thread-safe, Redis aceita thread_id externo, checkpointer
sobrevive a timeout, health_check degrada sem crash, verify scripts idempotentes.
