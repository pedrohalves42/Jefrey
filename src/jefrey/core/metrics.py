"""P6 — Central Prometheus Metrics Module.

Define todas as métricas do Jefrey usando prometheus_client.
Padrão: Counter (_total), Histogram (_seconds), Gauge.

Labels de BAIXA cardinalidade (sem user_id, sem content).
Provider/model/tool_name são dims controladas.

Referência: https://prometheus.io/docs/practices/naming/
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge

# =============================================================================
# 1. LLM LATENCY — Histogram (distribuição de latência de chamadas LLM)
# =============================================================================
LLM_LATENCY = Histogram(
    name="jefrey_llm_latency_seconds",
    documentation="Latência de chamadas LLM em segundos (provider + model)",
    labelnames=["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# =============================================================================
# 2. TOKENS & COST — Counters (acumulativos)
# =============================================================================
LLM_TOKENS = Counter(
    name="jefrey_llm_tokens_total",
    documentation="Total de tokens processados por LLM (input + output)",
    labelnames=["type", "provider", "model"],
    # type: "input" ou "output"
)

LLM_COST = Counter(
    name="jefrey_llm_cost_usd_total",
    documentation="Custo acumulado em USD por chamadas LLM",
    labelnames=["provider", "model"],
)

# =============================================================================
# 3. TOOLS BLOCKED — Counter (ferramentas bloqueadas pelo policy engine)
# =============================================================================
TOOLS_BLOCKED = Counter(
    name="jefrey_tools_blocked_total",
    documentation="Total de ferramentas bloqueadas pelo policy engine",
    labelnames=["tool_name", "reason"],
)

# =============================================================================
# 4. APPROVALS HITL — Counters (criação e decisão de aprovações)
# =============================================================================
APPROVALS_CREATED = Counter(
    name="jefrey_approvals_created_total",
    documentation="Total de aprovações HITL criadas",
    labelnames=["tool_name", "risk_level"],
)

APPROVALS_DECIDED = Counter(
    name="jefrey_approvals_decided_total",
    documentation="Total de decisões HITL tomadas (approved/denied/expired)",
    labelnames=["decision", "tool_name"],
)

# =============================================================================
# 5. MCP CALLS — Counter (chamadas a servidores MCP externos)
# =============================================================================
MCP_CALLS = Counter(
    name="jefrey_mcp_calls_total",
    documentation="Total de chamadas MCP realizadas",
    labelnames=["server", "status"],
    # status: "success" ou "error"
)

MCP_LATENCY = Histogram(
    name="jefrey_mcp_latency_seconds",
    documentation="Latência de chamadas MCP em segundos",
    labelnames=["server"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# =============================================================================
# 6b. TOOL EXECUTION LATENCY — Histogram (local tool invocations)
# =============================================================================
TOOL_EXEC_LATENCY = Histogram(
    name="jefrey_tool_exec_latency_seconds",
    documentation="Latência de execução de ferramentas locais em segundos",
    labelnames=["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# =============================================================================
# 6. SERVICE HEALTH — Gauge (estado do serviço)
# =============================================================================
SERVICE_HEALTH = Gauge(
    name="jefrey_service_health",
    documentation="Estado do serviço Jefrey (1=up, 0=down)",
    labelnames=["component"],
)

UPTIME = Gauge(
    name="jefrey_uptime_seconds",
    documentation="Tempo de atividade do serviço em segundos",
)

# =============================================================================
# 7. MEMORY OPS — Counters (operações de memória vetorial)
# =============================================================================
MEMORY_OPS = Counter(
    name="jefrey_memory_ops_total",
    documentation="Total de operações de memória vetorial",
    labelnames=["operation", "layer"],
    # operation: "add", "search", "get", "update", "delete"
)

MEMORY_LATENCY = Histogram(
    name="jefrey_memory_latency_seconds",
    documentation="Latência de operações de memória em segundos",
    labelnames=["operation", "layer"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
# =============================================================================
# 8. SKILL INIT + OAUTH + WEB SEARCH CACHE - P1.1 (AXIOM observabilidade)
# =============================================================================
SKILL_INIT_TOTAL = Counter(
    name="jefrey_skill_init_total",
    documentation="Total de inicializacoes de skills por status",
    labelnames=["skill", "status"],
)

OAUTH_REFRESH_TOTAL = Counter(
    name="jefrey_oauth_refresh_total",
    documentation="Total de refreshes OAuth por skill",
    labelnames=["skill", "status"],
)

WEB_SEARCH_CACHE_HIT = Counter(
    name="jefrey_web_search_cache_hit_total",
    documentation="Total de cache hits em web_search",
    labelnames=["mode"],
)

RATE_LIMIT_TOTAL = Counter(
    name="jefrey_rate_limit_total",
    documentation="Total de rate-limit decisions (allow/deny) por ferramenta",
    labelnames=["tool_name", "decision"],
)

CONFIG_VALID = Gauge(
    name="jefrey_config_valid",
    documentation="Config valida (1) ou invalida (0) - CIPHER-019/002/001",
)

