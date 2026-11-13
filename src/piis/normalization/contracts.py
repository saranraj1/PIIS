"""Feature contracts and leakage prevention guards for PIIS prediction models."""

from __future__ import annotations

from typing import Any, Dict, List, Set

# Strictly prohibited post-incident fields that must NEVER enter ticket-time models
POST_RESOLUTION_PROHIBITED_FIELDS: Set[str] = {
    "resolved_at",
    "resolution_summary",
    "root_cause_confirmed",
    "actual_resolution_steps",
    "post_incident_telemetry",
    "confirmed_root_cause",
    "troubleshooting_tickets",
}

# Permitted ticket-time feature fields available at triage timestamp
PERMITTED_TICKET_TIME_FIELDS: Set[str] = {
    "incident_id",
    "title",
    "description",
    "network_domain",
    "affected_region",
    "affected_subscribers",
    "network_element_ids",
    "created_at",
    "source_type",
    "source_dataset",
    "metadata",
}


class PredictionTimeFeatureContract:
    """Enforces strict prediction-time feature contracts and quarantines post-resolution data."""

    def __init__(self, allowed_fields: Set[str] = PERMITTED_TICKET_TIME_FIELDS):
        self.allowed_fields = allowed_fields

    def sanitize_incident_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Strip post-resolution and outcome leakage fields from an incident dictionary."""
        sanitized: Dict[str, Any] = {}
        for k, v in record.items():
            if k in POST_RESOLUTION_PROHIBITED_FIELDS:
                continue
            if k in self.allowed_fields:
                sanitized[k] = v

        return sanitized

    def validate_feature_vector(self, feature_names: List[str]) -> None:
        """Validate that a list of candidate feature names contains zero leaking fields."""
        leaking = [f for f in feature_names if f in POST_RESOLUTION_PROHIBITED_FIELDS]
        if leaking:
            raise ValueError(
                f"Data leakage detected! Prohibited post-resolution fields in feature contract: {leaking}"
            )
