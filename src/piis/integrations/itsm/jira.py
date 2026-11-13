"""Jira Service Management (JSM) integration adapter for PIIS."""

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


class JiraServiceManagementAdapter(IntegrationAdapter):
    """Adapter for ingesting and normalizing incident issues from Jira Service Management."""

    PRIORITY_MAP: Dict[str, str] = {
        "Highest": "CRITICAL",
        "High": "MAJOR",
        "Medium": "MINOR",
        "Low": "WARNING",
        "Lowest": "WARNING",
    }

    def __init__(
        self,
        adapter_id: str = "ITSM-JIRA-01",
        cloud_url: str = "https://telecom.atlassian.net",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(
            adapter_id=adapter_id,
            adapter_type=IntegrationType.ITSM,
            source_system="JiraServiceManagement",
            rate_limiter=rate_limiter or RateLimiter(requests_per_second=20.0, burst=40),
        )
        self.cloud_url = cloud_url

    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize raw Jira issue payload into canonical PIIS incident record."""
        payload = envelope.raw_payload
        issue_key = str(payload.get("key") or payload.get("id") or "").strip()
        if not issue_key:
            raise ValueError("Jira payload missing 'key' and 'id'")

        fields = payload.get("fields", payload)
        summary = str(fields.get("summary") or "Jira Incident").strip()
        description = fields.get("description", "")
        if isinstance(description, dict):
            # Atlassian Document Format (ADF) handling: extract text nodes
            description = self._extract_adf_text(description)
        else:
            description = str(description or summary).strip()

        # Parse creation timestamp
        created_raw = fields.get("created") or envelope.observation_timestamp
        if created_raw:
            try:
                # ISO formats with timezone offsets: e.g. 2026-11-02T08:30:00.000+0000
                dt = datetime.fromisoformat(created_raw.replace("+0000", "+00:00").replace("Z", "+00:00"))
                created_at_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            created_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Priority resolution
        priority_obj = fields.get("priority", {})
        priority_name = priority_obj.get("name") if isinstance(priority_obj, dict) else str(priority_obj)
        severity = self.PRIORITY_MAP.get(priority_name, "MINOR")

        # Network domain extraction from labels or custom fields
        labels = fields.get("labels", [])
        network_domain = "CROSS_DOMAIN"
        for lbl in labels:
            u_lbl = str(lbl).upper().strip()
            if "TRANSPORT" in u_lbl or "OPTICAL" in u_lbl or "IP" in u_lbl:
                network_domain = "TRANSPORT"
                break
            elif "CORE" in u_lbl:
                network_domain = "5G_CORE"
                break
            elif u_lbl == "RAN" or "RAN_" in u_lbl or "RAN-" in u_lbl or "RADIO" in u_lbl:
                network_domain = "RAN"
                break

        # Affected network elements from components or custom fields
        components = fields.get("components", [])
        network_elements = [c.get("name", str(c)) for c in components if isinstance(c, (dict, str))]
        if not network_elements:
            network_elements = ["UNKNOWN_CI"]

        canonical: Dict[str, Any] = {
            "schema_version": "1.0",
            "incident_id": f"INC-JIRA-{issue_key}",
            "title": summary,
            "description": description,
            "network_domain": network_domain,
            "fault_category": str(fields.get("issuetype", {}).get("name", "service_outage")).lower(),
            "severity": severity,
            "support_level_label": "L1",
            "support_level_rationale": "Ingested from Jira Service Management incident queue",
            "affected_region": "GLOBAL",
            "affected_subscribers": 0,
            "network_element_ids": network_elements,
            "created_at": created_at_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.OPERATOR_INTERNAL.value,
            "source_dataset": "Jira-ServiceManagement",
            "source_record_id": issue_key,
            "metadata": {
                "jira_key": issue_key,
                "jira_status": fields.get("status", {}).get("name", "Open") if isinstance(fields.get("status"), dict) else str(fields.get("status")),
                "raw_priority": priority_name,
                "labels": labels,
                "ingestion_envelope_id": envelope.envelope_id,
            },
        }

        self.record_success()
        return canonical

    def _extract_adf_text(self, node: Dict[str, Any]) -> str:
        """Helper to recursively extract text from Atlassian Document Format (ADF) dictionaries."""
        text_parts = []
        if node.get("type") == "text":
            text_parts.append(node.get("text", ""))
        for child in node.get("content", []):
            if isinstance(child, dict):
                text_parts.append(self._extract_adf_text(child))
        return " ".join(filter(None, text_parts))
