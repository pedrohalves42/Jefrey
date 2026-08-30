"""P6 — GET /metrics Endpoint (Prometheus Exposition Format).

Expõe todas as métricas Jefrey via prometheus_client.
Endpoint público — contém apenas counters/gauges, sem PII.

Monta uma aplicação ASGI separada e a mounta em /metrics no FastAPI principal.
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Expõe todas as métricas Jefrey no formato Prometheus exposition.",
    response_class=Response,
)
async def metrics_endpoint():
    """Retorna todas as métricas registradas no prometheus_client.

    Formato: texto Prometheus (CONTENT_TYPE_LATEST).
    Seguro: sem PII, apenas nomes de provider/model/tool.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
