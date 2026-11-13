"""Unit tests for normalization pipelines."""

import json
from pathlib import Path
import pytest

from piis.normalization.telemetry import (
    normalize_telecomts_telemetry,
    normalize_ucc5g_telemetry,
)
from piis.normalization.incidents import normalize_telecomts_incident


def test_telecomts_telemetry_normalization():
    p = Path("data/raw/SRC-002/jammer_metrics.csv")
    if not p.exists():
        pytest.skip("SRC-002 raw dataset not acquired")

    records = normalize_telecomts_telemetry(p, max_rows=3, validate=True)
    assert len(records) > 0

    first = records[0]
    assert first["schema_version"] == "1.0"
    assert first["source_type"] == "PUBLIC_REAL"
    assert first["source_dataset"] == "AliMaatouk/TelecomTS"
    assert first["network_domain"] == "RAN"
    assert "timestamp" in first
    assert first["timestamp"].endswith("Z")
    assert isinstance(first["metric_value"], (int, float))


def test_ucc5g_telemetry_normalization():
    sample_files = list(Path("data/raw/SRC-005/unpacked").rglob("*.csv"))
    if not sample_files:
        pytest.skip("SRC-005 unpacked traces not present")

    records = normalize_ucc5g_telemetry(sample_files[0], max_rows=3, validate=True)
    assert len(records) > 0

    first = records[0]
    assert first["schema_version"] == "1.0"
    assert first["source_type"] == "PUBLIC_REAL"
    assert first["source_dataset"] == "uccmisl/5Gdataset"
    assert first["network_element_id"].startswith("CELL-")
    assert first["original_timezone"] == "Europe/Dublin"


def test_telecomts_incident_normalization():
    p = Path("data/raw/SRC-002/jammer_chunked.jsonl")
    if not p.exists():
        pytest.skip("SRC-002 chunked.jsonl not present")

    line = p.read_text(encoding="utf-8").splitlines()[0]
    raw_obj = json.loads(line)
    inc = normalize_telecomts_incident(raw_obj, record_idx=0, validate=True)

    assert inc["incident_id"] == "INC-TELTS-JAMMER-0000"
    assert inc["network_domain"] == "RAN"
    assert inc["fault_category"] == "rf_jamming_interference"
    assert inc["severity"] == "MAJOR"
    assert inc["support_level_label"] == "L2"
    assert inc["root_cause_confirmed"] is True
    assert inc["source_type"] == "PUBLIC_REAL"
