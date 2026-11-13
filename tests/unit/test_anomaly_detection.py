"""Unit and adversarial tests for telemetry anomaly detection."""

from __future__ import annotations

import pandas as pd
import pytest

from piis.anomaly.isolation_forest import IsolationForestDetector
from piis.anomaly.models import AnomalySeverity
from piis.anomaly.pipeline import TelemetryAnomalyPipeline
from piis.anomaly.statistical import StatisticalThresholdDetector


def test_statistical_detector_surge_and_drop_sensitivity():
    detector = StatisticalThresholdDetector(alpha=0.2, beta=0.1, k_sigma=2.5, min_samples=5)

    # 1. Warm-up with nominal BLER (0.01)
    for _ in range(10):
        detector.update_and_evaluate("DL_BLER", 0.01)

    # BLER is SURGE sensitive: drop should NOT flag
    drop_viol = detector.update_and_evaluate("DL_BLER", 0.001)
    assert drop_viol is None

    # BLER is SURGE sensitive: severe spike SHOULD flag
    surge_viol = detector.update_and_evaluate("DL_BLER", 0.25)
    assert surge_viol is not None
    assert surge_viol.direction == "SURGE"
    assert surge_viol.metric_name == "DL_BLER"
    assert surge_viol.deviation_sigmas >= 2.5

    # 2. Reset and test RSRP (DROP sensitive)
    detector.reset()
    for _ in range(10):
        detector.update_and_evaluate("RSRP", -80.0)

    # RSRP surge (stronger signal) should NOT flag as failure
    surge_rsrp = detector.update_and_evaluate("RSRP", -65.0)
    assert surge_rsrp is None

    # RSRP severe drop (attenuation) SHOULD flag
    drop_rsrp = detector.update_and_evaluate("RSRP", -120.0)
    assert drop_rsrp is not None
    assert drop_rsrp.direction == "DROP"
    assert drop_rsrp.deviation_sigmas >= 2.5


def test_statistical_detector_batch_processing():
    detector = StatisticalThresholdDetector(k_sigma=2.5, min_samples=5)

    # Create synthetic series with a single extreme drop
    timestamps = [f"2026-03-01T10:{i:02d}:00Z" for i in range(20)]
    values = [-80.0] * 15 + [-125.0] + [-80.0] * 4  # spike drop at index 15
    df = pd.DataFrame({
        "timestamp": timestamps,
        "network_element_id": "CELL-101",
        "metric_name": "RSRP",
        "metric_value": values,
        "unit": "dBm",
    })

    violations = detector.detect_batch(df, window_size=10)
    assert len(violations) >= 1
    v = violations[0]
    assert v.metric_name == "RSRP"
    assert v.observed_value == -125.0
    assert v.direction == "DROP"
    assert v.timestamp == "2026-03-01T10:15:00Z"


def test_isolation_forest_fit_and_score():
    # Construct nominal multi-metric telemetry
    records = []
    for i in range(50):
        t = f"2026-03-01T10:{i:02d}:00Z"
        records.append({"timestamp": t, "network_element_id": "GNB-01", "metric_name": "RSRP", "metric_value": -80.0 + (i % 3)})
        records.append({"timestamp": t, "network_element_id": "GNB-01", "metric_name": "DL_BLER", "metric_value": 0.01 + 0.001 * (i % 2)})
    df = pd.DataFrame(records)

    detector = IsolationForestDetector(contamination=0.05, random_state=42)
    with pytest.raises(RuntimeError):
        detector.score(df)

    detector.fit(df)
    assert detector.is_fitted is True

    scores, confs = detector.score(df)
    assert len(scores) == 50
    assert len(confs) == 50
    assert (scores >= 0.0).all() and (scores <= 1.0).all()
    assert (confs >= 0.0).all() and (confs <= 1.0).all()


def test_pipeline_denoising_and_missing_values():
    pipeline = TelemetryAnomalyPipeline(score_threshold=0.50)

    # Data with a single-sample transient spike (sensor glitch) and NaNs
    timestamps = [f"2026-03-01T10:{i:02d}:00Z" for i in range(15)]
    values = [0.01] * 7 + [0.99] + [0.01] * 7  # spike at 7
    values[3] = None  # missing value

    df = pd.DataFrame({
        "timestamp": timestamps,
        "network_element_id": "CELL-101",
        "network_domain": "RAN",
        "metric_name": "DL_BLER",
        "metric_value": values,
        "unit": "ratio",
        "observation_id": [f"OBS-{i}" for i in range(15)],
    })

    clean_df = pipeline._denoise_and_impute(df)
    # Assert missing value was imputed
    assert clean_df["metric_value"].isna().sum() == 0
    # Assert 0.99 glitch was smoothed
    assert clean_df.loc[clean_df["timestamp"] == timestamps[7], "metric_value"].iloc[0] < 0.50


def test_pipeline_full_run_and_severity():
    pipeline = TelemetryAnomalyPipeline(score_threshold=0.40)

    # 15 nominal observations, followed by severe degradation
    records = []
    for i in range(25):
        t = f"2026-03-01T12:{i:02d}:00Z"
        val = 0.01 if i < 18 else 0.85  # sudden surge in BLER
        records.append({
            "observation_id": f"OBS-BLER-{i}",
            "timestamp": t,
            "network_element_id": "CELL-101",
            "network_domain": "RAN",
            "metric_name": "DL_BLER",
            "metric_value": val,
            "unit": "ratio",
            "source_type": "SYNTHETIC",
        })

    anomalies = pipeline.process_records(records, dataset_name="TestDataset")
    assert len(anomalies) > 0

    first_anom = anomalies[0]
    assert first_anom.network_element_id == "CELL-101"
    assert first_anom.network_domain == "RAN"
    assert first_anom.severity in [AnomalySeverity.CRITICAL, AnomalySeverity.MAJOR]
    assert first_anom.epistemic_status == "STATISTICAL_INFERENCE"
    assert first_anom.provenance["source_dataset"] == "TestDataset"
    assert len(first_anom.affected_metrics) >= 1
    assert first_anom.affected_metrics[0].metric_name == "DL_BLER"
