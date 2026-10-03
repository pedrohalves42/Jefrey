"""Agent LangGraph-based AI core — orchestration with RBAC, PolicyEngine, and HITL."""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx
from typing import Any, Dict, List, Optional, Tuple

from src.jefrey.core.policy import decide, check_risk, PolicyContext
from src.jefrey.core.rate_limit import RateLimiter
from src.jefrey.core.registry import get_tool, get_tool_risk, get_tool_required_role
from src.jefrey.core.hitl import HITLManager
from src.jefrey.core.rbac import RBAC
from src.jefrey.core.audit import AuditLogger, get_audit_logger
from src.jefrey.core.memory import MemoryManager
from src.jefrey.core.content_guard import sanitize_tool_output
from src.jefrey.core.checkpointer import _ns_thread_id

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

    # CIPHER-308: historico de conversa real por (user_id, thread). Antes o short-term era um
    # stub (get_messages -> []) e o LLM so recebia a mensagem atual: o Jefrey nao lembrava nada.
    _HIST_MAX = int(os.getenv("JEFREY_CHAT_HISTORY_TURNS", "12"))

    def _hist_key(self, state: "AgentState") -> str:
        return f"jefrey:wm:{state.user_id or 'guest'}:hist:{state.thread_id}"

    def _load_history(self, state: "AgentState") -> list:
        try:
            r = self.memory.short_term._redis  # type: ignore[attr-defined]
            raw = r.lrange(self._hist_key(state), -self._HIST_MAX * 2, -1)
            out = []
            for item in raw:
                m = json.loads(item)
                if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                    out.append({"role": m["role"], "content": m["content"]})
            return out
        except Exception as e:
            logger.warning("historico indisponivel (segue sem): %s", e)
            return []

    def _save_turn(self, state: "AgentState", user_input: str, answer: str) -> None:
        try:
            r = self.memory.short_term._redis  # type: ignore[attr-defined]
            k = self._hist_key(state)
            pipe = r.pipeline()
            pipe.rpush(k, json.dumps({"role": "user", "content": user_input[:4000]}, ensure_ascii=False))
            pipe.rpush(k, json.dumps({"role": "assistant", "content": answer[:4000]}, ensure_ascii=False))
            pipe.ltrim(k, -self._HIST_MAX * 2, -1)
            pipe.expire(k, 86400)
            pipe.execute()
        except Exception as e:
            logger.warning("falha ao salvar historico: %s", e)

    @staticmethod
    def _format_context(ctx) -> str:
        """Contexto legivel para o LLM (antes era o repr() de um dict)."""
        if not ctx:
            return "(sem memorias relevantes)"
        if isinstance(ctx, str):
            return ctx
        lines = []
        for m in (ctx.get("relevant_memories") or [])[:5]:
            content = m.get("content") if isinstance(m, dict) else str(m)
            if content:
                lines.append(f"- {str(content)[:500]}")
        when = ctx.get("current_datetime")
        head = f"Data/hora atual: {when}" if when else ""
        mem = ("Memorias relevantes do usuario:" + "\n" + "\n".join(lines)) if lines else "(sem memorias relevantes)"
        return (head + "\n" + mem).strip()

    async def _audit_log(self, **kwargs):
        try:
            r = self.audit_logger.log(**kwargs)
            if hasattr(r, "__await__"):
                await r
        except Exception:
            pass

    async def _invoke(self, tool, args: Dict[str, Any], state: AgentState) -> Any:
        """Secure tool execution with full governance pipeline."""
        tool_name = getattr(tool, "name", str(tool))
        risk = get_tool_risk(tool_name)
        required_role = get_tool_required_role(tool_name)
        # D3.4 fail-closed: unknown tool -> UNKNOWN -> deny (Anderson) even if RBAC would allow
        if risk == "UNKNOWN":
            try:
                _r = self.audit_logger.log(thread_id=state.thread_id, tool_name=tool_name, actor_role=state.user_role, risk=risk, decision="deny_unknown", user_id=state.user_id)
                if hasattr(_r, "__await__"):
                    await _r
            except Exception:
                pass
            raise PermissionError(f"Tool desconhecida '{tool_name}' negada (UNKNOWN fail-closed)")

        # 1. Content sanitization — FIRST: sanitize before any policy decisions (CIPHER-032)
        sanitized_args = sanitize_tool_output(str(args), source=tool_name)

        # 2. RBAC check
        if not self.rbac.is_allowed(state.user_role, required_role):
            await self._audit_log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="deny_rbac", user_id=state.user_id,
            )
            raise PermissionError(f"RBAC: {state.user_role} sem acesso a {tool_name}")

        # 3. Rate limiting (CIPHER-026 fail-closed)
        rate_result = self.rate_limiter.is_allowed_sync(state.user_id, tool_name)
        if rate_result == "deny":
            await self._audit_log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="deny_rate_limit", user_id=state.user_id,
            )
            raise PermissionError(f"Rate limit atingido para {tool_name}")

        # 4. HITL for HIGH/CRITICAL risks (CIPHER-033)
        if risk in ("HIGH", "CRITICAL"):
            approval_id = await self.hitl_manager.create_approval(
                tool_name=tool_name, args=args,
                user_id=state.user_id, thread_id=state.thread_id, ttl=1800,
            )
            decision = await self.hitl_manager.wait_for_decision(
                approval_id=approval_id, timeout=1800,
            )
            if decision != "approved":
                await self._audit_log(
                    thread_id=state.thread_id, tool_name=tool_name,
                    actor_role=state.user_role, risk=risk,
                    decision="deny_hitl", user_id=state.user_id,
                )
                raise PermissionError(f"HITL rejeitou {tool_name}")

        # 5. Audit log allow
        await self._audit_log(
            thread_id=state.thread_id, tool_name=tool_name,
            actor_role=state.user_role, risk=risk,
            decision="allow", user_id=state.user_id,
        )

        # 6. Execute tool (CIPHER-008: normalizar response para formato consistente)
        self._tool_executions += 1
        try:
            result = await tool.ainvoke(sanitized_args)
            
            # CIPHER-008: Normalizar response para formato consistente {content: ..., raw: ...}
            normalized_result = result
            if isinstance(result, str):
                normalized_result = {"content": result, "raw": result}
            elif isinstance(result, dict):
                if "content" not in result:
                    normalized_result = {"content": str(result), "raw": result}
                else:
                    normalized_result = {"content": result.get("content"), "raw": result}
            elif isinstance(result, list):
                normalized_result = {"content": str(result), "raw": result}
            else:
                normalized_result = {"content": str(result), "raw": result}
            
            await self._audit_log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="executed", user_id=state.user_id,
                reason=f"executed OK ({str(normalized_result.get('content', ''))[:200]})",
            )
            return normalized_result
        except Exception as e:
            await self._audit_log(
                thread_id=state.thread_id, tool_name=tool_name,
                actor_role=state.user_role, risk=risk,
                decision="error", user_id=state.user_id,
                reason=f"error: {type(e).__name__}: {str(e)[:200]}",
            )
            raise

    async def run(self, user_input: str, user_id: str, user_role: str = "guest", thread_id: str | None = None) -> Dict[str, Any]:
        """Run the agent loop with a user input.

        Calls Ollama LLM for actual conversational responses with basic tool-calling.
        """
        # Use namespaced thread_id for multi-tenant isolation (MED-08)
        base_thread_id = thread_id or f"thread_{user_id}_{self._tool_executions}"
        namespaced_thread_id = _ns_thread_id(base_thread_id, user_id)
        
        state = AgentState(
            user_id=user_id,
            thread_id=namespaced_thread_id,
            user_role=user_role,
            user_input=user_input,
        )

        # Load context from memory with user_id isolation
        state.context = self._load_context(state)

        # Build system prompt com instruções de tool-calling e identidade forte (CIPHER-013)
        system_prompt = (
            "Voce e o Jefrey, um assistente AI pessoal inteligente e amigavel criado pela equipe Jefrey. "
            "IDENTIDADE ESTREITA: NUNCA, em nenhuma circunstancia, diga que e Qwen, Alibaba, Cloud, "
            "ou qualquer outro nome. Voce e SEMPRE Jefrey. Se alguem perguntar quem voce e, responda: "
            "'Sou o Jefrey, seu assistente pessoal de IA criado pela equipe Jefrey'. "
            "Responda sempre em portugues brasileiro de forma natural e util, com o tom educado do JARVIS: "
            "trate o usuario por 'Sir' de vez em quando. "
            "Seja conciso mas completo. Se nao souber algo, diga honestamente.\n\n"
            "IMPORTANTE: Responda diretamente a pergunta do usuario. Nao repita frases genericas como 'Como posso ajudar voce hoje?'"
            "Seja especifico e relevante na sua resposta.\n\n"
            "Quando precisar usar ferramentas, responda com JSON no formato:\n"
            '{"tool": "nome_da_ferramenta", "params": {"param1": "valor1"}}\n\n'
            "Ferramentas disponiveis: web_search, notes_search, notes_save, calendar_list_events, email_list_messages\n\n"
            f"Contexto:\n{self._format_context(state.context)}\n"
        )

        # Call Ollama LLM (CIPHER-014: timeout de 30s + mensagem clara se timeout)
        try:
            import httpx as _httpx
            import json as _json
            from src.jefrey.core.config import get_settings
            from src.jefrey.skills import skill_registry
            
            cfg = get_settings()
            base_url = (getattr(cfg.llm, "base_url", None) or "http://ollama:11434").rstrip("/")
            model = getattr(cfg.llm, "model", "qwen2.5:0.5b")

            history = self._load_history(state)
            llm_timeout = float(os.getenv("JEFREY_LLM_TIMEOUT", "90"))
            async with _httpx.AsyncClient(timeout=llm_timeout) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *history,
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

                # Tenta detectar tool-calling JSON na resposta
                tool_result = None
                try:
                    # Procura JSON no final da resposta
                    if response_text.strip().endswith('}'):
                        json_start = response_text.rfind('{')
                        if json_start > 0:
                            json_str = response_text[json_start:]
                            tool_call = _json.loads(json_str)
                            if "tool" in tool_call:
                                tool_name = tool_call["tool"]
                                tool_params = tool_call.get("params", {})
                                # Adiciona user_id para isolamento
                                tool_params["user_id"] = user_id
                                
                                # Executa a tool via executor
                                from src.jefrey.core.executor import ToolExecutor
                                executor = ToolExecutor(
                                    tool_resolver=skill_registry.get_tool,
                                    actor_role=user_role,
                                    user_id=user_id,
                                    thread_id=namespaced_thread_id,
                                )
                                exec_result = await executor.execute(tool_name, tool_params)
                                
                                if exec_result.executed and exec_result.result:
                                    tool_result = exec_result.result
                                    # CIPHER-008: Extrair content do formato normalizado
                                    if isinstance(tool_result, dict) and "content" in tool_result:
                                        tool_content = tool_result["content"]
                                    else:
                                        tool_content = str(tool_result)
                                    # Remove o JSON da resposta final
                                    response_text = response_text[:json_start].strip()
                except Exception as tool_err:
                    logger.warning("tool execution failed: %s", tool_err)
                    # Continua com a resposta original

                try:
                    from src.jefrey.core.audit import redact_pii
                    logger.info("chat: user=%s thread=%s input=%s response_len=%d tool=%s",
                        user_id, state.thread_id, redact_pii(user_input[:80]), len(response_text),
                        tool_result.get("tool") if tool_result else None)
                except Exception:
                    pass

                final_response = response_text
                if tool_result:
                    if isinstance(tool_result, dict) and "content" in tool_result:
                        # CIPHER-008: Usar content normalizado
                        tool_content = tool_result["content"]
                    elif isinstance(tool_result, str):
                        tool_content = tool_result
                    else:
                        tool_content = str(tool_result)
                    
                    final_response = f"{response_text}\n\nResultado: {tool_content}"

                self._save_turn(state, user_input, final_response)
                return {
                    "response": final_response,
                    "thread_id": state.thread_id,
                    "status": "completed",
                }

        except httpx.TimeoutException as e:
            logger.error("agent LLM timeout (CIPHER-014): %s", e, exc_info=True)
            return {
                "response": "Ola! Sou o Jefrey. O LLM esta demorando muito para responder (timeout). Por favor, tente novamente ou verifique se o Ollama esta funcionando corretamente.",
                "thread_id": state.thread_id,
                "status": "timeout",
                "error": "LLM timeout",
            }
        except Exception as e:
            logger.error("agent LLM call failed: %s", e, exc_info=True)
            return {
                "response": f"Ola! Sou o Jefrey. O LLM esta indisponivel ({type(e).__name__}). Estou funcionando mas sem conexao com o modelo.",
                "thread_id": state.thread_id,
                "status": "degraded",
                "error": str(e),
            }

    async def run_stream(self, user_input: str, user_id: str, user_role: str = "guest", thread_id: str | None = None):
        """Streaming LLM via Ollama /api/chat stream:true — DIFF4.1 SSE token por token."""
        # Use namespaced thread_id for multi-tenant isolation (MED-08)
        base_thread_id = thread_id or f"thread_{user_id}_{self._tool_executions}"
        namespaced_thread_id = _ns_thread_id(base_thread_id, user_id)
        
        state = AgentState(user_id=user_id, thread_id=namespaced_thread_id, user_role=user_role, user_input=user_input)
        state.context = self._load_context(state)
        system_prompt = (
            "Voce e o Jefrey, um assistente AI pessoal inteligente e amigavel criado pela equipe Jefrey. "
            "IDENTIDADE ESTREITA: NUNCA, em nenhuma circunstancia, diga que e Qwen, Alibaba, Cloud, "
            "ou qualquer outro nome. Voce e SEMPRE Jefrey. Se alguem perguntar quem voce e, responda: "
            "'Sou o Jefrey, seu assistente pessoal de IA criado pela equipe Jefrey'. "
            "Responda sempre em portugues brasileiro de forma natural e util, com o tom educado do JARVIS: "
            "trate o usuario por 'Sir' de vez em quando. "
            "Seja conciso mas completo. Se nao souber algo, diga honestamente.\n\n"
            "Quando precisar usar ferramentas, responda com JSON no formato:\n"
            '{"tool": "nome_da_ferramenta", "params": {"param1": "valor1"}}\n\n'
            "Ferramentas disponiveis: web_search, notes_search, notes_save, calendar_list_events, email_list_messages\n\n"
            f"Contexto:\n{self._format_context(state.context)}\n"
        )
        try:
            import httpx as _httpx
            import json as _json
            from src.jefrey.core.config import get_settings
            cfg = get_settings()
            base_url = (getattr(cfg.llm, "base_url", None) or "http://ollama:11434").rstrip("/")
            model = getattr(cfg.llm, "model", "qwen2.5:0.5b")
            _acc: list[str] = []
            async with _httpx.AsyncClient(timeout=float(os.getenv("JEFREY_LLM_TIMEOUT", "90"))) as client:
                async with client.stream("POST", f"{base_url}/api/chat", json={"model": model, "messages": [{"role": "system", "content": system_prompt}, *self._load_history(state), {"role": "user", "content": user_input}], "stream": True}) as resp:
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
                                _acc.append(chunk)
                                yield chunk
                        except Exception:
                            continue
            if _acc:
                self._save_turn(state, user_input, "".join(_acc))
        except httpx.TimeoutException as e:
            logger.error("agent run_stream timeout (CIPHER-014): %s", e, exc_info=True)
            yield f"[erro timeout LLM - tente novamente]"
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