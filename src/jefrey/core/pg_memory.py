"""Long-term memory backend PostgreSQL + pgvector (compatível com a interface ChromaDB).

SECURITY (P6-pre): Todos os métodos filtram por user_id para isolamento multi-tenant.
O user_id é obrigatório em add/search/get/update/delete/list_recent.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import logging

from sqlalchemy import select, func, and_, not_, cast, Numeric

logger = logging.getLogger(__name__)
from sqlalchemy.dialects.postgresql import JSONB

from src.jefrey.core.db import get_db
from src.jefrey.core.models import memory_table
from src.jefrey.core.config import get_settings
from src.jefrey.core.metrics import MEMORY_OPS, MEMORY_LATENCY

def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)

def _build_filter(table, filter_metadata: dict | None, user_id: str | None = None):
    """Traduz um filtro estilo ChromaDB ({key: {$in/:eq...}}) para uma cláusula SQLAlchemy.

    SECURITY: Sempre inclui filtro por user_id quando fornecido.
    Chaves que existem como coluna (ex.: ``tags``) usam operadores nativos; chaves
    arbitrárias são resolvidas na coluna ``metadata_json`` (JSONB) via ``@>``
    (containment) ou ``->>`` (texto) conforme o operador.
    """
    clauses = []

    # SECURITY: filtro obrigatório por user_id (isolamento multi-tenant)
    if user_id is not None:
        clauses.append(table.user_id == user_id)

    if not filter_metadata:
        return and_(*clauses) if clauses else True

    # Apenas colunas conhecidas são filtráveis diretamente; qualquer outra chave é
    # resolvida em metadata_json (JSONB). Isso evita getattr(table, key) com chaves
    # arbitrárias (ex.: "__class__") vindas de ferramentas/agentes (injecao/robustez).
    _COLUMN_KEYS = {"tags", "title", "source", "importance", "created_at", "updated_at", "user_id"}
    for key, cond in filter_metadata.items():
        is_meta = key not in _COLUMN_KEYS
        if is_meta:
            col = table.metadata_json
            text_col = col.op("->>")(key)
        else:
            col = getattr(table, key)
        if isinstance(cond, dict):
            (op, val), = cond.items()
            if is_meta:
                clauses.append(_metadata_clause(text_col, col, op, val, key))
            elif op == "$in":
                clauses.append(col.op("&&")(val) if key == "tags" else col.in_(val))
            elif op == "$eq":
                clauses.append(col == val)
            elif op == "$ne":
                clauses.append(col != val)
            elif op == "$gt":
                clauses.append(col > val)
            elif op == "$gte":
                clauses.append(col >= val)
            elif op == "$lt":
                clauses.append(col < val)
            elif op == "$lte":
                clauses.append(col <= val)
            else:
                clauses.append(col == val)
        else:
            if is_meta:
                clauses.append(_metadata_clause(text_col, col, "$eq", cond, key))
            else:
                clauses.append(col == cond)
    return and_(*clauses)

def _metadata_clause(text_col, col, op: str, val, key: str) -> Any:
    """Constrói a cláusula para filtros sobre a coluna JSONB ``metadata_json``.

    ``$eq``/``$ne`` usam containment (``@>``) passando o **dict** Python para o
    ``cast(..., JSONB)`` — assim o driver serializa em objeto jsonb correto
    (passar ``json.dumps(...)`` faz o psycopg re-serializar a string e quebrar o ``@>``).
    ``$in`` usa comparação textual (``->>``); operadores de comparação (``$gt`` etc.)
    fazem cast para numérico.
    """
    if op == "$in":
        return text_col.in_(val)
    if op in ("$eq", "default"):
        return col.op("@>")(cast({key: val}, JSONB))
    if op == "$ne":
        return not_(col.op("@>")(cast({key: val}, JSONB)))
    numeric = text_col.cast(Numeric)
    if op == "$gt":
        return numeric > val
    if op == "$gte":
        return numeric >= val
    if op == "$lt":
        return numeric < val
    if op == "$lte":
        return numeric <= val
    return col.op("@>")(cast({key: val}, JSONB))

class PostgresLongTermMemory:
    """Memória de longo prazo vetorial no PostgreSQL (pgvector).

    SECURITY: Todos os métodos exigem user_id para isolamento multi-tenant.
    """

    def __init__(
        self,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        embeddings=None,
        default_layer: str = "episodic",
    ):
        s = get_settings().memory.long_term
        self._top_k = top_k or s.top_k
        self._similarity_threshold = (
            similarity_threshold if similarity_threshold is not None else s.similarity_threshold
        )
        self._default_layer = default_layer
        if embeddings is None:
            from src.jefrey.core.memory import get_embeddings
            embeddings = get_embeddings()
        self._embeddings = embeddings

    def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        layer: str | None = None,
        user_id: str = "system",
    ) -> str:
        import time as _time
        _layer = layer or self._default_layer
        _start = _time.monotonic()
        try:
            table = memory_table(_layer)
            metadata = dict(metadata or {})
            tags = metadata.pop("tags", []) or []
            title = metadata.pop("title", None)
            source = metadata.pop("source", "user")
            metadata = {k: _jsonable(v) for k, v in metadata.items()}
            embedding = self._embeddings.embed_query(content)
            rec = table(
                id=uuid.UUID(memory_id) if memory_id else uuid.uuid4(),
                user_id=user_id,
                content=content,
                embedding=embedding,
                title=title,
                source=source,
                tags=list(tags),
                metadata_json=metadata,
            )
            with get_db() as session:
                session.add(rec)
                session.flush()
                rid = str(rec.id)
            _elapsed = _time.monotonic() - _start
            MEMORY_LATENCY.labels(operation="add", layer=_layer).observe(_elapsed)
            MEMORY_OPS.labels(operation="add", layer=_layer).inc()
            logger.info("add layer=%s id=%s user=%s tags=%s", _layer, rid, user_id, tags)
            return rid
        except Exception:
            _elapsed = _time.monotonic() - _start
            MEMORY_LATENCY.labels(operation="add", layer=_layer).observe(_elapsed)
            MEMORY_OPS.labels(operation="add", layer=_layer).inc()
            raise

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter_metadata: dict | None = None,
        layer: str | None = None,
        user_id: str = "system",
    ) -> list[dict]:
        import time as _time
        _layer = layer or self._default_layer
        _start = _time.monotonic()
        try:
            table = memory_table(_layer)
            top_k = top_k or self._top_k
            q = self._embeddings.embed_query(query)
            distance = table.embedding.cosine_distance(q)
            stmt = select(table, distance.label("distance")).where(
                _build_filter(table, filter_metadata, user_id=user_id)
            )
            stmt = stmt.order_by(distance).limit(top_k)
            results: list[dict] = []
            try:
                with get_db() as session:
                    rows = session.execute(stmt).all()
                    for rec, dist in rows:
                        similarity = 1 - float(dist)
                        if similarity < self._similarity_threshold:
                            continue
                        results.append(self._to_dict(rec, similarity))
            except Exception as e:  # noqa: BLE001
                logger.error("search layer=%s falhou: %s", _layer, e)
                raise
            _elapsed = _time.monotonic() - _start
            MEMORY_LATENCY.labels(operation="search", layer=_layer).observe(_elapsed)
            MEMORY_OPS.labels(operation="search", layer=_layer).inc()
            logger.debug("search layer=%s query=%r top_k=%s user=%s -> %d", _layer, query[:50], top_k, user_id, len(results))
            return results
        except Exception:
            _elapsed = _time.monotonic() - _start
            MEMORY_LATENCY.labels(operation="search", layer=_layer).observe(_elapsed)
            MEMORY_OPS.labels(operation="search", layer=_layer).inc()
            raise

    def get(self, memory_id: str, layer: str | None = None, user_id: str = "system") -> dict | None:
        table = memory_table(layer or self._default_layer)
        with get_db() as session:
            rec = session.get(table, uuid.UUID(memory_id))
            if rec is None:
                return None
            # SECURITY: ownership check — só retorna se pertence ao user
            if rec.user_id != user_id:
                logger.warning("get id=%s negado: user=%s não é owner (owner=%s)", memory_id, user_id, rec.user_id)
                return None
            return self._to_dict(rec)

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
        layer: str | None = None,
        user_id: str = "system",
    ) -> bool:
        table = memory_table(layer or self._default_layer)
        with get_db() as session:
            rec = session.get(table, uuid.UUID(memory_id))
            if rec is None:
                logger.warning("update id=%s nao encontrado (layer=%s)", memory_id, layer or self._default_layer)
                return False
            # SECURITY: ownership check
            if rec.user_id != user_id:
                logger.warning("update id=%s negado: user=%s não é owner", memory_id, user_id)
                return False
            if content is not None:
                rec.content = content
                rec.embedding = self._embeddings.embed_query(content)
            if metadata:
                md = dict(rec.metadata_json or {})
                tags = metadata.pop("tags", None)
                title = metadata.pop("title", None)
                source = metadata.pop("source", None)
                md.update({k: _jsonable(v) for k, v in metadata.items()})
                rec.metadata_json = md
                if tags is not None:
                    rec.tags = list(tags)
                if title is not None:
                    rec.title = title
                if source is not None:
                    rec.source = source
            session.add(rec)
        return True

    def delete(self, memory_id: str, layer: str | None = None, user_id: str = "system") -> bool:
        table = memory_table(layer or self._default_layer)
        with get_db() as session:
            rec = session.get(table, uuid.UUID(memory_id))
            if rec is None:
                return False
            # SECURITY: ownership check
            if rec.user_id != user_id:
                logger.warning("delete id=%s negado: user=%s não é owner", memory_id, user_id)
                return False
            session.delete(rec)
        logger.info("delete id=%s layer=%s user=%s", memory_id, layer or self._default_layer, user_id)
        return True

    def list_recent(
        self,
        limit: int = 20,
        filter_metadata: dict | None = None,
        layer: str | None = None,
        user_id: str = "system",
    ) -> list[dict]:
        table = memory_table(layer or self._default_layer)
        stmt = (
            select(table)
            .where(_build_filter(table, filter_metadata, user_id=user_id))
            .order_by(table.created_at.desc())
            .limit(limit)
        )
        with get_db() as session:
            rows = session.execute(stmt).all()
            return [self._to_dict(r[0]) for r in rows]

    def count(self, layer: str | None = None, user_id: str | None = None) -> int:
        table = memory_table(layer or self._default_layer)
        with get_db() as session:
            q = select(func.count()).select_from(table)
            if user_id is not None:
                q = q.where(table.user_id == user_id)
            return session.scalar(q) or 0

    def health_check(self) -> dict:
        """Verifica saúde do backend Postgres (contagem + captura de erro)."""
        try:
            n = self.count()
            return {"status": "ok", "backend": "postgres", "count": n}
        except Exception as e:  # noqa: BLE001
            logger.error("health_check postgres falhou: %s", e)
            return {"status": "error", "backend": "postgres", "error": str(e)}

    @staticmethod
    def _to_dict(rec, similarity: float | None = None) -> dict:
        d = {
            "id": str(rec.id),
            "user_id": rec.user_id,
            "content": rec.content,
            "title": rec.title,
            "source": rec.source,
            "tags": list(rec.tags or []),
            "metadata": dict(rec.metadata_json or {}),
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        }
        if similarity is not None:
            d["similarity"] = round(similarity, 4)
        return d
