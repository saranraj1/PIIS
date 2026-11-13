"""Unit tests for network impact analysis and blast radius quantification."""

from __future__ import annotations

from piis.correlation.models import CorrelatedIncidentCluster
from piis.correlation.topology import TelecomTopologyGraph
from piis.impact.analyzer import NetworkImpactAnalyzer


def test_impact_analyzer_direct_and_inferred_elements():
    topo = TelecomTopologyGraph.build_reference_topology()
    analyzer = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=1)

    # 1. Leaf node failure (CELL-101): Has no downstream dependencies, so inferred elements should be empty
    cluster_leaf = CorrelatedIncidentCluster(
        cluster_id="CLUST-TEST-001",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:05:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-1"],
        telemetry_anomaly_ids=[],
        affected_elements=["CELL-101"],
        correlation_edges=[],
    )
    assess_leaf = analyzer.assess_impact(cluster_leaf)
    assert assess_leaf.cluster_id == "CLUST-TEST-001"
    assert assess_leaf.direct_elements == ["CELL-101"]
    assert assess_leaf.inferred_elements == []  # Strictly downstream: no false upstream inference!
    assert assess_leaf.total_element_count == 1
    assert assess_leaf.affected_domains == ["RAN"]

    # 2. Parent node failure (GNB-TESTBED-5G-01): Downstream cells are correctly inferred
    cluster_parent = CorrelatedIncidentCluster(
        cluster_id="CLUST-TEST-002",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:05:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-2"],
        telemetry_anomaly_ids=[],
        affected_elements=["GNB-TESTBED-5G-01"],
        correlation_edges=[],
    )
    assess_parent = analyzer.assess_impact(cluster_parent)
    assert assess_parent.direct_elements == ["GNB-TESTBED-5G-01"]
    assert set(assess_parent.inferred_elements) == {"CELL-101", "CELL-102", "CELL-103"}
    assert "SW-ACCESS-SITE01" not in assess_parent.inferred_elements  # Upstream switch is NOT inferred!
    assert assess_parent.total_element_count == 4
    assert assess_parent.epistemic_status == "DERIVED_ESTIMATE"


def test_zero_fabrication_subscriber_impact():
    topo = TelecomTopologyGraph.build_reference_topology()
    analyzer = NetworkImpactAnalyzer(topology=topo)

    # 1. Elements with nominal subscribers in reference topology
    # CELL-101 has 1500 nominal subscribers (leaf)
    cluster_leaf = CorrelatedIncidentCluster(
        cluster_id="CLUST-TEST-SUBS",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:00:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-1"],
        affected_elements=["CELL-101"],
    )
    assess_leaf = analyzer.assess_impact(cluster_leaf)
    assert assess_leaf.estimated_affected_subscribers == 1500
    assert "nominal capacity" in assess_leaf.subscriber_impact_basis
    assert "Not dynamically observed from active UE counters" in assess_leaf.subscriber_impact_basis

    # Parent GNB failure impacts GNB (5000) + 3 cells (1500 + 1500 + 2000) = 10000
    cluster_parent = CorrelatedIncidentCluster(
        cluster_id="CLUST-TEST-PARENT",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:00:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-1"],
        affected_elements=["GNB-TESTBED-5G-01"],
    )
    assess_parent = analyzer.assess_impact(cluster_parent)
    assert assess_parent.estimated_affected_subscribers == 10000

    # 2. Unknown elements with zero metadata: MUST be None, never hallucinated!
    empty_topo = TelecomTopologyGraph()
    empty_topo.add_node("UNKNOWN-BOX", domain="RAN")  # no nominal_subscribers
    analyzer_empty = NetworkImpactAnalyzer(topology=empty_topo)

    cluster_empty = CorrelatedIncidentCluster(
        cluster_id="CLUST-TEST-EMPTY",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:00:00Z",
        primary_domain="RAN",
        involved_domains=["RAN"],
        direct_alarm_ids=["ALM-2"],
        affected_elements=["UNKNOWN-BOX"],
    )
    assess_empty = analyzer_empty.assess_impact(cluster_empty)
    assert assess_empty.estimated_affected_subscribers is None
    assert assess_empty.subscriber_impact_basis is None


def test_severity_risk_level_calibration():
    topo = TelecomTopologyGraph.build_reference_topology()
    analyzer = NetworkImpactAnalyzer(topology=topo)

    # Multi-domain Core failure should escalate to CRITICAL
    core_cluster = CorrelatedIncidentCluster(
        cluster_id="CLUST-CORE-OUTAGE",
        earliest_timestamp="2026-03-01T10:00:00Z",
        latest_timestamp="2026-03-01T10:00:00Z",
        primary_domain="5G_CORE",
        involved_domains=["5G_CORE", "TRANSPORT", "SERVICE"],
        direct_alarm_ids=["ALM-UPF", "ALM-SMF", "ALM-RTR"],
        affected_elements=["UPF-CORE-PRIMARY", "SMF-CORE-01", "RTR-IPMPLS-AGG01"],
    )
    core_assess = analyzer.assess_impact(core_cluster)
    assert core_assess.risk_score >= 0.75
    assert core_assess.severity_risk_level == "CRITICAL"
