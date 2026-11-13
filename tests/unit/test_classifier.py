"""Unit tests for fault category classification models."""

from pathlib import Path
import pytest
from piis.classification.models import (
    FaultCategoryClassifier,
    compute_classification_metrics,
)


@pytest.fixture
def sample_incidents():
    return [
        {
            "incident_id": f"INC-{i:03d}",
            "title": "Severe RF signal attenuation",
            "description": f"Sector GNB-{i} reports degraded block error rate.",
            "network_domain": "RAN",
            "affected_subscribers": 50 + i,
            "network_element_ids": [f"GNB-{i}"],
            "fault_category": "ran_signal_degradation",
        }
        for i in range(5)
    ] + [
        {
            "incident_id": f"INC-AUTH-{i:03d}",
            "title": "Core authentication timeout",
            "description": f"AUSF-{i} reports HTTP/2 timeout on SBI interface.",
            "network_domain": "5G_CORE",
            "affected_subscribers": 500 + i,
            "network_element_ids": [f"AUSF-{i}"],
            "fault_category": "subscriber_authentication_failure",
        }
        for i in range(5)
    ]


def test_classifier_fit_predict_lr(sample_incidents):
    clf = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf.fit(sample_incidents)

    preds = clf.predict(sample_incidents)
    assert len(preds) == len(sample_incidents)
    assert preds[0] == "ran_signal_degradation"
    assert preds[5] == "subscriber_authentication_failure"

    probs = clf.predict_proba(sample_incidents)
    assert probs.shape == (10, 2)


def test_classifier_fit_predict_rf(sample_incidents):
    clf = FaultCategoryClassifier(model_type="random_forest", random_state=42)
    clf.fit(sample_incidents)

    preds = clf.predict(sample_incidents)
    assert len(preds) == len(sample_incidents)
    assert preds[0] == "ran_signal_degradation"


def test_classifier_save_load(sample_incidents, tmp_path: Path):
    model_path = tmp_path / "test_model.joblib"
    clf = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf.fit(sample_incidents)
    clf.save(model_path)

    assert model_path.exists()
    assert model_path.with_suffix(".json").exists()

    loaded = FaultCategoryClassifier.load(model_path)
    preds_loaded = loaded.predict(sample_incidents)
    assert preds_loaded == clf.predict(sample_incidents)


def test_compute_classification_metrics():
    y_true = ["cat_a", "cat_a", "cat_b", "cat_b"]
    y_pred = ["cat_a", "cat_a", "cat_b", "cat_a"]

    metrics = compute_classification_metrics(y_true, y_pred)
    assert metrics["accuracy"] == 0.75
    assert "macro_f1" in metrics
    assert "per_class" in metrics
    assert "confusion_matrix" in metrics
