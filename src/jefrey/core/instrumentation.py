"""P6 — Decoradores de Instrumentação para Prometheus.

Fornece @timed (Histogram) e @counted (Counter) reutilizáveis.
Decorators são idempotentes — podem ser empilhados.

Uso:
    from src.jefrey.core.instrumentation import timed, counted
    from src.jefrey.core.metrics import LLM_LATENCY, LLM_TOKENS

    @timed(LLM_LATENCY, label_fn=lambda self, *a, **kw: {"provider": cfg.provider, "model": cfg.model})
    async def _invoke(self, tool_name, args):
        ...
"""
from __future__ import annotations

import functools
import time
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def timed(histogram, label_fn: Callable | None = None, raise_on_error: bool = False):
    """Decorator que observa latência de uma função em um Histogram.

    Args:
        histogram: instância de prometheus_client.Histogram
        label_fn: callable que retorna dict de labels. Recebe os mesmos args da função.
        raise_on_error: se True, relança exceções; se False, apenas loga.

    Para sync e async functions.
    """
    def decorator(fn):
        if _is_async(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                labels = label_fn(*args, **kwargs) if label_fn else {}
                start = time.monotonic()
                try:
                    result = await fn(*args, **kwargs)
                    elapsed = time.monotonic() - start
                    histogram.labels(**labels).observe(elapsed)
                    return result
                except Exception as e:
                    elapsed = time.monotonic() - start
                    histogram.labels(**labels).observe(elapsed)
                    if not raise_on_error:
                        logger.warning("timed: exception in %s after %.3fs: %s", fn.__name__, elapsed, type(e).__name__)
                    raise
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                labels = label_fn(*args, **kwargs) if label_fn else {}
                start = time.monotonic()
                try:
                    result = fn(*args, **kwargs)
                    elapsed = time.monotonic() - start
                    histogram.labels(**labels).observe(elapsed)
                    return result
                except Exception as e:
                    elapsed = time.monotonic() - start
                    histogram.labels(**labels).observe(elapsed)
                    if not raise_on_error:
                        logger.warning("timed: exception in %s after %.3fs: %s", fn.__name__, elapsed, type(e).__name__)
                    raise
            return sync_wrapper
    return decorator


def counted(counter, label_fn: Callable | None = None, raise_on_error: bool = False):
    """Decorator que incrementa um Counter após execução bem-sucedida.

    Args:
        counter: instância de prometheus_client.Counter
        label_fn: callable que retorna dict de labels. Recebe os mesmos args da função.
        raise_on_error: se True, relança exceções; se False, apenas loga.

    Para sync e async functions.
    """
    def decorator(fn):
        if _is_async(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                labels = label_fn(*args, **kwargs) if label_fn else {}
                try:
                    result = await fn(*args, **kwargs)
                    counter.labels(**labels).inc()
                    return result
                except Exception as e:
                    if raise_on_error:
                        raise
                    logger.warning("counted: exception in %s: %s", fn.__name__, type(e).__name__)
                    raise
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                labels = label_fn(*args, **kwargs) if label_fn else {}
                try:
                    result = fn(*args, **kwargs)
                    counter.labels(**labels).inc()
                    return result
                except Exception as e:
                    if raise_on_error:
                        raise
                    logger.warning("counted: exception in %s: %s", fn.__name__, type(e).__name__)
                    raise
            return sync_wrapper
    return decorator


def _is_async(fn) -> bool:
    """Detecta se a função é async."""
    import asyncio
    return asyncio.iscoroutinefunction(fn)
