"""Endpoints REST para o sistema de memória (Fase P5).

Endpoints:
  GET /memory/search?q=termo  -> Busca semântica de memórias relevantes com score de similaridade
  GET /memory/health          -> Status dos backends de memória (curto e longo prazo)

SECURITY (P6-pre): user_id extraído do request.state (via middleware) para isolamento
multi-tenant. A busca e listagem retornam apenas memórias do usuário autenticado.
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
    q: str = Query(..., description="Termo ou frase para busca semântica na memória"),
    limit: Optional[int] = Query(5, description="Número máximo de memórias a retornar"),
):
    """Busca memórias de longo prazo usando similaridade vetorial.

    SECURITY: filtra por user_id (multi-tenant isolation).
    """
    if not q.strip():
        return {"memories": [], "count": 0}
    try:
        # SECURITY: extrai user_id do middleware
        user_id = getattr(request.state, "user_id", "anonymous")
        mm = get_memory_manager()
        # Chama busca vetorial com filtro por user_id
        results = mm.long_term.search(q, limit=limit, user_id=user_id)
        return {"memories": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Erro na busca de memória: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def memory_health():
    """Retorna o estado operacional e métricas básicas dos subsistemas de memória.

    SECURITY: health check é público (não filtra por user_id — métricas agregadas).
    """
    try:
        mm = get_memory_manager()
        total_long_term = mm.long_term.count()
        short_term_count = len(mm.short_term.get_messages())
        return {
            "status": "healthy",
            "short_term_messages": short_term_count,
            "long_term_memories": total_long_term,
        }
    except Exception as e:
        logger.error(f"Erro ao verificar health da memória: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
        }
