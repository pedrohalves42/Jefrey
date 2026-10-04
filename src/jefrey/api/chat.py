"""REST API para chat assíncrono com o agente (Fase P5).



Endpoints:

  POST /chat                    -> Inicia/envia mensagem para o agente (com content_guard)

  POST /chat/resume/{thread_id} -> Continua execução suspensa por HITL pendente

  GET  /chat/status/{thread_id} -> Consulta status atual de execução de uma thread



SECURITY (P6-pre): Todos os endpoints extraem user_id do request.state (via middleware)

para isolamento multi-tenant em memória e aprovações.

"""

from __future__ import annotations



import asyncio

import logging

import json

import time

from typing import Dict




from fastapi import APIRouter, HTTPException, Request

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field



from src.jefrey.core.agent import JefreyAgent

from src.jefrey.core.content_guard import sanitize_tool_output

# CONTENT GUARD substitui padroes de prompt injection por "[BLOQUEADO]" (core/content_guard.py)

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

def _request_user(request: Request) -> str:
    """CIPHER-301: identidade vinda do middleware (dev-token JWT / token de servico).
    Sem Authorization -> "anonymous". Antes era fixo em "anonymous" para todos."""
    uid = getattr(request.state, "user_id", None)
    if not uid or uid == "system":
        return "anonymous"
    return str(uid)



# Singleton agent instance (stateless, created once)
_shared_agent = None

def _get_shared_agent() -> JefreyAgent:
    """Get or create singleton JefreyAgent instance."""
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = JefreyAgent()
    return _shared_agent



# Armazena tarefas do agente em execução ativa

_RUNNING_TASKS: Dict[str, asyncio.Task] = {}



# P5-FIX-2: Timestamp do último cleanup de tasks mortas

_last_cleanup: float = 0.0

_CLEANUP_INTERVAL: float = 10.0  # Limpa a cada 10s (reduzido de 60s para evitar task accumulation)



async def _cleanup_stale_tasks():

    """Remove tasks que terminaram mas ficaram no dict (pós-restart ou crash parcial)."""

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

    message: str = Field(..., min_length=1, max_length=10000, description="Mensagem do usuário (1-10000 chars)")

    thread_id: str = Field(

        default="default",

        pattern=r'^[a-zA-Z0-9_\-]{1,128}$',

        description="ID da thread (alfanumérico, 1-128 chars)",

    )



@router.post("")

async def chat(request: Request, req: ChatRequest):

    """Envia mensagem ao agente Jefrey.

    Modo público: usuário "anonymous" — sem autenticação obrigatória.


    Aplica content_guard para mitigar prompt injection. Se o agente atingir uma

    ferramenta de alto risco (HIGH/CRITICAL), ele cria um approval e o endpoint

    retorna imediatamente com status 'pending_approval' (modo assíncrono).



    SECURITY: user_id extraído do request.state (middleware) para isolamento multi-tenant.

    """

    # P5-FIX-2: Limpa tasks mortas periodicamente

    await _cleanup_stale_tasks()



    # Modo público: usuário sempre "anonymous" (middleware não extrai user_id para paths públicos)
    user_id = _request_user(request)

    thread_id = req.thread_id

    message = req.message.strip()



    if not message:

        raise HTTPException(status_code=400, detail="Mensagem não pode ser vazia")



    # --- CONTENT GUARD (Mitigação de Prompt Injection) ---

    sanitized = sanitize_tool_output(message, source="user_input")

    if "[BLOQUEADO]" in sanitized:  # marcador real de core/content_guard.py

        logger.warning(

            "chat: input bloqueado pelo content_guard para thread=%s user=%s. Original=%s",

            thread_id, user_id, redact_pii(message[:100]),

        )

        raise HTTPException(

            status_code=400,

            detail="Mensagem bloqueada por regras de segurança (prompt de entrada suspeito)",

        )



    # Verifica se já há uma tarefa ativa rodando nesta thread (composto por user+thread)

    task_key = f"{user_id}:{thread_id}"

    # Cleanup stale done task before new run (allows poll complete -> idle transition properly)

    if task_key in _RUNNING_TASKS and _RUNNING_TASKS[task_key].done():

        _RUNNING_TASKS.pop(task_key, None)

    if task_key in _RUNNING_TASKS and not _RUNNING_TASKS[task_key].done():

        # Retorna status running para evitar execuções concorrentes na mesma thread

        return {

            "status": "running",

            "thread_id": thread_id,

            "message": "Agente já está executando nesta thread.",

        }



    agent = JefreyAgent()



    async def _run_agent_task():

        try:

            return await agent.run(sanitized, user_id=user_id, thread_id=thread_id)

        except Exception as e:

            logger.error(f"chat: falha na execução do agente (thread_id={thread_id} user={user_id}): {e}", exc_info=True)

            raise e

        # NOTE: don't pop here — keep task in _RUNNING_TASKS so GET /status can return complete

        # Cleanup is handled by _cleanup_stale_tasks after _CLEANUP_INTERVAL (60s) or explicit pop on next POST



    task = asyncio.create_task(_run_agent_task())

    _RUNNING_TASKS[task_key] = task



    # Polling inicial de até 5.0 segundos para responder rápido se terminar ou se for para HITL

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

                logger.error("chat: erro na execução (thread=%s): %s", thread_id, e, exc_info=True)

                raise HTTPException(status_code=500, detail="Erro interno na execução. Tente novamente.")



        # Modo público: sem HITL - agente responde sozinho
        # Se houver qualquer aprovação pendente no banco para esta thread, retorna imediatamente


        await asyncio.sleep(0.2)



    # Se ainda estiver rodando após 5 segundos, retorna 'running' para que o cliente faça polling

    return {

        "status": "running",

        "thread_id": thread_id,

        "message": "Execução longa iniciada. Consulte o status ou aguarde notificações.",

    }





@router.post("/stream")

async def chat_stream(request: Request, req: ChatRequest):

    """POST /chat/stream — SSE token por token via Ollama stream:true (DIFF4.1).

    

    Retorna text/event-stream com eventos JSON:

      data: {"type":"token","content":"..."}

      data: {"type":"done","thread_id":"..."}

      data: {"type":"pending_approval"} quando HITL pendente

    Mantem POST /chat classico intacto para compat.

    """

    # Modo público: usuário sempre "anonymous" (middleware não extrai user_id para paths públicos)
    user_id = _request_user(request)

    thread_id = req.thread_id

    message = req.message.strip()

    if not message:

        raise HTTPException(status_code=400, detail="Mensagem nao pode ser vazia")

    sanitized = sanitize_tool_output(message, source="user_input")

    if "[BLOQUEADO]" in sanitized:  # CIPHER-310: antes a condicao nunca era verdadeira

        raise HTTPException(status_code=400, detail="Mensagem bloqueada por regras de seguranca")

    agent = JefreyAgent()

    def _sse(obj: dict) -> str:
        return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

    async def event_gen():
        full = ""
        try:
            async for ev in agent.run_events(sanitized, user_id=user_id, thread_id=thread_id):
                if ev.get("type") == "token":
                    full += ev.get("content", "")
                yield _sse(ev)
            _brain2_enqueue_fire_and_forget(user_id, thread_id, sanitized, full)
            yield _sse({"type": "done", "thread_id": thread_id})
        except asyncio.CancelledError:
            raise  # cliente desconectou
        except Exception as e:
            logger.error("chat/stream event_gen error: %s", e, exc_info=True)
            yield _sse({"type": "error", "message": "Algo deu errado ao responder. Tente de novo."})

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/resume/{thread_id}")

async def resume_chat(request: Request, thread_id: str):

    """Resume a execução de uma thread suspensa após a aprovação humana de uma ferramenta.



    P5-FIX-1: Verifica approval pendente no DB antes de decidir a ação.

    Não recria task com input vazio — retorna idle ou pending_approval.



    SECURITY: user_id extraído do request.state para isolamento multi-tenant.

    """

    # SECURITY: extrai user_id do middleware (modo público: sempre "anonymous")
    user_id = _request_user(request)

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



    # Se há task ativa em memória, aguarda resultado

    if task and not task.done():

        start_time = time.monotonic()

        while time.monotonic() - start_time < 8.0:

            if task.done():

                try:

                    result = task.result()
                    # Extract response text from agent result dict
                    if isinstance(result, dict):
                        response = result.get('response', str(result))
                    else:
                        response = str(result)

                    return {

                        "status": "complete",

                        "response": response,

                        "thread_id": thread_id,

                    }

                except Exception as e:

                    logger.error("chat: erro na retomada (thread=%s): %s", thread_id, e, exc_info=True)

                    raise HTTPException(status_code=500, detail="Erro interno na retomada. Tente novamente.")



            try:
                pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
            except Exception as e:
                logger.warning("get_pending failed: %s", e)
                pending = []

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



    # Se a task já terminou, retorna o resultado

    if task and task.done():

        try:

            result = task.result()
            # Extract response text from agent result dict
            if isinstance(result, dict):
                response = result.get('response', str(result))
            else:
                response = str(result)

            return {

                "status": "complete",

                "response": response,

                "thread_id": thread_id,

            }

        except Exception as e:

            logger.error("chat: erro na task finalizada (thread=%s): %s", thread_id, e, exc_info=True)

            return {

                "status": "error",

                "error": "Erro interno na execução da tarefa.",

                "thread_id": thread_id,

            }



    # Se não há task ativa (servidor reiniciou ou nunca existiu task), verifica DB

    try:
        pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
    except Exception as e:
        logger.warning("get_pending failed: %s", e)
        pending = []

    if pending:

        # Ainda há aprovação pendente — orienta o cliente a decidir primeiro

        return {

            "status": "pending_approval",

            "approval_id": pending[0]["id"],

            "thread_id": thread_id,

            "message": (

                f"Aprovação '{pending[0]['id']}' ainda pendente para "

                f"ferramenta '{pending[0]['tool_name']}'. "

                f"Decida via POST /approvals/{pending[0]['id']}/decide antes de resumir."

            ),

        }



    # Sem task ativa e sem approval pendente — thread está ociosa

    return {

        "status": "idle",

        "thread_id": thread_id,

        "message": (

            "Nenhuma tarefa ativa e nenhuma aprovação pendente nesta thread. "

            "Envie uma nova mensagem via POST /chat para continuar a conversa."

        ),

    }



@router.get("/status/{thread_id}")

async def get_chat_status(request: Request, thread_id: str):

    """Consulta o status de execução de uma thread.



    SECURITY: user_id extraído do request.state para isolamento multi-tenant.

    """

    # SECURITY: extrai user_id do middleware (modo público: sempre "anonymous")
    user_id = _request_user(request)

    task_key = f"{user_id}:{thread_id}"

    task = _RUNNING_TASKS.get(task_key)

    if task:

        if task.done():

            try:

                result = task.result()
                # Extract response text from agent result dict
                if isinstance(result, dict):
                    response = result.get('response', str(result))
                else:
                    response = str(result)

                return {

                    "status": "complete",

                    "response": response,

                    "thread_id": thread_id,

                }

            except Exception as e:

                logger.error("chat: erro ao obter resultado da task (thread=%s): %s", thread_id, e, exc_info=True)

                return {

                    "status": "error",

                    "error": "Erro interno ao obter resultado.",

                    "thread_id": thread_id,

                }

        try:
            pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
        except Exception as e:
            logger.warning("get_pending failed: %s", e)
            pending = []

        if pending:

            return {

                "status": "pending_approval",

                "approval_id": pending[0]["id"],

                "thread_id": thread_id,

            }

        return {"status": "running", "thread_id": thread_id}

    else:

        try:
            pending = ApprovalManager().get_pending(thread_id, user_id=user_id)
        except Exception as e:
            logger.warning("get_pending failed: %s", e)
            pending = []

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

