"""P6.2 — OpenTelemetry Tracing Setup (Diff 5 Enhanced Health).

Configura tracing distribuído com OpenTelemetry.
Suporta exportadores OTLP (Jaeger, Zipkin, Grafana Tempo, etc.)
e console para desenvolvimento.

Referências:
- Book 4 (Prometheus Up & Running) — Cap 6: Histograms e Exemplars
- Book 5 (MCP Spec) — Observability requirements
- OpenTelemetry Python SDK docs
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer = None
_meter = None
_initialized = False


def init_telemetry(
    service_name: str = "jefrey-mcp",
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[dict] = None,
    sample_rate: float = 1.0,
    enable_console: bool = False,
) -> None:
    """Inicializa OpenTelemetry tracing e metrics.

    Args:
        service_name: Nome do serviço (ex: "jefrey-mcp", "jefrey-api")
        otlp_endpoint: Endpoint OTLP (ex: "http://jaeger:4318/v1/traces")
        otlp_headers: Headers extras para OTLP (ex: auth tokens)
        sample_rate: Taxa de amostragem (0.0 a 1.0)
        enable_console: Se True, exporta para console (dev)
    """
    global _tracer, _meter, _initialized

    if _initialized:
        logger.warning("Telemetry already initialized, skipping")
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    except ImportError:
        logger.warning("opentelemetry not installed, tracing disabled")
        return

    # Resource
    resource = Resource.create({SERVICE_NAME: service_name})

    # --- Tracing ---
    trace_provider = TracerProvider(resource=resource)

    # OTLP Exporter (traces)
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers=otlp_headers or {},
            )
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP trace exporter configured: %s", otlp_endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp not installed, skipping OTLP traces")

    # Console Exporter (traces) - dev only
    if enable_console:
        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("Console trace exporter enabled")
        except ImportError:
            pass

    trace.set_tracer_provider(trace_provider)

    # --- Metrics ---
    readers = []

    # OTLP Exporter (metrics)
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            metric_exporter = OTLPMetricExporter(
                endpoint=otlp_endpoint.replace("/traces", "/metrics"),
                headers=otlp_headers or {},
            )
            readers.append(PeriodicExportingMetricReader(metric_exporter, export_interval_millis=30000))
            logger.info("OTLP metric exporter configured")
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp not installed, skipping OTLP metrics")

    # Console Exporter (metrics) - dev only
    if enable_console:
        try:
            from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
            readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=30000))
        except ImportError:
            pass

    if readers:
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

    # Get tracer and meter
    _tracer = trace.get_tracer(service_name)
    _meter = metrics.get_meter(service_name)

    _initialized = True
    logger.info("OpenTelemetry initialized for service: %s", service_name)


def get_tracer():
    """Retorna o tracer global (inicializa no-op se necessário)."""
    global _tracer
    if _tracer is None:
        try:
            from opentelemetry import trace
            _tracer = trace.get_tracer("jefrey-mcp")
        except ImportError:
            # No-op tracer
            class NoOpTracer:
                def start_as_current_span(self, name, **kwargs):
                    class NoOpSpan:
                        def __enter__(self): return self
                        def __exit__(self, *args): pass
                        def set_attribute(self, *args, **kwargs): pass
                        def add_event(self, *args, **kwargs): pass
                        def record_exception(self, *args, **kwargs): pass
                        def set_status(self, *args, **kwargs): pass
                    return NoOpSpan()
            _tracer = NoOpTracer()
    return _tracer


def get_meter():
    """Retorna o meter global (inicializa no-op se necessário)."""
    global _meter
    if _meter is None:
        try:
            from opentelemetry import metrics
            _meter = metrics.get_meter("jefrey-mcp")
        except ImportError:
            class NoOpMeter:
                def create_counter(self, *args, **kwargs):
                    class NoOpCounter:
                        def add(self, *args, **kwargs): pass
                    return NoOpCounter()
                def create_histogram(self, *args, **kwargs):
                    class NoOpHistogram:
                        def record(self, *args, **kwargs): pass
                    return NoOpHistogram()
                def create_up_down_counter(self, *args, **kwargs):
                    class NoOpUDC:
                        def add(self, *args, **kwargs): pass
                    return NoOpUDC()
                def create_gauge(self, *args, **kwargs):
                    class NoOpGauge:
                        def set(self, *args, **kwargs): pass
                    return NoOpGauge()
            _meter = NoOpMeter()
    return _meter


def shutdown_telemetry() -> None:
    """Desliga telemetria graciosamente."""
    global _initialized
    if _initialized:
        try:
            from opentelemetry import trace, metrics
            trace.get_tracer_provider().shutdown()
            metrics.get_meter_provider().shutdown()
            logger.info("OpenTelemetry shutdown complete")
        except Exception as e:
            logger.warning("Error shutting down telemetry: %s", e)
        _initialized = False


# Convenience: decorator para spans automáticos
def trace_span(name: str, attributes: Optional[dict] = None):
    """Decorator para criar span automático em funções async."""
    def decorator(func):
        import functools
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator