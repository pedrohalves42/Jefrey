"""REST HITL -- aprovacoes (P4, Decisao 2 -- Opcao A) + CIPHER-019/020/024.

Endpoints (Starlette -- sem dependencia de FastAPI):
  GET  /approvals/pending        -> lista pendencias (?thread_id= opcional). RESPOSTA OMITE
                                     arguments_json (CIPHER-020) para nao vazar PII de HIGH tools.
  POST /approvals/{id}/decide     -> body {"decision": "approved"|"rejected", "decided_by": "..."}

CIPHER-019: todos os endpoints exigem Bearer token (JEFREY_API__SECRET_KEY) validado em
middleware Starlette ANTES de qualquer rota. Sem token valido -> 401. Se o secret nao esta
configurado, nenhum token e valido -> o endpoint recusa TUDO (nunca sobe sem autenticacao).

SECURITY (P6-pre): Multi-tenant isolation via user_id.
- /approvals/pending filtra por X-User-Id (so retorna approvals do usuario)
- /approvals/{id}/decide verifica ownership (so o dono pode decidir)

O agent loop faz polling via ApprovalManager.wait_for_decision(); este endpoint e a
interface pela qual o humano (ou o n8n em P5) decide. Opcao B (webhook n8n) fica para P5.
"""
from __future__ import annotations

import hmac
import logging
import uuid

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.jefrey.core.config import get_settings
from src.jefrey.core.hitl import ApprovalManager

logger = logging.getLogger(__name__)

# Campos expostos em /approvals/pending (CIPHER-020: NAO inclui arguments_json).
_PENDING_FIELDS = (
    "id", "user_id", "thread_id", "tool_name", "risk_level", "reason",
    "status", "created_by", "created_at", "expires_at",
)

# DEFAULT para requests sem X-User-Id (compatibilidade com clientes legados)
_DEFAULT_USER = "anonymous"

class _UserContextMiddleware(BaseHTTPMiddleware):
    """Extrai user_id do header X-User-Id e injeta no request.state.

    SECURITY: NAO valida user_id no server-side -- a validacao de identidade
    vem do Bearer token (CIPHER-019). O X-User-Id apenas indica QUAL usuario
    esta fazendo a request para isolamento multi-tenant.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user_id = request.headers.get("X-User-Id", _DEFAULT_USER)
        return await call_next(request)

class _AuthMiddleware(BaseHTTPMiddleware):
    """CIPHER-019: exige Bearer token em TODAS as rotas do app de aprovacoes."""

    async def dispatch(self, request, call_next):
        secret = get_settings().api.secret_key
        auth = request.headers.get("Authorization", "")
        # SECURITY (CIPHER-003): comparacao timing-safe para evitar timing attack
        expected = f"Bearer {secret}"
        if secret and hmac.compare_digest(auth, expected):
            return await call_next(request)
        # Sem token valido -> 401. Se secret vazio, nenhum token casa -> recusa total
        # (o endpoint de aprovacao NUNCA fica sem autenticacao em producao).
        logger.warning("approvals: request sem token Bearer valido -> 401 (path=%s)", request.url.path)
        return JSONResponse({"ok": False, "error": "nao autorizado"}, status_code=401)

async def list_pending(request):
    thread_id = request.query_params.get("thread_id")
    # SECURITY: filtra por user_id do request (multi-tenant isolation)
    user_id = getattr(request.state, "user_id", _DEFAULT_USER)
    rows = ApprovalManager().get_pending(thread_id, user_id=user_id)
    # CIPHER-020: filtra campos sensiveis (PII) da resposta da listagem.
    summary = [{k: r.get(k) for k in _PENDING_FIELDS if k in r} for r in rows]
    return JSONResponse({"pending": summary, "count": len(summary)})

async def decide(request):
    approval_id = request.path_params["id"]
    # CIPHER-024: uuid invalido -> 400 (nao 500). Validado ANTES de tocar o banco.
    try:
        uuid.UUID(approval_id)
    except (ValueError, AttributeError):
        return JSONResponse({"ok": False, "error": "approval_id invalido"}, status_code=400)
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
    # SECURITY: ownership check -- passa user_id para validacao
    user_id = getattr(request.state, "user_id", _DEFAULT_USER)
    # CIPHER-111: trilha de auto-approval HIGH/CRITICAL (single-tenant OK; multi-tenant exigiria RBAC ADMIN)
    try:
        _row = ApprovalManager().get(approval_id)  # type: ignore[attr-defined]
        if _row is not None:
            _risk = getattr(_row, "risk_level", None) or (isinstance(_row, dict) and _row.get("risk_level"))
            if _risk in ("high", "critical"):
                logger.warning("CIPHER-111: auto-approval %s risk=%s by user_id=%s (review RBAC)", approval_id, _risk, user_id)
    except Exception:
        pass
    ok = ApprovalManager().decide(approval_id, decision, decided_by, user_id=user_id)
    if not ok:
        return JSONResponse(
            {"ok": False, "error": "approval nao encontrado, ja decidido, ou sem permissao"},
            status_code=404,
        )
    return JSONResponse({"ok": True, "id": approval_id, "decision": decision})

def build_approvals_app() -> Starlette:
    """Monta a sub-aplicacao Starlette de aprovacoes HITL.

    Rotas RELATIVAS ao mount point (montado em /approvals no FastAPI principal).
    Portanto as rotas finais sao /approvals/pending e /approvals/{id}/decide.
    """
    app = Starlette(routes=[
        Route("/pending", list_pending, methods=["GET"]),
        Route("/{id}/decide", decide, methods=["POST"]),
    ])
    app.add_middleware(_UserContextMiddleware)  # SECURITY: extrai user_id
    app.add_middleware(_AuthMiddleware)  # CIPHER-019
    return app
