"""Prometheus metrics integration adapter for PIIS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import math
import uuid

from piis.integrations.contracts import (
    IngestionEnvelope,
    IntegrationAdapter,
    IntegrationType,
    RateLimiter,
)
from piis.provenance import SourceType


class PrometheusAdapter(IntegrationAdapter):
    """Adapter for ingesting and normalizing Prometheus query/vector metrics."""

    # Explicit unit mappings for common telecom KPI metrics
    METRIC_UNIT_MAP: Dict[str, str] = {
        "vswr": "ratio",
        "rsrp": "dBm",
        "sinr": "dB",
        "bler": "ratio",
        "packet_drop_rate": "ratio",
        "latency_ms": "ms",
        "prb_utilization": "ratio",
        "tx_bytes_total": "bytes",
        "rx_bytes_total": "bytes",
        "cpu_usage_ratio": "ratio",
        "memory_usage_bytes": "bytes",
    }

    def __init__(
        self,
        adapter_id: str = "TELEM-PROM-01",
        prometheus_url: str = "http://prometheus:9090",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.TELEMETRY,
            source_system="Prometheus",
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=100.0, burst=200),
        )
        self.prometheus_url = prometheus_url

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize a single metric observation or vector item into canonical PIIS telemetry schema."""
        p = envelope.raw_payload

        # Prometheus vector item: {"metric": {"__name__": "...", "instance": "..."}, "value": [timestamp, "value"]}
        metric_labels = p.get("metric", {})
        metric_name = metric_labels.get("__name__") or p.get("metric_name") or "unknown_metric"

        # Observation timestamp
        raw_val = p.get("value")
        obs_time_str = envelope.observation_timestamp
        metric_val: Optional[float] = None

        if isinstance(raw_val, (list, tuple)) and len(raw_val) >= 2:
            # [unix_timestamp_seconds, "value_string"]
            unix_sec = float(raw_val[0])
            obs_dt = datetime.fromtimestamp(unix_sec, tz=timezone.utc)
            obs_time_str = obs_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"
            try:
                metric_val = float(raw_val[1])
            except (ValueError, TypeError):
                metric_val = None
        elif "value" in p and not isinstance(p["value"], (list, tuple)):
            try:
                metric_val = float(p["value"])
            except (ValueError, TypeError):
                metric_val = None

        if not obs_time_str:
            obs_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Network element identifier from labels (instance, node, cell_id, ne_id)
        element_id = (
            metric_labels.get("network_element_id")
            or metric_labels.get("ne_id")
            or metric_labels.get("instance")
            or metric_labels.get("node")
            or p.get("network_element_id")
            or "GENERIC_NE"
        )

        # Domain deduction
        domain = metric_labels.get("domain") or metric_labels.get("network_domain")
        if not domain:
            u_name = metric_name.lower()
            if any(k in u_name for k in ["vswr", "rsrp", "bler", "prb", "cell", "gnb"]):
                domain = "RAN"
            elif any(k in u_name for k in ["upf", "amf", "smf", "packet_drop"]):
                domain = "CORE"
            elif any(k in u_name for k in ["interface", "router", "bgp", "optical", "link"]):
                domain = "TRANSPORT"
            else:
                domain = "CROSS_DOMAIN"

        # Resolve unit
        unit = p.get("unit")
        if not unit:
            for k, u in self.METRIC_UNIT_MAP.items():
                if k in metric_name.lower():
                    unit = u
                    break

        obs_id = p.get("observation_id") or f"OBS-PROM-{uuid.uuid4().hex[:10].upper()}"

        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "observation_id": obs_id,
            "incident_id": p.get("incident_id") or envelope.metadata.get("incident_id"),
            "timestamp": obs_time_str,
            "network_element_id": str(element_id),
            "network_domain": domain,
            "metric_name": metric_name,
            "metric_value": metric_val if (metric_val is not None and not math.isnan(metric_val)) else None,
            "unit": unit,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "metadata": {
                "prometheus_labels": metric_labels,
                "ingested_at": envelope.ingested_at,
                "ingestion_envelope_id": envelope.envelope_id,
            },
        }

        self.record_success()
        return canonical

    def normalize_batch(self, envelope: IngestionEnvelope) -> List[Dict[str, Any]]:
        """Normalize Prometheus query result containing multiple series/points."""
        data = envelope.raw_payload.get("data", envelope.raw_payload)
        result = data.get("result", [])

        if not isinstance(result, list):
            # Single object
            return [self.normalize(envelope)]

        observations = []
        for item in result:
            single_env = IngestionEnvelope(
                envelope_id=f"{envelope.envelope_id}-{len(observations)}",
                source_system=envelope.source_system,
                source_type=envelope.source_type,
                raw_payload=item,
                ingested_at=envelope.ingested_at,
                external_event_id=envelope.external_event_id,
                observation_timestamp=envelope.observation_timestamp,
                metadata=envelope.metadata,
            )
            observations.append(self.normalize(single_env))
        return observations
