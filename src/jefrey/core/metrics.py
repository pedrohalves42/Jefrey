"""P6 — Central Prometheus Metrics Module (Enhanced Diff 5).

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
# 5b. MCP SERVER METRICS (Diff 5) — Server-side tool calls, cache, auth
# =============================================================================
MCP_TOOL_CALLS = Counter(
    name="jefrey_mcp_tool_calls_total",
    documentation="Total de chamadas de ferramentas MCP (server-side)",
    labelnames=["tool_name", "status"],
    # status: "success", "error", "blocked", "hitl_pending", "hitl_approved", "hitl_denied"
)

MCP_TOOL_LATENCY = Histogram(
    name="jefrey_mcp_tool_latency_seconds",
    documentation="Latência de execução de ferramentas MCP (server-side)",
    labelnames=["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

MCP_CACHE_HITS = Counter(
    name="jefrey_mcp_cache_hits_total",
    documentation="Total de cache hits no discovery cache",
)

MCP_CACHE_MISSES = Counter(
    name="jefrey_mcp_cache_misses_total",
    documentation="Total de cache misses no discovery cache",
)

MCP_OAUTH_VALIDATIONS = Counter(
    name="jefrey_mcp_oauth_validations_total",
    documentation="Total de validações OAuth (token checks)",
    labelnames=["result"],
    # result: "valid", "invalid", "missing", "error"
)

MCP_RATE_LIMIT_DECISIONS = Counter(
    name="jefrey_mcp_rate_limit_decisions_total",
    documentation="Decisões de rate-limit por ferramenta",
    labelnames=["tool_name", "decision"],
    # decision: "allow", "deny"
)

MCP_BRIDGE_EXECUTIONS = Counter(
    name="jefrey_mcp_bridge_executions_total",
    documentation="Total de execuções via n8n Bridge",
    labelnames=["workflow", "mode", "status"],
    # mode: "mcp", "webhook"
    # status: "success", "error", "timeout", "hitl_rejected"
)

# =============================================================================
# 6. TOOL EXECUTION LATENCY — Histogram (local tool invocations)
# =============================================================================
TOOL_EXEC_LATENCY = Histogram(
    name="jefrey_tool_exec_latency_seconds",
    documentation="Latência de execução de ferramentas locais em segundos",
    labelnames=["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# =============================================================================
# 7. SERVICE HEALTH — Gauge (estado do serviço)
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
# 8. MEMORY OPS — Counters (operações de memória vetorial)
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
# 9. SKILL INIT + OAUTH + WEB SEARCH CACHE - P1.1 (AXIOM observabilidade)
# =============================================================================
SKILL_INIT_TOTAL = Counter(
    name="jefrey_skill_init_total",
    documentation="Total de inicializações de skills por status",
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
    documentation="Config válida (1) ou inválida (0) - CIPHER-019/002/001",
)

# FASE1 C2: kid legacy sem user_id label (Prometheus cardinality - Brazil ch.5)
EVENTBUS_KID_LEGACY_TOTAL = Counter(
    name="jefrey_eventbus_kid_legacy_total",
    documentation="Total de mensagens EventBus sem kid (v0 compat, DeprecationWarning)",
    labelnames=[],
)

# =============================================================================
# 10. STT/TTS — P1 Voz (Livro 4 cap5 cardinality <800, cap6 histogram)
# =============================================================================
STT_DURATION = Histogram(
    name="jefrey_stt_duration_seconds",
    documentation="Latência STT (transcrição) em segundos",
    labelnames=["provider", "model"],
    buckets=(0.1, 0.3, 0.6, 1.0, 2.0, 5.0),
)

TTS_DURATION = Histogram(
    name="jefrey_tts_duration_seconds",
    documentation="Latência TTS (síntese) em segundos",
    labelnames=["provider", "voice"],
    buckets=(0.1, 0.3, 0.6, 1.0, 2.5, 5.0),
)

STT_REQUESTS = Counter(
    name="jefrey_stt_requests_total",
    documentation="Total de requisições STT por status",
    labelnames=["status"],
)

TTS_REQUESTS = Counter(
    name="jefrey_tts_requests_total",
    documentation="Total de requisições TTS por status",
    labelnames=["status"],
)


# =============================================================================
# Helper: metricas derivadas / utilitários
# =============================================================================
def record_mcp_tool_call(tool_name: str, status: str, latency: float) -> None:
    """Registra chamada de tool MCP (server-side) de forma conveniente."""
    MCP_TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()
    MCP_TOOL_LATENCY.labels(tool_name=tool_name).observe(latency)


def record_cache_hit() -> None:
    MCP_CACHE_HITS.inc()


def record_cache_miss() -> None:
    MCP_CACHE_MISSES.inc()


def record_oauth_validation(result: str) -> None:
    """result: 'valid' | 'invalid' | 'missing' | 'error'"""
    MCP_OAUTH_VALIDATIONS.labels(result=result).inc()


def record_rate_limit_decision(tool_name: str, decision: str) -> None:
    """decision: 'allow' | 'deny'"""
    MCP_RATE_LIMIT_DECISIONS.labels(tool_name=tool_name, decision=decision).inc()


def record_bridge_execution(workflow: str, mode: str, status: str) -> None:
    """mode: 'mcp' | 'webhook'; status: 'success' | 'error' | 'timeout' | 'hitl_rejected'"""
    MCP_BRIDGE_EXECUTIONS.labels(workflow=workflow, mode=mode, status=status).inc()