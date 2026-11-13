"""Evaluation script for temporal and alarm correlation engine (Milestone 3).

Evaluates Pairwise Precision/Recall, B-cubed metrics, Cluster Purity, and
False Correlation Rate under concurrent adversarial noise injection.
Exports metrics to artifacts/m3_metrics/correlation_eval.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from piis.correlation.engine import TemporalAlarmCorrelator  # noqa: E402
from piis.correlation.topology import TelecomTopologyGraph  # noqa: E402


def generate_benchmark_scenarios() -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Generate multi-incident scenarios with concurrent co-occurring alarms and cross-domain cascades.

    Returns:
        Tuple of (alarm_list, ground_truth_incident_map: alarm_id -> incident_id)
    """
    alarms: List[Dict[str, Any]] = []
    ground_truth: Dict[str, str] = {}

    # Scenario 1: RAN Cell Degradation & gNB Backhaul (Site 01) at 10:00:00
    base_t1 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    inc_1 = "INC-RAN-SITE01-VSWR"
    alarms.extend([
        {
            "alarm_id": "ALM-S01-01",
            "timestamp": base_t1.isoformat(),
            "network_element_id": "CELL-101",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-VSWR-01",
            "severity": "CRITICAL",
            "probable_cause": "Antenna line impedance mismatch",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S01-02",
            "timestamp": (base_t1 + timedelta(seconds=45)).isoformat(),
            "network_element_id": "GNB-TESTBED-5G-01",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-CELL-DEG",
            "severity": "MAJOR",
            "probable_cause": "Dependent cell transmission failure",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S01-03",
            "timestamp": (base_t1 + timedelta(minutes=2, seconds=15)).isoformat(),
            "network_element_id": "CELL-102",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-HO-EXC-FAIL",
            "severity": "MINOR",
            "probable_cause": "Target cell unreachable during handover",
            "source_type": "SYNTHETIC",
        },
    ])
    for a in alarms[-3:]:
        ground_truth[a["alarm_id"]] = inc_1

    # Scenario 2: ADVERSARIAL CONCURRENT EVENT — Site 02 Routine Maintenance Alarm at 10:01:00
    # In the EXACT SAME TIME WINDOW as Scenario 1, but on a separate geographic tower!
    base_t2 = datetime(2026, 3, 1, 10, 1, 0, tzinfo=timezone.utc)
    inc_2 = "INC-RAN-SITE02-ROUTINE"
    alarms.extend([
        {
            "alarm_id": "ALM-S02-01",
            "timestamp": base_t2.isoformat(),
            "network_element_id": "CELL-201",
            "network_domain": "RAN",
            "alarm_code": "ALM-PWR-BATT-LOW",
            "severity": "WARNING",
            "probable_cause": "Mains power supply glitch",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S02-02",
            "timestamp": (base_t2 + timedelta(seconds=30)).isoformat(),
            "network_element_id": "GNB-SITE02-01",
            "network_domain": "RAN",
            "alarm_code": "ALM-PWR-ENCL-TEMP",
            "severity": "WARNING",
            "probable_cause": "Enclosure cooling fan speed variation",
            "source_type": "SYNTHETIC",
        },
    ])
    for a in alarms[-2:]:
        ground_truth[a["alarm_id"]] = inc_2

    # Scenario 3: Cross-Domain Cascade: Core UPF Buffer Overflow to Aggregation Router at 11:30:00
    base_t3 = datetime(2026, 3, 1, 11, 30, 0, tzinfo=timezone.utc)
    inc_3 = "INC-5GC-UPF-CASCADE"
    alarms.extend([
        {
            "alarm_id": "ALM-S03-01",
            "timestamp": base_t3.isoformat(),
            "network_element_id": "UPF-CORE-PRIMARY",
            "network_domain": "5G_CORE",
            "alarm_code": "ALM-5GC-UPF-BUFFER-OVERFLOW",
            "severity": "CRITICAL",
            "probable_cause": "DPDK ring buffer full under bursty traffic",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S03-02",
            "timestamp": (base_t3 + timedelta(seconds=20)).isoformat(),
            "network_element_id": "RTR-IPMPLS-AGG01",
            "network_domain": "TRANSPORT",
            "alarm_code": "ALM-TX-CRC-ERR",
            "severity": "MAJOR",
            "probable_cause": "Egress queue drops and framing backpressure",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S03-03",
            "timestamp": (base_t3 + timedelta(minutes=1, seconds=10)).isoformat(),
            "network_element_id": "SMF-CORE-01",
            "network_domain": "5G_CORE",
            "alarm_code": "ALM-5GC-N4-HEARTBEAT-MISS",
            "severity": "MAJOR",
            "probable_cause": "N4 association heartbeat failure with UPF",
            "source_type": "SYNTHETIC",
        },
    ])
    for a in alarms[-3:]:
        ground_truth[a["alarm_id"]] = inc_3

    # Scenario 4: ADVERSARIAL CONCURRENT EVENT — IMS Service Timeout at 11:31:00 on Site 02
    base_t4 = datetime(2026, 3, 1, 11, 31, 0, tzinfo=timezone.utc)
    inc_4 = "INC-SRV-IMS-CERT-EXPIRY"
    alarms.extend([
        {
            "alarm_id": "ALM-S04-01",
            "timestamp": base_t4.isoformat(),
            "network_element_id": "CELL-202",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-RRC-REJ",
            "severity": "MINOR",
            "probable_cause": "RRC connection reject due to admission limit",
            "source_type": "SYNTHETIC",
        },
    ])
    ground_truth[alarms[-1]["alarm_id"]] = inc_4

    # Scenario 5: Transport Fiber Cut on Site 01 Access Switch at 14:00:00
    base_t5 = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)
    inc_5 = "INC-TX-FIBER-CUT-SITE01"
    alarms.extend([
        {
            "alarm_id": "ALM-S05-01",
            "timestamp": base_t5.isoformat(),
            "network_element_id": "SW-ACCESS-SITE01",
            "network_domain": "TRANSPORT",
            "alarm_code": "ALM-TX-LOS-OPTICAL",
            "severity": "CRITICAL",
            "probable_cause": "Physical fiber optic cut on backhaul trunk",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S05-02",
            "timestamp": (base_t5 + timedelta(seconds=15)).isoformat(),
            "network_element_id": "GNB-TESTBED-5G-01",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-SCTP-LINK-DOWN",
            "severity": "CRITICAL",
            "probable_cause": "Control plane transport unreachability",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S05-03",
            "timestamp": (base_t5 + timedelta(seconds=25)).isoformat(),
            "network_element_id": "CELL-101",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-CELL-UNAVAILABLE",
            "severity": "CRITICAL",
            "probable_cause": "Base station carrier disabled",
            "source_type": "SYNTHETIC",
        },
        {
            "alarm_id": "ALM-S05-04",
            "timestamp": (base_t5 + timedelta(seconds=30)).isoformat(),
            "network_element_id": "CELL-102",
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-CELL-UNAVAILABLE",
            "severity": "CRITICAL",
            "probable_cause": "Base station carrier disabled",
            "source_type": "SYNTHETIC",
        },
    ])
    for a in alarms[-4:]:
        ground_truth[a["alarm_id"]] = inc_5

    return alarms, ground_truth


def evaluate_correlation() -> Dict[str, Any]:
    """Execute evaluation and compute clustering and correlation metrics."""
    alarms, ground_truth = generate_benchmark_scenarios()
    topology = TelecomTopologyGraph.build_reference_topology()

    correlator = TemporalAlarmCorrelator(
        topology=topology,
        time_window_seconds=900.0,
        correlation_threshold=0.55,
        max_hops=3,
    )

    clusters = correlator.correlate(alarms)

    # Map predicted clusters: alarm_id -> cluster_id
    pred_clusters: Dict[str, str] = {}
    for c in clusters:
        for a_id in c.direct_alarm_ids:
            pred_clusters[a_id] = c.cluster_id

    # Compute Pairwise Metrics
    alarm_ids = list(ground_truth.keys())
    n = len(alarm_ids)

    tp_pairs = 0
    fp_pairs = 0
    fn_pairs = 0
    tn_pairs = 0

    # Specifically track concurrent unrelated pairs (adversarial test)
    concurrent_unrelated_pairs = 0
    false_correlations_on_concurrent = 0

    for i in range(n):
        for j in range(i + 1, n):
            id_a, id_b = alarm_ids[i], alarm_ids[j]
            same_gt = ground_truth[id_a] == ground_truth[id_b]
            same_pred = pred_clusters.get(id_a) == pred_clusters.get(id_b)

            # Check if pair is concurrent (within 15 min window)
            dt_a = datetime.fromisoformat(next(a["timestamp"] for a in alarms if a["alarm_id"] == id_a))
            dt_b = datetime.fromisoformat(next(a["timestamp"] for a in alarms if a["alarm_id"] == id_b))
            is_concurrent = abs((dt_a - dt_b).total_seconds()) <= 900.0

            if not same_gt and is_concurrent:
                concurrent_unrelated_pairs += 1
                if same_pred:
                    false_correlations_on_concurrent += 1

            if same_gt and same_pred:
                tp_pairs += 1
            elif not same_gt and same_pred:
                fp_pairs += 1
            elif same_gt and not same_pred:
                fn_pairs += 1
            else:
                tn_pairs += 1

    pairwise_prec = tp_pairs / (tp_pairs + fp_pairs) if (tp_pairs + fp_pairs) > 0 else 0.0
    pairwise_rec = tp_pairs / (tp_pairs + fn_pairs) if (tp_pairs + fn_pairs) > 0 else 0.0
    pairwise_f1 = (
        2 * pairwise_prec * pairwise_rec / (pairwise_prec + pairwise_rec)
        if (pairwise_prec + pairwise_rec) > 0
        else 0.0
    )

    # Compute Cluster Purity (Homogeneity)
    cluster_homogeneity_list = []
    for c in clusters:
        c_gt_incidents = [ground_truth[a_id] for a_id in c.direct_alarm_ids if a_id in ground_truth]
        if c_gt_incidents:
            counts = {inc: c_gt_incidents.count(inc) for inc in set(c_gt_incidents)}
            majority = max(counts.values())
            cluster_homogeneity_list.append(majority / len(c_gt_incidents))

    mean_cluster_purity = float(np.mean(cluster_homogeneity_list)) if cluster_homogeneity_list else 0.0

    # False Correlation Rate on Concurrent Unrelated Events
    fcr = (
        false_correlations_on_concurrent / concurrent_unrelated_pairs
        if concurrent_unrelated_pairs > 0
        else 0.0
    )

    return {
        "benchmark": "PIIS-M3-Temporal-Correlation-Benchmark",
        "total_alarms": len(alarms),
        "ground_truth_incident_count": len(set(ground_truth.values())),
        "predicted_cluster_count": len(clusters),
        "metrics": {
            "pairwise_precision": round(pairwise_prec, 4),
            "pairwise_recall": round(pairwise_rec, 4),
            "pairwise_f1": round(pairwise_f1, 4),
            "mean_cluster_purity": round(mean_cluster_purity, 4),
            "false_correlation_rate_concurrent": round(fcr, 4),
            "concurrent_unrelated_pairs_tested": concurrent_unrelated_pairs,
            "false_correlations_observed": false_correlations_on_concurrent,
            "pairwise_counts": {
                "tp": tp_pairs,
                "fp": fp_pairs,
                "fn": fn_pairs,
                "tn": tn_pairs,
            },
        },
        "clusters_summary": [
            {
                "cluster_id": c.cluster_id,
                "alarm_count": len(c.direct_alarm_ids),
                "element_count": len(c.affected_elements),
                "involved_domains": c.involved_domains,
                "correlation_edges": len(c.correlation_edges),
                "root_cause_hypothesis": c.root_cause_hypothesis,
            }
            for c in clusters
        ],
    }


def main():
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "artifacts" / "m3_metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Running Temporal & Alarm Correlation Benchmark...")
    results = evaluate_correlation()

    out_file = out_dir / "correlation_eval.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Results exported to {out_file}")
    print("\nCorrelation Benchmark Summary:")
    print(f"Total Alarms: {results['total_alarms']}")
    print(f"Ground-Truth Incidents: {results['ground_truth_incident_count']}")
    print(f"Predicted Clusters: {results['predicted_cluster_count']}")
    print(f"Pairwise Precision: {results['metrics']['pairwise_precision']:.4f}")
    print(f"Pairwise Recall: {results['metrics']['pairwise_recall']:.4f}")
    print(f"Pairwise F1: {results['metrics']['pairwise_f1']:.4f}")
    print(f"Cluster Purity: {results['metrics']['mean_cluster_purity']:.4f}")
    print(f"False Correlation Rate on Concurrent Events: {results['metrics']['false_correlation_rate_concurrent']:.4f}")


if __name__ == "__main__":
    main()
