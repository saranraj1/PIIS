"""Normalization pipeline for incident records to canonical schema."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict
import jsonschema

from piis.provenance import SourceType

# Load canonical incident schema
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "incident.schema.json"
with SCHEMA_PATH.open("r", encoding="utf-8") as f:
    INCIDENT_SCHEMA = json.load(f)
VALIDATOR = jsonschema.Draft202012Validator(
    INCIDENT_SCHEMA,
    format_checker=jsonschema.FormatChecker()
)


def validate_canonical_incident(record: Dict[str, Any]) -> None:
    """Validate a single incident record against canonical schema."""
    errors = list(VALIDATOR.iter_errors(record))
    if errors:
        msg = "; ".join(f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors)
        raise jsonschema.ValidationError(f"Invalid canonical incident record: {msg}")


def normalize_telecomts_incident(
    raw_record: Dict[str, Any],
    record_idx: int,
    base_epoch: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    validate: bool = True,
) -> Dict[str, Any]:
    """Transform TelecomTS chunked diagnostic record into canonical incident."""
    anomaly_meta = raw_record.get("anomalies", {})
    ticket_text = anomaly_meta.get("troubleshooting_tickets", "")
    env_desc = raw_record.get("context", {}).get("environment_description", "")
    
    # Anomaly timing
    dur = anomaly_meta.get("anomaly_duration", {})
    start_sec = float(dur.get("start", 0))
    dt_created = base_epoch + pd_to_timedelta_sec(start_sec)
    dt_created_str = dt_created.strftime("%Y-%m-%dT%H:%M:%SZ")

    end_sec = dur.get("end")
    dt_resolved_str = None
    if end_sec is not None:
        dt_resolved = base_epoch + pd_to_timedelta_sec(float(end_sec))
        dt_resolved_str = dt_resolved.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Support level routing ground truth under PIIS policy:
    # Radio jamming interference requires field diagnostics & spectrum analysis -> L2
    support_level = "L2"
    support_rationale = (
        "Active radio frequency interference requires advanced RF spectrum analysis "
        "and physical site triangulation by L2 radio network engineering."
    )

    incident_id = f"INC-TELTS-JAMMER-{record_idx:04d}"
    canonical: Dict[str, Any] = {
        "schema_version": "1.0",
        "incident_id": incident_id,
        "title": "Severe wireless communication degradation from external RF interference",
        "description": f"Testbed incident: {env_desc}. Symptoms: High DL/UL block errors, link degradation.",
        "network_domain": "RAN",
        "fault_category": "rf_jamming_interference",
        "severity": "MAJOR",
        "support_level_label": support_level,
        "support_level_rationale": support_rationale,
        "affected_region": "LAB-TESTBED-ZONE-A",
        "affected_subscribers": 1,
        "network_element_ids": ["GNB-TESTBED-5G-01"],
        "created_at": dt_created_str,
        "resolved_at": dt_resolved_str,
        "resolution_summary": ticket_text,
        "root_cause_confirmed": True,
        "source_type": SourceType.PUBLIC_REAL.value,
        "source_dataset": "AliMaatouk/TelecomTS",
        "source_record_id": f"chunked_record_{record_idx}",
        "scenario_family_id": "RF-JAMMING-01",
        "split_group_id": f"telecomts-run-{record_idx}",
        "annotation_status": "REVIEWED",
        "metadata": {
            "affected_kpis": anomaly_meta.get("affected_kpis", []),
            "zone": raw_record.get("labels", {}).get("zone", "A"),
            "mobility": raw_record.get("labels", {}).get("mobility", "No"),
        },
    }

    if validate:
        validate_canonical_incident(canonical)

    return canonical


def pd_to_timedelta_sec(seconds: float) -> Any:
    """Helper for timedelta conversion."""
    import pandas as pd
    return pd.to_timedelta(seconds, unit="s")
