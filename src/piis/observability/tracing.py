"""OpenTelemetry tracing instrumentation and OTLP export for PIIS operations."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger("piis.observability.tracing")

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SimpleSpanProcessor,
        SpanExporter,
        SpanExportResult,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    HAVE_OTEL = True
except ImportError:
    HAVE_OTEL = False
    SpanExporter = object  # type: ignore


class NoOpSpan:
    """Fallback span when OpenTelemetry is not installed."""
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass


class FailSafeSpanExporter(SpanExporter):
    """Wrapper around any SpanExporter that guarantees collector failures never crash the app."""

    def __init__(self, underlying_exporter: Any):
        self.underlying = underlying_exporter
        self.consecutive_failures = 0

    def export(self, spans: Any) -> Any:
        try:
            res = self.underlying.export(spans)
            self.consecutive_failures = 0
            return res
        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(
                "OTLP span export failed (collector unavailable or timeout): %s. "
                "Incident decision processing remains unaffected.",
                str(e),
            )
            if HAVE_OTEL:
                return SpanExportResult.FAILURE
            return None

    def shutdown(self) -> None:
        try:
            self.underlying.shutdown()
        except Exception:
            pass


class InMemorySimulatedCollector(SpanExporter):
    """In-memory simulated OTLP collector for unit and integration testing."""

    def __init__(self, should_fail: bool = False):
        self.spans: List[Any] = []
        self.should_fail = should_fail

    def export(self, spans: Any) -> Any:
        if self.should_fail:
            raise ConnectionError("Simulated OTLP collector endpoint connection refused (ECONNREFUSED :4317)")
        self.spans.extend(spans)
        if HAVE_OTEL:
            return SpanExportResult.SUCCESS
        return None

    def shutdown(self) -> None:
        pass

    def clear(self) -> None:
        self.spans.clear()


_TRACER_CONFIGURED = False
_ACTIVE_EXPORTER: Optional[Any] = None
_CURRENT_PROVIDER: Optional[Any] = None


def configure_tracing(
    collector_endpoint: Optional[str] = None,
    exporter: Optional[Any] = None,
    service_name: str = "piis-decision-support",
    use_batch: bool = False,
    timeout: float = 5.0,
) -> bool:
    """Initialize OpenTelemetry tracer provider with an active exporter and fail-safe processor."""
    global _TRACER_CONFIGURED, _ACTIVE_EXPORTER, _CURRENT_PROVIDER

    if not HAVE_OTEL:
        return False

    endpoint = collector_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    # If no custom exporter provided, try instantiating OTLP gRPC exporter if endpoint configured
    active_exp = exporter
    if active_exp is None and endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            active_exp = OTLPSpanExporter(endpoint=endpoint, insecure=True, timeout=timeout)
        except Exception as e:
            logger.warning("Could not initialize OTLPSpanExporter for endpoint '%s': %s", endpoint, e)
            return False

    if active_exp is None:
        # Default: TracerProvider initialized without remote export
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        _CURRENT_PROVIDER = provider
        try:
            trace.set_tracer_provider(provider)
        except Exception:
            pass
        _TRACER_CONFIGURED = True
        return True

    safe_exporter = FailSafeSpanExporter(active_exp)
    _ACTIVE_EXPORTER = safe_exporter

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    processor = BatchSpanProcessor(safe_exporter) if use_batch else SimpleSpanProcessor(safe_exporter)
    provider.add_span_processor(processor)
    _CURRENT_PROVIDER = provider
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    _TRACER_CONFIGURED = True
    return True


def get_tracer(instrumenting_module_name: str = "piis.tracer", version: str = "1.0.0") -> Any:
    """Return the tracer from the active TracerProvider if configured, otherwise global."""
    if HAVE_OTEL:
        if _CURRENT_PROVIDER is not None:
            return _CURRENT_PROVIDER.get_tracer(instrumenting_module_name, version)
        return trace.get_tracer(instrumenting_module_name, version)
    return None


def flush_tracing(timeout_millis: int = 30000) -> bool:
    """Force flush active tracer provider."""
    global _CURRENT_PROVIDER
    if _CURRENT_PROVIDER is not None and hasattr(_CURRENT_PROVIDER, "force_flush"):
        try:
            return bool(_CURRENT_PROVIDER.force_flush(timeout_millis=timeout_millis))
        except Exception:
            return False
    return True


def shutdown_tracing() -> None:
    """Flush and shut down active tracer provider."""
    global _CURRENT_PROVIDER, _ACTIVE_EXPORTER, _TRACER_CONFIGURED
    if _CURRENT_PROVIDER is not None:
        try:
            _CURRENT_PROVIDER.shutdown()
        except Exception:
            pass
        _CURRENT_PROVIDER = None
    _ACTIVE_EXPORTER = None
    _TRACER_CONFIGURED = False


def get_current_trace_context() -> Dict[str, str]:
    """Extract W3C traceparent and trace IDs from current active span."""
    if not HAVE_OTEL:
        return {}

    carrier: Dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier


def inject_trace_context(headers: Dict[str, str]) -> None:
    """Inject W3C traceparent into outbound header dictionary."""
    if HAVE_OTEL:
        TraceContextTextMapPropagator().inject(headers)


def extract_trace_context(headers: Dict[str, str]) -> Any:
    """Extract trace context from inbound headers to link parent span."""
    if HAVE_OTEL:
        return TraceContextTextMapPropagator().extract(headers)
    return None


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Iterator[Any]:
    """Context manager executing code inside an OpenTelemetry trace span."""
    if HAVE_OTEL:
        tracer = get_tracer("piis.tracer", "1.0.0")
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    else:
        yield NoOpSpan()
