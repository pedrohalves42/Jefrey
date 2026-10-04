"""Jefrey n8n Bridge (Fase P3b, Diff 4) — Execucao de workflows n8n com HITL.

Ponte entre Jefrey e n8n para execucao de workflows automatizados.
Suporta dois modos de comunicacao:
  * MCP: via MCPClient com OAuth (n8n expoe MCP Server)
  * Webhook: fallback HTTP direto para /webhook/* do n8n

Workflows classificados como HIGH/CRITICAL pelo PolicyEngine passam
obrigatoriamente pelo HITLManager antes da execucao (aprovacao humana).

Referencia: Book 5 (MCP Spec 2026-07-28), Book 1 (DDIA - idempotencia),
Book 7 (Security Engineering - least privilege).
"""
from __future__ import annotations

import os
import json
import logging
import asyncio
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos e constantes
# ---------------------------------------------------------------------------
class BridgeMode(str, Enum):
    """Modo de comunicacao com o n8n."""
    MCP = "mcp"          # Via MCPClient (n8n expoe MCP Server)
    WEBHOOK = "webhook"  # Via HTTP POST direto para webhook n8n
    AUTO = "auto"        # Tenta MCP primeiro, fallback para webhook


class WorkflowStatus(str, Enum):
    """Status de execucao de um workflow."""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class WorkflowResult:
    """Resultado da execucao de um workflow n8n."""
    workflow_name: str
    status: WorkflowStatus
    data: dict | None = None
    error: str | None = None
    approval_id: str | None = None
    elapsed_secs: float = 0.0
    mode: str = ""  # "mcp" ou "webhook"

    def to_dict(self) -> dict:
        return {
            "workflow": self.workflow_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "approval_id": self.approval_id,
            "elapsed": round(self.elapsed_secs, 3),
            "mode": self.mode,
        }


# ---------------------------------------------------------------------------
# Registro de workflows conhecidos com metadata de risco
# ---------------------------------------------------------------------------
@dataclass
class WorkflowSpec:
    """Especificacao de um workflow n8n registrado."""
    name: str
    description: str = ""
    risk: str = "LOW"           # LOW, MEDIUM, HIGH, CRITICAL
    required_role: str = "user"
    webhook_path: str = ""      # ex: /webhook/jefrey-send-message
    mcp_tool: str = ""          # nome da tool MCP equivalente
    timeout: float = 30.0
    idempotent: bool = False    # Book 1: safe to retry?


# Workflows pre-registrados (fail-closed: so executa workflows conhecidos)
_WORKFLOW_REGISTRY: dict[str, WorkflowSpec] = {}


def register_workflow(spec: WorkflowSpec) -> None:
    """Registra um workflow no bridge (fail-closed: so conhecidos executam)."""
    _WORKFLOW_REGISTRY[spec.name] = spec
    logger.info("n8n bridge: workflow '%s' registrado (risk=%s)", spec.name, spec.risk)


def get_workflow(name: str) -> WorkflowSpec | None:
    """Busca workflow registrado."""
    return _WORKFLOW_REGISTRY.get(name)


def list_workflows() -> list[dict]:
    """Lista todos os workflows registrados."""
    return [
        {
            "name": w.name,
            "description": w.description,
            "risk": w.risk,
            "required_role": w.required_role,
            "has_webhook": bool(w.webhook_path),
            "has_mcp_tool": bool(w.mcp_tool),
        }
        for w in _WORKFLOW_REGISTRY.values()
    ]


# Registrar workflows padrao
def _register_defaults() -> None:
    """Registra workflows padrao do Jefrey."""
    defaults = [
        WorkflowSpec(
            name="browser_control",
            description="Navega para URL via n8n browser automation",
            risk="LOW",
            webhook_path="/webhook/jefrey-browser",
            mcp_tool="browser_control",
            timeout=15.0,
        ),
        WorkflowSpec(
            name="send_message",
            description="Envia mensagem via WhatsApp/Telegram",
            risk="HIGH",
            required_role="admin",
            webhook_path="/webhook/jefrey-send-message",
            mcp_tool="send_message",
            timeout=10.0,
        ),
        WorkflowSpec(
            name="email_send",
            description="Envia email (integracao Gmail/Outlook)",
            risk="HIGH",
            required_role="admin",
            webhook_path="/webhook/jefrey-email",
            mcp_tool="email_send",
            timeout=15.0,
        ),
        WorkflowSpec(
            name="calendar_create",
            description="Cria evento no Google Calendar",
            risk="HIGH",
            required_role="admin",
            webhook_path="/webhook/jefrey-calendar",
            mcp_tool="calendar_create",
            timeout=10.0,
        ),
        WorkflowSpec(
            name="search_web",
            description="Busca na web via n8n SerpAPI/Google",
            risk="LOW",
            webhook_path="/webhook/jefrey-search",
            mcp_tool="search_web",
            timeout=20.0,
        ),
    ]
    for spec in defaults:
        register_workflow(spec)


_register_defaults()


# ---------------------------------------------------------------------------
# N8nBridge — classe principal
# ---------------------------------------------------------------------------
class N8nBridge:
    """Ponte Jefrey <-> n8n com HITL para workflows HIGH/CRITICAL.

    Uso:
        bridge = N8nBridge()
        result = await bridge.execute("email_send", {"to": "x@y.com", ...}, user_id="pedro")
    """

    def __init__(
        self,
        n8n_base_url: str | None = None,
        mode: BridgeMode = BridgeMode.AUTO,
        mcp_url: str | None = None,
        oauth_tokens: list[str] | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._base_url = n8n_base_url or os.getenv(
            "JEFREY_N8N_BASE_URL",
            os.getenv("N8N_WEBHOOK_URL", "http://jefrey-n8n:5678"),
        )
        self._mode = mode
        self._mcp_url = mcp_url or os.getenv("JEFREY_N8N_MCP_URL", "")
        self._oauth_tokens = oauth_tokens
        self._default_timeout = default_timeout
        self._mcp_client = None
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._hitl_count: int = 0

    # ----- HITL integration -----
    async def _check_hitl(
        self, spec: WorkflowSpec, args: dict, user_id: str, thread_id: str,
    ) -> WorkflowResult | None:
        """Verifica se workflow precisa de aprovacao HITL.

        Retorna WorkflowResult com status AWAITING_APPROVAL se precisar,
        None se pode executar direto.
        """
        if spec.risk not in ("HIGH", "CRITICAL"):
            return None  # LOW/MEDIUM executam direto

        # RBAC check
        from src.jefrey.core.rbac import RBAC, resolve_role
        rbac = RBAC()
        effective_role = resolve_role(user_id).value

        if not rbac.is_allowed(effective_role, spec.required_role):
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.REJECTED,
                error=f"RBAC: role '{effective_role}' nao tem permissao (requer '{spec.required_role}')",
                mode=self._mode.value,
            )

        # HITL: criar pedido de aprovacao
        from src.jefrey.core.hitl import HITLManager
        hitl = HITLManager()
        try:
            approval_id = await hitl.create_approval(
                tool_name=f"n8n:{spec.name}",
                args=args,
                user_id=user_id,
                thread_id=thread_id,
                risk_level=spec.risk,
                reason=f"Workflow n8n '{spec.name}' classificado como {spec.risk}",
            )
            self._hitl_count += 1
            logger.info(
                "n8n bridge: HITL approval requested for '%s' (id=%s)",
                spec.name, approval_id[:8],
            )

            # Aguardar decisao (com timeout)
            decision = await hitl.wait_for_decision(
                approval_id, timeout=spec.timeout,
            )

            if decision == "approved":
                return None  # Aprovado - pode executar
            else:
                return WorkflowResult(
                    workflow_name=spec.name,
                    status=WorkflowStatus.REJECTED,
                    approval_id=approval_id[:8],
                    error=f"HITL: workflow '{spec.name}' rejeitado ou expirado",
                    mode=self._mode.value,
                )
        except Exception as exc:
            logger.warning("n8n bridge: HITL check failed for '%s': %s", spec.name, exc)
            # Fail-closed: se HITL falha, bloqueia execucao
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.FAILED,
                error=f"HITL indisponivel (fail-closed): {exc}",
                mode=self._mode.value,
            )

    # ----- Execucao via webhook -----
    async def _execute_webhook(
        self, spec: WorkflowSpec, args: dict, user_id: str,
    ) -> WorkflowResult:
        """Executa workflow via HTTP webhook do n8n."""
        import httpx

        webhook_url = f"{self._base_url.rstrip('/')}{spec.webhook_path}"

        # SSRF check (CIPHER-032)
        from src.jefrey.core.connections import _is_blocked_url
        if _is_blocked_url(webhook_url):
            # Permitir URLs internas conhecidas do n8n (docker-compose service)
            if "jefrey-n8n" not in webhook_url and "localhost" not in webhook_url:
                return WorkflowResult(
                    workflow_name=spec.name,
                    status=WorkflowStatus.FAILED,
                    error=f"SSRF blocked: {webhook_url}",
                    mode="webhook",
                )

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=spec.timeout) as client:
                response = await client.post(
                    webhook_url,
                    json={**args, "user_id": user_id},
                    headers={
                        "X-User-Id": user_id,
                        "X-Jefrey-Workflow": spec.name,
                        "Content-Type": "application/json",
                    },
                )
            elapsed = time.monotonic() - start

            if response.status_code < 400:
                try:
                    data = response.json()
                except Exception:
                    data = {"raw": response.text[:1000]}
                return WorkflowResult(
                    workflow_name=spec.name,
                    status=WorkflowStatus.SUCCESS,
                    data=data,
                    elapsed_secs=elapsed,
                    mode="webhook",
                )
            else:
                return WorkflowResult(
                    workflow_name=spec.name,
                    status=WorkflowStatus.FAILED,
                    error=f"n8n HTTP {response.status_code}: {response.text[:300]}",
                    elapsed_secs=elapsed,
                    mode="webhook",
                )
        except asyncio.TimeoutError:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.TIMEOUT,
                error=f"Timeout apos {spec.timeout}s",
                elapsed_secs=time.monotonic() - start,
                mode="webhook",
            )
        except Exception as exc:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.FAILED,
                error=f"Webhook error: {type(exc).__name__}: {exc}",
                elapsed_secs=time.monotonic() - start,
                mode="webhook",
            )

    # ----- Execucao via MCP -----
    async def _execute_mcp(
        self, spec: WorkflowSpec, args: dict, user_id: str, thread_id: str,
    ) -> WorkflowResult:
        """Executa workflow via MCPClient (n8n MCP Server)."""
        from src.jefrey.mcp.client import MCPClient, MCPClientError

        if not self._mcp_url:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.FAILED,
                error="MCP URL nao configurada (JEFREY_N8N_MCP_URL)",
                mode="mcp",
            )

        start = time.monotonic()
        try:
            client = MCPClient(
                name=f"n8n-{spec.name}",
                url=self._mcp_url,
                oauth_tokens=self._oauth_tokens,
                timeout=spec.timeout,
            )
            async with client:
                tool_name = spec.mcp_tool or spec.name
                # Injetar thread_id nos args para rastreabilidade
                mcp_args = {**args, "thread_id": thread_id}
                raw = await client.call_tool(tool_name, mcp_args)

            elapsed = time.monotonic() - start
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                data = {"raw": raw[:1000] if raw else ""}

            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.SUCCESS,
                data=data,
                elapsed_secs=elapsed,
                mode="mcp",
            )
        except MCPClientError as exc:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.FAILED,
                error=f"MCP error: {exc.message}",
                elapsed_secs=time.monotonic() - start,
                mode="mcp",
            )
        except asyncio.TimeoutError:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.TIMEOUT,
                error=f"MCP timeout apos {spec.timeout}s",
                elapsed_secs=time.monotonic() - start,
                mode="mcp",
            )
        except Exception as exc:
            return WorkflowResult(
                workflow_name=spec.name,
                status=WorkflowStatus.FAILED,
                error=f"MCP unexpected: {type(exc).__name__}: {exc}",
                elapsed_secs=time.monotonic() - start,
                mode="mcp",
            )

    # ----- Metodo principal -----
    async def execute(
        self,
        workflow_name: str,
        args: dict | None = None,
        *,
        user_id: str = "system",
        thread_id: str = "",
    ) -> WorkflowResult:
        """Executa um workflow n8n com verificacao HITL.

        Fluxo:
        1. Lookup no registry (fail-closed: so workflows conhecidos)
        2. HITL check para HIGH/CRITICAL (aprovacao humana)
        3. Execucao via MCP ou webhook (conforme modo)
        4. Audit log do resultado

        Args:
            workflow_name: nome do workflow registrado
            args: argumentos para o workflow
            user_id: ID do usuario que solicitou
            thread_id: ID da thread para rastreabilidade

        Returns:
            WorkflowResult com status e dados
        """
        args = args or {}
        self._execution_count += 1

        # 1. Lookup (fail-closed)
        spec = get_workflow(workflow_name)
        if spec is None:
            self._failure_count += 1
            logger.warning("n8n bridge: workflow '%s' nao registrado (fail-closed)", workflow_name)
            return WorkflowResult(
                workflow_name=workflow_name,
                status=WorkflowStatus.REJECTED,
                error=f"Workflow '{workflow_name}' nao registrado no bridge (fail-closed)",
                mode=self._mode.value,
            )

        # 2. HITL check
        hitl_result = await self._check_hitl(spec, args, user_id, thread_id)
        if hitl_result is not None:
            self._failure_count += 1
            self._audit(spec, hitl_result, user_id, thread_id)
            return hitl_result

        # 3. Execucao
        result: WorkflowResult

        if self._mode == BridgeMode.MCP:
            result = await self._execute_mcp(spec, args, user_id, thread_id)
        elif self._mode == BridgeMode.WEBHOOK:
            result = await self._execute_webhook(spec, args, user_id)
        else:
            # AUTO: tenta MCP primeiro, fallback webhook
            if self._mcp_url:
                result = await self._execute_mcp(spec, args, user_id, thread_id)
                if result.status in (WorkflowStatus.FAILED, WorkflowStatus.TIMEOUT):
                    logger.info(
                        "n8n bridge: MCP falhou para '%s', fallback webhook", spec.name,
                    )
                    result = await self._execute_webhook(spec, args, user_id)
            else:
                result = await self._execute_webhook(spec, args, user_id)

        # 4. Contadores e audit
        if result.status == WorkflowStatus.SUCCESS:
            self._success_count += 1
        else:
            self._failure_count += 1
        self._audit(spec, result, user_id, thread_id)

        return result

    def _audit(
        self, spec: WorkflowSpec, result: WorkflowResult,
        user_id: str, thread_id: str,
    ) -> None:
        """Log de auditoria da execucao do workflow."""
        try:
            from src.jefrey.core.audit import get_audit_logger
            get_audit_logger().log(
                thread_id=thread_id or "n8n-bridge",
                tool_name=f"n8n:{spec.name}",
                actor_role=spec.required_role,
                risk=spec.risk.lower(),
                decision="allow" if result.status == WorkflowStatus.SUCCESS else "deny",
                user_id=user_id,
                detail={
                    "workflow": spec.name,
                    "status": result.status.value,
                    "mode": result.mode,
                    "elapsed": result.elapsed_secs,
                    "error": result.error,
                },
            )
        except Exception as exc:
            logger.warning("n8n bridge audit failed: %s", exc)

    def health(self) -> dict:
        """Info de saude do bridge para o health endpoint."""
        return {
            "mode": self._mode.value,
            "n8n_base_url": self._base_url,
            "mcp_url": self._mcp_url or None,
            "workflows_registered": len(_WORKFLOW_REGISTRY),
            "executions": self._execution_count,
            "successes": self._success_count,
            "failures": self._failure_count,
            "hitl_requests": self._hitl_count,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_bridge_instance: N8nBridge | None = None


def get_bridge() -> N8nBridge:
    """Retorna singleton do N8nBridge."""
    global _bridge_instance
    if _bridge_instance is None:
        mode_str = os.getenv("JEFREY_N8N_BRIDGE_MODE", "auto").lower()
        try:
            mode = BridgeMode(mode_str)
        except ValueError:
            mode = BridgeMode.AUTO

        tokens_raw = os.getenv("JEFREY_MCP_CLIENT_TOKENS", "")
        tokens = [t.strip() for t in tokens_raw.split(",") if t.strip()] or None

        _bridge_instance = N8nBridge(
            mode=mode,
            oauth_tokens=tokens,
        )
        logger.info("n8n bridge initialized (mode=%s)", mode.value)
    return _bridge_instance


def reset_bridge() -> None:
    """Reseta o singleton (para testes)."""
    global _bridge_instance
    _bridge_instance = None
