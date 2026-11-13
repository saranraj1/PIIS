"""OSS/NMS Alarm integration adapter with 3GPP and multi-vendor lifecycle mapping."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from piis.integrations.contracts import (
    IngestionEnvelope,
    IntegrationAdapter,
    IntegrationType,
    RateLimiter,
)
from piis.provenance import SourceType


class AlarmLifecycleState(str, Enum):
    """3GPP operational lifecycle state for network element alarms."""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED = "CLEARED"


class OSSAlarmAdapter(IntegrationAdapter):
    """Adapter for ingesting, normalizing, and tracking network alarms from OSS/NMS brokers."""

    # Standard 3GPP 32.111-2 Severity Mapping
    SEVERITY_MAP: Dict[str, str] = {
        "CRITICAL": "CRITICAL",
        "MAJOR": "MAJOR",
        "MINOR": "MINOR",
        "WARNING": "WARNING",
        "INDETERMINATE": "UNKNOWN",
        "CLEARED": "UNKNOWN",
        "1": "CRITICAL",
        "2": "MAJOR",
        "3": "MINOR",
        "4": "WARNING",
        "5": "UNKNOWN",
    }

    # Explicit vendor-specific alarm code translation to 3GPP canonical categories
    VENDOR_CODE_MAP: Dict[str, Dict[str, str]] = {
        "NOKIA": {
            "7100": "ALM-RAN-VSWR-HIGH",
            "7210": "ALM-RAN-MIMO-CALIB-FAULT",
            "7650": "ALM-TRANSPORT-PTP-SYNC-LOSS",
            "7820": "ALM-RAN-RRU-OPTICAL-FAIL",
        },
        "ERICSSON": {
            "A102": "ALM-RAN-VSWR-HIGH",
            "B205": "ALM-RAN-RADIO-LINK-FAILURE",
            "C310": "ALM-TRANSPORT-SYNCE-UNSTABLE",
        },
        "HUAWEI": {
            "ALM-26241": "ALM-RAN-VSWR-HIGH",
            "ALM-26244": "ALM-RAN-RF-UNIT-MAINTENANCE",
            "ALM-25888": "ALM-TRANSPORT-CLOCK-OUT-OF-LOCK",
        },
    }

    def __init__(
        self,
        adapter_id: str = "ALARM-OSS-01",
        source_system: str = "GenericOSS",
        vendor_hint: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.OSS_NMS_ALARM,
            source_system=source_system,
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=100.0, burst=200),
        )
        self.vendor_hint = vendor_hint

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize raw OSS/NMS alarm payload into canonical PIIS alarm schema."""
        p = envelope.raw_payload

        # Alarm ID
        alarm_id = (
            str(p.get("alarm_id") or p.get("id") or p.get("alarm_identifier") or envelope.external_event_id or "")
        ).strip()
        if not alarm_id:
            alarm_id = f"ALM-OSS-{uuid.uuid4().hex[:10].upper()}"

        # Network element
        element_id = str(
            p.get("network_element_id")
            or p.get("element_id")
            or p.get("ne_name")
            or p.get("managed_object")
            or p.get("dn")
            or "GENERIC_NE"
        ).strip()

        # Domain
        domain = str(p.get("network_domain") or p.get("domain") or "").upper()
        if not domain or domain not in {"RAN", "CORE", "TRANSPORT"}:
            if any(k in element_id.upper() for k in ["GNB", "ENB", "CELL", "RRU", "BBU"]):
                domain = "RAN"
            elif any(k in element_id.upper() for k in ["UPF", "AMF", "SMF", "MME", "SGW"]):
                domain = "CORE"
            elif any(k in element_id.upper() for k in ["ROUTER", "SWITCH", "CSR", "OPTICAL", "IP"]):
                domain = "TRANSPORT"
            else:
                domain = "CROSS_DOMAIN"

        # Alarm Code and vendor resolution
        vendor = str(p.get("vendor") or self.vendor_hint or "").upper()
        raw_code = str(p.get("alarm_code") or p.get("specific_problem") or p.get("event_type") or "UNKNOWN_ALARM").strip()
        
        canonical_code = raw_code
        if vendor in self.VENDOR_CODE_MAP and raw_code in self.VENDOR_CODE_MAP[vendor]:
            canonical_code = self.VENDOR_CODE_MAP[vendor][raw_code]

        # Severity
        sev_raw = str(p.get("severity") or p.get("perceived_severity") or "UNKNOWN").upper()
        severity = self.SEVERITY_MAP.get(sev_raw, "UNKNOWN")

        # Timestamp
        ts_raw = p.get("timestamp") or p.get("event_time") or envelope.observation_timestamp
        if ts_raw:
            try:
                dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                ts_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Lifecycle & clear time
        lifecycle_raw = str(p.get("lifecycle") or p.get("alarm_status") or "ACTIVE").upper()
        if "CLEAR" in lifecycle_raw:
            lifecycle = AlarmLifecycleState.CLEARED.value
            clear_time = p.get("clear_timestamp") or ts_str
        elif "ACK" in lifecycle_raw:
            lifecycle = AlarmLifecycleState.ACKNOWLEDGED.value
            clear_time = None
        else:
            lifecycle = AlarmLifecycleState.ACTIVE.value
            clear_time = None

        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "alarm_id": alarm_id,
            "incident_id": p.get("incident_id") or envelope.metadata.get("incident_id"),
            "timestamp": ts_str,
            "network_element_id": element_id,
            "network_domain": domain,
            "alarm_code": canonical_code,
            "severity": severity,
            "probable_cause": str(p.get("probable_cause") or p.get("cause") or canonical_code),
            "clear_timestamp": clear_time,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "metadata": {
                "source_system": self.source_system,
                "vendor": vendor if vendor else "GENERIC",
                "vendor_specific_code": raw_code,
                "lifecycle_state": lifecycle,
                "site_id": p.get("site_id"),
                "cell_id": p.get("cell_id"),
                "ingested_at": envelope.ingested_at,
                "ingestion_envelope_id": envelope.envelope_id,
            },
        }

        self.record_success()
        return canonical
