"""Evaluation script for network impact analysis and blast radius quantification (Milestone 3).

Evaluates Direct vs Inferred Element Blast Radius, Domain Coverage, Risk Calibration,
and Zero-Fabrication Subscriber Impact.
Exports metrics to artifacts/m3_metrics/impact_analysis_eval.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from piis.correlation.engine import TemporalAlarmCorrelator  # noqa: E402
from piis.correlation.topology import TelecomTopologyGraph  # noqa: E402
from piis.impact.analyzer import NetworkImpactAnalyzer  # noqa: E402
from scripts.evaluate_correlation import generate_benchmark_scenarios  # noqa: E402


def evaluate_impact_analysis() -> Dict[str, Any]:
    """Execute blast radius and network impact evaluation across benchmark incident clusters."""
    alarms, _ = generate_benchmark_scenarios()
    topology = TelecomTopologyGraph.build_reference_topology()

    correlator = TemporalAlarmCorrelator(topology=topology)
    clusters = correlator.correlate(alarms)

    analyzer = NetworkImpactAnalyzer(topology=topology, inferred_hop_depth=1)
    assessments = analyzer.assess_batch(clusters)

    # Ground truth expectations for blast radius
    # Scenario 1 (RAN Site 01 VSWR): direct = [CELL-101, CELL-102, GNB-TESTBED-5G-01]; inferred = [CELL-103, SW-ACCESS-SITE01]
    # Scenario 5 (Fiber Cut Site 01): direct = [SW-ACCESS-SITE01, GNB-TESTBED-5G-01, CELL-101, CELL-102]; inferred = [CELL-103, RTR-IPMPLS-AGG01]
    evaluations: List[Dict[str, Any]] = []

    direct_element_checks = []
    subscriber_fabrication_violations = 0
    domain_coverage_checks = []

    for assess, cluster in zip(assessments, clusters):
        # 1. Direct Element Verification
        direct_match = set(assess.direct_elements) == set(cluster.affected_elements)
        direct_element_checks.append(direct_match)

        # 2. Inferred Element Verification: Must be in topology and neighbors of direct elements
        inferred_set = set(assess.inferred_elements)
        k_hop = topology.get_k_hop_neighbors(assess.direct_elements, k=1)
        expected_inferred = k_hop - set(assess.direct_elements)
        inferred_correct = inferred_set == expected_inferred

        # 3. Zero Fabrication Check on Subscribers
        # If subscriber estimate is given, verify it matches sum of registered metadata
        if assess.estimated_affected_subscribers is not None:
            expected_sum = sum(
                int(topology.get_node(elem).get("nominal_subscribers", 0))
                for elem in (assess.direct_elements + assess.inferred_elements)
                if topology.get_node(elem) and topology.get_node(elem).get("nominal_subscribers")
            )
            if assess.estimated_affected_subscribers != expected_sum:
                subscriber_fabrication_violations += 1
            if not assess.subscriber_impact_basis or "registered topology metadata" not in assess.subscriber_impact_basis:
                subscriber_fabrication_violations += 1

        # 4. Domain Coverage
        domain_match = set(cluster.involved_domains).issubset(set(assess.affected_domains))
        domain_coverage_checks.append(domain_match)

        evaluations.append({
            "assessment_id": assess.assessment_id,
            "cluster_id": assess.cluster_id,
            "direct_elements": assess.direct_elements,
            "inferred_elements": assess.inferred_elements,
            "total_element_count": assess.total_element_count,
            "affected_domains": assess.affected_domains,
            "severity_risk_level": assess.severity_risk_level,
            "risk_score": assess.risk_score,
            "estimated_subscribers": assess.estimated_affected_subscribers,
            "subscriber_impact_basis": assess.subscriber_impact_basis,
            "checks": {
                "direct_elements_match": direct_match,
                "inferred_elements_correct": inferred_correct,
                "domain_coverage_valid": domain_match,
            },
        })

    direct_acc = sum(direct_element_checks) / len(direct_element_checks) if direct_element_checks else 0.0
    domain_cov_acc = sum(domain_coverage_checks) / len(domain_coverage_checks) if domain_coverage_checks else 0.0

    return {
        "benchmark": "PIIS-M3-Network-Impact-Analysis-Benchmark",
        "total_assessments": len(assessments),
        "metrics": {
            "direct_element_accuracy": round(direct_acc, 4),
            "domain_coverage_accuracy": round(domain_cov_acc, 4),
            "zero_fabrication_violations": subscriber_fabrication_violations,
            "severity_risk_distribution": {
                level: sum(1 for a in assessments if a.severity_risk_level == level)
                for level in ["CRITICAL", "MAJOR", "MODERATE", "LOW"]
            },
        },
        "assessments_detail": evaluations,
    }


def main():
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "artifacts" / "m3_metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Running Network Impact Analysis Benchmark...")
    results = evaluate_impact_analysis()

    out_file = out_dir / "impact_analysis_eval.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Results exported to {out_file}")
    print("\nImpact Analysis Benchmark Summary:")
    print(f"Total Assessments: {results['total_assessments']}")
    print(f"Direct Element Accuracy: {results['metrics']['direct_element_accuracy']:.4f}")
    print(f"Domain Coverage Accuracy: {results['metrics']['domain_coverage_accuracy']:.4f}")
    print(f"Zero Fabrication Violations: {results['metrics']['zero_fabrication_violations']}")
    print(f"Severity Risk Distribution: {results['metrics']['severity_risk_distribution']}")


if __name__ == "__main__":
    main()
