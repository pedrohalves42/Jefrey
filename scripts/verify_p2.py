"""Verificação da Fase P2: OpenAI Agents SDK & Responses API + checkpointer Postgres.

Cobre:
  1. Imports do novo runtime (agent, checkpointer, openai_agent).
  2. LangGraph + AsyncPostgresSaver persiste estado entre turnos (substitui MemorySaver).
  3. PostgresSessionStore (agent_sessions) faz round-trip em Postgres.
  4. OpenAIAgent constrói, health_check e expõe a ferramenta memory_search.
  5. JefreyAgent (default langgraph) integra checkpointer Postgres no health_check.
  6. Policy Engine (RBAC/HITL): LOW=allow, HIGH/CRITICAL=deny (approval persistido em Postgres).
  7. (Opcional) run real na OpenAI se JEFREY_ALLOW_LIVE_OPENAI=1 e OPENAI_API_KEY definidos.

Observação: psycopg v3 assíncrono exige SelectorEventLoop no Windows.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # BUG-6 (same class): garante utf-8 no console Windows (cp1252) p/ log com emoji
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_p2")


def _test_imports() -> None:
    from src.jefrey.core.agent import JefreyAgent  # noqa: F401
    from src.jefrey.core.checkpointer import get_postgres_checkpointer  # noqa: F401
    from src.jefrey.core.openai_agent import OpenAIAgent, PostgresSessionStore  # noqa: F401

    logger.info("Imports OK (agent, checkpointer, openai_agent)")


async def _test_langgraph_postgres_persistence() -> None:
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.graph import END, StateGraph

    from src.jefrey.core.checkpointer import get_postgres_checkpointer

    class S(TypedDict):
        messages: Annotated[list, add_messages]

    async def node(state: S):
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=f"echo:{getattr(last, 'content', '')}")]}

    wg = StateGraph(S)
    wg.add_node("echo", node)
    wg.set_entry_point("echo")
    wg.add_edge("echo", END)

    cp = await get_postgres_checkpointer()
    compiled = wg.compile(checkpointer=cp)
    tid = "persist-test"
    # P2: o checkpointer é durável (Postgres), então limpamos o thread antes de
    # rodar para garantir idempotência em re-execuções (senão o estado anterior
    # acumula e o assert de 4 mensagens falha).
    # NB: adelete_thread recebe um ÚNICO thread_id (str), não uma lista.
    await cp.adelete_thread(tid)
    await compiled.ainvoke({"messages": [HumanMessage(content="ola")]}, config={"configurable": {"thread_id": tid}})
    r2 = await compiled.ainvoke({"messages": [HumanMessage(content="tudo")]}, config={"configurable": {"thread_id": tid}})
    assert len(r2["messages"]) == 4, f"persistencia falhou: {len(r2['messages'])}"
    logger.info("LangGraph+Postgres checkpointer: estado persistido entre turnos (4 msgs)")


async def _test_openai_session_store() -> None:
    from src.jefrey.core.openai_agent import PostgresSessionStore

    store = PostgresSessionStore()
    tid = "sess-test"
    await store.clear(tid)
    items = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "ola"}]
    await store.save(tid, items)
    loaded = await store.load(tid)
    assert loaded == items, f"round-trip falhou: {loaded}"
    logger.info("PostgresSessionStore: round-trip OK (tabela agent_sessions)")


async def _test_openai_agent_health() -> None:
    from src.jefrey.core.openai_agent import OpenAIAgent

    agent = OpenAIAgent(tools=[])  # não chama o modelo
    h = await agent.health_check()
    assert h["status"] == "healthy", h
    assert "policy" in h, h
    names = [t.name for t in agent._agent_tools]
    assert "memory_search" in names, names
    logger.info(
        "OpenAIAgent: health_check OK (store) + %d ferramentas (inclui memory_search) + policy=%s",
        len(agent.tools_lc), h.get("policy"),
    )


async def _test_jefrey_agent_integration() -> None:
    from src.jefrey.core.agent import JefreyAgent
    from src.jefrey.skills import load_skills, skill_registry

    load_skills()
    agent = JefreyAgent(tools=skill_registry.get_all_tools())
    h = await agent.health_check()
    assert "status" in h, h
    assert h.get("checkpoint") == "ok", h
    assert "policy" in h, h
    logger.info(
        "JefreyAgent (langgraph+Postgres): status=%s checkpoint=%s policy=%s",
        h.get("status"),
        h.get("checkpoint"),
        h.get("policy"),
    )


async def _test_policy_engine() -> None:
    from src.jefrey.core.schema import init_db
    from src.jefrey.core.policy import (
        get_policy_engine, PolicyContext, Decision,
    )
    from src.jefrey.core.hitl import ApprovalManager

    init_db()  # garante a tabela approvals
    pe = get_policy_engine()

    # LOW -> ALLOW (auto-aprovado)
    r1 = pe.decide("save_note", {"content": "test"}, PolicyContext(thread_id="t1"))
    assert r1.decision == Decision.ALLOW, r1

    # HIGH (ferramenta externa, ex.: email) -> DENY em modo autônomo, com approval registrado
    r2 = pe.decide("email_send", {"to": "a@b.com"}, PolicyContext(thread_id="t2"))
    assert r2.decision == Decision.DENY, r2
    assert r2.approval_id is not None, "HITL deve registrar um approval"
    store = ApprovalManager()
    pending = store.get_pending(thread_id="t2")
    assert any(p["id"] == r2.approval_id for p in pending), "approval não persistido em Postgres"

    # CRITICAL -> DENY
    r3 = pe.decide("rm_rf_everything", {}, PolicyContext(thread_id="t3"))
    assert r3.decision == Decision.DENY, r3

    # admin bypass (RBAC, P4 estende papéis)
    r4 = pe.decide("email_send", {}, PolicyContext(thread_id="t4", user_role="admin"))
    assert r4.decision == Decision.ALLOW, r4

    logger.info("PolicyEngine: LOW=allow HIGH/CRITICAL=deny(approval) admin=bypass OK")


async def _maybe_live_openai_run() -> None:
    if os.environ.get("JEFREY_ALLOW_LIVE_OPENAI") == "1" and os.environ.get("OPENAI_API_KEY"):
        from src.jefrey.core.openai_agent import OpenAIAgent

        agent = OpenAIAgent(tools=[])
        out = await agent.run("Responda com exatamente uma palavra: pong.", thread_id="live")
        assert out and isinstance(out, str), out
        logger.info("OpenAI live run OK: %r", out)
    else:
        logger.info(
            "OpenAI live run: pulado (defina JEFREY_ALLOW_LIVE_OPENAI=1 + OPENAI_API_KEY para executar)"
        )


async def main() -> int:
    _test_imports()
    await _test_langgraph_postgres_persistence()
    await _test_openai_session_store()
    await _test_openai_agent_health()
    await _test_jefrey_agent_integration()
    await _test_policy_engine()
    await _maybe_live_openai_run()
    logger.info("✅ P2 verificado com sucesso (OpenAI Agents SDK + checkpointer Postgres).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
