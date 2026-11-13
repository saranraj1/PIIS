"""PIIS Milestone M5.5 Workstream A — Temporal Evidence Integrity Test Suite.

Verifies the 18 evaluation scenarios required by Phase A5:
1. Fresh telemetry (within threshold) -> FRESH, SUPPORTED
2. Telemetry older than configured threshold -> STALE, SAFE_ABSTAIN
3. Telemetry exactly at threshold (age == max_age) -> FRESH
4. Telemetry just beyond threshold (age == max_age + 1s) -> STALE
5. Observation captured 72 hours before incident creation -> STALE, SAFE_ABSTAIN
6. Historical incident evidence with valid historical relevance -> HISTORICAL_CONTEXT retained
7. Old telemetry received recently (ingested recently, observed old) -> STALE (observation time governs)
8. Delayed ingestion -> Flagged as delayed, observation age governs
9. Missing observation timestamp -> MISSING_TIMESTAMP, SAFE_ABSTAIN
10. Invalid timestamp -> INVALID_TIMESTAMP, SAFE_ABSTAIN
11. Naive timestamp -> Safely converted to UTC with explicit normalization note
12. Future timestamp exceeding skew tolerance -> FUTURE_DATED, SAFE_ABSTAIN
13. Clock skew within tolerance (+45s future) -> CLOCK_SKEW_ACCEPTED
14. Mixed fresh and stale observations -> Fresh confirmed, stale flagged
15. Fresh alarm with stale supporting telemetry -> STALE, SAFE_ABSTAIN
16. Stale alarm with fresh independent evidence -> Stale alarm flagged, fresh evidence evaluated
17. Multiple sources with different freshness policies -> Evaluated under respective source policies
18. Persistent incident with intermittent fresh samples -> Corroborated active
"""

from datetime import datetime, timedelta, timezone
import pytest

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import (
    EvidenceType,
    HypothesisStatus,
    InvestigationEvidenceItem,
)
from piis.investigation.temporal import (
    EvidenceTemporalStatus,
    TemporalEvidenceEvaluator,
    parse_utc_timestamp,
)
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


@pytest.fixture(scope="module")
def investigation_engine():
    docs, chunks = build_knowledge_base()
    retrieval_engine = HybridRetrievalEngine()
    retrieval_engine.index_chunks(chunks)
    return IncidentInvestigationEngine(retrieval_engine=retrieval_engine)


@pytest.fixture
def evaluator():
    return TemporalEvidenceEvaluator()


# =========================================================================
# 1. Fresh telemetry
# =========================================================================
def test_01_fresh_telemetry_within_threshold(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(seconds=120)).isoformat()
    item = InvestigationEvidenceItem(
        evidence_id="EVID-001",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-01",
        observed_at=obs_time,
        content_summary="PRB utilization 88%",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.FRESH
    assert res.is_current_confirmation is True
    assert res.age_seconds == pytest.approx(120, abs=1.0)


# =========================================================================
# 2. Telemetry older than configured threshold (3600s)
# =========================================================================
def test_02_telemetry_older_than_threshold(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(seconds=4500)).isoformat()
    item = InvestigationEvidenceItem(
        evidence_id="EVID-002",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-01",
        observed_at=obs_time,
        content_summary="PRB utilization 88%",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.STALE
    assert res.is_current_confirmation is False
    assert "exceeds maximum permitted age" in res.status_detail


# =========================================================================
# 3. Telemetry exactly at threshold (3600.0s)
# =========================================================================
def test_03_telemetry_exactly_at_threshold(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(seconds=3600)).isoformat()
    item = InvestigationEvidenceItem(
        evidence_id="EVID-003",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-01",
        observed_at=obs_time,
        content_summary="PRB utilization 88%",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.FRESH
    assert res.is_current_confirmation is True


# =========================================================================
# 4. Telemetry just beyond threshold (3601.0s)
# =========================================================================
def test_04_telemetry_just_beyond_threshold(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(seconds=3601)).isoformat()
    item = InvestigationEvidenceItem(
        evidence_id="EVID-004",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-01",
        observed_at=obs_time,
        content_summary="PRB utilization 88%",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.STALE
    assert res.is_current_confirmation is False


# =========================================================================
# 5. Observation captured 72 hours before incident creation
# =========================================================================
def test_05_observation_72_hours_before_incident(investigation_engine):
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    incident = {
        "incident_id": "INC-72H-TEST",
        "title": "Historical degradation report",
        "description": "Delayed log aggregation uploaded data from 3 days ago. No live telemetry available.",
        "alarm_codes": [],
        "network_element_ids": ["GNB-HIST-01"],
        "network_domain": "RAN",
        "created_at": stale_time,
    }
    ctx = investigation_engine.investigate(incident, m2_classification={}, m3_network_intelligence={})
    assert ctx.sufficiency_report.is_sufficient is False
    assert ctx.sufficiency_report.has_stale_evidence is True
    assert len(ctx.sufficiency_report.stale_evidence_details) > 0
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


# =========================================================================
# 6. Historical incident evidence with valid historical relevance
# =========================================================================
def test_06_historical_incident_evidence_retained(evaluator):
    now = datetime.now(timezone.utc)
    hist_time = (now - timedelta(days=180)).isoformat() # 6 months old
    item = InvestigationEvidenceItem(
        evidence_id="EVID-HIST-01",
        evidence_type=EvidenceType.HISTORICAL_CASE,
        source_ref="INC-2024-FIBER-01",
        observed_at=hist_time,
        content_summary="Prior fiber cut on span A-B resolved via re-splicing.",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.HISTORICAL_CONTEXT
    assert res.is_current_confirmation is False
    assert "HISTORICAL_CONTEXT" in res.status_detail


# =========================================================================
# 7. Old telemetry received recently (Observation time governs!)
# =========================================================================
def test_07_old_telemetry_received_recently(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(hours=48)).isoformat() # 48h old observation
    ingest_time = (now - timedelta(seconds=10)).isoformat() # Ingested 10s ago
    item = InvestigationEvidenceItem(
        evidence_id="EVID-007",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="DelayedProbe-01",
        observed_at=obs_time,
        content_summary="Delayed queue burst telemetry",
    )
    res = evaluator.evaluate_item(item, reference_time=now, ingested_at=ingest_time)
    assert res.temporal_status == EvidenceTemporalStatus.STALE
    assert res.is_current_confirmation is False
    assert res.ingestion_delay_seconds > 86400
    assert "Delayed ingestion" in res.status_detail


# =========================================================================
# 8. Delayed ingestion within fresh observation window
# =========================================================================
def test_08_delayed_ingestion_within_window(evaluator):
    now = datetime.now(timezone.utc)
    obs_time = (now - timedelta(seconds=500)).isoformat()
    ingest_time = (now - timedelta(seconds=100)).isoformat()
    item = InvestigationEvidenceItem(
        evidence_id="EVID-008",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-02",
        observed_at=obs_time,
        content_summary="Slightly delayed probe ingestion",
    )
    res = evaluator.evaluate_item(item, reference_time=now, ingested_at=ingest_time)
    assert res.temporal_status == EvidenceTemporalStatus.FRESH
    assert res.is_current_confirmation is True
    assert res.ingestion_delay_seconds == pytest.approx(400, abs=2.0)


# =========================================================================
# 9. Missing observation timestamp
# =========================================================================
def test_09_missing_observation_timestamp(evaluator):
    now = datetime.now(timezone.utc)
    item = InvestigationEvidenceItem(
        evidence_id="EVID-009",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-NoTime",
        observed_at=None,
        content_summary="Telemetry without timestamp",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.MISSING_TIMESTAMP
    assert res.is_current_confirmation is False


# =========================================================================
# 10. Invalid timestamp
# =========================================================================
def test_10_invalid_timestamp(evaluator):
    now = datetime.now(timezone.utc)
    item = InvestigationEvidenceItem(
        evidence_id="EVID-010",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="CorruptProbe",
        observed_at="corrupted-date-not-iso",
        content_summary="Corrupted telemetry timestamp",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.INVALID_TIMESTAMP
    assert res.is_current_confirmation is False


# =========================================================================
# 11. Naive timestamp converted safely to UTC
# =========================================================================
def test_11_naive_timestamp_converted(evaluator):
    naive_str = "2026-11-01 10:00:00"
    dt, note = parse_utc_timestamp(naive_str)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert "NAIVE" in note


# =========================================================================
# 12. Future timestamp exceeding skew tolerance
# =========================================================================
def test_12_future_timestamp_exceeding_tolerance(evaluator):
    now = datetime.now(timezone.utc)
    future_time = (now + timedelta(seconds=1800)).isoformat() # 30 min future
    item = InvestigationEvidenceItem(
        evidence_id="EVID-012",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="FutureProbe",
        observed_at=future_time,
        content_summary="Telemetry with forward clock drift",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.FUTURE_DATED
    assert res.is_current_confirmation is False
    assert "FUTURE_DATED" in res.status_detail


# =========================================================================
# 13. Clock skew within tolerance (+45s future)
# =========================================================================
def test_13_clock_skew_within_tolerance(evaluator):
    now = datetime.now(timezone.utc)
    skew_time = (now + timedelta(seconds=45)).isoformat() # +45s (< 60s tolerance)
    item = InvestigationEvidenceItem(
        evidence_id="EVID-013",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="SkewProbe",
        observed_at=skew_time,
        content_summary="Telemetry with slight NTP jitter",
    )
    res = evaluator.evaluate_item(item, reference_time=now)
    assert res.temporal_status == EvidenceTemporalStatus.CLOCK_SKEW_ACCEPTED
    assert res.is_current_confirmation is True
    assert "within clock-skew tolerance" in res.status_detail


# =========================================================================
# 14. Mixed fresh and stale observations
# =========================================================================
def test_14_mixed_fresh_and_stale_observations(evaluator):
    now = datetime.now(timezone.utc)
    fresh_item = InvestigationEvidenceItem(
        evidence_id="EVID-F",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="FreshProbe",
        observed_at=(now - timedelta(seconds=120)).isoformat(),
        content_summary="Live VSWR 2.2:1",
    )
    stale_item = InvestigationEvidenceItem(
        evidence_id="EVID-S",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="OldProbe",
        observed_at=(now - timedelta(hours=24)).isoformat(),
        content_summary="Old CPU metric",
    )
    results, stale_details, _ = evaluator.evaluate_register(
        evidence_register=[fresh_item, stale_item],
        incident={"incident_id": "INC-MIX", "created_at": now.isoformat()},
        reference_time=now,
    )
    assert len(results) == 2
    assert results[0].is_current_confirmation is True
    assert results[1].is_current_confirmation is False
    assert len(stale_details) == 1
    assert "EVID-S" in stale_details[0]


# =========================================================================
# 15. Fresh alarm with stale supporting telemetry -> Abstains
# =========================================================================
def test_15_fresh_alarm_with_stale_supporting_telemetry(investigation_engine):
    now = datetime.now(timezone.utc)
    fresh_alarm_time = (now - timedelta(minutes=5)).isoformat()
    stale_telemetry_time = (now - timedelta(hours=48)).isoformat()

    incident = {
        "incident_id": "INC-FRESH-ALM-STALE-TEL",
        "title": "Optical loss of signal with stale telemetry",
        "description": "ALM-TRANS-OPTICAL-LOS raised 5 minutes ago. Fiber trunk A-B.",
        "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
        "network_element_ids": ["OPT-SWITCH-01"],
        "network_domain": "TRANSPORT",
        "created_at": fresh_alarm_time,
    }
    m3 = {
        "anomalies": [
            {
                "network_element_id": "OPT-SWITCH-01",
                "metric_name": "optical_rx_power_dbm",
                "timestamp": stale_telemetry_time,
                "fused_score": 0.95,
            }
        ],
        "alarm_cluster": {
            "cluster_id": "CLUST-OPT-01",
            "cluster_window_start": fresh_alarm_time,
            "dominant_alarm_code": "ALM-TRANS-OPTICAL-LOS",
            "affected_elements": ["OPT-SWITCH-01"],
            "alarm_events": ["ALM-TRANS-OPTICAL-LOS"],
        },
    }
    ctx = investigation_engine.investigate(incident, m2_classification={}, m3_network_intelligence=m3)
    # Stale telemetry prevents automated SOP recommendation
    assert ctx.sufficiency_report.has_stale_evidence is True
    assert ctx.sufficiency_report.is_sufficient is False
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


# =========================================================================
# 16. Stale alarm with fresh independent evidence
# =========================================================================
def test_16_stale_alarm_with_fresh_independent_evidence(evaluator):
    now = datetime.now(timezone.utc)
    stale_alarm_time = (now - timedelta(hours=24)).isoformat()
    fresh_telemetry_time = (now - timedelta(minutes=2)).isoformat()

    alarm_item = InvestigationEvidenceItem(
        evidence_id="EVID-ALM-STALE",
        evidence_type=EvidenceType.ALARM_CLUSTER,
        source_ref="OldAlarmCluster",
        observed_at=stale_alarm_time,
        content_summary="Alarm cluster from yesterday",
    )
    tel_item = InvestigationEvidenceItem(
        evidence_id="EVID-TEL-FRESH",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="LiveProbe",
        observed_at=fresh_telemetry_time,
        content_summary="Live current metric anomaly",
    )

    res_alarm = evaluator.evaluate_item(alarm_item, reference_time=now)
    res_tel = evaluator.evaluate_item(tel_item, reference_time=now)

    assert res_alarm.temporal_status == EvidenceTemporalStatus.STALE
    assert res_alarm.is_current_confirmation is False
    assert res_tel.temporal_status == EvidenceTemporalStatus.FRESH
    assert res_tel.is_current_confirmation is True


# =========================================================================
# 17. Multiple sources with different freshness policies
# =========================================================================
def test_17_multiple_sources_different_freshness_policies(evaluator):
    now = datetime.now(timezone.utc)
    
    # Telemetry: threshold 3600s -> 5000s is STALE
    item_tel = InvestigationEvidenceItem(
        evidence_id="EVID-T17",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Probe-17",
        observed_at=(now - timedelta(seconds=5000)).isoformat(),
        content_summary="Telemetry 5000s old",
    )
    # Topology: threshold 86400s -> 5000s is FRESH
    item_top = InvestigationEvidenceItem(
        evidence_id="EVID-TOP17",
        evidence_type=EvidenceType.TOPOLOGY_IMPACT,
        source_ref="TopologyAnalyzer",
        observed_at=(now - timedelta(seconds=5000)).isoformat(),
        content_summary="Topology 5000s old",
    )
    # Runbook: threshold 1 yr -> 30 days is FRESH
    item_run = InvestigationEvidenceItem(
        evidence_id="EVID-RUN17",
        evidence_type=EvidenceType.APPROVED_RUNBOOK,
        source_ref="SOP-VSWR",
        observed_at=(now - timedelta(days=30)).isoformat(),
        content_summary="Runbook SOP-RAN-VSWR-001",
    )

    res_tel = evaluator.evaluate_item(item_tel, reference_time=now)
    res_top = evaluator.evaluate_item(item_top, reference_time=now)
    res_run = evaluator.evaluate_item(item_run, reference_time=now)

    assert res_tel.temporal_status == EvidenceTemporalStatus.STALE
    assert res_top.temporal_status == EvidenceTemporalStatus.FRESH
    assert res_run.temporal_status == EvidenceTemporalStatus.FRESH


# =========================================================================
# 18. Persistent incident with intermittent fresh samples
# =========================================================================
def test_18_persistent_incident_with_intermittent_fresh_samples(investigation_engine):
    now = datetime.now(timezone.utc)
    fresh_time = (now - timedelta(minutes=3)).isoformat()
    incident = {
        "incident_id": "INC-PERSISTENT-18",
        "title": "Persistent radio link degradation",
        "description": "Continuous high return loss on AAU antenna port. Multiple periodic samples confirm ongoing state.",
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        "network_element_ids": ["gNodeB-101"],
        "network_domain": "RAN",
        "created_at": fresh_time,
    }
    m2 = {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.94}
    m3 = {
        "anomalies": [
            {
                "network_element_id": "gNodeB-101",
                "metric_name": "vswr",
                "timestamp": fresh_time,
                "fused_score": 0.92,
            }
        ],
        "alarm_cluster": {
            "cluster_id": "CLUST-18",
            "cluster_window_start": fresh_time,
            "dominant_alarm_code": "ALM-RAN-VSWR-HIGH",
            "affected_elements": ["gNodeB-101"],
            "alarm_events": ["ALM-RAN-VSWR-HIGH"],
        },
    }
    ctx = investigation_engine.investigate(incident, m2_classification=m2, m3_network_intelligence=m3)
    assert ctx.sufficiency_report.is_sufficient is True
    assert ctx.sufficiency_report.has_stale_evidence is False
    assert ctx.hypotheses[0].status == HypothesisStatus.SUPPORTED
    assert ctx.recommendations[0].source_runbook_id == "SOP-RAN-VSWR-001"
