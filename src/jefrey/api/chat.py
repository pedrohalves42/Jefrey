"""REST API para chat assÃ­ncrono com o agente (Fase P5).

Endpoints:
  POST /chat                    -> Inicia/envia mensagem para o agente (com content_guard)
  POST /chat/resume/{thread_id} -> Continua execuÃ§Ã£o suspensa por HITL pendente
  GET  /chat/status/{thread_id} -> Consulta status atual de execuÃ§Ã£o de uma thread

SECURITY (P6-pre): Todos os endpoints extraem user_id do request.state (via middleware)
para isolamento multi-tenant em memÃ³ria e aprovaÃ§Ãµes.
"""
from __future__ import annotations

import asyncio
import logging
import json
import time
from typing import Any, Dict

import re as _re
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.jefrey.core.agent import JefreyAgent
from src.jefrey.core.content_guard import sanitize_tool_output
from src.jefrey.core.audit import redact_pii
from src.jefrey.brain2.queue import get_brain2_queue
from src.jefrey.core.hitl import ApprovalManager

logger = logging.getLogger(__name__)
def _brain2_enqueue_fire_and_forget(user_id: str, thread_id: str, user_input: str, response: str):
    try:
        q = get_brain2_queue()
        mid = q.enqueue(user_id=user_id, thread_id=thread_id, user_input=user_input, response=response, meta={"source": "chat"})
        logger.info("brain2 enqueue ok user=%s thread=%s id=%s", user_id, thread_id, mid)
    except Exception as e:
        logger.warning("brain2 enqueue failed (non-critical): %s", e, exc_info=True)


router = APIRouter(prefix="/chat", tags=["chat"])

# Armazena tarefas do agente em execuÃ§Ã£o ativa
_RUNNING_TASKS: Dict[str, asyncio.Task] = {}

# P5-FIX-2: Timestamp do Ãºltimo cleanup de tasks mortas
_last_cleanup: float = 0.0
_CLEANUP_INTERVAL: float = 10.0  # Limpa a cada 10s (reduzido de 60s para evitar task accumulation)

async def _cleanup_stale_tasks():
    """Remove tasks que terminaram mas ficaram no dict (pÃ³s-restart ou crash parcial)."""
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    stale = [tid for tid, t in _RUNNING_TASKS.items() if t.done()]
    for tid in stale:
        _RUNNING_TASKS.pop(tid, None)
        logger.info("chat: task stale removida no cleanup: thread=%s", tid)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="Mensagem do usuÃ¡rio (1-10000 chars)")
    thread_id: str = Field(
        default="default",
        pattern=r'^[a-zA-Z0-9_\-]{1,128}$',
        description="ID da thread (alfanumÃ©rico, 1-128 chars)",
    )

@router.post("")
async def chat(request: Request, req: ChatRequest):
    """Envia mensagem ao agente Jefrey.

    Aplica content_guard para mitigar prompt injection. Se o agente atingir uma
    ferramenta de alto risco (HIGH/CRITICAL), ele cria um approval e o endpoint
    retorna imediatamente com status 'pending_approval' (modo assÃ­ncrono).

    SECURITY: user_id extraÃ­do do request.state (middleware) para isolamento multi-tenant.
    """
    # P5-FIX-2: Limpa tasks mortas periodicamente
    await _cleanup_stale_tasks()

    # SECURITY: extrai user_id do middleware
    user_id = getattr(request.state, "user_id", "anonymous")
    thread_id = req.thread_id
    message = req.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Mensagem nÃ£o pode ser vazia")

    # --- CONTENT GUARD (MitigaÃ§Ã£o de Prompt Injection) ---
    sanitized = sanitize_tool_output(message, source="user_input")
    if "[CONTEÃšDO BLOQUEADO" in sanitized:
        logger.warning(
            "chat: input bloqueado pelo content_guard para thread=%s user=%s. Original=%s",
            thread_id, user_id, redact_pii(message[:100]),
        )
        raise HTTPException(
            status_code=400,
            detail="Mensagem bloqueada por regras de seguranÃ§a (prompt de entrada suspeito)",
        )

    # Verifica se jÃ¡ hÃ¡ uma tarefa ativa rodando nesta thread (composto por user+thread)
    task_key = f"{user_id}:{thread_id}"
    # Cleanup stale done task before new run (allows poll complete -> idle transition properly)
    if task_key in _RUNNING_TASKS and _RUNNING_TASKS[task_key].done():
        _RUNNING_TASKS.pop(task_key, None)
    if task_key in _RUNNING_TASKS and not _RUNNING_TASKS[task_key].done():
        # Retorna status running para evitar execuÃ§Ãµes concorrentes na mesma thread
        return {
            "status": "running",
            "thread_id": thread_id,
            "message": "Agente jÃ¡ estÃ¡ executando nesta thread.",
        }

    agent = JefreyAgent()

    async def _run_agent_task():
        try:
            return await agent.run(sanitized, user_id=user_id)
        except Exception as e:
            logger.error(f"chat: falha na execuÃ§Ã£o do agente (thread_id={thread_id} user={user_id}): {e}", exc_info=True)
            raise e
        # NOTE: don't pop here â€” keep task in _RUNNING_TASKS so GET /status can return complete
        # Cleanup is handled by _cleanup_stale_tasks after _CLEANUP_INTERVAL (60s) or explicit pop on next POST

    task = asyncio.create_task(_run_agent_task())
    _RUNNING_TASKS[task_key] = task

    # Polling inicial de atÃ© 5.0 segundos para responder rÃ¡pido se terminar ou se for para HITL
    start_time = time.monotonic()
    while time.monotonic() - start_time < 5.0:
        if task.done():
            try:
                result = task.result()
                # agent.run() returns dict with 'response' key
                response_text = result.get('response', str(result)) if isinstance(result, dict) else str(result)
                _brain2_enqueue_fire_and_forget(user_id, thread_id, sanitized, response_text)
                return {
                    'status': 'complete',
                    'response': response_text,
                    'thread_id': thread_id,
                }
            except Exception as e:
                logger.error("chat: erro na execuÃ§Ã£o (thread=%s): %s", thread_id, e, exc_info=True)
                raise HTTPException(status_code=500, detail="Erro interno na execuÃ§Ã£o. Tente novamente.")

        # Se houver qualquer aprovaÃ§Ã£o pendente no banco para esta thread, retorna imediatamente
        pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
        if pending:
            return {
                "status": "pending_approval",
                "approval_id": pending[0]["id"],
                "thread_id": thread_id,
                "message": f"Aguardando aprovaÃ§Ã£o humana para ferramenta '{pending[0]['tool_name']}'",
            }

        await asyncio.sleep(0.2)

    # Se ainda estiver rodando apÃ³s 5 segundos, retorna 'running' para que o cliente faÃ§a polling
    return {
        "status": "running",
        "thread_id": thread_id,
        "message": "ExecuÃ§Ã£o longa iniciada. Consulte o status ou aguarde notificaÃ§Ãµes.",
    }


@router.post("/stream")
async def chat_stream(request: Request, req: ChatRequest):
    """POST /chat/stream â€” SSE token por token via Ollama stream:true (DIFF4.1).
    
    Retorna text/event-stream com eventos JSON:
      data: {"type":"token","content":"..."}
      data: {"type":"done","thread_id":"..."}
      data: {"type":"pending_approval"} quando HITL pendente
    Mantem POST /chat classico intacto para compat.
    """
    user_id = getattr(request.state, "user_id", "anonymous")
    thread_id = req.thread_id
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensagem nao pode ser vazia")
    sanitized = sanitize_tool_output(message, source="user_input")
    if "[CONTE" in sanitized and "BLOQUEADO" in sanitized:
        raise HTTPException(status_code=400, detail="Mensagem bloqueada por regras de seguranca")
    pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
    if pending:
        async def pending_gen():
            yield f"data: {json.dumps({"type": "pending_approval", "approval_id": pending[0]["id"], "thread_id": thread_id}, ensure_ascii=False)}\n\n"
        return StreamingResponse(pending_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    agent = JefreyAgent()
    async def event_gen():
        full = ""
        try:
            async for chunk in agent.run_stream(sanitized, user_id=user_id):
                full += chunk
                yield f"data: {json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)}\n\n"
            _brain2_enqueue_fire_and_forget(user_id, thread_id, sanitized, full)
            yield f"data: {json.dumps({"type": "done", "thread_id": thread_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("chat/stream event_gen error: %s", e, exc_info=True)
            yield f"data: {json.dumps({"type": "error", "message": str(e)[:200]}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

@router.post("/resume/{thread_id}")
async def resume_chat(request: Request, thread_id: str):
    """Resume a execuÃ§Ã£o de uma thread suspensa apÃ³s a aprovaÃ§Ã£o humana de uma ferramenta.

    P5-FIX-1: Verifica approval pendente no DB antes de decidir a aÃ§Ã£o.
    NÃ£o recria task com input vazio â€” retorna idle ou pending_approval.

    SECURITY: user_id extraÃ­do do request.state para isolamento multi-tenant.
    """
    # SECURITY: extrai user_id do middleware
    user_id = getattr(request.state, "user_id", "anonymous")
    # CIPHER-113: rate-limit leve para status polling (evita oracle de thread_id enumeravel) - P2
    try:
        from src.jefrey.core.rate_limit import get_rate_limiter
        if get_rate_limiter().is_allowed_sync(user_id or "anon", "chat_status", rate=60) == "deny":
            raise HTTPException(status_code=429, detail="rate limited: tente novamente em alguns segundos")
    except HTTPException:
        raise
    except Exception:
        pass  # fail-open se Redis down -> nao quebra GET
    task_key = f"{user_id}:{thread_id}"
    task = _RUNNING_TASKS.get(task_key)

    # Se hÃ¡ task ativa em memÃ³ria, aguarda resultado
    if task and not task.done():
        start_time = time.monotonic()
        while time.monotonic() - start_time < 8.0:
            if task.done():
                try:
                    response = task.result()
                    return {
                        "status": "complete",
                        "response": response,
                        "thread_id": thread_id,
                    }
                except Exception as e:
                    logger.error("chat: erro na retomada (thread=%s): %s", thread_id, e, exc_info=True)
                    raise HTTPException(status_code=500, detail="Erro interno na retomada. Tente novamente.")

            pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
            if pending:
                return {
                    "status": "pending_approval",
                    "approval_id": pending[0]["id"],
                    "thread_id": thread_id,
                }
            await asyncio.sleep(0.2)
        return {
            "status": "running",
            "thread_id": thread_id,
            "message": "A tarefa continua rodando em background apÃ³s a aprovaÃ§Ã£o.",
        }

    # Se a task jÃ¡ terminou, retorna o resultado
    if task and task.done():
        try:
            response = task.result()
            return {
                "status": "complete",
                "response": response,
                "thread_id": thread_id,
            }
        except Exception as e:
            logger.error("chat: erro na task finalizada (thread=%s): %s", thread_id, e, exc_info=True)
            return {
                "status": "error",
                "error": "Erro interno na execuÃ§Ã£o da tarefa.",
                "thread_id": thread_id,
            }

    # Se nÃ£o hÃ¡ task ativa (servidor reiniciou ou nunca existiu task), verifica DB
    pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
    if pending:
        # Ainda hÃ¡ aprovaÃ§Ã£o pendente â€” orienta o cliente a decidir primeiro
        return {
            "status": "pending_approval",
            "approval_id": pending[0]["id"],
            "thread_id": thread_id,
            "message": (
                f"AprovaÃ§Ã£o '{pending[0]['id']}' ainda pendente para "
                f"ferramenta '{pending[0]['tool_name']}'. "
                f"Decida via POST /approvals/{pending[0]['id']}/decide antes de resumir."
            ),
        }

    # Sem task ativa e sem approval pendente â€” thread estÃ¡ ociosa
    return {
        "status": "idle",
        "thread_id": thread_id,
        "message": (
            "Nenhuma tarefa ativa e nenhuma aprovaÃ§Ã£o pendente nesta thread. "
            "Envie uma nova mensagem via POST /chat para continuar a conversa."
        ),
    }

@router.get("/status/{thread_id}")
async def get_chat_status(request: Request, thread_id: str):
    """Consulta o status de execuÃ§Ã£o de uma thread.

    SECURITY: user_id extraÃ­do do request.state para isolamento multi-tenant.
    """
    # SECURITY: extrai user_id do middleware
    user_id = getattr(request.state, "user_id", "anonymous")
    task_key = f"{user_id}:{thread_id}"
    task = _RUNNING_TASKS.get(task_key)
    if task:
        if task.done():
            try:
                res = task.result()
                return {
                    "status": "complete",
                    "response": res,
                    "thread_id": thread_id,
                }
            except Exception as e:
                logger.error("chat: erro ao obter resultado da task (thread=%s): %s", thread_id, e, exc_info=True)
                return {
                    "status": "error",
                    "error": "Erro interno ao obter resultado.",
                    "thread_id": thread_id,
                }
        pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
        if pending:
            return {
                "status": "pending_approval",
                "approval_id": pending[0]["id"],
                "thread_id": thread_id,
            }
        return {"status": "running", "thread_id": thread_id}
    else:
        pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
        if pending:
            return {
                "status": "pending_approval",
                "approval_id": pending[0]["id"],
                "thread_id": thread_id,
            }
        return {
            "status": "idle",
            "thread_id": thread_id,
            "message": "Nenhuma tarefa ativa sendo executada nesta thread no momento.",
        }
