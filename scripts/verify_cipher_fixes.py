"""Verifica que todos os fixes CIPHER foram aplicados corretamente.

Rodar após cada bloco de remediação:
    python scripts/verify_cipher_fixes.py
"""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CHECKS = [
    # CIPHER-001: user_role ausente do schema (corpo de _make_wrapper)
    ("CIPHER-001: user_role ausente do schema MCP",
     lambda: "user_role" not in open("src/jefrey/mcp/server.py", encoding="utf-8")
             .read().split("def _make_wrapper")[1].split("def ")[0]),

    # CIPHER-002: WindowsSelectorEventLoopPolicy protegida por sys.platform
    ("CIPHER-002: WindowsSelectorEventLoopPolicy protegida por sys.platform",
     lambda: all(
         'if sys.platform == "win32"' in open(f, encoding="utf-8").read()
         for f in ["scripts/smoke_test.py", "scripts/verify_p2.py", "scripts/verify_p3b.py"]
     )),

    # CIPHER-002b: compat.py criado
    ("CIPHER-002b: compat.py criado",
     lambda: os.path.exists("src/jefrey/core/compat.py")),

    # CIPHER-004: MCPClientError definido
    ("CIPHER-004: MCPClientError definido",
     lambda: "class MCPClientError" in open("src/jefrey/mcp/client.py", encoding="utf-8").read()),

    # CIPHER-011: content_guard.py criado
    ("CIPHER-011: content_guard.py criado",
     lambda: os.path.exists("src/jefrey/core/content_guard.py")),

    # CIPHER-012: approval_id completo não exposto no response
    ("CIPHER-012: approval_id completo não exposto no response",
     lambda: '"approval_id="' not in open("src/jefrey/mcp/server.py", encoding="utf-8").read()),

    # CIPHER-013: .gitignore cobre .env
    ("CIPHER-013: .gitignore cobre .env",
     lambda: ".env" in open(".gitignore", encoding="utf-8").read()),

    # CIPHER-017: repositório git inicializado
    ("CIPHER-017: repositório git inicializado",
     lambda: os.path.exists(".git")),

    # CIPHER-018: tool_timeout em MCPServerSettings
    ("CIPHER-018: tool_timeout em MCPServerSettings",
     lambda: "tool_timeout" in open("src/jefrey/core/config.py", encoding="utf-8").read()),
]


def main() -> int:
    passed = failed = 0
    for name, check in CHECKS:
        try:
            ok = bool(check())
        except Exception as e:  # noqa: BLE001
            ok = False
            detail = f" → ERRO: {e}"
        else:
            detail = ""
        print(f"{'✅' if ok else '❌'} {name}{detail}")
        passed += ok
        failed += (not ok)
    print(f"\n{passed}/{passed + failed} checks passaram")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
