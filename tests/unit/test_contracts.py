"""Unit tests for prediction-time feature contracts and leakage guards."""

import pytest
from piis.normalization.contracts import (
    POST_RESOLUTION_PROHIBITED_FIELDS,
    PredictionTimeFeatureContract,
)


def test_contract_sanitizes_post_resolution_fields():
    contract = PredictionTimeFeatureContract()
    leaky_incident = {
        "incident_id": "INC-TEST-001",
        "title": "Degraded sector",
        "description": "Customer calls reporting low throughput",
        "network_domain": "RAN",
        "created_at": "2026-03-01T12:00:00Z",
        # Leaky post-resolution fields:
        "resolved_at": "2026-03-01T14:30:00Z",
        "resolution_summary": "Replaced faulty antenna jumper cable",
        "root_cause_confirmed": True,
        "source_type": "PUBLIC_REAL",
    }

    sanitized = contract.sanitize_incident_record(leaky_incident)

    # Permitted fields remain
    assert sanitized["incident_id"] == "INC-TEST-001"
    assert sanitized["title"] == "Degraded sector"
    assert sanitized["network_domain"] == "RAN"
    assert sanitized["created_at"] == "2026-03-01T12:00:00Z"

    # Prohibited fields must be stripped completely
    for prohibited in POST_RESOLUTION_PROHIBITED_FIELDS:
        assert prohibited not in sanitized


def test_contract_validates_feature_vector_rejects_leakage():
    contract = PredictionTimeFeatureContract()

    safe_features = ["word_count", "domain_ran", "rsrp_mean", "subscriber_count"]
    contract.validate_feature_vector(safe_features)  # Must pass

    leaky_features = ["word_count", "rsrp_mean", "resolution_summary"]
    with pytest.raises(ValueError, match="Data leakage detected"):
        contract.validate_feature_vector(leaky_features)
