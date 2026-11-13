"""Unit tests for UI-4.1 Telemetry Temporal Integrity, Causal Envelopes, and Impact Grounding."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest

from piis.anomaly.pipeline import TelemetryAnomalyPipeline
from piis.correlation.engine import TemporalAlarmCorrelator
from piis.correlation.topology import TelecomTopologyGraph
from piis.impact.analyzer import NetworkImpactAnalyzer
from piis.correlation.models import CorrelatedIncidentCluster


def _generate_telemetry_series(
    element_id: str,
    metric_name: str,
    start_time: datetime,
    values: List[float],
    unit: str = "%",
) -> List[Dict[str, Any]]:
    """Helper to generate chronological telemetry records."""
    records = []
    for idx, val in enumerate(values):
        t = (start_time + timedelta(seconds=idx * 60)).isoformat()
        records.append({
            "observation_id": f"obs-{element_id}-{idx:03d}",
            "network_element_id": element_id,
            "network_domain": "RAN",
            "metric_name": metric_name,
            "metric_value": val,
            "unit": unit,
            "timestamp": t,
            "is_imputed": False,
        })
    return records


class TestTelemetryTemporalIntegrity:
    """Verifies that TelemetryAnomalyPipeline adheres to strict causal temporal ordering."""

    def test_future_mutation_does_not_alter_past_predictions(self):
        """Mutating future observations at t >= 15 MUST NOT alter anomaly outcomes at t < 15."""
        base_time = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
        # 15 nominal samples around 30.0 with minor variation
        past_values = [30.0, 31.0, 29.5, 30.5, 32.0, 28.5, 31.2, 30.1, 29.8, 30.4, 31.1, 29.9, 30.2, 31.5, 30.0]
        past_records = _generate_telemetry_series("GNB-SITE01", "PRB_UTIL_DL", base_time, past_values)

        pipeline_a = TelemetryAnomalyPipeline()
        anomalies_past_only = pipeline_a.process_records(past_records)

        # Now append 5 future samples at t=15..19 with extreme spikes (100.0)
        future_spikes = [100.0, 99.0, 100.0, 98.5, 100.0]
        future_records = _generate_telemetry_series(
            "GNB-SITE01",
            "PRB_UTIL_DL",
            base_time + timedelta(seconds=15 * 60),
            future_spikes,
        )
        combined_records = past_records + future_records

        pipeline_b = TelemetryAnomalyPipeline()
        anomalies_with_future = pipeline_b.process_records(combined_records)

        # Isolate anomalies occurring during the past window (first 15 minutes)
        cutoff_iso = (base_time + timedelta(seconds=14 * 60)).isoformat()
        past_window_anoms = [a for a in anomalies_with_future if a.start_timestamp <= cutoff_iso]

        # In a strictly causal system, past anomaly detections are completely invariant to future spikes
        assert len(past_window_anoms) == len(anomalies_past_only)
        for a_past, a_comb in zip(anomalies_past_only, past_window_anoms):
            assert a_past.anomaly_id == a_comb.anomaly_id
            assert a_past.anomaly_score == a_comb.anomaly_score
            assert a_past.start_timestamp == a_comb.start_timestamp

    def test_causal_forward_imputation_no_future_leakage(self):
        """Denoising and imputation must only use past information (ffill limit=3, no bfill)."""
        base_time = datetime(2026, 11, 3, 11, 0, 0, tzinfo=timezone.utc)
        # Series with a missing gap (None) followed by a massive surge
        records = [
            {"network_element_id": "GNB-01", "network_domain": "RAN", "metric_name": "PRB_UTIL_DL", "metric_value": 20.0, "timestamp": (base_time + timedelta(minutes=0)).isoformat()},
            {"network_element_id": "GNB-01", "network_domain": "RAN", "metric_name": "PRB_UTIL_DL", "metric_value": 21.0, "timestamp": (base_time + timedelta(minutes=1)).isoformat()},
            {"network_element_id": "GNB-01", "network_domain": "RAN", "metric_name": "PRB_UTIL_DL", "metric_value": None, "timestamp": (base_time + timedelta(minutes=2)).isoformat()},
            {"network_element_id": "GNB-01", "network_domain": "RAN", "metric_name": "PRB_UTIL_DL", "metric_value": 95.0, "timestamp": (base_time + timedelta(minutes=3)).isoformat()},
        ]

        pipeline = TelemetryAnomalyPipeline()
        import pandas as pd
        df = pd.DataFrame(records)
        cleaned = pipeline._denoise_and_impute(df)

        # Index 2 had None. It should forward-fill with 21.0, NOT backward-fill with 95.0
        val_at_gap = cleaned.loc[2, "metric_value"]
        assert val_at_gap == pytest.approx(21.0, abs=1e-3), "Missing value backward-filled from future surge!"

    def test_insufficient_samples_warmup_safety(self):
        """Fewer than min_samples (10) should not emit spurious anomaly breaches during warm-up."""
        base_time = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        few_samples = [20.0, 25.0, 22.0, 24.0]
        records = _generate_telemetry_series("GNB-01", "PRB_UTIL_DL", base_time, few_samples)

        pipeline = TelemetryAnomalyPipeline()
        anomalies = pipeline.process_records(records)
        # Should be empty because sample count < 10 warm-up threshold
        assert len(anomalies) == 0

    def test_empty_records_returns_empty_safely(self):
        """Empty input records should return empty anomaly list without exceptions."""
        pipeline = TelemetryAnomalyPipeline()
        assert pipeline.process_records([]) == []


class TestNetworkImpactGrounding:
    """Verifies that NetworkImpactAnalyzer distinguishes zero capacity from unknown capacity."""

    def test_distinguishes_unknown_from_zero_subscribers(self):
        """When an element has no registered nominal subscribers, estimate must be None, not 0."""
        topo = TelecomTopologyGraph()
        # Add transport node with NO subscriber mapping
        topo.add_node("SW-CORE-AGG", domain="TRANSPORT", element_type="SWITCH", nominal_subscribers=None)
        # Add access node with nominal subscribers = 0 (unoccupied testbed)
        topo.add_node("CELL-TEST-ZERO", domain="RAN", element_type="CELL", nominal_subscribers=0)

        analyzer = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=0)

        # Case 1: Target element has no subscriber data
        cluster_unknown = CorrelatedIncidentCluster(
            cluster_id="CLUST-SW",
            earliest_timestamp="2026-11-03T10:00:00Z",
            latest_timestamp="2026-11-03T10:05:00Z",
            primary_domain="TRANSPORT",
            involved_domains=["TRANSPORT"],
            direct_alarm_ids=[],
            telemetry_anomaly_ids=[],
            affected_elements=["SW-CORE-AGG"],
        )
        assess_unknown = analyzer.assess_impact(cluster_unknown)
        assert assess_unknown.estimated_affected_subscribers is None
        assert assess_unknown.subscriber_impact_basis is None

        # Case 2: Target element has explicit 0 subscriber capacity
        cluster_zero = CorrelatedIncidentCluster(
            cluster_id="CLUST-ZERO",
            earliest_timestamp="2026-11-03T10:00:00Z",
            latest_timestamp="2026-11-03T10:05:00Z",
            primary_domain="RAN",
            involved_domains=["RAN"],
            direct_alarm_ids=[],
            telemetry_anomaly_ids=[],
            affected_elements=["CELL-TEST-ZERO"],
        )
        assess_zero = analyzer.assess_impact(cluster_zero)
        assert assess_zero.estimated_affected_subscribers == 0
        assert assess_zero.subscriber_impact_basis is not None
        assert "Aggregated nominal capacity" in assess_zero.subscriber_impact_basis


class TestAlarmCorrelationGrounding:
    """Verifies that alarm correlation outputs retain underlying evidence and derive confidence from affinity."""

    def test_correlation_retains_evidence_and_derives_affinity(self):
        """Correlated clusters retain direct alarm IDs and rationales from edge affinity."""
        topo = TelecomTopologyGraph.build_reference_topology()
        correlator = TemporalAlarmCorrelator(topology=topo)

        alarms = [
            {
                "alarm_id": "ALM-001",
                "network_element_id": "GNB-TESTBED-5G-01",
                "domain": "RAN",
                "alarm_code": "CELL-UNAVAILABLE",
                "severity": "CRITICAL",
                "timestamp": "2026-11-03T10:00:00Z",
                "probable_cause": "Radio link failure",
            },
            {
                "alarm_id": "ALM-002",
                "network_element_id": "CELL-101",
                "domain": "RAN",
                "alarm_code": "CELL-DEG",
                "severity": "MAJOR",
                "timestamp": "2026-11-03T10:01:00Z",
                "probable_cause": "Downstream degradation",
            },
        ]

        clusters = correlator.correlate(alarms=alarms)
        assert len(clusters) == 1
        cluster = clusters[0]

        # Retains underlying evidence
        assert "ALM-001" in cluster.direct_alarm_ids
        assert "ALM-002" in cluster.direct_alarm_ids
        assert "GNB-TESTBED-5G-01" in cluster.affected_elements
        assert "CELL-101" in cluster.affected_elements

        # Correlation edges and rationales
        assert len(cluster.correlation_edges) >= 1
        edge = cluster.correlation_edges[0]
        assert edge.affinity_score > 0.0
        assert "hop distance" in edge.rationale_text or "same element" in edge.rationale_text
        assert cluster.epistemic_status == "HYPOTHESIS"
