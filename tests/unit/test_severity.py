"""Unit tests for incident severity prediction models."""

from pathlib import Path
import pytest
from piis.classification.models import (
    SeverityPredictor,
    compute_classification_metrics,
)


@pytest.fixture
def severity_sample_incidents():
    records = []
    # 5 Critical
    for i in range(5):
        records.append({
            "incident_id": f"INC-CRIT-{i}",
            "title": "Complete base station power outage",
            "description": f"Site {i} totally dark, battery empty.",
            "network_domain": "RAN",
            "affected_subscribers": 1200 + i,
            "network_element_ids": [f"GNB-{i}"],
            "severity": "CRITICAL",
        })
    # 5 Minor
    for i in range(5):
        records.append({
            "incident_id": f"INC-MIN-{i}",
            "title": "PRB utilization congestion alert",
            "description": f"Cell {i} PRB capacity high.",
            "network_domain": "RAN",
            "affected_subscribers": 80 + i,
            "network_element_ids": [f"GNB-C-{i}"],
            "severity": "MINOR",
        })
    return records


def test_severity_predictor_fit_predict(severity_sample_incidents):
    predictor = SeverityPredictor(model_type="logistic_regression", random_state=42)
    predictor.fit(severity_sample_incidents)

    preds = predictor.predict(severity_sample_incidents)
    assert len(preds) == 10
    assert preds[0] == "CRITICAL"
    assert preds[5] == "MINOR"


def test_severity_save_load(severity_sample_incidents, tmp_path: Path):
    path = tmp_path / "severity_test.joblib"
    predictor = SeverityPredictor(model_type="logistic_regression", random_state=42)
    predictor.fit(severity_sample_incidents)
    predictor.save(path)

    loaded = SeverityPredictor.load(path)
    assert loaded.predict(severity_sample_incidents) == predictor.predict(severity_sample_incidents)


def test_high_severity_recall():
    y_true = ["CRITICAL", "MAJOR", "MINOR", "WARNING"]
    y_pred = ["CRITICAL", "MAJOR", "WARNING", "WARNING"]

    metrics = compute_classification_metrics(y_true, y_pred)
    assert metrics["high_severity_recall"] == 1.0
