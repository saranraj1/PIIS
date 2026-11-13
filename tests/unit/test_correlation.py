"""Unit and adversarial tests for temporal and alarm correlation."""

from __future__ import annotations

from datetime import datetime, timezone

from piis.correlation.engine import TemporalAlarmCorrelator
from piis.correlation.topology import TelecomTopologyGraph


def test_topology_graph_operations():
    topo = TelecomTopologyGraph()
    topo.add_node("CELL-A", domain="RAN", element_type="CELL")
    topo.add_node("GNB-A", domain="RAN", element_type="GNB")
    topo.add_node("RTR-A", domain="TRANSPORT", element_type="ROUTER")
    topo.add_node("DISCONNECTED-NODE", domain="CORE")

    topo.add_edge("CELL-A", "GNB-A", relation="serves_cell")
    topo.add_edge("GNB-A", "RTR-A", relation="backhaul")

    # Shortest path distances
    assert topo.shortest_path_distance("CELL-A", "CELL-A") == 0
    assert topo.shortest_path_distance("CELL-A", "GNB-A") == 1
    assert topo.shortest_path_distance("CELL-A", "RTR-A") == 2
    assert topo.shortest_path_distance("CELL-A", "DISCONNECTED-NODE") is None

    # Neighbors and k-hop
    neighbors = topo.get_neighbors("GNB-A")
    assert "CELL-A" in neighbors and "RTR-A" in neighbors

    k_hop = topo.get_k_hop_neighbors(["CELL-A"], k=2)
    assert "GNB-A" in k_hop
    assert "RTR-A" in k_hop
    assert "DISCONNECTED-NODE" not in k_hop


def test_correlator_groups_adjacent_events():
    topo = TelecomTopologyGraph.build_reference_topology()
    correlator = TemporalAlarmCorrelator(topology=topo, time_window_seconds=900.0)

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    t1 = datetime(2026, 3, 1, 10, 1, 30, tzinfo=timezone.utc).isoformat()  # 90s later

    # Alarms on adjacent nodes: CELL-101 and parent GNB-TESTBED-5G-01
    alarms = [
        {
            "alarm_id": "ALM-1",
            "timestamp": t0,
            "network_element_id": "CELL-101",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-VSWR",
            "severity": "CRITICAL",
        },
        {
            "alarm_id": "ALM-2",
            "timestamp": t1,
            "network_element_id": "GNB-TESTBED-5G-01",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-DEG",
            "severity": "MAJOR",
        },
    ]

    clusters = correlator.correlate(alarms)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert set(cluster.direct_alarm_ids) == {"ALM-1", "ALM-2"}
    assert set(cluster.affected_elements) == {"CELL-101", "GNB-TESTBED-5G-01"}
    assert cluster.epistemic_status == "HYPOTHESIS"
    assert len(cluster.correlation_edges) == 1

    edge = cluster.correlation_edges[0]
    assert edge.hop_distance == 1
    assert "hop distance 1" in edge.rationale_text


def test_correlator_separates_distant_or_delayed_events():
    topo = TelecomTopologyGraph.build_reference_topology()
    correlator = TemporalAlarmCorrelator(topology=topo, time_window_seconds=900.0)

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    t_delayed = datetime(2026, 3, 1, 10, 30, 0, tzinfo=timezone.utc).isoformat()  # 30 mins later (> 15 min window)

    # 1. Delayed event on same node
    alarms_delayed = [
        {"alarm_id": "ALM-A", "timestamp": t0, "network_element_id": "CELL-101", "network_domain": "RAN"},
        {"alarm_id": "ALM-B", "timestamp": t_delayed, "network_element_id": "CELL-101", "network_domain": "RAN"},
    ]
    clusters_delayed = correlator.correlate(alarms_delayed)
    assert len(clusters_delayed) == 2  # Separated by time window

    # 2. Simultaneous events on unrelated disjoint sites (Site 01 vs Site 02)
    # Both at t0, but on completely different physical locations
    alarms_disjoint = [
        {"alarm_id": "ALM-SITE01", "timestamp": t0, "network_element_id": "CELL-101", "network_domain": "RAN"},
        {"alarm_id": "ALM-SITE02", "timestamp": t0, "network_element_id": "CELL-201", "network_domain": "RAN"},
    ]
    clusters_disjoint = correlator.correlate(alarms_disjoint)
    assert len(clusters_disjoint) == 2  # Separated by topology (no false correlation)
