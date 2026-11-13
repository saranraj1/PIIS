"""Prometheus metrics registry and instrumentation for PIIS operational observability."""

from __future__ import annotations


try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    HAVE_PROMETHEUS = True
except ImportError:
    HAVE_PROMETHEUS = False


# Dedicated Collector Registry for PIIS
if HAVE_PROMETHEUS:
    PIIS_REGISTRY = CollectorRegistry()

    # Ingestion Metrics
    INGESTION_TOTAL = Counter(
        "piis_ingestion_total",
        "Total events ingested by the unified pipeline",
        ["source_system", "status"],
        registry=PIIS_REGISTRY,
    )

    INGESTION_LATENCY_SECONDS = Histogram(
        "piis_ingestion_latency_seconds",
        "Latency of event normalization and schema validation in seconds",
        ["source_system"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        registry=PIIS_REGISTRY,
    )

    NORMALIZATION_FAILURES_TOTAL = Counter(
        "piis_normalization_failures_total",
        "Total failures during payload normalization or schema validation",
        ["source_system", "failure_reason"],
        registry=PIIS_REGISTRY,
    )

    DUPLICATES_TOTAL = Counter(
        "piis_duplicates_total",
        "Total duplicate ingestion attempts detected and suppressed",
        ["source_system"],
        registry=PIIS_REGISTRY,
    )

    # Investigation Metrics
    INVESTIGATION_LATENCY_SECONDS = Histogram(
        "piis_investigation_latency_seconds",
        "Total latency of the multi-milestone investigation engine in seconds",
        ["network_domain"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
        registry=PIIS_REGISTRY,
    )

    SAFE_ABSTENTIONS_TOTAL = Counter(
        "piis_safe_abstentions_total",
        "Total safe operational abstentions enforced to protect telecom networks",
        ["network_domain", "abstention_reason"],
        registry=PIIS_REGISTRY,
    )

    RECOMMENDATIONS_TOTAL = Counter(
        "piis_recommendations_total",
        "Total evidence-grounded diagnostic recommendations generated",
        ["network_domain", "risk_classification"],
        registry=PIIS_REGISTRY,
    )

    # Human Review Metrics
    REVIEWS_TOTAL = Counter(
        "piis_reviews_total",
        "Total human operator reviews submitted and cryptographically signed",
        ["decision", "operator_role"],
        registry=PIIS_REGISTRY,
    )

    # Adapter Health Gauge
    ADAPTER_HEALTH_STATUS = Gauge(
        "piis_adapter_health_status",
        "Current health state of an integration adapter (1=Healthy, 0.5=Degraded, 0=Unhealthy)",
        ["adapter_id", "adapter_type"],
        registry=PIIS_REGISTRY,
    )
else:
    PIIS_REGISTRY = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"


def record_ingestion(source: str, status: str, latency: float) -> None:
    """Record an ingestion event."""
    if HAVE_PROMETHEUS:
        INGESTION_TOTAL.labels(source_system=source, status=status).inc()
        INGESTION_LATENCY_SECONDS.labels(source_system=source).observe(latency)


def record_duplicate(source: str) -> None:
    """Record a duplicate event suppression."""
    if HAVE_PROMETHEUS:
        DUPLICATES_TOTAL.labels(source_system=source).inc()


def record_failure(source: str, reason: str) -> None:
    """Record a normalization or schema failure."""
    if HAVE_PROMETHEUS:
        NORMALIZATION_FAILURES_TOTAL.labels(source_system=source, failure_reason=reason).inc()


def record_investigation(domain: str, latency: float, recommendations: int, safe_abstain: bool, reason: str = "") -> None:
    """Record investigation outcome metrics."""
    if HAVE_PROMETHEUS:
        INVESTIGATION_LATENCY_SECONDS.labels(network_domain=domain).observe(latency)
        if safe_abstain:
            SAFE_ABSTENTIONS_TOTAL.labels(network_domain=domain, abstention_reason=reason or "INCONCLUSIVE").inc()
        if recommendations > 0:
            RECOMMENDATIONS_TOTAL.labels(network_domain=domain, risk_classification="READ_ONLY_SAFE").inc(recommendations)


def record_review(decision: str, role: str) -> None:
    """Record a human operator review."""
    if HAVE_PROMETHEUS:
        REVIEWS_TOTAL.labels(decision=decision, operator_role=role).inc()


def set_adapter_health(adapter_id: str, adapter_type: str, state: str) -> None:
    """Update adapter health gauge."""
    if HAVE_PROMETHEUS:
        score = 1.0 if state == "HEALTHY" else (0.5 if state == "DEGRADED" else 0.0)
        ADAPTER_HEALTH_STATUS.labels(adapter_id=adapter_id, adapter_type=adapter_type).set(score)


def get_latest_metrics() -> bytes:
    """Serialize all metrics for the Prometheus scraping endpoint."""
    if HAVE_PROMETHEUS and PIIS_REGISTRY:
        return generate_latest(PIIS_REGISTRY)
    return b"# Prometheus client not available\n"
