"""REST HITL — aprovações (P4, Decisão 2 — Opção A).

Endpoints (Starlette — sem dependência de FastAPI):
  GET  /approvals/pending        -> lista aprovações pendentes (?thread_id= opcional)
  POST /approvals/{id}/decide     -> body {"decision": "approved"|"rejected", "decided_by": "..."}

O agent loop faz polling via ApprovalManager.wait_for_decision(); este endpoint é
a interface pela qual o humano (ou o n8n em P5) decide. Opção B (webhook n8n)
fica para P5.
"""
from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.jefrey.core.hitl import ApprovalManager

logger = logging.getLogger(__name__)


async def list_pending(request):
    thread_id = request.query_params.get("thread_id")
    rows = ApprovalManager().get_pending(thread_id)
    return JSONResponse({"pending": rows, "count": len(rows)})


async def decide(request):
    approval_id = request.path_params["id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    decision = body.get("decision")
    decided_by = body.get("decided_by", "human")
    if decision not in ("approved", "rejected"):
        return JSONResponse(
            {"ok": False, "error": "decision deve ser 'approved' ou 'rejected'"},
            status_code=400,
        )
    ok = ApprovalManager().decide(approval_id, decision, decided_by)
    if not ok:
        return JSONResponse(
            {"ok": False, "error": "approval não encontrado ou já decidido"},
            status_code=404,
        )
    return JSONResponse({"ok": True, "id": approval_id, "decision": decision})


def build_approvals_app() -> Starlette:
    return Starlette(routes=[
        Route("/approvals/pending", list_pending, methods=["GET"]),
        Route("/approvals/{id}/decide", decide, methods=["POST"]),
    ])
