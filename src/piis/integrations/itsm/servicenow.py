"""ServiceNow ITSM integration adapter for PIIS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from piis.integrations.contracts import (
    IngestionEnvelope,
    IntegrationAdapter,
    IntegrationType,
    RateLimiter,
)
from piis.provenance import SourceType


class ServiceNowAdapter(IntegrationAdapter):
    """Adapter for ingesting and normalizing incident tickets from ServiceNow."""

    # Explicit mapping from ServiceNow priority values to PIIS canonical severity
    PRIORITY_MAP: Dict[str, str] = {
        "1": "CRITICAL",
        "2": "MAJOR",
        "3": "MINOR",
        "4": "WARNING",
        "5": "WARNING",
    }

    # ServiceNow state mapping to PIIS lifecycle
    STATE_MAP: Dict[str, str] = {
        "1": "NEW",
        "2": "IN_PROGRESS",
        "3": "ON_HOLD",
        "6": "RESOLVED",
        "7": "CLOSED",
        "8": "CANCELED",
    }

    def __init__(
        self,
        adapter_id: str = "ITSM-SERVICENOW-01",
        instance_url: str = "https://telecom.service-now.com",
        rate_limiter: Optional[RateLimiter] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.ITSM,
            source_system="ServiceNow",
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=25.0, burst=50),
        )
        self.instance_url = instance_url
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize raw ServiceNow incident dictionary into canonical PIIS incident record."""
        payload = envelope.raw_payload
        sys_id = str(payload.get("sys_id", "")).strip()
        number = str(payload.get("number", sys_id)).strip()

        if not number:
            raise ValueError("ServiceNow incident missing both 'number' and 'sys_id'")

        # Extract timestamps
        created_on = payload.get("sys_created_on") or envelope.observation_timestamp
        if created_on:
            try:
                # Handle space-separated ServiceNow datetime: 'YYYY-MM-DD HH:MM:SS'
                if " " in created_on and "T" not in created_on:
                    dt = datetime.strptime(created_on, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    created_at_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                elif "T" in created_on:
                    dt = datetime.fromisoformat(created_on.replace("Z", "+00:00"))
                    created_at_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Map priority to canonical severity
        priority_raw = str(payload.get("priority", "3")).strip()
        severity = self.PRIORITY_MAP.get(priority_raw, "MINOR")

        # Resolve network domain
        domain_raw = str(
            payload.get("u_network_domain") or payload.get("category") or "CROSS_DOMAIN"
        ).upper()
        if "TRANSPORT" in domain_raw or "OPTICAL" in domain_raw or "IP" in domain_raw or "ROUTER" in domain_raw:
            network_domain = "TRANSPORT"
        elif "CORE" in domain_raw or "UPF" in domain_raw or "AMF" in domain_raw:
            network_domain = "5G_CORE"
        elif domain_raw == "RAN" or "RAN_" in domain_raw or "RAN-" in domain_raw or "RADIO" in domain_raw or "WIRELESS" in domain_raw:
            network_domain = "RAN"
        else:
            network_domain = "CROSS_DOMAIN"

        # Resolve network elements
        cmdb_ci = payload.get("cmdb_ci")
        network_elements: List[str] = []
        if isinstance(cmdb_ci, str) and cmdb_ci:
            network_elements.append(cmdb_ci.strip())
        elif isinstance(cmdb_ci, dict) and "name" in cmdb_ci:
            network_elements.append(str(cmdb_ci["name"]).strip())
        elif isinstance(payload.get("network_element_ids"), list):
            network_elements = [str(x) for x in payload["network_element_ids"]]

        if not network_elements:
            network_elements = ["UNKNOWN_CI"]

        # Parse affected subscribers
        subscribers = 0
        try:
            subscribers = int(payload.get("u_affected_subscribers", 0))
        except (ValueError, TypeError):
            subscribers = 0

        # Map assignment group to canonical support level enum ['L1', 'L2', 'L3', 'HUMAN_REVIEW', 'UNLABELED']
        grp_raw = str(payload.get("support_level_label") or payload.get("assignment_group") or "L1").upper()
        if "L3" in grp_raw or "TIER-3" in grp_raw or "TIER 3" in grp_raw:
            support_level = "L3"
        elif "L2" in grp_raw or "TIER-2" in grp_raw or "TIER 2" in grp_raw:
            support_level = "L2"
        elif "L1" in grp_raw or "TIER-1" in grp_raw or "TIER 1" in grp_raw or "NOC" in grp_raw:
            support_level = "L1"
        else:
            support_level = "HUMAN_REVIEW"

        # Construct canonical incident record
        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "incident_id": f"INC-SNOW-{number}",
            "title": str(payload.get("short_description") or "ServiceNow Incident").strip(),
            "description": str(payload.get("description") or payload.get("short_description") or "").strip(),
            "network_domain": network_domain,
            "fault_category": str(payload.get("u_fault_category") or payload.get("subcategory") or "unspecified_outage"),
            "severity": severity,
            "support_level_label": support_level,
            "support_level_rationale": "Ingested from ServiceNow ticket assignment group",
            "affected_region": str(payload.get("location") or payload.get("u_region") or "GLOBAL"),
            "affected_subscribers": max(0, subscribers),
            "network_element_ids": network_elements,
            "created_at": created_at_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "source_dataset": "ServiceNow-ITSM",
            "source_record_id": number,
            "metadata": {
                "servicenow_sys_id": sys_id,
                "servicenow_number": number,
                "external_state": self.STATE_MAP.get(str(payload.get("state", "1")), "UNKNOWN"),
                "raw_priority": priority_raw,
                "raw_urgency": str(payload.get("urgency", "")),
                "raw_impact": str(payload.get("impact", "")),
                "caller_id": str(payload.get("caller_id", "")),
                "ingestion_envelope_id": envelope.envelope_id,
            },
        }

        self.record_success()
        return canonical
