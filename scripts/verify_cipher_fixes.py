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

    # CIPHER-019: HITL REST exige Bearer token (Authorization / 401 / secret_key)
    ("CIPHER-019: HITL REST exige Bearer token (Authorization/401/secret_key)",
     lambda: ("Authorization" in open("src/jefrey/api/approvals.py", encoding="utf-8").read()
              and "401" in open("src/jefrey/api/approvals.py", encoding="utf-8").read()
              and "secret_key" in open("src/jefrey/api/approvals.py", encoding="utf-8").read())),

    # CIPHER-020: /approvals/pending não expõe arguments_json
    ("CIPHER-020: /approvals/pending não expõe arguments_json",
     lambda: "arguments_json" not in open("src/jefrey/api/approvals.py", encoding="utf-8")
             .read().split("async def list_pending")[1]),

    # CIPHER-021: mode='off' não pula RBAC (RBAC checado ANTES do off)
    ("CIPHER-021: mode='off' não pula RBAC (RBAC antes do off)",
     lambda: (lambda b: b.find("RBACEngine().check") != -1
              and b.find('self._mode == "off"') != -1
              and b.find("RBACEngine().check") < b.find('self._mode == "off"'))(
         open("src/jefrey/core/policy.py", encoding="utf-8")
         .read().split("def decide")[1].split("def _hitl")[0])),

    # CIPHER-022: actor_role resolvido server-side (resolve_role em rbac + agent)
    ("CIPHER-022: actor_role resolvido server-side (resolve_role em rbac+agent)",
     lambda: ("def resolve_role" in open("src/jefrey/core/rbac.py", encoding="utf-8").read()
              and "resolve_role" in open("src/jefrey/core/agent.py", encoding="utf-8")
              .read().split("class JefreyAgent")[1])),

    # CIPHER-023: ToolExecutor._invoke usa to_thread/iscoroutinefunction p/ sync
    ("CIPHER-023: ToolExecutor._invoke usa to_thread/iscoroutinefunction p/ sync",
     lambda: ("to_thread" in open("src/jefrey/core/executor.py", encoding="utf-8").read()
              or "iscoroutinefunction" in open("src/jefrey/core/executor.py", encoding="utf-8").read())),

    # CIPHER-024: uuid inválido em /decide -> 400 (não 500)
    ("CIPHER-024: uuid inválido em /decide -> 400 (não 500)",
     lambda: ("status_code=400" in open("src/jefrey/api/approvals.py", encoding="utf-8").read()
              and "uuid.UUID" in open("src/jefrey/api/approvals.py", encoding="utf-8").read())),

    # CIPHER-025: AuditLogger dual-write fallback (audit_fallback_path + _write_fallback)
    ("CIPHER-025: AuditLogger dual-write fallback (audit_fallback_path + _write_fallback)",
     lambda: ("audit_fallback_path" in open("src/jefrey/core/config.py", encoding="utf-8").read()
              and "_write_fallback" in open("src/jefrey/core/audit.py", encoding="utf-8").read())),

    # === SECURITY P6-pre: Multi-tenant isolation ===

    # SEC-001: user_id coluna presente em models.py (_MemoryMixin)
    ("SEC-001: user_id coluna em _MemoryMixin (models.py)",
     lambda: "user_id" in open("src/jefrey/core/models.py", encoding="utf-8").read()
             .split("class _MemoryMixin")[1].split("class ")[0]),

    # SEC-002: pg_memory.py filtra por user_id em search/get/delete
    ("SEC-002: pg_memory.py filtra por user_id (search/get/delete)",
     lambda: ("user_id" in open("src/jefrey/core/pg_memory.py", encoding="utf-8").read()
              and "rec.user_id != user_id" in open("src/jefrey/core/pg_memory.py", encoding="utf-8").read())),

    # SEC-003: hitl.py get_pending filtra por user_id
    ("SEC-003: hitl.py get_pending filtra por user_id",
     lambda: "user_id" in open("src/jefrey/core/hitl.py", encoding="utf-8").read()
             .split("def get_pending")[1].split("def ")[0]),

    # SEC-004: approvals.py ownership check em decide
    ("SEC-004: approvals.py ownership check em decide",
     lambda: "user_id" in open("src/jefrey/api/approvals.py", encoding="utf-8").read()
             .split("async def decide")[1]),

    # SEC-005: FastAPI auth middleware existe
    ("SEC-005: FastAPI auth middleware (auth_middleware.py)",
     lambda: os.path.exists("src/jefrey/api/auth_middleware.py")
             and "Bearer" in open("src/jefrey/api/auth_middleware.py", encoding="utf-8").read()),

    # SEC-006: secret_key production validation
    ("SEC-006: secret_key production validation em APISettings",
     lambda: "validate_for_production" in open("src/jefrey/core/config.py", encoding="utf-8").read()
             and "validate_for_production()" in open("src/jefrey/api/main.py", encoding="utf-8").read()),
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
