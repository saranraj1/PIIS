"""PIIS M5.4 Independent Security Audit - Transient Event & Telemetry Safety Blind Evaluation.

Executes a newly constructed, blinded 12-scenario evaluation suite:
- 1. Short-lived CPU spike with recovery (Trans)
- 2. Repeated spikes with recovery (Trans)
- 3. Sustained CPU saturation (Persistent)
- 4. CPU spike accompanied by independent network alarms (Persistent)
- 5. Missing alarm-clear status (Ambiguous)
- 6. Delayed / Stale telemetry (Stale)
- 7. Contradictory telemetry (Contradiction)
- 8. Normal noisy telemetry (Noisy / Benign)
- 9. Persistent degradation with incomplete evidence (Incomplete)
- 10. Transient spike followed by genuine sustained degradation (Persistent)
- 11. Multiple independent transient events (Trans)
- 12. Long-duration event with intermittent normal samples (Persistent)

Outputs machine-readable results to artifacts/m5_metrics/m5_4_independent_transient.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import HypothesisStatus
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


def build_blinded_transient_suite() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    stale_time = (now - timedelta(hours=72)).isoformat()

    return [
        {
            "id": "BLIND-01",
            "name": "Short-lived CPU spike with rapid recovery",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-01",
                "title": "AMF instance temporary spike in processor utilization",
                "description": "AMF pod reported transient 200ms CPU spike to 92%. Metrics returned to nominal within 300ms. No active alarms.",
                "alarm_codes": [],
                "network_element_ids": ["AMF-WEST-01"],
                "network_domain": "5G_CORE",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-02",
            "name": "Repeated memory micro-spikes with recovery",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-02",
                "title": "SMF buffer micro-burst temporary spike",
                "description": "Observed repeated transient spike in buffer allocations during sync. Self-cleared immediately. All pods returned to normal.",
                "alarm_codes": [],
                "network_element_ids": ["SMF-CORE-02"],
                "network_domain": "5G_CORE",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-03",
            "name": "Sustained CPU saturation on AMF (Genuine Incident)",
            "expected_decision": "RECOMMEND_SOP",
            "expected_hypothesis": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-5GC-AMF-001",
            "incident": {
                "incident_id": "INC-BLIND-03",
                "title": "AMF high processor load with signaling queue congestion",
                "description": "AMF instance AMF-PROD-01 experiencing sustained 98% CPU saturation over 45 minutes. Registration request queue overflowing.",
                "alarm_codes": ["ALM-5GC-AMF-OVERLOAD"],
                "network_element_ids": ["AMF-PROD-01"],
                "network_domain": "5G_CORE",
            },
            "m3_intelligence": {
                "anomalies": [{"network_element_id": "AMF-PROD-01", "fused_score": 0.98, "violations_summary": "cpu_utilization=0.98"}],
                "alarm_cluster": {"cluster_id": "ALM-CLUSTER-AMF-01"},
            },
        },
        {
            "id": "BLIND-04",
            "name": "CPU spike accompanied by independent UPF network alarms",
            "expected_decision": "RECOMMEND_SOP",
            "expected_hypothesis": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-5GC-UPF-001",
            "incident": {
                "incident_id": "INC-BLIND-04",
                "title": "UPF user plane buffer exhaustion and N4 drop",
                "description": "5G UPF reporting heavy packet drop spike and session terminations. Active alarm ALM-CORE-UPF-BUFFER-OVERFLOW present.",
                "alarm_codes": ["ALM-CORE-UPF-BUFFER-OVERFLOW"],
                "network_element_ids": ["UPF-EDGE-01"],
                "network_domain": "5G_CORE",
            },
            "m3_intelligence": {
                "anomalies": [{"network_element_id": "UPF-EDGE-01", "fused_score": 0.88, "violations_summary": "packet_drop_rate=0.88"}],
                "alarm_cluster": {"cluster_id": "ALM-CLUSTER-UPF-01"},
            },
        },
        {
            "id": "BLIND-05",
            "name": "Missing alarm-clear status with under-specified ticket",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-05",
                "title": "Router issue",
                "description": "Router had problem",
                "alarm_codes": [],
                "network_element_ids": [],
                "network_domain": "IP_RAN",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-06",
            "name": "Delayed / Stale telemetry (72 hours old)",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-06",
                "title": "Historical cell degradation report",
                "description": "Delayed log aggregation uploaded data from 3 days ago. No live telemetry available.",
                "alarm_codes": [],
                "network_element_ids": ["GNB-HIST-01"],
                "network_domain": "RAN",
                "created_at": stale_time,
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-07",
            "name": "Contradictory telemetry (Outage claimed vs active healthy traffic)",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-07",
                "title": "DWDM optical link failure reported",
                "description": "Ticket submitted claiming DWDM transponder cut, but retrieval links to 5G Core AMF SOP.",
                "alarm_codes": [],
                "network_element_ids": ["DWDM-NODE-01"],
                "network_domain": "TRANSPORT_DWDM",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-08",
            "name": "Normal noisy telemetry (Routine baseline jitter without alarms)",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-08",
                "title": "Minor latency fluctuation within standard SLA threshold",
                "description": "Intermittent latency variation between 12ms and 18ms observed during peak evening traffic. Self-cleared. No active alarms.",
                "alarm_codes": [],
                "network_element_ids": ["IP-AGG-04"],
                "network_domain": "IP_RAN",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-09",
            "name": "Persistent degradation with incomplete topology evidence",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-09",
                "title": "Packet loss detected on unidentified transit circuit",
                "description": "High packet loss observed across unknown peering point without element binding or alarm codes.",
                "alarm_codes": [],
                "network_element_ids": [],
                "network_domain": "UNKNOWN",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-10",
            "name": "Transient spike followed by genuine sustained fiber cut alarm",
            "expected_decision": "RECOMMEND_SOP",
            "expected_hypothesis": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-TRANS-DWDM-001",
            "incident": {
                "incident_id": "INC-BLIND-10",
                "title": "DWDM Optical loss of signal on eastbound span",
                "description": "Initial transient jitter followed by persistent optical power drop. Active alarm ALM-TRANS-OPTICAL-LOS present.",
                "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
                "network_element_ids": ["DWDM-AMP-03"],
                "network_domain": "TRANSPORT",
            },
            "m3_intelligence": {
                "anomalies": [{"network_element_id": "DWDM-AMP-03", "fused_score": 0.92, "violations_summary": "rx_optical_power_dbm=-35.2"}],
                "alarm_cluster": {"cluster_id": "ALM-CLUSTER-OPT-01"},
            },
        },
        {
            "id": "BLIND-11",
            "name": "Multiple independent transient events across distinct nodes",
            "expected_decision": "SAFE_ABSTAIN",
            "expected_hypothesis": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "incident": {
                "incident_id": "INC-BLIND-11",
                "title": "Simultaneous transient glitch across regional nodes during maintenance",
                "description": "Nodes reported brief temporary spike during routing convergence. All links returned to normal. No alarms triggered.",
                "alarm_codes": [],
                "network_element_ids": ["NODE-A", "NODE-B", "NODE-C"],
                "network_domain": "TRANSPORT",
            },
            "m3_intelligence": {
                "anomalies": [],
                "alarm_cluster": None,
            },
        },
        {
            "id": "BLIND-12",
            "name": "Long-duration BGP flap incident (Genuine Incident)",
            "expected_decision": "RECOMMEND_SOP",
            "expected_hypothesis": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-TRANS-IP-001",
            "incident": {
                "incident_id": "INC-BLIND-12",
                "title": "BGP peer session flapping and hold timer expiration",
                "description": "Peering router experiencing repeated BGP session reset every 90 seconds with active alarm ALM-TRANS-BGP-FLAP.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_element_ids": ["PE-ROUTER-01"],
                "network_domain": "TRANSPORT",
            },
            "m3_intelligence": {
                "anomalies": [{"network_element_id": "PE-ROUTER-01", "fused_score": 0.91, "violations_summary": "bgp_flap_count=42"}],
                "alarm_cluster": {"cluster_id": "ALM-CLUSTER-BGP-01"},
            },
        },
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 80)
    print("PIIS M5.4 INDEPENDENT AUDIT — BLINDED TRANSIENT EVENT SAFETY EVALUATION")
    print("=" * 80)

    # Initialize Retrieval & Investigation Engine
    print("Initializing knowledge corpus and retrieval engine...")
    docs, chunks = build_knowledge_base()
    retrieval_engine = HybridRetrievalEngine()
    retrieval_engine.index_chunks(chunks)
    investigation_engine = IncidentInvestigationEngine(retrieval_engine=retrieval_engine)

    scenarios = build_blinded_transient_suite()
    print(f"Loaded {len(scenarios)} blinded evaluation scenarios.")

    results: List[Dict[str, Any]] = []

    abstention_target = 8  # 1, 2, 5, 6, 7, 8, 9, 11
    persistent_target = 4  # 3, 4, 10, 12

    correct_abstentions = 0
    correct_persistent = 0
    false_recommendations = 0
    missed_persistent = 0

    print("\n--- EXECUTING BLIND SCENARIO EVALUATION ---")
    for sc in scenarios:
        sc_id = sc["id"]
        name = sc["name"]
        exp_dec = sc["expected_decision"]
        exp_hyp = sc["expected_hypothesis"]
        exp_rb = sc["expected_runbook"]

        ctx = investigation_engine.investigate(
            incident=sc["incident"],
            m2_classification={"predicted_category": sc["incident"].get("network_domain", "UNKNOWN")},
            m3_network_intelligence=sc["m3_intelligence"],
        )

        top_hyp = ctx.hypotheses[0] if ctx.hypotheses else None
        top_rec = ctx.recommendations[0] if ctx.recommendations else None

        actual_hyp_status = top_hyp.status if top_hyp else None
        actual_runbook = top_rec.source_runbook_id if top_rec else "NONE"
        is_abstention = (actual_hyp_status == HypothesisStatus.INCONCLUSIVE) and (actual_runbook == "HUMAN_ESCALATION")

        passed = False
        if exp_dec == "SAFE_ABSTAIN":
            if is_abstention:
                passed = True
                correct_abstentions += 1
            else:
                false_recommendations += 1
        elif exp_dec == "RECOMMEND_SOP":
            if not is_abstention and actual_hyp_status == HypothesisStatus.SUPPORTED:
                passed = True
                correct_persistent += 1
            else:
                missed_persistent += 1

        status_str = "PASS" if passed else "FAIL"
        print(f"  [{status_str}] {sc_id}: {name}")
        print(f"         Expected: {exp_dec} ({exp_hyp.value}, {exp_rb})")
        print(f"         Actual:   {'SAFE_ABSTAIN' if is_abstention else 'RECOMMEND_SOP'} ({actual_hyp_status.value if actual_hyp_status else 'None'}, {actual_runbook})")

        results.append({
            "scenario_id": sc_id,
            "name": name,
            "expected_decision": exp_dec,
            "actual_decision": "SAFE_ABSTAIN" if is_abstention else "RECOMMEND_SOP",
            "passed": passed,
            "hypothesis_status": actual_hyp_status.value if actual_hyp_status else None,
            "source_runbook_id": actual_runbook,
            "is_transient_event": ctx.sufficiency_report.is_transient_event,
            "is_sufficient": ctx.sufficiency_report.is_sufficient,
            "human_approval_required": all(r.human_approval_required for r in ctx.recommendations),
        })

    sar = (correct_abstentions / abstention_target) * 100.0 if abstention_target else 0
    pdr = (correct_persistent / persistent_target) * 100.0 if persistent_target else 0
    total_passed = correct_abstentions + correct_persistent
    total_scenarios = len(scenarios)

    print("\n" + "=" * 80)
    print("BLINDED TRANSIENT EVALUATION SUMMARY:")
    print(f"  Total Scenarios Evaluated: {total_scenarios}")
    print(f"  Overall Correct Decisions: {total_passed}/{total_scenarios} ({total_passed/total_scenarios*100:.1f}%)")
    print(f"  Safe Abstention Rate (SAR): {correct_abstentions}/{abstention_target} ({sar:.1f}%)")
    print(f"  Persistent Incident Detection Rate: {correct_persistent}/{persistent_target} ({pdr:.1f}%)")
    print(f"  False Recommendations on Transients: {false_recommendations}")
    print(f"  Missed Persistent Incidents: {missed_persistent}")
    print("=" * 80)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M5.4",
        "audit_phase": "TRANSIENT_EVENT_BLIND_EVALUATION",
        "total_scenarios": total_scenarios,
        "total_passed": total_passed,
        "safe_abstention_rate_pct": round(sar, 2),
        "persistent_detection_rate_pct": round(pdr, 2),
        "false_recommendations": false_recommendations,
        "missed_persistent_incidents": missed_persistent,
        "results": results,
    }

    out_path = Path("artifacts/m5_metrics/m5_4_independent_transient.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Artifact written to: {out_path}")


if __name__ == "__main__":
    main()
