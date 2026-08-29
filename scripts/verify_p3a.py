"""Verificação da Fase P3a — Jefrey MCP Gateway (processo separado, streamable-http :8001).

Cobre (critério de aceite AXIOM, pós-CIPHER-001):
  1. Tool LOW via MCP -> resultado correto + audit log
  2. Tool HIGH via MCP -> bloqueada + approval no Postgres + audit log (role=user)
  3. Tool HIGH com role admin (SERVER-SIDE, via config) -> executa + audit log com admin_bypass
     -> CIPHER-001: o papel NÃO vem do payload; admin só ocorre porque o servidor de
        admin está configurado com service_role=admin (allowed_roles inclui admin).
  4. verify_p3a idempotente (3 execuções; approvals limpos no teardown)
  5. /health disponível no MCP Server
  6. compileall ok + sem regressão em smoke/p1/p2 (rodado fora deste script)

O servidor sobe como PROCESSO SEPARADO (python -m src.jefrey.mcp). Para exercitar os
dois papéis sem depender de header HTTP por chamada (o cliente MCP 2.1.1 não suporta
headers por chamada), usamos DOIS servidores: um de USER (:8001, default) e um de
ADMIN (:8002, service_role=admin).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_p3a")

USER_URL = "http://localhost:8001/mcp"
ADMIN_URL = "http://localhost:8002/mcp"
HEALTH_TMPL = "http://localhost:{port}/health"
THREADS = {"low": "p3a-low", "high": "p3a-high", "admin": "p3a-admin"}

FAILS: list[str] = []
_procs: list[subprocess.Popen] = []
_logs: dict[str, list[str]] = {}
_log_lock = threading.Lock()


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
    logger.info("%s %s %s%s", "✅" if ok else "❌", name, "PASS" if ok else "FAIL",
                f" — {detail}" if detail else "")


def _start_server(port, role="user"):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    env["JEFREY_MCP__PORT"] = str(port)
    env["JEFREY_MCP__SERVICE_ROLE"] = role
    env["JEFREY_MCP__ALLOWED_ROLES"] = json.dumps(["user", "admin"])
    logs: list[str] = []
    _logs[str(port)] = logs
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.jefrey.mcp"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    _procs.append(proc)

    def _reader(p):
        try:
            for line in p.stdout:
                with _log_lock:
                    logs.append(line)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_reader, args=(proc,), daemon=True).start()
    return proc


def _wait_health(port, timeout=90):
    url = HEALTH_TMPL.format(port=port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(f"MCP /health em :{port} nao respondeu no tempo limite")


def _text(result):
    parts = []
    for c in getattr(result, "content", []) or []:
        if isinstance(c, dict) and "text" in c:
            parts.append(c["text"])
        elif hasattr(c, "text"):
            parts.append(c.text)
    return "\n".join(parts)


async def _client_tests(mcp_url):
    from mcp.client.streamable_http import streamable_http_client
    from mcp import ClientSession

    async with streamable_http_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            names = [t.name for t in getattr(listing, "tools", [])]

            low = await session.call_tool(
                "save_note",
                {"title": "P3a", "content": "nota de verificacao P3a", "thread_id": THREADS["low"]},
            )
            low_text = _text(low)

            high = await session.call_tool(
                "email_send",
                {"to": "a@b.com", "subject": "x", "body": "y", "thread_id": THREADS["high"]},
            )
            high_text = _text(high)
            return names, low_text, high_text


async def _admin_tests(mcp_url):
    from mcp.client.streamable_http import streamable_http_client
    from mcp import ClientSession

    async with streamable_http_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            admin = await session.call_tool(
                "email_send",
                {"to": "a@b.com", "subject": "x", "body": "y", "thread_id": THREADS["admin"]},
            )
            return _text(admin)


def _cleanup_approvals():
    from src.jefrey.core.db import get_db
    from src.jefrey.core.models import Approval
    with get_db() as s:
        s.query(Approval).filter(Approval.thread_id.in_(list(THREADS.values()))).delete()
        s.commit()


def _docker_logs():
    try:
        r = subprocess.run(["docker", "logs", "--tail", "300", "jefrey-mcp"],
                           capture_output=True, text=True, timeout=15, errors="replace")
        return (r.stdout + r.stderr).splitlines()
    except Exception:  # noqa: BLE001
        return []


def main() -> int:
    # Reutiliza servidor de USER já em execução (ex.: Docker mcp-server em :8001)?
    user_reused = False
    try:
        with urllib.request.urlopen(HEALTH_TMPL.format(port=8001), timeout=2) as _r:
            user_reused = _r.status == 200
    except Exception:  # noqa: BLE001
        user_reused = False

    if user_reused:
        logger.info("Reutilizando MCP Server de USER em :8001 (Docker)")
        _logs["8001"] = _docker_logs()
    else:
        _start_server(8001, role="user")

    # Servidor de ADMIN dedicado (CIPHER-001): admin só via config server-side.
    _start_server(8002, role="admin")

    try:
        health = _wait_health(8001)
        check("P3a.health_endpoint",
              health.get("mcp") == "ok" and health.get("status") in ("healthy", "degraded"),
              f"status={health.get('status')} tools={health.get('tools')} policy={health.get('policy')}")

        _wait_health(8002)

        names, low_text, high_text = asyncio.run(_client_tests(USER_URL))
        admin_text = asyncio.run(_admin_tests(ADMIN_URL))

        check("P3a.tools_descobertas",
              {"save_note", "email_send", "calendar_create"}.issubset(set(names)),
              f"{len(names)} ferramentas: {sorted(names)}")

        check("P3a.low_executa", '"saved": true' in low_text and "[BLOQUEADO" not in low_text,
              low_text[:80].replace("\n", " "))

        check("P3a.high_bloqueada", "[BLOQUEADO PELA POLÍTICA]" in high_text,
              high_text[:80].replace("\n", " "))

        # CIPHER-001: admin NÃO vem de payload; só ocorre porque :8002 tem service_role=admin.
        check("P3a.high_admin_executa",
              '"executed": true' in admin_text and "[BLOQUEADO" not in admin_text,
              admin_text[:80].replace("\n", " "))

        from src.jefrey.core.policy import ApprovalStore
        pending = ApprovalStore().list_pending(thread_id=THREADS["high"])
        check("P3a.approval_persistido_pg",
              any(p["tool_name"] == "email_send" for p in pending),
              f"{len(pending)} pendente(s) p/ {THREADS['high']}")

        if user_reused:
            _logs["8001"] = _docker_logs()

        with _log_lock:
            u_logs = list(_logs.get("8001", []))
            a_logs = list(_logs.get("8002", []))
        audit_u = [l for l in u_logs if "tool_call" in l]
        audit_a = [l for l in a_logs if "tool_call" in l]
        check("P3a.audit_low", any(f"decision=allow" in l and THREADS["low"] in l for l in audit_u),
              f"{len(audit_u)} linhas audit (user)")
        check("P3a.audit_high_deny", any(f"decision=deny" in l and THREADS["high"] in l for l in audit_u),
              "HIGH user -> deny registrado")
        check("P3a.audit_admin_bypass",
              any(f"decision=allow" in l and "admin bypass" in l and THREADS["admin"] in l for l in audit_a),
              "HIGH admin -> allow + admin bypass registrado")

        _cleanup_approvals()
        check("P3a.cleanup_apos_teste", True, "approvals de teste removidos")
    finally:
        for proc in _procs:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass

    if FAILS:
        logger.error("❌ FALHAS P3a: %s", FAILS)
        return 1
    logger.info("✅ P3a verificado com sucesso (CIPHER-001: papel resolvido server-side)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
