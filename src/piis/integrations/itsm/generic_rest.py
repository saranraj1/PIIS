"""Generic REST ITSM adapter with customizable field mappings for proprietary ticketing systems."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from piis.integrations.contracts import (
    IngestionEnvelope,
    IntegrationAdapter,
    IntegrationType,
    RateLimiter,
)
from piis.provenance import SourceType


class GenericRestITSMAdapter(IntegrationAdapter):
    """Configurable adapter mapping generic REST JSON payloads to canonical incidents."""

    def __init__(
        self,
        adapter_id: str = "ITSM-GENERIC-01",
        source_system: str = "GenericITSM",
        field_mapping: Optional[Dict[str, str]] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.ITSM,
            source_system=source_system,
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=30.0, burst=60),
        )
        self.field_mapping = field_mapping or {
            "id": "incident_id",
            "title": "title",
            "description": "description",
            "domain": "network_domain",
            "severity": "severity",
            "created_at": "created_at",
            "elements": "network_element_ids",
        }

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize payload using configurable field mappings."""
        p = envelope.raw_payload
        m = self.field_mapping

        raw_id = str(p.get(m.get("id", "id")) or envelope.external_event_id or envelope.envelope_id)
        raw_title = str(p.get(m.get("title", "title")) or "Generic Telecom Incident").strip()
        raw_desc = str(p.get(m.get("description", "description")) or raw_title).strip()
        raw_domain = str(p.get(m.get("domain", "domain")) or "CROSS_DOMAIN").upper()
        raw_sev = str(p.get(m.get("severity", "severity")) or "MINOR").upper()

        if raw_sev not in {"CRITICAL", "MAJOR", "MINOR", "WARNING"}:
            raw_sev = "MINOR"

        elements = p.get(m.get("elements", "elements"), ["GENERIC_ELEMENT"])
        if isinstance(elements, str):
            elements = [elements]

        created_at_raw = p.get(m.get("created_at", "created_at")) or envelope.observation_timestamp
        if not created_at_raw:
            created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            try:
                dt = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
                created_at_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if "CORE" in raw_domain:
            domain_val = "5G_CORE"
        elif raw_domain in {"RAN", "TRANSPORT", "SERVICE"}:
            domain_val = raw_domain
        else:
            domain_val = "CROSS_DOMAIN"

        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "incident_id": f"INC-{self.source_system.upper()}-{raw_id}",
            "title": raw_title,
            "description": raw_desc,
            "network_domain": domain_val,
            "fault_category": str(p.get("category", "unspecified_outage")).lower(),
            "severity": raw_sev,
            "support_level_label": "L1",
            "support_level_rationale": "Ingested from generic REST ticketing interface",
            "affected_region": str(p.get("region", "GLOBAL")),
            "affected_subscribers": int(p.get("subscribers", 0)),
            "network_element_ids": [str(e) for e in elements],
            "created_at": created_at_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "source_dataset": f"{self.source_system}-ITSM",
            "source_record_id": raw_id,
            "metadata": {
                "source_system": self.source_system,
                "ingestion_envelope_id": envelope.envelope_id,
                "raw_fields": p,
            },
        }

        self.record_success()
        return canonical
