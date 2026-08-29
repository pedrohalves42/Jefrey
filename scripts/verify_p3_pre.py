"""Validação PRÉ-P3 (estresse de camadas locais/single-thread sob condições de P3).

Cobre os 6 pontos de risco levantados antes de P3:
  1. PolicyEngine sob chamadas concorrentes (mix LOW/HIGH) -> audit log completo, sem deadlock, sem approval duplicado
  2. RedisWorkingMemory sob thread_id externo (formato n8n, longo, com caracteres especiais)
  3. AsyncPostgresSaver sob SelectorEventLoop com gap > 5s (simula timeout do n8n) -> próximo checkpoint não corrompe
  4. PolicyEngine modo audit vs enforce (autonomous True/False) -> executa? loga? decisão correta?
  5. health_check agregado com Redis DOWN (docker stop fiel) -> degraded sem crash; recover sem restart
  6. Idempotência dos verify_p1/verify_p2 -> executado fora deste script (3x cada)

Assume Windows + SelectorEventLoop (psycopg v3 async) e reconfigure utf-8 p/ logs com emoji.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages  # import de modulo (get_type_hints resolve em globals)

sys.path.insert(0, str(Path(__file__).parent.parent))
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_p3_pre")

# ---- captura de audit log (src.jefrey.core.policy) ----
_audit_records: list[str] = []
_CAP_LOCK = threading.Lock()


class _AuditCapture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith("tool_call"):
            with _CAP_LOCK:
                _audit_records.append(msg)


_AUDIT_CAP = _AuditCapture()
_AUDIT_CAP.setLevel(logging.INFO)
logging.getLogger("src.jefrey.core.policy").addHandler(_AUDIT_CAP)

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAILS.append(name)
    logger.info("%s %s %s%s", "✅" if ok else "❌", name, status, f" — {detail}" if detail else "")


# =====================================================================
# Ponto 1 — PolicyEngine concorrente
# =====================================================================
def _test_concurrent_policy() -> None:
    from src.jefrey.core.policy import get_policy_engine, PolicyContext, PolicyResult

    pe = get_policy_engine()  # singleton: mode=enforce, autonomous=True (defaults)
    check("P1.engine_singleton", pe.mode == "enforce", f"mode={pe.mode}")

    tools = ["notes_save", "web_search", "email_send", "memory_search", "calendar_create"]
    # risco: notes/web_search/memory=LOW ; email/calendar=HIGH
    high_idx = {2, 4}
    tids = [f"p3-conc-{uuid.uuid4()}" for _ in tools]
    results: list[tuple[str, object]] = []
    rlock = threading.Lock()
    barrier = threading.Barrier(len(tools))

    def worker(i: int):
        try:
            ctx = PolicyContext(thread_id=tids[i], user_role="user", autonomous=True)
            res = pe.decide(tools[i], {"idx": i}, ctx)
            pe.audit(tools[i], res, ctx)
            with rlock:
                results.append((tools[i], res))
        except Exception as e:  # noqa: BLE001
            with rlock:
                results.append((tools[i], e))

    threads = [threading.Thread(target=lambda i=i: (barrier.wait(), worker(i))) for i in range(len(tools))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    alive = [t for t in threads if t.is_alive()]
    check("P1.no_deadlock", not alive, f"threads vivas={len(alive)}")

    ok_results = [(t, r) for (t, r) in results if isinstance(r, PolicyResult)]
    check("P1.all_resolved", len(ok_results) == len(tools), f"{len(ok_results)}/{len(tools)} sem excecao")

    with _CAP_LOCK:
        audit_n = len(_audit_records)
    check("P1.audit_log_completo", audit_n >= len(tools), f"{audit_n} linhas auditadas (esperado>={len(tools)})")

    approval_ids = [r.approval_id for (_, r) in ok_results if r.approval_id]
    check("P1.high_gera_approval", len(approval_ids) == len(high_idx),
          f"{len(approval_ids)} approvals (esperado={len(high_idx)})")
    check("P1.sem_approval_duplicado", len(set(approval_ids)) == len(approval_ids),
          f"ids unicos={len(set(approval_ids))}")

    # LOW deve ser ALLOW; HIGH deve ser DENY (enforce+autonomous)
    low_allowed = all(r.decision.value == "allow" for (t, r) in ok_results if t not in {tools[i] for i in high_idx})
    high_denied = all(r.decision.value == "deny" for (t, r) in ok_results if t in {tools[i] for i in high_idx})
    check("P1.low_allow_high_deny", low_allowed and high_denied,
          f"low_allowed={low_allowed} high_denied={high_denied}")

    # confere no Postgres que os approvals realmente persisted (sem perda sob concorrência)
    from src.jefrey.core.policy import ApprovalStore
    pending = ApprovalStore().list_pending()
    persisted = [p for p in pending if p["id"] in set(approval_ids)]
    check("P1.approvals_persistidos_pg", len(persisted) == len(approval_ids),
          f"{len(persisted)}/{len(approval_ids)} presentes na tabela approvals")


# =====================================================================
# Ponto 2 — RedisWorkingMemory com thread_id externo (n8n)
# =====================================================================
def _test_redis_external_thread_id() -> None:
    from src.jefrey.core.memory import get_memory_manager
    from langchain_core.messages import HumanMessage, AIMessage

    mm = get_memory_manager()
    rd = mm.short_term
    check("P2.redis_disponivel", rd._redis is not None, "backend=redis")

    cases = {
        "n8n_padrao": "n8n:workflow:abc123:exec:456",
        "n8n_longo": "n8n:workflow:" + "x" * 250 + ":exec:" + "y" * 50,
        "n8n_especial": "n8n:wf/with spaces/and/unicode-ção:exec:9",
    }
    for label, tid in cases.items():
        sess = rd.session(tid)
        key = sess._key()
        check(f"P2.{label}.key_ok", key.startswith("jefrey:wm:"), key[:60])
        sess.add(HumanMessage(content=f"oi {label}"))
        sess.add(AIMessage(content=f"resp {label}"))
        msgs = sess.get_messages()
        ok_len = len(msgs) == 2
        # round-trip conteudo
        ok_content = (msgs[0].content == f"oi {label}" and msgs[1].content == f"resp {label}")
        check(f"P2.{label}.add_get", ok_len and ok_content, f"msgs={len(msgs)}")
        # list_sessions encontra
        found = tid in sess.list_sessions()
        check(f"P2.{label}.list_sessions", found, f"encontrado={found}")
        # clear
        sess.clear()
        ok_clear = len(sess) == 0
        check(f"P2.{label}.clear", ok_clear, f"apos clear len={len(sess)}")


# =====================================================================
# Ponto 3 — AsyncPostgresSaver com gap > 5s (timeout n8n)
# =====================================================================
async def _test_checkpointer_timeout() -> None:
    from langgraph.graph import StateGraph, START, END
    from langchain_core.messages import HumanMessage, AIMessage
    from src.jefrey.core.checkpointer import get_postgres_checkpointer

    cp = await get_postgres_checkpointer()
    tid = f"p3-timeout-{uuid.uuid4()}"

    class S(TypedDict):
        messages: Annotated[list, add_messages]

    async def node(state: S):
        return {"messages": [AIMessage(content="ok")]}

    g = StateGraph(S)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    compiled = g.compile(checkpointer=cp)

    await cp.adelete_thread(tid)  # idempotência
    r1 = await compiled.ainvoke(
        {"messages": [HumanMessage(content="primeiro")]},
        config={"configurable": {"thread_id": tid}},
    )
    check("P3.persist_1", len(r1["messages"]) == 2, f"msgs={len(r1['messages'])}")

    # simula timeout / gap longo do n8n (conexão ociosa > pool idle)
    await asyncio.sleep(6)

    r2 = await compiled.ainvoke(
        {"messages": [HumanMessage(content="segundo")]},
        config={"configurable": {"thread_id": tid}},
    )
    check("P3.persist_2_sem_corrupcao", len(r2["messages"]) == 4,
          f"msgs={len(r2['messages'])} (esperado 4)")

    # re-leitura confirma estado consistente
    snap = await cp.aget_tuple(config={"configurable": {"thread_id": tid}})
    check("P3.relativa_integra", snap is not None and len(snap.checkpoint["channel_values"]["messages"]) == 4,
          "checkpoint re-lido ok")

    await cp.adelete_thread(tid)


# =====================================================================
# Ponto 4 — PolicyEngine audit vs enforce
# =====================================================================
def _test_audit_vs_enforce() -> None:
    from src.jefrey.core.policy import PolicyEngine, ApprovalStore, PolicyContext

    with _CAP_LOCK:
        _audit_records.clear()

    # 4a: audit + autonomous=True  -> HIGH deve ser DENY (bloqueado); LOW ALLOW; tudo auditado
    pe_a = PolicyEngine(mode="audit", autonomous=True, approval_store=ApprovalStore())
    r_high_a = pe_a.decide("email_send", {"to": "x@y.com"}, PolicyContext(thread_id="t4a"))
    pe_a.audit("email_send", r_high_a, PolicyContext(thread_id="t4a"))
    r_low_a = pe_a.decide("notes_save", {}, PolicyContext(thread_id="t4a"))
    pe_a.audit("notes_save", r_low_a, PolicyContext(thread_id="t4a"))
    check("P4.audit_auto.high_bloqueado", r_high_a.decision.value == "deny",
          f"decision={r_high_a.decision.value}")
    check("P4.audit_auto.low_allow", r_low_a.decision.value == "allow",
          f"decision={r_low_a.decision.value}")

    # 4b: audit + autonomous=False -> HIGH deve ser HITL (EXECUTA, pendente)
    pe_b = PolicyEngine(mode="audit", autonomous=False, approval_store=ApprovalStore())
    r_high_b = pe_b.decide("email_send", {"to": "x@y.com"}, PolicyContext(thread_id="t4b"))
    pe_b.audit("email_send", r_high_b, PolicyContext(thread_id="t4b"))
    check("P4.audit_noauto.high_hitl", r_high_b.decision.value == "hitl",
          f"decision={r_high_b.decision.value} (executa como HITL)")

    # 4c: off -> LOW allow; audit() ainda emite log (nao tratado como silencio)
    pe_c = PolicyEngine(mode="off", autonomous=True, approval_store=ApprovalStore())
    r_off = pe_c.decide("email_send", {}, PolicyContext(thread_id="t4c"))
    pe_c.audit("email_send", r_off, PolicyContext(thread_id="t4c"))
    check("P4.off.allow", r_off.decision.value == "allow", f"reason={r_off.reason}")

    with _CAP_LOCK:
        n = len(_audit_records)
    check("P4.audit_log_sai_mesmo_em_audit", n >= 3,
          f"{n} linhas 'tool_call' registradas (audit nunca silencioso)")


# =====================================================================
# Ponto 5 — health_check com Redis DOWN (docker stop fiel)
# =====================================================================
def _test_health_redis_down() -> None:
    from src.jefrey.core.memory import get_memory_manager

    mm = get_memory_manager()
    before = mm.health_check()
    check("P5.antes_saudavel", before["status"] == "healthy",
          f"status={before['status']} redis={before['redis'].get('status')}")

    # tenta parar o container redis de forma fiel
    stopped = False
    try:
        rc = os.system("docker stop jefrey-redis")
        stopped = rc == 0
    except Exception:  # noqa: BLE001
        stopped = False
    if not stopped:
        logger.warning("P5: nao conseguiu docker stop — simulando cliente morto")
        # fallback: injeta cliente que falha no ping
        import redis as _redis

        class _Dead:
            def ping(self):
                raise _redis.exceptions.ConnectionError("simulado")

            def get(self, *a, **k):
                raise _redis.exceptions.ConnectionError("simulado")

        mm.short_term._redis = _Dead()

    during = None
    try:
        # aguarda o redis cair de fato
        time.sleep(2)
        during = mm.health_check()
        check("P5.com_redis_down_degraded", during["status"] == "degraded",
              f"status={during['status']} redis={during['redis'].get('status')}")
        check("P5.nao_crash", during["redis"].get("status") in ("error", "local_fallback"),
              f"redis_substatus={during['redis'].get('status')}")
    finally:
        # SEMPRE sobe o redis de novo (fim fiel do teste)
        try:
            os.system("docker start jefrey-redis")
        except Exception:  # noqa: BLE001
            pass
        # espera voltar
        up = False
        for _ in range(30):
            try:
                if mm.short_term._redis is not None and mm.short_term._redis.ping():
                    up = True
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1)
        check("P5.redis_volta", up, "redis respondeu ao ping apos start")

    after = mm.health_check()
    check("P5.recupera_healthy_sem_restart", after["status"] == "healthy",
          f"status={after['status']} redis={after['redis'].get('status')}")


async def main() -> int:
    logger.info("=== Ponto 1: PolicyEngine concorrente ===")
    _test_concurrent_policy()
    logger.info("=== Ponto 2: RedisWorkingMemory thread_id externo ===")
    _test_redis_external_thread_id()
    logger.info("=== Ponto 3: Checkpointer com gap > 5s ===")
    await _test_checkpointer_timeout()
    logger.info("=== Ponto 4: PolicyEngine audit vs enforce ===")
    _test_audit_vs_enforce()
    logger.info("=== Ponto 5: health_check com Redis DOWN ===")
    _test_health_redis_down()

    logger.info("=== RESUMO ===")
    if FAILS:
        logger.error("❌ FALHAS: %s", FAILS)
        return 1
    logger.info("✅ PRÉ-P3 validado: pontos 1-5 sem quebra silenciosa")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
