"""
PIIS M5 Final Closure — Comprehensive Temporal Evidence Regression Test Suite.
Validates Workstream D:
1. Observation time governs over ingestion time (delayed ingestion does not disguise stale observations).
2. Stale telemetry in a multi-metric cluster forces safe abstention.
3. Historical context preservation retains older reference cases without triggering staleness abstention.
4. Clock skew tolerance strict boundaries: +55s passes with note; +65s fails and is rejected.
5. Grossly corrupt future timestamps (+43200s) are rejected and flagged.
6. Naive ISO strings without timezone are safely parsed as UTC with warning.
7. Missing timestamps are flagged and rejected.
8. Deterministic backtesting: reference_time overrides ensure deterministic evaluation.
"""

from datetime import datetime, timezone, timedelta
import pytest

from piis.investigation.schemas import EvidenceType, InvestigationEvidenceItem
from piis.investigation.temporal import (
    EvidenceTemporalStatus,
    TemporalEvidenceEvaluator,
    parse_utc_timestamp,
)


@pytest.fixture
def evaluator():
    return TemporalEvidenceEvaluator()


def test_observation_time_governs_over_ingestion_time(evaluator):
    """Verify that observation time governs even if telemetry was ingested seconds ago."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    obs_time = (now - timedelta(hours=3)).isoformat()
    ingest_time = (now - timedelta(seconds=10)).isoformat()

    item = InvestigationEvidenceItem(
        evidence_id="EVID-TEMP-01",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Kafka-Collector-01",
        observed_at=obs_time,
        raw_metadata={"ingested_at": ingest_time},
        content_summary="Optical power -35.2 dBm",
    )
    result = evaluator.evaluate_item(item, reference_time=now)
    assert result.temporal_status == EvidenceTemporalStatus.STALE
    assert result.is_current_confirmation is False
    assert result.age_seconds == pytest.approx(10800, abs=2.0)
    assert "stale" in result.status_detail.lower() or "delayed ingestion" in result.status_detail.lower()


def test_stale_telemetry_in_cluster_forces_safe_abstention(evaluator):
    """Verify that any stale metric in a cluster marks the cluster as containing stale evidence."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    fresh_item = InvestigationEvidenceItem(
        evidence_id="EVID-FRESH-01",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-A",
        observed_at=(now - timedelta(seconds=60)).isoformat(),
        content_summary="VSWR 1.8",
    )
    stale_item = InvestigationEvidenceItem(
        evidence_id="EVID-STALE-01",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-B",
        observed_at=(now - timedelta(hours=4)).isoformat(),
        content_summary="Packet drop 12%",
    )

    incident = {
        "incident_id": "INC-TEST-STALE",
        "created_at": now.isoformat(),
    }
    results, stale_details, defects = evaluator.evaluate_register(
        [fresh_item, stale_item], incident=incident, reference_time=now
    )
    assert len(stale_details) > 0
    assert any("EVID-STALE-01" in s for s in stale_details)


def test_historical_context_preservation_does_not_trigger_staleness(evaluator):
    """Verify that historical incident cases are classified as HISTORICAL_CONTEXT and not stale."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    old_case_time = (now - timedelta(days=90)).isoformat()

    hist_item = InvestigationEvidenceItem(
        evidence_id="EVID-HIST-01",
        evidence_type=EvidenceType.HISTORICAL_CASE,
        source_ref="INC-TELTS-SYNC-0001",
        observed_at=old_case_time,
        content_summary="Resolved PTP jitter by replacing SFP transceiver on Leaf-02.",
    )
    result = evaluator.evaluate_item(hist_item, reference_time=now)
    assert result.temporal_status == EvidenceTemporalStatus.HISTORICAL_CONTEXT
    assert "historical" in result.status_detail.lower()


def test_clock_skew_tolerance_boundary(evaluator):
    """Verify clock skew: +55s is accepted with note; +65s is rejected as future dated."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Within tolerance (+55s)
    item_55s = InvestigationEvidenceItem(
        evidence_id="EVID-SKEW-55",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Edge-DU-01",
        observed_at=(now + timedelta(seconds=55)).isoformat(),
        content_summary="VSWR 1.6",
    )
    res_55s = evaluator.evaluate_item(item_55s, reference_time=now)
    assert res_55s.temporal_status == EvidenceTemporalStatus.CLOCK_SKEW_ACCEPTED
    assert "clock-skew" in res_55s.status_detail.lower()

    # Exceeding tolerance (+65s)
    item_65s = InvestigationEvidenceItem(
        evidence_id="EVID-SKEW-65",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Edge-DU-01",
        observed_at=(now + timedelta(seconds=65)).isoformat(),
        content_summary="VSWR 1.6",
    )
    res_65s = evaluator.evaluate_item(item_65s, reference_time=now)
    assert res_65s.temporal_status == EvidenceTemporalStatus.FUTURE_DATED
    assert "future" in res_65s.status_detail.lower()


def test_grossly_corrupted_future_timestamp_rejected(evaluator):
    """Verify grossly corrupt future timestamp (+43200s, 12 hours) is rejected."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    item_corrupt = InvestigationEvidenceItem(
        evidence_id="EVID-CORRUPT-FUTURE",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Gateway-Clock-Err",
        observed_at=(now + timedelta(hours=12)).isoformat(),
        content_summary="Optical power -28 dBm",
    )
    res = evaluator.evaluate_item(item_corrupt, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.FUTURE_DATED
    assert res.is_current_confirmation is False


def test_naive_iso_timestamp_parsed_safely_as_utc():
    """Verify naive ISO datetime string is safely parsed as UTC with an explicit warning note."""
    naive_str = "2026-11-02T08:15:00"
    dt, note = parse_utc_timestamp(naive_str)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 8
    assert dt.minute == 15
    assert "NAIVE" in note


def test_missing_timestamp_entirely_rejected(evaluator):
    """Verify telemetry observation missing timestamp entirely is rejected."""
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    item_none = InvestigationEvidenceItem(
        evidence_id="EVID-NONE-TS",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Missing-Header-Packet",
        observed_at=None,
        content_summary="Throughput drop",
    )
    res = evaluator.evaluate_item(item_none, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.MISSING_TIMESTAMP
    assert res.is_current_confirmation is False


def test_deterministic_backtesting_with_fixed_reference_time(evaluator):
    """Verify evaluation is 100% deterministic with reference_time override."""
    fixed_ref = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    item = InvestigationEvidenceItem(
        evidence_id="EVID-DETERMINISTIC",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Historical-Playback",
        observed_at="2026-06-15T09:55:00+00:00",
        content_summary="PRB 92%",
    )
    res1 = evaluator.evaluate_item(item, reference_time=fixed_ref)
    res2 = evaluator.evaluate_item(item, reference_time=fixed_ref)
    assert res1.temporal_status == res2.temporal_status == EvidenceTemporalStatus.FRESH
    assert res1.age_seconds == res2.age_seconds == 300.0
