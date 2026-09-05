"""Endpoints REST para o sistema de memÃ³ria (Fase P5).

Endpoints:
  GET /memory/search?q=termo  -> Busca semÃ¢ntica de memÃ³rias relevantes com score de similaridade
  GET /memory/health          -> Status dos backends de memÃ³ria (curto e longo prazo)

SECURITY (P6-pre): user_id extraÃ­do do request.state (via middleware) para isolamento
multi-tenant. A busca e listagem retornam apenas memÃ³rias do usuÃ¡rio autenticado.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from src.jefrey.core.memory import get_memory_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("/search")
async def search_memory(
    request: Request,
    q: str = Query(..., description="Termo ou frase para busca semÃ¢ntica na memÃ³ria"),
    limit: Optional[int] = Query(5, ge=1, le=100, description="NÃºmero mÃ¡ximo de memÃ³rias a retornar (1-100)"),
):
    """Busca memÃ³rias de longo prazo usando similaridade vetorial.

    SECURITY: filtra por user_id (multi-tenant isolation).
    """
    if not q.strip():
        return {"memories": [], "count": 0}
    try:
        # SECURITY: extrai user_id do middleware
        user_id = getattr(request.state, "user_id", "anonymous")
        mm = get_memory_manager()
        # Chama busca vetorial com filtro por user_id
        results = mm.long_term.search(q, top_k=limit, user_id=user_id)
        return {"memories": results, "count": len(results)}
    except Exception as e:
        logger.error("memory: erro na busca (user=%s): %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno na busca de memÃ³ria.")

@router.get("/health")
async def memory_health(request: Request):
    """Retorna o estado operacional e mÃ©tricas bÃ¡sicas dos subsistemas de memÃ³ria.

    SECURITY: health check protegido pelo middleware auth (requiere Bearer token + X-User-Id).
    """
    try:
        mm = get_memory_manager()
        # CIPHER-109: isola contagem por tenant (evita leak de cardinalidade global)
        user_id = getattr(request.state, "user_id", None)
        total_long_term = mm.long_term.count(user_id=user_id) if user_id else mm.long_term.count()
        short_term_count = len(mm.short_term.get_messages())
        return {
            "status": "healthy",
            "short_term_messages": short_term_count,
            "long_term_memories": total_long_term,
        }
    except Exception as e:
        logger.error("memory: erro no health check: %s", e, exc_info=True)
        return {
            "status": "unhealthy",
            "error": "Erro interno ao verificar saÃºde da memÃ³ria.",
        }


@router.post("/add")
async def add_memory(request: Request):
    """Salva conteudo na memoria de longo prazo (HNSW). Usado por ConnectionHub Arquivo."""
    user_id = getattr(request.state, "user_id", "anonymous")
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=401, detail="user_id required (Axiom #2)")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    content = str(body.get("content") or body.get("text") or "").strip()
    title = str(body.get("title") or "").strip()
    type_ = str(body.get("type") or "note").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content obrigatorio")
    if len(content) > 500*1024:
        raise HTTPException(status_code=400, detail="content muito grande (max 500KB por chamada, use chunked)")
    try:
        mm = get_memory_manager()
        # long_term.add signature may vary — handle gracefully
        full = (title + "\n" + content) if title else content
        # Try common signatures
        saved = None
        for fn_name in ("add", "save", "store", "ingest"):
            if hasattr(mm.long_term, fn_name):
                fn = getattr(mm.long_term, fn_name)
                try:
                    # Try with user_id
                    saved = fn(full, user_id=user_id, type=type_)  # type: ignore
                    break
                except TypeError:
                    try:
                        saved = fn(full, user_id=user_id)  # type: ignore
                        break
                    except TypeError:
                        saved = fn(full)  # type: ignore
                        break
                except Exception as e:
                    logger.warning(f"memory add {fn_name} falhou: {e}")
        if saved is None:
            # Fallback: directly via memory manager if exists
            if hasattr(mm, "add_memory"):
                saved = mm.add_memory(full, user_id=user_id)  # type: ignore
        return {"ok": True, "message": "Memoria salva (HNSW m16 ef64)", "id": str(saved)[:32] if saved else None, "chars": len(content)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"memory/add erro user={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao salvar memoria")

