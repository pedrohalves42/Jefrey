"""P6 - Verificacao de Observabilidade (Prometheus + Grafana).

Verifica: metricas definidas, decorators, endpoint, instrumentacao,
config Prometheus, dashboard Grafana, docker-compose.
"""
from __future__ import annotations

import os
import sys
import json

# Adiciona raiz ao path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ASCII-safe symbols
PASS = "+"
FAIL = "x"


def _read(path: str) -> str:
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return ""
    with open(full, encoding="utf-8") as f:
        return f.read()


def _exists(path: str) -> bool:
    return os.path.isfile(os.path.join(ROOT, path))


def _grafana_panel_count() -> int:
    path = os.path.join(ROOT, "docker/grafana/dashboards/jefrey.json")
    if not os.path.isfile(path):
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("panels", []))
    except Exception:
        return 0


def _check_no_userid_labels() -> bool:
    """Verifica que 'user_id' NAO aparece em labelnames= de metrics.py."""
    content = _read("src/jefrey/core/metrics.py")
    import re
    # Encontra todas as ocorrencias de labelnames=(...)
    label_blocks = re.findall(r'labelnames\s*=\s*\(([^)]*)\)', content)
    for block in label_blocks:
        if "user_id" in block:
            return False
    return True


# =============================================================================
# Checks
# =============================================================================
checks = [
    # --- Core Metrics Module ---
    ("P06-01", "metrics.py existe",
     lambda: _exists("src/jefrey/core/metrics.py")),
    ("P06-02", "Histogram LLM latency definido",
     lambda: "jefrey_llm_latency_seconds" in _read("src/jefrey/core/metrics.py")),
    ("P06-03", "Counter LLM tokens definido",
     lambda: "jefrey_llm_tokens_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-04", "Counter LLM cost definido",
     lambda: "jefrey_llm_cost_usd_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-05", "Counter tools blocked definido",
     lambda: "jefrey_tools_blocked_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-06", "Counter approvals created definido",
     lambda: "jefrey_approvals_created_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-07", "Counter approvals decided definido",
     lambda: "jefrey_approvals_decided_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-08", "Counter MCP calls definido",
     lambda: "jefrey_mcp_calls_total" in _read("src/jefrey/core/metrics.py")),
    ("P06-09", "Gauge service health definido",
     lambda: "jefrey_service_health" in _read("src/jefrey/core/metrics.py")),
    ("P06-09b", "Histogram tool exec latency definido",
     lambda: "jefrey_tool_exec_latency_seconds" in _read("src/jefrey/core/metrics.py")),
    ("P06-10", "Memory ops counter definido",
     lambda: "jefrey_memory_ops_total" in _read("src/jefrey/core/metrics.py")),
    # --- Instrumentation Module ---
    ("P06-11", "instrumentation.py existe com @timed e @counted",
     lambda: _exists("src/jefrey/core/instrumentation.py")
     and "def timed" in _read("src/jefrey/core/instrumentation.py")
     and "def counted" in _read("src/jefrey/core/instrumentation.py")),
    # --- Metrics Endpoint ---
    ("P06-12", "GET /metrics endpoint registrado",
     lambda: _exists("src/jefrey/api/metrics_endpoint.py")
     and "/metrics" in _read("src/jefrey/api/metrics_endpoint.py")
     and "generate_latest" in _read("src/jefrey/api/metrics_endpoint.py")),
    ("P06-13", "Metrics router importado em main.py",
     lambda: "metrics_endpoint" in _read("src/jefrey/api/main.py")
     and "metrics_router" in _read("src/jefrey/api/main.py")),
    # --- Instrumentation in Modules ---
    ("P06-14", "executor.py instrumentado (TOOLS_BLOCKED + TOOL_EXEC_LATENCY)",
     lambda: "TOOLS_BLOCKED" in _read("src/jefrey/core/executor.py")
     and "TOOL_EXEC_LATENCY" in _read("src/jefrey/core/executor.py")),
    ("P06-15", "hitl.py instrumentado (APPROVALS_CREATED + APPROVALS_DECIDED)",
     lambda: "APPROVALS_CREATED" in _read("src/jefrey/core/hitl.py")
     and "APPROVALS_DECIDED" in _read("src/jefrey/core/hitl.py")),
    ("P06-16", "mcp/client.py instrumentado (MCP_CALLS + MCP_LATENCY)",
     lambda: "MCP_CALLS" in _read("src/jefrey/mcp/client.py")
     and "MCP_LATENCY" in _read("src/jefrey/mcp/client.py")),
    ("P06-17", "pg_memory.py instrumentado (MEMORY_OPS + MEMORY_LATENCY)",
     lambda: "MEMORY_OPS" in _read("src/jefrey/core/pg_memory.py")
     and "MEMORY_LATENCY" in _read("src/jefrey/core/pg_memory.py")),
    # --- Docker Infrastructure ---
    ("P06-18", "prometheus.yml existe e aponta para jefrey-api:8000",
     lambda: _exists("docker/prometheus/prometheus.yml")
     and "jefrey-api:8000" in _read("docker/prometheus/prometheus.yml")),
    ("P06-19", "Grafana dashboard JSON valido (6 paineis)",
     lambda: _grafana_panel_count() == 6),
    ("P06-20", "Grafana datasource provisioning existe",
     lambda: _exists("docker/grafana/provisioning/datasources/datasource.yml")
     and "prometheus" in _read("docker/grafana/provisioning/datasources/datasource.yml").lower()),
    ("P06-21", "Grafana dashboard provisioning existe",
     lambda: _exists("docker/grafana/provisioning/dashboards/dashboard.yml")),
    ("P06-22", "docker-compose.yml tem servicos prometheus + grafana",
     lambda: "prometheus:" in _read("docker-compose.yml")
     and "grafana:" in _read("docker-compose.yml")
     and "jefrey_prometheus_data" in _read("docker-compose.yml")),
    ("P06-23", "docker-compose.yml: Prometheus retem 30d",
     lambda: "storage.tsdb.retention.time=30d" in _read("docker-compose.yml")),
    ("P06-24", "docker-compose.yml: Grafana sign-up desabilitado",
     lambda: 'GF_USERS_ALLOW_SIGN_UP: "false"' in _read("docker-compose.yml")),
    # --- Dependency ---
    ("P06-25", "prometheus-client na pyproject.toml",
     lambda: "prometheus-client" in _read("pyproject.toml")),
    # --- Security ---
    ("P06-26", "Sem user_id nas labels de metricas (baixa cardinalidade)",
     lambda: _check_no_userid_labels()),
]


def main() -> None:
    print()
    print(f"  {'=' * 60}")
    print(f"  P6 - Verificacao de Observabilidade (Prometheus + Grafana)")
    print(f"  {'=' * 60}")
    print()

    passed = 0
    failed = 0
    failed_checks = []

    for check_id, description, test_fn in checks:
        try:
            result = test_fn()
        except Exception as e:
            result = False
            description += f" (exception: {e})"

        if result:
            print(f"  {GREEN}{PASS}{RESET} {check_id}: {description}")
            passed += 1
        else:
            print(f"  {RED}{FAIL}{RESET} {check_id}: {description}")
            failed += 1
            failed_checks.append((check_id, description))

    total = passed + failed
    print()
    print(f"  {'=' * 60}")
    print(f"  Total: {total} | {GREEN}Passed: {passed}{RESET} | {RED}Failed: {failed}{RESET}")

    if failed:
        print()
        print(f"  {YELLOW}Failed checks:{RESET}")
        for cid, desc in failed_checks:
            print(f"    {RED}{FAIL}{RESET} {cid}: {desc}")

    print(f"\n  {'=' * 60}\n")

    if failed:
        sys.exit(1)
    else:
        print(f"  {GREEN}{BOLD}ALL P6 CHECKS PASSED!{RESET}")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
