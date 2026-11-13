"""Adversarial and boundary stress tests for Milestone 3.1 verification gate."""

from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from piis.anomaly.pipeline import TelemetryAnomalyPipeline
from piis.correlation.engine import TemporalAlarmCorrelator
from piis.correlation.models import CorrelatedIncidentCluster
from piis.correlation.topology import TelecomTopologyGraph
from piis.impact.analyzer import NetworkImpactAnalyzer


def test_adversarial_same_site_unrelated_alarms_separated():
    """Verify that AlarmCompatibilityPolicy separates incompatible simultaneous alarms on the same node."""
    topo = TelecomTopologyGraph.build_reference_topology()
    correlator = TemporalAlarmCorrelator(topology=topo)

    t0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    # Two simultaneous alarms on CELL-101 with incompatible root causes: RF Hardware vs Software License
    alarms = [
        {"alarm_id": "ALM-HW", "timestamp": t0, "network_element_id": "CELL-101", "network_domain": "RAN", "alarm_code": "ALM-RAN-VSWR-01"},
        {"alarm_id": "ALM-LIC", "timestamp": t0, "network_element_id": "CELL-101", "network_domain": "RAN", "alarm_code": "ALM-LIC-EXPIRE"},
    ]

    clusters = correlator.correlate(alarms)
    # Remediated behavior: The policy identifies RF_HARDWARE vs SOFTWARE_LICENSE as incompatible and separates them
    assert len(clusters) == 2
    c1_alarms = clusters[0].direct_alarm_ids
    c2_alarms = clusters[1].direct_alarm_ids
    assert ("ALM-HW" in c1_alarms and "ALM-LIC" in c2_alarms) or ("ALM-LIC" in c1_alarms and "ALM-HW" in c2_alarms)


def test_adversarial_unknown_element_isolation():
    """Verify that alarms on unmapped network elements form isolated clusters without throwing errors."""
    topo = TelecomTopologyGraph.build_reference_topology()
    correlator = TemporalAlarmCorrelator(topology=topo)

    t0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    alarms = [
        {"alarm_id": "ALM-UNKNOWN", "timestamp": t0, "network_element_id": "NEW-DARK-ROUTER-99", "network_domain": "TRANSPORT"},
        {"alarm_id": "ALM-KNOWN", "timestamp": t0, "network_element_id": "CELL-101", "network_domain": "RAN"},
    ]

    clusters = correlator.correlate(alarms)
    assert len(clusters) == 2
    cluster_elements = [c.affected_elements for c in clusters]
    assert ["NEW-DARK-ROUTER-99"] in cluster_elements
    assert ["CELL-101"] in cluster_elements


def test_adversarial_directed_blast_radius_leaf_isolation():
    """Verify that leaf cell failures do NOT infer parent gNodeB or switch upstream (DEF-M3-003 fixed)."""
    topo = TelecomTopologyGraph.build_reference_topology()
    analyzer = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=1)

    # Leaf cell failure
    cluster = CorrelatedIncidentCluster(
        cluster_id="CLUST-LEAF-TEST",
        earliest_timestamp="2026-03-01T12:00:00Z",
        latest_timestamp="2026-03-01T12:00:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-1"],
        affected_elements=["CELL-101"],
    )

    assessment = analyzer.assess_impact(cluster)
    assert assessment.direct_elements == ["CELL-101"]
    # Upstream parent gNodeB must NOT be inferred
    assert "GNB-TESTBED-5G-01" not in assessment.inferred_elements
    assert assessment.inferred_elements == []
    assert assessment.affected_domains == ["RAN"]


def test_adversarial_directed_blast_radius_parent_cascade():
    """Verify that parent failures correctly infer downstream dependent children."""
    topo = TelecomTopologyGraph.build_reference_topology()
    analyzer = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=1)

    # gNodeB outage
    cluster_gnb = CorrelatedIncidentCluster(
        cluster_id="CLUST-GNB-TEST",
        earliest_timestamp="2026-03-01T12:00:00Z",
        latest_timestamp="2026-03-01T12:00:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-GNB"],
        affected_elements=["GNB-TESTBED-5G-01"],
    )
    assess_gnb = analyzer.assess_impact(cluster_gnb)
    assert assess_gnb.direct_elements == ["GNB-TESTBED-5G-01"]
    assert set(assess_gnb.inferred_elements) == {"CELL-101", "CELL-102", "CELL-103"}
    assert "SW-ACCESS-SITE01" not in assess_gnb.inferred_elements  # Upstream switch is NOT inferred

    # Access Switch outage (multi-hop cascade: depth=2)
    analyzer_2hop = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=2)
    cluster_sw = CorrelatedIncidentCluster(
        cluster_id="CLUST-SW-TEST",
        earliest_timestamp="2026-03-01T12:00:00Z",
        latest_timestamp="2026-03-01T12:00:00Z",
        primary_domain="TRANSPORT",
        involved_domains=["TRANSPORT"],
        direct_alarm_ids=["ALM-SW"],
        affected_elements=["SW-ACCESS-SITE01"],
    )
    assess_sw = analyzer_2hop.assess_impact(cluster_sw)
    assert assess_sw.direct_elements == ["SW-ACCESS-SITE01"]
    assert "GNB-TESTBED-5G-01" in assess_sw.inferred_elements
    assert "CELL-101" in assess_sw.inferred_elements


def test_adversarial_causal_invariance_future_mutations():
    """Verify that changing future observations after timestamp T never alters predictions for t <= T (DEF-M3-002 fixed)."""
    pipe = TelemetryAnomalyPipeline(score_threshold=0.50)

    timestamps = [f"2026-03-01T10:{i:02d}:00Z" for i in range(30)]
    # Nominal baseline for first 15 steps, then degradation
    values_base = [0.01] * 15 + [0.85] * 15

    df_base = pd.DataFrame({
        "timestamp": timestamps,
        "network_element_id": "CELL-101",
        "network_domain": "RAN",
        "metric_name": "DL_BLER",
        "metric_value": values_base,
        "unit": "ratio",
        "observation_id": [f"OBS-{i}" for i in range(30)],
    })

    cutoff_t = timestamps[14]
    anom_base = pipe.process_dataframe(df_base)
    past_preds_base = set(a.start_timestamp for a in anom_base if a.start_timestamp <= cutoff_t)

    # 1. Mutate future with extreme values
    df_future_outliers = df_base.copy()
    df_future_outliers.loc[df_future_outliers["timestamp"] > cutoff_t, "metric_value"] = -9999.0
    anom_future_outliers = pipe.process_dataframe(df_future_outliers)
    past_preds_outliers = set(a.start_timestamp for a in anom_future_outliers if a.start_timestamp <= cutoff_t)
    assert past_preds_base == past_preds_outliers

    # 2. Mutate future with all missing values (NaNs)
    df_future_nans = df_base.copy()
    df_future_nans.loc[df_future_nans["timestamp"] > cutoff_t, "metric_value"] = None
    anom_future_nans = pipe.process_dataframe(df_future_nans)
    past_preds_nans = set(a.start_timestamp for a in anom_future_nans if a.start_timestamp <= cutoff_t)
    assert past_preds_base == past_preds_nans


def test_adversarial_causal_missing_and_irregular_telemetry():
    """Verify graceful handling of leading missing values and duplicate timestamps."""
    pipe = TelemetryAnomalyPipeline(score_threshold=0.40)

    # Missing first 3 values, then normal values, then duplicate timestamp
    timestamps = [
        "2026-03-01T10:00:00Z",
        "2026-03-01T10:01:00Z",
        "2026-03-01T10:02:00Z",
        "2026-03-01T10:03:00Z",
        "2026-03-01T10:04:00Z",
        "2026-03-01T10:04:00Z",  # Duplicate timestamp
        "2026-03-01T10:05:00Z",
    ]
    values = [None, None, None, 0.01, 0.01, 0.01, 0.90]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "network_element_id": "CELL-101",
        "network_domain": "RAN",
        "metric_name": "DL_BLER",
        "metric_value": values,
        "unit": "ratio",
        "observation_id": [f"OBS-{i}" for i in range(len(timestamps))],
    })

    # Should process without exception and impute missing leading values causally
    clean_df = pipe._denoise_and_impute(df)
    assert clean_df["metric_value"].isna().sum() == 0
    assert clean_df.iloc[0]["metric_value"] == 0.0  # leading missing filled with 0.0 causally
