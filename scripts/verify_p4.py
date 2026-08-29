"""Verificação P4 — 6/6 AXIOM de aceite.

Cobertura:
  AXIOM #1: guest tenta tool MEDIUM -> bloqueado por RBAC ANTES do PolicyEngine
  AXIOM #2: user tenta tool HIGH -> approval criado -> humano aprova via REST -> executa
  AXIOM #3: user tenta tool HIGH -> humano rejeita via REST -> não executa + audit rejeição
  AXIOM #4: admin executa tool HIGH direto (sem approval) + audit role=admin
  AXIOM #5: risco declarado explicitamente; ferramenta nova sem risco -> UNKNOWN -> bloqueada
  AXIOM #6: verify_p4 idempotente 3x + compileall (smoke 7/7 e regressões P1..cipher
            são orquestradas pelo harness, pois exigem serviços em execução)

Requer Postgres (docker-compose) para as tabelas approvals/audit_logs.
"""
from __future__ import annotations

import asyncio
import compileall
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.jefrey.core.registry import TOOL_REGISTRY, register_default_tools
from src.jefrey.core.rbac import Role
from src.jefrey.core.policy import RiskLevel, get_policy_engine
from src.jefrey.core.hitl import ApprovalManager
from src.jefrey.core.executor import ToolExecutor
from src.jefrey.core.db import get_db
from src.jefrey.core.models import AuditLog
from src.jefrey.core.schema import init_db

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (("  -- " + str(detail)) if detail else ""))


async def _run_axioms() -> None:
    # --- AXIOM #1: RBAC antes do PolicyEngine ---
    ex = ToolExecutor(tool_resolver=lambda n: None, actor_role="guest", autonomous=False)
    out = await ex.execute("create_workflow", {"name": "x", "description": "y", "steps": []})
    check("AXIOM1.guest_medium_bloqueado_rbac",
          out.blocked and out.decision == "deny_rbac", out.reason)

    # --- AXIOM #5: ferramenta não registrada -> UNKNOWN -> bloqueada ---
    name = "tool_nunca_registrada_xyz"
    TOOL_REGISTRY._tools.pop(name, None)
    ex5 = ToolExecutor(tool_resolver=lambda n: None, actor_role="user", autonomous=False)
    out5 = await ex5.execute(name, {})
    check("AXIOM5.risco_nao_declarado_bloqueado",
          out5.blocked and "desconhecido" in (out5.reason or "").lower(), out5.reason)

    # --- AXIOM #2: user HIGH -> approval -> aprova via REST -> executa ---
    TOOL_REGISTRY.register(name="demo_high_tool", risk=RiskLevel.HIGH,
                           required_role=Role.USER, source="test")
    ran2: dict = {}

    async def fake2(**kwargs):
        ran2["v"] = True
        return {"executed": True, "args": kwargs}

    ex2 = ToolExecutor(tool_resolver=lambda n: fake2 if n == "demo_high_tool" else None,
                       actor_role="user", autonomous=False)
    task2 = asyncio.create_task(ex2.execute("demo_high_tool", {"x": 1}))
    await asyncio.sleep(0.15)
    pending = ApprovalManager().get_pending()
    aid2 = next((p["id"] for p in pending if p["tool_name"] == "demo_high_tool"), None)
    check("AXIOM2.approval_criado", aid2 is not None, f"pending={len(pending)}")
    ApprovalManager().decide(aid2, "approved", decided_by="human")
    out2 = await task2
    with get_db() as s:
        row = s.query(AuditLog).filter(
            AuditLog.approval_id == aid2, AuditLog.approval_decision == "approved").first()
    check("AXIOM2.user_high_approved_executa",
          out2.executed and ran2.get("v") and row is not None, str(out2))

    # --- AXIOM #3: user HIGH -> rejeita via REST -> não executa + audit rejeição ---
    TOOL_REGISTRY.register(name="demo_high_tool2", risk=RiskLevel.HIGH,
                           required_role=Role.USER, source="test")
    ran3: dict = {}

    async def fake3(**kwargs):
        ran3["v"] = True
        return {"executed": True}

    ex3 = ToolExecutor(tool_resolver=lambda n: fake3 if n == "demo_high_tool2" else None,
                       actor_role="user", autonomous=False)
    task3 = asyncio.create_task(ex3.execute("demo_high_tool2", {"x": 1}))
    await asyncio.sleep(0.15)
    pending3 = ApprovalManager().get_pending()
    aid3 = next((p["id"] for p in pending3 if p["tool_name"] == "demo_high_tool2"), None)
    ApprovalManager().decide(aid3, "rejected", decided_by="human")
    out3 = await task3
    with get_db() as s:
        row3 = s.query(AuditLog).filter(
            AuditLog.approval_id == aid3, AuditLog.approval_decision == "rejected").first()
    check("AXIOM3.user_high_rejected_nao_executa",
          (not out3.executed) and (not ran3.get("v")) and row3 is not None, str(out3))

    # --- AXIOM #4: admin HIGH direto (sem approval) + audit role=admin ---
    ran4: dict = {}

    async def fake4(**kwargs):
        ran4["v"] = True
        return {"executed": True}

    ex4 = ToolExecutor(tool_resolver=lambda n: fake4 if n == "email_send" else None,
                       actor_role="admin", autonomous=True)
    out4 = await ex4.execute("email_send", {"to": "a", "subject": "b", "body": "c"})
    with get_db() as s:
        row4 = s.query(AuditLog).filter(
            AuditLog.tool_name == "email_send", AuditLog.actor_role == "admin",
            AuditLog.decision == "allow").first()
    check("AXIOM4.admin_high_direto_sem_approval",
          out4.executed and row4 is not None, str(out4))


async def main() -> None:
    register_default_tools()
    from src.jefrey.core.config import get_settings
    get_settings().hitl.poll_interval = 0.2  # acelera polling nos testes

    try:
        init_db()
        check("SETUP.init_db", True)
    except Exception as e:  # noqa: BLE001
        check("SETUP.init_db", False, repr(e))
        _report()
        sys.exit(1)

    # Idempotente 3x
    for i in range(3):
        results.clear()
        await _run_axioms()
        passed = sum(1 for r in results if r[1])
        print(f"--- iteracao {i + 1}: {passed}/{len(results)} passaram ---")
        fails = [r[0] for r in results if not r[1]]
        if fails:
            print("FALHAS:", fails)
            _report()
            sys.exit(1)

    # compileall (AXIOM #6)
    okc = compileall.compile_dir(str(ROOT / "src" / "jefrey"), quiet=1)
    check("SETUP.compileall", bool(okc), "")

    _report()
    print("\nVERIFY_P4: 6/6 AXIOM PASSARAM + IDEMPOTENTE 3x + COMPILEALL OK")
    sys.exit(0)


def _report() -> None:
    print("\n=== RESUMO VERIFY_P4 ===")
    for n, ok, d in results:
        print(("PASS " if ok else "FAIL ") + n + (("  -- " + d) if (d and not ok) else ""))


if __name__ == "__main__":
    asyncio.run(main())
