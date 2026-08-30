"""REST API para chat assíncrono com o agente (Fase P5).

Endpoints:
  POST /chat                    -> Inicia/envia mensagem para o agente (com content_guard)
  POST /chat/resume/{thread_id} -> Continua execução suspensa por HITL pendente
  GET  /chat/status/{thread_id} -> Consulta status atual de execução de uma thread
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from src.jefrey.core.agent import JefreyAgent
from src.jefrey.core.content_guard import sanitize_tool_output
from src.jefrey.core.hitl import ApprovalManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Armazena tarefas do agente em execução ativa
_RUNNING_TASKS: Dict[str, asyncio.Task] = {}

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

@router.post("")
async def chat(req: ChatRequest):
    """Envia mensagem ao agente Jefrey.

    Aplica content_guard para mitigar prompt injection. Se o agente atingir uma
    ferramenta de alto risco (HIGH/CRITICAL), ele cria um approval e o endpoint
    retorna imediatamente com status 'pending_approval' (modo assíncrono).
    """
    thread_id = req.thread_id
    message = req.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Mensagem não pode ser vazia")

    # --- CONTENT GUARD (Mitigação de Prompt Injection) ---
    sanitized = sanitize_tool_output(message, source="user_input")
    if "[CONTEÚDO BLOQUEADO" in sanitized:
        logger.warning(
            "chat: input bloqueado pelo content_guard para thread=%s. Original=%s",
            thread_id, message[:100],
        )
        raise HTTPException(
            status_code=400,
            detail="Mensagem bloqueada por regras de segurança (prompt de entrada suspeito)",
        )

    # Verifica se já há uma tarefa ativa rodando nesta thread
    if thread_id in _RUNNING_TASKS and not _RUNNING_TASKS[thread_id].done():
        # Retorna status running para evitar execuções concorrentes na mesma thread
        return {
            "status": "running",
            "thread_id": thread_id,
            "message": "Agente já está executando nesta thread.",
        }

    agent = JefreyAgent()

    async def _run_agent_task():
        try:
            return await agent.run(sanitized, thread_id)
        except Exception as e:
            logger.error(f"chat: falha na execução do agente (thread_id={thread_id}): {e}", exc_info=True)
            raise e
        finally:
            _RUNNING_TASKS.pop(thread_id, None)

    task = asyncio.create_task(_run_agent_task())
    _RUNNING_TASKS[thread_id] = task

    # Polling inicial de até 5.0 segundos para responder rápido se terminar ou se for para HITL
    start_time = time.monotonic()
    while time.monotonic() - start_time < 5.0:
        if task.done():
            try:
                response = task.result()
                return {
                    "status": "complete",
                    "response": response,
                    "thread_id": thread_id,
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erro na execução: {e}")

        # Se houver qualquer aprovação pendente no banco para esta thread, retorna imediatamente
        pending = ApprovalManager().get_pending(thread_id)
        if pending:
            return {
                "status": "pending_approval",
                "approval_id": pending[0]["id"],
                "thread_id": thread_id,
                "message": f"Aguardando aprovação humana para ferramenta '{pending[0]['tool_name']}'",
            }

        await asyncio.sleep(0.2)

    # Se ainda estiver rodando após 5 segundos, retorna 'running' para que o cliente faça polling
    return {
        "status": "running",
        "thread_id": thread_id,
        "message": "Execução longa iniciada. Consulte o status ou aguarde notificações.",
    }

@router.post("/resume/{thread_id}")
async def resume_chat(thread_id: str):
    """Resume a execução de uma thread suspensa após a aprovação humana de uma ferramenta."""
    task = _RUNNING_TASKS.get(thread_id)

    if task and not task.done():
        # A tarefa já está rodando em background (provavelmente fazendo polling no DB).
        # Vamos apenas aguardar um pouco para retornar o resultado se estiver concluído.
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
                    raise HTTPException(status_code=500, detail=f"Erro na retomada: {e}")

            # Se ainda houver outra aprovação pendente subsequente
            pending = ApprovalManager().get_pending(thread_id)
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
            "message": "A tarefa continua rodando em background após a aprovação.",
        }

    # Se não houver tarefa ativa em memória (ex.: reinício do servidor), recria rodando com input vazio
    # para que o LangGraph recupere o último checkpoint da thread e retome.
    agent = JefreyAgent()

    async def _resume_agent_task():
        try:
            return await agent.run("", thread_id)
        except Exception as e:
            logger.error(f"chat: falha ao resumir thread_id={thread_id}: {e}", exc_info=True)
            raise e
        finally:
            _RUNNING_TASKS.pop(thread_id, None)

    task = asyncio.create_task(_resume_agent_task())
    _RUNNING_TASKS[thread_id] = task

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
                raise HTTPException(status_code=500, detail=f"Erro na retomada do checkpoint: {e}")

        pending = ApprovalManager().get_pending(thread_id)
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
        "message": "Thread retomada a partir do checkpoint. Executando em background.",
    }

@router.get("/status/{thread_id}")
async def get_chat_status(thread_id: str):
    """Consulta o status de execução de uma thread."""
    task = _RUNNING_TASKS.get(thread_id)
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
                return {
                    "status": "error",
                    "error": str(e),
                    "thread_id": thread_id,
                }
        pending = ApprovalManager().get_pending(thread_id)
        if pending:
            return {
                "status": "pending_approval",
                "approval_id": pending[0]["id"],
                "thread_id": thread_id,
            }
        return {"status": "running", "thread_id": thread_id}
    else:
        pending = ApprovalManager().get_pending(thread_id)
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
