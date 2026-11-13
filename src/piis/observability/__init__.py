"""PIIS Audit & Observability Integration Package."""

from piis.observability.logging import (
    get_correlation_id,
    set_correlation_id,
    setup_structured_logging,
)
from piis.observability.metrics import (
    CONTENT_TYPE_LATEST,
    get_latest_metrics,
    record_duplicate,
    record_failure,
    record_ingestion,
    record_investigation,
    record_review,
    set_adapter_health,
)
from piis.observability.tracing import trace_span

__all__ = [
    "CONTENT_TYPE_LATEST",
    "get_correlation_id",
    "get_latest_metrics",
    "record_duplicate",
    "record_failure",
    "record_ingestion",
    "record_investigation",
    "record_review",
    "set_adapter_health",
    "set_correlation_id",
    "setup_structured_logging",
    "trace_span",
]
