"""OpenTelemetry (OTLP) Metrics integration adapter for PIIS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from piis.integrations.contracts import (
    IngestionEnvelope,
    IntegrationAdapter,
    IntegrationType,
    RateLimiter,
)
from piis.provenance import SourceType


class OpenTelemetryMetricsAdapter(IntegrationAdapter):
    """Adapter for ingesting and normalizing OpenTelemetry OTLP/JSON metric records."""

    def __init__(
        self,
        adapter_id: str = "TELEM-OTLP-01",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.TELEMETRY,
            source_system="OpenTelemetry",
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=100.0, burst=200),
        )

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize an OTLP data point dictionary into canonical telemetry record."""
        p = envelope.raw_payload
        metric_name = p.get("name") or p.get("metric_name") or "unknown_otlp_metric"
        unit = p.get("unit") or None

        # Data point can be Gauge, Sum, or direct point
        point = p.get("point") or p
        val = point.get("as_double") if "as_double" in point else point.get("as_int", point.get("value"))
        try:
            metric_val = float(val) if val is not None else None
        except (ValueError, TypeError):
            metric_val = None

        # OTLP timestamps are typically nanoseconds since epoch
        nano_ts = point.get("time_unix_nano") or point.get("timestamp_nano")
        if nano_ts:
            try:
                sec = float(nano_ts) / 1e9
                obs_dt = datetime.fromtimestamp(sec, tz=timezone.utc)
                obs_time_str = obs_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"
            except Exception:
                obs_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            obs_time_str = envelope.observation_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        attributes = point.get("attributes", {})
        if isinstance(attributes, list):
            # OTLP list of {"key": "...", "value": {"string_value": "..."}}
            attr_dict = {}
            for item in attributes:
                k = item.get("key")
                v = item.get("value", {})
                attr_dict[k] = v.get("string_value", v.get("int_value", v.get("bool_value", str(v))))
            attributes = attr_dict

        element_id = (
            attributes.get("service.name")
            or attributes.get("host.name")
            or attributes.get("network_element_id")
            or p.get("network_element_id")
            or "OTLP_NODE"
        )
        domain = attributes.get("network.domain") or "CROSS_DOMAIN"

        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "observation_id": f"OBS-OTLP-{uuid.uuid4().hex[:10].upper()}",
            "incident_id": p.get("incident_id") or envelope.metadata.get("incident_id"),
            "timestamp": obs_time_str,
            "network_element_id": str(element_id),
            "network_domain": domain,
            "metric_name": metric_name,
            "metric_value": metric_val,
            "unit": unit,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "metadata": {
                "otlp_attributes": attributes,
                "ingested_at": envelope.ingested_at,
                "ingestion_envelope_id": envelope.envelope_id,
            },
        }

        self.record_success()
        return canonical
