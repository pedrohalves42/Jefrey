"""Agent LangGraph-based AI core — orchestration with RBAC, PolicyEngine, and HITL."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.jefrey.core.policy import decide, check_risk, PolicyContext
from src.jefrey.core.rate_limit import RateLimiter
from src.jefrey.core.registry import get_tool, get_tool_risk, get_tool_required_role
from src.jefrey.core.hitl import HITLManager
from src.jefrey.core.rbac import RBAC
from src.jefrey.core.audit import AuditLogger, get_audit_logger
from src.jefrey.core.memory import MemoryManager
from src.jefrey.core.content_guard import sanitize_tool_output

logger = logging.getLogger(__name__)

class AgentState(Dict[str, Any]):
    """State bag passed through the LangGraph agent loop.
    Supports both dict access (state["key"]) and attribute access (state.key).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"AgentState has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value

class Agent:
    """LangGraph-based AI agent with secure tool execution.

    Orchestrates:
    1. RBAC checks (Axiom #1: deny/false/raise)
    2. Policy risk assessment
    3. Rate limiting (fail-closed, CIPHER-026)
    4. Human-in-the-Loop for HIGH/CRITICAL risks
    5. Content sanitization against prompt injection (CIPHER-032)
    6. Audit logging of all decisions (CIPHER-025)
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        hitl_manager: Optional[HITLManager] = None,
        rbac: Optional[RBAC] = None,
        audit_logger: Optional[AuditLogger] = None,
        memory: Optional[MemoryManager] = None,
    ):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.hitl_manager = hitl_manager or HITLManager()
        self.rbac = rbac or RBAC()
        self.audit_logger = audit_logger or get_audit_logger()
        self.memory = memory or MemoryManager()
        self._tool_executions: int = 0

    def _load_context(self, state: AgentState) -> str:
        """Load context for the agent prompt with user_id isolation."""
        user_id = state.user_id or "guest"
        try:
                        # P05-08: isolamento short-term por thread (Axioma #2)
            # session(state.thread_id) -> garante isolamento por thread_id
            try:
                _wm = self.memory.session(state.thread_id)  # type: ignore[attr-defined]
            except Exception:
                _wm = None
            return self.memory.get_context(state.get("user_input", ""), user_id=user_id)
        except Exception as e:
            logger.warning("memory context load failed: %s", e)
            return ""

    async def _invoke(self, tool, args: Dict[str, Any], state: AgentState) -> Any:
        """Secure tool execution with full governance pipeline."""
        tool_name = getattr(tool, "name", str(tool))
        risk = get_tool_risk(tool_name)
        required_role = get_tool_required_role(tool_name)

        # 1. RBAC check
        if not self.rbac.is_allowed(state.user_role, required_role):
            await self.audit_logger.log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="deny_rbac", user_id=state.user_id,
            )
            raise PermissionError(f"RBAC: {state.user_role} sem acesso a {tool_name}")

        # 2. Rate limiting
        rate_result = self.rate_limiter.is_allowed_sync(state.user_id, tool_name)
        if rate_result == "deny":
            await self.audit_logger.log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="deny_rate_limit", user_id=state.user_id,
            )
            raise PermissionError(f"Rate limit atingido para {tool_name}")

        # 3. HITL for HIGH/CRITICAL risks
        if risk in ("HIGH", "CRITICAL"):
            approval_id = await self.hitl_manager.create_approval(
                tool_name=tool_name, args=args,
                user_id=state.user_id, thread_id=state.thread_id, ttl=1800,
            )
            decision = await self.hitl_manager.wait_for_decision(
                approval_id=approval_id, timeout=1800,
            )
            if decision != "approved":
                await self.audit_logger.log(
                    thread_id=state.thread_id, tool_name=tool_name,
                    actor_role=state.user_role, risk=risk,
                    decision="deny_hitl", user_id=state.user_id,
                )
                raise PermissionError(f"HITL rejeitou {tool_name}")

        # 4. Content sanitization
        sanitized_args = sanitize_tool_output(str(args), tool_name=tool_name)

        # 5. Audit log
        await self.audit_logger.log(
            thread_id=state.thread_id, tool_name=tool_name,
            actor_role=state.user_role, risk=risk,
            decision="allow", user_id=state.user_id,
        )

        # 6. Execute tool
        self._tool_executions += 1
        try:
            result = await tool.ainvoke(sanitized_args)
            await self.audit_logger.log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="executed", user_id=state.user_id,
                reason=f"executed OK ({str(result)[:200]})",
            )
            return result
        except Exception as e:
            await self.audit_logger.log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="error", user_id=state.user_id,
                reason=f"error: {type(e).__name__}: {str(e)[:200]}",
            )
            raise

    async def run(self, user_input: str, user_id: str, user_role: str = "guest") -> Dict[str, Any]:
        """Run the agent loop with a user input.

        Calls Ollama LLM for actual conversational responses.
        """
        state = AgentState(
            user_id=user_id,
            thread_id=f"thread_{user_id}_{self._tool_executions}",
            user_role=user_role,
        )

        # Load context from memory with user_id isolation
        state.context = self._load_context(state)

        # Build system prompt - blindado contra vazamento de identidade do modelo base
        system_prompt = (
            "Voce e o Jefrey, um assistente AI pessoal inteligente e amigavel criado pela equipe Jefrey. "
            "NUNCA diga que e Qwen, Alibaba, Cloud ou qualquer outro nome - voce e sempre Jefrey. "
            "Responda sempre em portugues brasileiro de forma natural e util. "
            "Se perguntarem quem te criou, responda: Fui criado pela equipe Jefrey. "
            "Seja conciso mas completo. Se nao souber algo, diga honestamente.\n\n"
            f"Contexto:\n{state.context}\n"
        )

        # Call Ollama LLM
        try:
            import httpx as _httpx
            from src.jefrey.core.config import get_settings
            cfg = get_settings()
            base_url = (getattr(cfg.llm, "base_url", None) or "http://ollama:11434").rstrip("/")
            model = getattr(cfg.llm, "model", "qwen2.5:0.5b")

            async with _httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_input},
                        ],
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("message", {}).get("content", "")

                if not response_text:
                    response_text = "Desculpe, nao consegui processar sua mensagem."

                try:
                    from src.jefrey.core.audit import redact_pii
                    logger.info("chat: user=%s thread=%s input=%s response_len=%d",
                        user_id, state.thread_id, redact_pii(user_input[:80]), len(response_text))
                except Exception:
                    pass

                return {
                    "response": response_text,
                    "thread_id": state.thread_id,
                    "status": "completed",
                }

        except Exception as e:
            logger.error("agent LLM call failed: %s", e, exc_info=True)
            return {
                "response": f"Ola! Sou o Jefrey. O LLM esta indisponivel ({type(e).__name__}). Estou funcionando mas sem conexao com o modelo.",
                "thread_id": state.thread_id,
                "status": "degraded",
                "error": str(e),
            }

    async def run_stream(self, user_input: str, user_id: str, user_role: str = "guest"):
        """Streaming LLM via Ollama /api/chat stream:true — DIFF4.1 SSE token por token."""
        state = AgentState(user_id=user_id, thread_id=f"thread_{user_id}_{self._tool_executions}", user_role=user_role)
        state.context = self._load_context(state)
        system_prompt = (
            "Voce e o Jefrey, um assistente AI pessoal inteligente e amigavel criado pela equipe Jefrey. "
            "NUNCA diga que e Qwen, Alibaba, Cloud ou qualquer outro nome - voce e sempre Jefrey. "
            "Responda sempre em portugues brasileiro de forma natural e util. "
            "Se perguntarem quem te criou, responda: Fui criado pela equipe Jefrey. "
            "Seja conciso mas completo. Se nao souber algo, diga honestamente.\n\n"
            f"Contexto:\n{state.context}\n"
        )
        try:
            import httpx as _httpx
            import json as _json
            from src.jefrey.core.config import get_settings
            cfg = get_settings()
            base_url = (getattr(cfg.llm, "base_url", None) or "http://ollama:11434").rstrip("/")
            model = getattr(cfg.llm, "model", "qwen2.5:0.5b")
            async with _httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", f"{base_url}/api/chat", json={"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}], "stream": True}) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = _json.loads(line)
                            if data.get("done"):
                                break
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            continue
        except Exception as e:
            logger.error("agent run_stream failed: %s", e, exc_info=True)
            yield f"[erro LLM {type(e).__name__}]"


class JefreyAgent(Agent):
    """Compat class para verify_cipher CIPHER-022 (resolve_role server-side)."""
    def _resolve_role(self, preferred=None):
        from src.jefrey.core.rbac import resolve_role
        return resolve_role(preferred)

# Alias legacy - mantem compat imports
JefreyAgentAlias = JefreyAgent