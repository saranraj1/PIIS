"""Unit tests for PIIS canonical JSON Schemas."""

import json
from pathlib import Path
from typing import Dict
import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def load_schema(name: str) -> Dict:
    path = SCHEMA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def incident_validator():
    return jsonschema.Draft202012Validator(
        load_schema("incident.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


@pytest.fixture
def telemetry_validator():
    return jsonschema.Draft202012Validator(
        load_schema("telemetry.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


@pytest.fixture
def alarm_validator():
    return jsonschema.Draft202012Validator(
        load_schema("alarm.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


@pytest.fixture
def resolution_validator():
    return jsonschema.Draft202012Validator(
        load_schema("resolution.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


@pytest.fixture
def evidence_validator():
    return jsonschema.Draft202012Validator(
        load_schema("evidence.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


@pytest.fixture
def recommendation_validator():
    return jsonschema.Draft202012Validator(
        load_schema("recommendation.schema.json"),
        format_checker=jsonschema.FormatChecker()
    )


def test_valid_incident_record(incident_validator):
    rec = {
        "schema_version": "1.0",
        "incident_id": "INC-TEST-001",
        "title": "Test RAN incident",
        "description": "Baseband processing error on sector 1",
        "network_domain": "RAN",
        "fault_category": "baseband_error",
        "severity": "MAJOR",
        "support_level_label": "L2",
        "support_level_rationale": "Elevated diagnostics required",
        "affected_region": "REGION-NORTH",
        "affected_subscribers": 150,
        "network_element_ids": ["GNB-001"],
        "created_at": "2026-03-01T12:00:00Z",
        "resolved_at": None,
        "resolution_summary": None,
        "root_cause_confirmed": False,
        "source_type": "PUBLIC_REAL",
        "source_dataset": "test_dataset",
        "source_record_id": "rec_001",
        "scenario_family_id": None,
        "split_group_id": None,
        "annotation_status": "REVIEWED",
        "metadata": {"test": True},
    }
    incident_validator.validate(rec)


def test_invalid_incident_missing_required_fields(incident_validator):
    rec = {
        "schema_version": "1.0",
        "title": "Incomplete record",
        # Missing incident_id, description, network_domain, created_at, source_type
    }
    with pytest.raises(jsonschema.ValidationError):
        incident_validator.validate(rec)


def test_invalid_incident_illegal_enum(incident_validator):
    rec = {
        "schema_version": "1.0",
        "incident_id": "INC-ERR-001",
        "description": "Invalid domain test",
        "network_domain": "INVALID_DOMAIN_VALUE",
        "created_at": "2026-03-01T12:00:00Z",
        "source_type": "PUBLIC_REAL",
    }
    with pytest.raises(jsonschema.ValidationError):
        incident_validator.validate(rec)


def test_valid_telemetry_record(telemetry_validator):
    rec = {
        "schema_version": "1.0",
        "observation_id": "OBS-001",
        "incident_id": "INC-TEST-001",
        "timestamp": "2026-03-01T12:00:00.123Z",
        "network_element_id": "GNB-001",
        "network_domain": "RAN",
        "metric_name": "RSRP",
        "metric_value": -85.5,
        "unit": "dBm",
        "source_type": "PUBLIC_REAL",
        "source_dataset": "test_ds",
        "source_record_id": "row_1",
        "original_timezone": "UTC",
        "metadata": {},
    }
    telemetry_validator.validate(rec)


def test_valid_alarm_record(alarm_validator):
    rec = {
        "schema_version": "1.0",
        "alarm_id": "ALM-001",
        "incident_id": "INC-TEST-001",
        "timestamp": "2026-03-01T12:00:00Z",
        "network_element_id": "GNB-001",
        "network_domain": "RAN",
        "alarm_code": "ALM-RAN-VSWR-01",
        "severity": "CRITICAL",
        "probable_cause": "Antenna line mismatch",
        "clear_timestamp": None,
        "source_type": "PUBLIC_REAL",
        "source_dataset": "test_ds",
        "source_record_id": "alm_row_1",
        "metadata": {},
    }
    alarm_validator.validate(rec)


def test_valid_evidence_record(evidence_validator):
    rec = {
        "evidence_id": "EVID-001",
        "evidence_type": "TELEMETRY",
        "source_type": "PUBLIC_REAL",
        "source_ref": "OBS-001",
        "observed_at": "2026-03-01T12:00:00Z",
        "excerpt": "RSRP dropped to -115 dBm",
        "trust_status": "SOURCE_VALIDATED",
        "metadata": {},
    }
    evidence_validator.validate(rec)


def test_valid_recommendation_record(recommendation_validator):
    rec = {
        "recommendation_id": "REC-001",
        "incident_id": "INC-TEST-001",
        "decision": "L2",
        "severity_recommendation": "MAJOR",
        "observed_facts": ["RSRP -115 dBm", "High BLER"],
        "model_predictions": ["fault_category: radio_degradation (0.92)"],
        "hypotheses": ["Antenna feeder moisture ingress"],
        "recommended_checks": ["Measure VSWR", "Check RRU amplifier status"],
        "caveats": ["Rain in region may affect millimeter wave band"],
        "evidence_refs": ["EVID-001"],
        "model_version": "classifier-v0.1",
        "policy_version": "1.0",
        "generated_at": "2026-03-01T12:01:00Z",
        "status": "PENDING_REVIEW",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    recommendation_validator.validate(rec)
