"""Endpoints REST para o sistema de memÃ³ria (Fase P5).

Endpoints:
  GET /memory/search?q=termo  -> Busca semÃ¢ntica de memÃ³rias relevantes com score de similaridade
  GET /memory/health          -> Status dos backends de memÃ³ria (curto e longo prazo)

SECURITY (P6-pre): user_id extraÃ­do do request.state (via middleware) para isolamento
multi-tenant. A busca e listagem retornam apenas memÃ³rias do usuÃ¡rio autenticado.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from src.jefrey.core.embeddings import EmbeddingsUnavailable
import asyncio
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
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
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        raise HTTPException(status_code=503, detail=str(e))
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
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("memory: erro no health check: %s", e, exc_info=True)
        return {
            "status": "unhealthy",
            "error": "Erro interno ao verificar saÃºde da memÃ³ria.",
        }


_MEMORY_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="user_id required (Axiom #2)")
    return str(user_id)


@router.post("/add")
async def add_memory(request: Request):
    """Guarda um texto na memoria de longo prazo do usuario autenticado."""
    user_id = _require_user(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    content = str(body.get("content") or body.get("text") or "").strip()
    title = str(body.get("title") or "").strip()[:200]
    type_ = str(body.get("type") or "note").strip()[:40]
    if not content:
        raise HTTPException(status_code=400, detail="content obrigatorio")
    if len(content) > 500 * 1024:
        raise HTTPException(status_code=400, detail="content muito grande (max 500KB por chamada)")
    full = (title + "\n" + content) if title else content
    try:
        memory_id = get_memory_manager().long_term.add(
            full, metadata={"type": type_, **({"title": title} if title else {})}, user_id=user_id)
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("memory/add erro user=%s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao salvar memoria")
    return {"ok": True, "id": memory_id, "chars": len(full)}


@router.get("/recent")
async def recent_memories(request: Request, limit: int = Query(30, ge=1, le=200)):
    """O que o usuario guardou, do mais novo para o mais antigo."""
    user_id = _require_user(request)
    try:
        items = get_memory_manager().long_term.list_recent(limit=limit, user_id=user_id)
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("memory/recent erro user=%s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao listar memorias")
    return {"memories": items, "count": len(items)}


@router.delete("/{memory_id}")
async def delete_memory(request: Request, memory_id: str):
    """Esquece uma memoria de verdade. So o dono consegue; id de outro usuario vira 404."""
    user_id = _require_user(request)
    if not _MEMORY_ID.match(memory_id):
        raise HTTPException(status_code=400, detail="id invalido")
    try:
        ok = get_memory_manager().long_term.delete(memory_id, user_id=user_id)
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("memory/delete erro user=%s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao apagar memoria")
    if not ok:
        raise HTTPException(status_code=404, detail="memoria nao encontrada")
    return {"ok": True, "id": memory_id}


@router.post("/import")
async def import_document(request: Request, file: UploadFile = File(...)):
    """Importa um documento de texto: corta em trechos e guarda cada um na memoria do usuario."""
    from src.jefrey.core.ingest import MAX_BYTES, MAX_CHUNKS, IngestError, chunk_text, extract_text

    user_id = _require_user(request)
    data = await file.read(MAX_BYTES + 1)
    name = (file.filename or "documento")[:200]
    try:
        text = extract_text(name, data)
    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    chunks = chunk_text(text)
    if len(chunks) > MAX_CHUNKS:
        raise HTTPException(status_code=413, detail=f"documento longo demais ({len(chunks)} trechos; o maximo e {MAX_CHUNKS})")
    ltm = get_memory_manager().long_term
    ids: list[str] = []
    try:
        for i, piece in enumerate(chunks):
            ids.append(ltm.add(f"{name}\n{piece}",
                               metadata={"title": name, "type": "document", "chunk": i + 1, "chunks": len(chunks)},
                               user_id=user_id))
    except EmbeddingsUnavailable as e:  # sem busca por sentido: 503 com mensagem clara (nao 500)
        for mid in ids:  # tambem nao deixa documento pela metade
            try:
                ltm.delete(mid, user_id=user_id)
            except Exception:
                pass
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("memory/import erro user=%s: %s", user_id, e, exc_info=True)
        for mid in ids:  # nao deixa documento pela metade
            try:
                ltm.delete(mid, user_id=user_id)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Erro ao importar o documento")
    return {"ok": True, "title": name, "chunks": len(ids), "chars": len(text)}


@router.get("/search-engine")
async def search_engine(request: Request):
    """Motor da busca por sentido em uso e o melhor disponivel agora (para oferecer 'melhorar a busca')."""
    from src.jefrey.core.memory import search_engine_status

    _require_user(request)
    return await asyncio.to_thread(search_engine_status)


@router.post("/search-engine/upgrade")
async def upgrade_search(request: Request):
    """Troca para o melhor motor disponivel e reindexa as memorias. Nada e apagado."""
    from src.jefrey.core.memory import upgrade_search_engine

    _require_user(request)
    try:
        return await asyncio.to_thread(upgrade_search_engine)
    except EmbeddingsUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
