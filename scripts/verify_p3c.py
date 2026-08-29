"""Verificação end-to-end da Fase P3c — Jefrey como MCP Client.

Cenário AXIOM (Decisão 1 = Opção C, Decisão 2 = módulo isolado):
  Jefrey -> MCPClient (src/jefrey/mcp/client.py) -> servidor MCP externo -> ferramenta.

Coverage:
  1. MCPClient (stdio) conecta num servidor MCP externo REAL (scripts/mcp_external_demo_server.py)
     e executa ferramentas (add/echo/jefrey_ping) com resultado correto.
  2. MCPClient (streamable-http) conecta no Jefrey MCP Server já em execução (localhost:8001/mcp)
     e lista as ferramentas (prova o transporte HTTP contra servidor real).
  3. Config: MCPClientSettings + ExternalMCPServer parseiam via env (AppSettings).
  4. Sem regressão: compileall=0 + smoke 7/7 + verify_p3b (que por sua vez revalida P1/P2/P3a).

O cliente é um módulo ISOLADO (fora do loop LangGraph); a integração no agent loop é P4.
"""
from __future__ import annotations

import asyncio
import compileall
import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

# Garante saída UTF-8 mesmo em pipe/console cp1252 (imprime ✅/❌ sem quebrar).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.jefrey.mcp.client import MCPClient  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"❌ {name}" + (f" — {detail}" if detail else ""))


def _run_sub(cmd: list[str], timeout: int = 600) -> int:
    print(f"\n--- subprocess: {' '.join(cmd)} ---")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT após {timeout}s: {' '.join(cmd)}")
        return 2


async def run_stdio_client() -> None:
    demo = str(ROOT / "scripts" / "mcp_external_demo_server.py")
    async with MCPClient(name="demo", command=[sys.executable, demo]) as c:
        tools = await c.list_tools()
        names = [t["name"] for t in tools]
        check("P3c.stdio_list_tools", names == ["add", "echo", "jefrey_ping"], f"{names}")
        add = await c.call_tool("add", {"a": 2, "b": 3})
        check("P3c.stdio_add", add.strip() == "5", f"add(2,3)={add!r}")
        echo = await c.call_tool("echo", {"text": "hi"})
        check("P3c.stdio_echo", echo.strip() == "hi", f"echo={echo!r}")
        ping = await c.call_tool("jefrey_ping")
        check("P3c.stdio_ping", ping.strip() == "pong", f"ping={ping!r}")


async def run_http_client() -> None:
    # CIPHER-007: checagens mais fortes — quantidade mínima + ferramentas-chave + metadados.
    url = "http://localhost:8001/mcp"
    try:
        async with MCPClient(name="jefrey", url=url) as c:
            tools = await c.list_tools()
            names = [t["name"] for t in tools]
            check("P3c.http_list_tools", len(names) >= 17, f"{len(names)} ferramentas (>=17)")
            check("P3c.http_save_note_present", "save_note" in names, f"ex.: {names[:5]}")
            check("P3c.http_email_send_present", "email_send" in names, f"ex.: {names[:5]}")
            # toda ferramenta deve expor nome e descrição (contrato MCP mínimo)
            ok_meta = all(t.get("name") and t.get("description") for t in tools)
            check("P3c.http_tool_metadata", ok_meta, f"{len(tools)} ferramentas com nome+descrição")
    except Exception as e:  # noqa: BLE001
        check("P3c.http_list_tools", False, f"Jefrey MCP Server :8001 indisponível ({e}); rode 'docker compose up -d'")


async def run_config_check() -> None:
    from src.jefrey.core.config import AppSettings, ExternalMCPServer, MCPClientSettings
    cfg = AppSettings()
    ok_enabled = isinstance(cfg.mcp_client, MCPClientSettings)
    check("P3c.config_mcp_client_present", ok_enabled, "MCPClientSettings em AppSettings")
    spec = ExternalMCPServer(name="n8n", url="http://n8n:5678/mcp/x", transport="streamable-http")
    client = MCPClient.from_spec(spec)
    check("P3c.config_from_spec_http", client.url == "http://n8n:5678/mcp/x", client.url)
    spec2 = ExternalMCPServer(name="cli", command="python x.py", transport="stdio")
    client2 = MCPClient.from_spec(spec2)
    check("P3c.config_from_spec_stdio", client2.command == ["python", "x.py"], str(client2.command))


async def main_async() -> None:
    await run_config_check()
    await run_stdio_client()
    await run_http_client()


def main() -> int:
    print("=== P3c: Jefrey como MCP Client ===")
    asyncio.run(main_async())

    # compilação
    ok_compile = compileall.compile_dir(str(ROOT / "src"), quiet=1)
    check("P3c.compileall", ok_compile is True, f"result={ok_compile}")

    # smoke 7/7
    rc = _run_sub([sys.executable, "scripts/smoke_test.py"])
    check("P3c.smoke_7_7", rc == 0, f"smoke rc={rc}")

    # regressão: P3b (que cobre P1/P2/P3a)
    rc_p3b = _run_sub([sys.executable, "scripts/verify_p3b.py"])
    check("P3c.no_regression_verify_p3b", rc_p3b == 0, f"verify_p3b rc={rc_p3b}")

    print(f"\n=== P3c: {PASS} passou, {FAIL} falhou ===")
    if FAIL == 0:
        print("✅ P3c verificado com sucesso (MCPClient stdio+http + config + sem regressão P1/P2/P3a/P3b)")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
