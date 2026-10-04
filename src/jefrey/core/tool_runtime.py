"""Execucao segura de ferramentas pelo agente.

Ordem (fail-closed): catalogo -> argumentos -> [aprovacao humana se risco alto] -> execucao
com tempo limite -> filtro de injecao no resultado -> auditoria e metricas.
O modelo so escolhe NOME e ARGUMENTOS; risco, aprovacao e identidade vem do servidor.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from src.jefrey.core.tool_catalog import ToolPolicy, policy_for

logger = logging.getLogger(__name__)

MAX_RESULT_CHARS = 4000
DEFAULT_TOOL_TIMEOUT = 60.0

ApprovalHook = Callable[[str, str, dict], Awaitable[None]]  # (approval_id, tool, info)


@dataclass
class ToolOutcome:
    tool: str
    status: str  # ok | error | unknown_tool | approval_rejected | approval_expired | bad_arguments
    content: str  # texto que volta para o modelo e para o usuario
    approval_id: Optional[str] = None
    risk: str = "unknown"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _hide_user_id(schema: dict) -> dict:
    """Remove user_id do esquema mostrado ao modelo: a identidade nunca vem do modelo."""
    s = json.loads(json.dumps(schema))
    s.get("properties", {}).pop("user_id", None)
    if "required" in s:
        s["required"] = [r for r in s["required"] if r != "user_id"]
    s.pop("title", None)
    return s


def tool_spec(tool: Any) -> dict:
    """Descricao neutra {name, description, parameters} de uma BaseTool."""
    schema: dict = {"type": "object", "properties": {}}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None and hasattr(args_schema, "model_json_schema"):
        schema = args_schema.model_json_schema()
    schema = _hide_user_id(schema)
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    desc = (getattr(tool, "description", "") or "").strip().split("\n")[0]
    return {"name": tool.name, "description": desc[:300], "parameters": schema}


def clean_args(tool: Any, args: Any) -> tuple[dict, Optional[str]]:
    """Mantem so argumentos que a ferramenta declara. Retorna (args, erro)."""
    if not isinstance(args, dict):
        return {}, "os argumentos precisam ser um objeto"
    allowed = set()
    required: list[str] = []
    schema = getattr(tool, "args_schema", None)
    if schema is not None and hasattr(schema, "model_json_schema"):
        js = schema.model_json_schema()
        allowed = set(js.get("properties", {}).keys())
        required = [r for r in js.get("required", []) if r != "user_id"]
    out = {k: v for k, v in args.items() if k in allowed and k != "user_id"} if allowed else {
        k: v for k, v in args.items() if k != "user_id"}
    missing = [r for r in required if r not in out]
    if missing:
        return out, "faltam argumentos obrigatorios: " + ", ".join(missing)
    return out, None


def stringify(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and isinstance(result.get("content"), str):
        return result["content"]
    if isinstance(result, dict) and isinstance(result.get("message"), str):
        return result["message"]
    if isinstance(result, list):
        if not result:
            return "Nenhum resultado encontrado."
        if all(isinstance(r, dict) and isinstance(r.get("content"), str) for r in result):
            lines = []
            for r in result:
                title = (r.get("metadata") or {}).get("title") if isinstance(r.get("metadata"), dict) else None
                sim = r.get("similarity")
                body = r["content"].strip()
                if title and body.startswith(str(title) + "\n"):  # o titulo ja foi indexado junto: nao repete
                    body = body[len(str(title)) + 1:].strip()
                head = (f"{title}: " if title and body != str(title) else "")
                tail = f" (parecido {round(sim * 100)}%)" if isinstance(sim, (int, float)) else ""
                lines.append(f"- {head}{body}{tail}")
            return "\n".join(lines)
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


@dataclass
class ToolRuntime:
    user_id: str
    thread_id: str
    resolver: Callable[[str], Any]
    on_approval: Optional[ApprovalHook] = None
    timeout: float = DEFAULT_TOOL_TIMEOUT
    approval_timeout: Optional[float] = None
    actor_role: str = "user"
    _audit: list = field(default_factory=list, repr=False)

    # ---- auditoria / metricas (nunca derrubam a execucao) ----
    def _audit_call(self, tool: str, risk: str, decision: str, reason: str = "",
                    approval_id: str | None = None, approval_decision: str | None = None) -> None:
        try:
            from src.jefrey.core.audit import audit_tool_call
            audit_tool_call(thread_id=self.thread_id, tool_name=tool, actor_role=self.actor_role, risk=risk,
                            decision=decision, reason=reason or None, approval_id=approval_id,
                            approval_decision=approval_decision, source="agent", user_id=self.user_id)
        except Exception as e:
            logger.warning("auditoria falhou (%s): %s", tool, e)

    def _blocked_metric(self, tool: str, reason: str) -> None:
        try:
            from src.jefrey.core.metrics import TOOLS_BLOCKED
            TOOLS_BLOCKED.labels(tool_name=tool if policy_for(tool) else "desconhecida", reason=reason).inc()
        except Exception:
            pass

    async def run(self, name: str, args: Any) -> ToolOutcome:
        policy: ToolPolicy | None = policy_for(name)
        if policy is None:
            self._audit_call(name, "unknown", "deny", "ferramenta fora do catalogo")
            self._blocked_metric(name, "not_in_catalog")
            return ToolOutcome(name, "unknown_tool", f"A ferramenta '{name}' nao existe ou nao e permitida.")

        tool = self.resolver(name)
        if tool is None:
            self._audit_call(name, policy.risk, "deny", "ferramenta nao carregada")
            return ToolOutcome(name, "unknown_tool", f"A ferramenta '{name}' nao esta disponivel agora.", risk=policy.risk)

        clean, err = clean_args(tool, args)
        if err:
            return ToolOutcome(name, "bad_arguments", f"Argumentos invalidos para {name}: {err}.", risk=policy.risk)

        approval_id: str | None = None
        if policy.needs_approval:
            decision, approval_id = await self._ask_human(name, policy, clean)
            if decision != "approved":
                status = "approval_expired" if decision == "expired" else "approval_rejected"
                self._audit_call(name, policy.risk, "deny", f"aprovacao {decision}", approval_id, decision)
                self._blocked_metric(name, f"approval_{decision}")
                msg = ("O usuario nao respondeu a tempo; a acao NAO foi executada."
                       if decision == "expired" else "O usuario negou a acao; ela NAO foi executada.")
                return ToolOutcome(name, status, msg, approval_id=approval_id, risk=policy.risk)
            self._audit_call(name, policy.risk, "allow", "aprovado pelo usuario", approval_id, "approved")
        else:
            self._audit_call(name, policy.risk, "allow", "risco baixo/medio")

        return await self._invoke(name, tool, clean, policy, approval_id)

    async def _ask_human(self, name: str, policy: ToolPolicy, args: dict) -> tuple[str, str | None]:
        from src.jefrey.core.hitl import ApprovalManager
        mgr = ApprovalManager()
        reason = f"{policy.label}"
        approval_id = await asyncio.to_thread(
            mgr.create, thread_id=self.thread_id, tool_name=name, arguments=args,
            risk_level=policy.risk, reason=reason, created_by="agent", user_id=self.user_id)
        if self.on_approval:
            try:
                await self.on_approval(approval_id, name, {"label": policy.label, "risk": policy.risk})
            except Exception as e:  # falha de notificacao nao pode liberar a acao
                logger.warning("on_approval falhou: %s", e)
        decision = await mgr.wait_for_decision(approval_id, timeout=self.approval_timeout)
        return decision, approval_id

    async def _invoke(self, name: str, tool: Any, args: dict, policy: ToolPolicy, approval_id: str | None) -> ToolOutcome:
        from src.jefrey.core.content_guard import sanitize_tool_output
        started = time.monotonic()
        try:
            payload = {**args, "user_id": self.user_id}  # identidade SEMPRE do servidor
            if hasattr(tool, "ainvoke"):
                result = await asyncio.wait_for(tool.ainvoke(payload), timeout=self.timeout)
            else:
                result = await asyncio.wait_for(asyncio.to_thread(tool, **payload), timeout=self.timeout)
            text = stringify(result)
        except asyncio.TimeoutError:
            logger.warning("ferramenta %s estourou %.0fs", name, self.timeout)
            return ToolOutcome(name, "error", f"A ferramenta {name} demorou demais e foi interrompida.",
                               approval_id, policy.risk)
        except Exception as e:
            logger.warning("ferramenta %s falhou: %s: %s", name, type(e).__name__, e)
            return ToolOutcome(name, "error", f"A ferramenta {name} falhou ({type(e).__name__}). "
                               "Pode ser falta de login ou configuracao.", approval_id, policy.risk)
        finally:
            try:
                from src.jefrey.core.metrics import TOOL_EXEC_LATENCY
                TOOL_EXEC_LATENCY.labels(tool_name=name).observe(time.monotonic() - started)
            except Exception:
                pass
        # resultado de ferramenta e conteudo NAO confiavel (pode vir da web): filtra injecao
        text = sanitize_tool_output(text, source=f"tool:{name}")
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n...[resultado cortado]"
        return ToolOutcome(name, "ok", text, approval_id, policy.risk)
