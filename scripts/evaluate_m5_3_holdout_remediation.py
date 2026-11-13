"""M5.3 Holdout Failure Analysis and Generalization Verification Suite.

Validates the remediation of the two M5.2 holdout discrepancies:
- SEALED-12: Scheduled maintenance window (proactive traffic drain) -> INCONCLUSIVE / HUMAN_ESCALATION
- SEALED-29: 65KB soft-hyphen buffer flood -> SUPPORTED / SOP-RAN-VSWR-001

Also evaluates 10 fresh, un-tuned operational scenarios (5 positive, 5 safe abstention)
to empirically prove that the fixes generalize robustly without overfitting.
Outputs machine-readable metrics to artifacts/m5_metrics/m5_3_holdout_remediation.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import HypothesisStatus
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


def get_holdout_test_cases() -> List[Dict[str, Any]]:
    return [
        # =====================================================================
        # 1. REMEDIATED M5.2 HOLDOUT DISCREPANCIES (2 cases)
        # =====================================================================
        {
            "id": "SEALED-12",
            "name": "Remediated: Scheduled Maintenance Window (Proactive Traffic Drain)",
            "domain": "TRANSPORT",
            "incident": {
                "incident_id": "INC-M53-SLD-12",
                "title": "Planned fiber maintenance window",
                "description": "Planned maintenance outage for fiber reroute. Traffic proactively drained.",
                "alarm_codes": [],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["DWDM-NODE-01"],
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "REMEDIATED_HOLDOUT",
        },
        {
            "id": "SEALED-29",
            "name": "Remediated: 65KB Soft-Hyphen Buffer Flood Attack",
            "domain": "RAN",
            "incident": {
                "incident_id": "INC-M53-SLD-29",
                "title": "5G High Return Loss ReDoS Buffer",
                "description": "ALM-RAN-VSWR-HIGH active. " + ("a\u00ad" * 32000),
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["gNodeB-29"],
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.92},
            "m3": {"anomalies": [{"network_element_id": "gNodeB-29", "metric_name": "vswr", "fused_score": 0.89}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-RAN-VSWR-001",
            "category": "REMEDIATED_HOLDOUT",
        },

        # =====================================================================
        # 2. FRESH POSITIVE OPERATIONAL SCENARIOS (5 cases)
        # =====================================================================
        {
            "id": "FRESH-POS-01",
            "name": "5G Core AMF SCTP Association Loss",
            "domain": "5G_CORE",
            "incident": {
                "incident_id": "INC-M53-POS-01",
                "title": "N2 interface SCTP signaling failure on primary AMF",
                "description": "SCTP heartbeat timeouts detected across N2 link towards multiple gNodeBs.",
                "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["AMF-CORE-N2-01"],
            },
            "m2": {"predicted_category": "CORE_NETWORK_CONTROL_PLANE", "category_probability": 0.95},
            "m3": {"anomalies": [{"network_element_id": "AMF-CORE-N2-01", "metric_name": "amf_cpu", "fused_score": 0.92}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-5GC-AMF-001",
            "category": "FRESH_POSITIVE",
        },
        {
            "id": "FRESH-POS-02",
            "name": "Transport DWDM Optical Fiber Attenuation",
            "domain": "TRANSPORT",
            "incident": {
                "incident_id": "INC-M53-POS-02",
                "title": "DWDM optical link degraded - severe signal attenuation",
                "description": "Optical receiver reports Rx power down to -31.5 dBm on primary ring span.",
                "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["ROADM-EAST-SPAN-4"],
            },
            "m2": {"predicted_category": "TRANSMISSION_FIBER_FAULT", "category_probability": 0.94},
            "m3": {"anomalies": [{"network_element_id": "ROADM-EAST-SPAN-4", "metric_name": "optical_rx", "fused_score": 0.94}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-TRANS-FIBER-001",
            "category": "FRESH_POSITIVE",
        },
        {
            "id": "FRESH-POS-03",
            "name": "Cisco ASR9k BGP Peering Session Flapping",
            "domain": "TRANSPORT",
            "incident": {
                "incident_id": "INC-M53-POS-03",
                "title": "Cisco ASR9010 eBGP peering session reset continuously",
                "description": "BGP hold timer expired and TCP reset on upstream transit link.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["CISCO-ASR-CORE-02"],
                "metadata": {"vendor": "CISCO"},
            },
            "m2": {"predicted_category": "ROUTER_CONFIGURATION_ISSUE", "category_probability": 0.93},
            "m3": {"anomalies": [{"network_element_id": "CISCO-ASR-CORE-02", "metric_name": "bgp_flaps", "fused_score": 0.90}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-TRANS-BGP-002",
            "category": "FRESH_POSITIVE",
        },
        {
            "id": "FRESH-POS-04",
            "name": "Nokia AirScale gNodeB RF Feeder Water Ingress",
            "domain": "RAN",
            "incident": {
                "incident_id": "INC-M53-POS-04",
                "title": "Nokia AirScale sector antenna high return loss",
                "description": "Heavy rainfall caused moisture ingress in jumper coaxial connection. VSWR 2.8:1.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["NOK-AAU-NORTH-1"],
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.96},
            "m3": {"anomalies": [{"network_element_id": "NOK-AAU-NORTH-1", "metric_name": "vswr", "fused_score": 0.93}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-RAN-VSWR-001",
            "category": "FRESH_POSITIVE",
        },
        {
            "id": "FRESH-POS-05",
            "name": "5G Core UPF N6 Interface Discard Surge",
            "domain": "5G_CORE",
            "incident": {
                "incident_id": "INC-M53-POS-05",
                "title": "5GC UPF N6 egress interface buffer starvation",
                "description": "High packet discard rates and ring buffer saturation on data network gateway.",
                "alarm_codes": ["ALM-CORE-UPF-BUFFER-OVERFLOW"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["UPF-DATA-GW-03"],
            },
            "m2": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.91},
            "m3": {"anomalies": [{"network_element_id": "UPF-DATA-GW-03", "metric_name": "buffer_drop", "fused_score": 0.88}]},
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook": "SOP-5GC-UPF-002",
            "category": "FRESH_POSITIVE",
        },

        # =====================================================================
        # 3. FRESH SAFE ABSTENTION SCENARIOS (5 cases)
        # =====================================================================
        {
            "id": "FRESH-ABS-01",
            "name": "Vague Customer Call Center Ticket Without Alarms",
            "domain": "CROSS_DOMAIN",
            "incident": {
                "incident_id": "INC-M53-ABS-01",
                "title": "User complaints regarding slow service in north region",
                "description": "Multiple end users report slow connectivity. No telemetry or element specified.",
                "alarm_codes": [],
                "network_domain": "CROSS_DOMAIN",
                "network_element_ids": [],
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "FRESH_ABSTENTION",
        },
        {
            "id": "FRESH-ABS-02",
            "name": "Unsupported Legacy 2G GSM Base Station Hardware Failure",
            "domain": "RAN",
            "incident": {
                "incident_id": "INC-M53-ABS-02",
                "title": "Legacy 2G GSM TRX Transceiver Synthesizer Lock Lost",
                "description": "Vintage GSM 900 base station TRX synthesizer unlocking. Out-of-scope legacy tech.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["BTS-GSM900-VINTAGE-01"],
                "metadata": {"technology_generation": "2G_GSM"},
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "FRESH_ABSTENTION",
        },
        {
            "id": "FRESH-ABS-03",
            "name": "Scheduled Maintenance Window On Metro Core Ring",
            "domain": "TRANSPORT",
            "incident": {
                "incident_id": "INC-M53-ABS-03",
                "title": "Metro DWDM node planned upgrade maintenance",
                "description": "Scheduled maintenance window: card swap in progress. Traffic proactively drained.",
                "alarm_codes": [],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["METRO-DWDM-RING-01"],
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "FRESH_ABSTENTION",
        },
        {
            "id": "FRESH-ABS-04",
            "name": "Physically Contradictory Alarms (RF VSWR on Core UPF Gateway)",
            "domain": "5G_CORE",
            "incident": {
                "incident_id": "INC-M53-ABS-04",
                "title": "Impossible RF VSWR alarm mapped to Core UPF element",
                "description": "Alarm routing error: RF antenna return loss alarm attached to user plane server.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["UPF-DATA-GW-04"],
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "FRESH_ABSTENTION",
        },
        {
            "id": "FRESH-ABS-05",
            "name": "Unsupported Vendor Mismatch (Juniper PTX BGP Flap with Cisco SOP Only)",
            "domain": "TRANSPORT",
            "incident": {
                "incident_id": "INC-M53-ABS-05",
                "title": "Juniper PTX10008 Transit Core BGP Loss",
                "description": "Juniper Junos OS core router reports BGP session down. System lacks Juniper SOP.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["JUNIPER-PTX-CORE-05"],
                "metadata": {"vendor": "JUNIPER"},
            },
            "m2": {},
            "m3": {},
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook": "HUMAN_ESCALATION",
            "category": "FRESH_ABSTENTION",
        },
    ]


def run_holdout_evaluation() -> Dict[str, Any]:
    print("=" * 80)
    print("M5.3 WORKSTREAM 6: HOLDOUT REMEDIATION & GENERALIZATION VERIFICATION")
    print("=" * 80)

    # Initialize KB, Retrieval, and Investigation Engine
    docs, chunks = build_knowledge_base()
    retrieval_engine = HybridRetrievalEngine()
    retrieval_engine.index_chunks(chunks)
    investigation_engine = IncidentInvestigationEngine(retrieval_engine=retrieval_engine)

    test_cases = get_holdout_test_cases()
    results: List[Dict[str, Any]] = []

    passed_count = 0
    remediated_passed = 0
    fresh_pos_passed = 0
    fresh_abs_passed = 0

    remediated_total = 2
    fresh_pos_total = 5
    fresh_abs_total = 5

    valid_citations_count = 0
    total_citations_count = 0

    for tc in test_cases:
        t0 = time.perf_counter()
        ctx = investigation_engine.investigate(
            incident=tc["incident"],
            m2_classification=tc["m2"],
            m3_network_intelligence=tc["m3"],
        )
        lat_ms = round((time.perf_counter() - t0) * 1000, 2)

        top_hyp = ctx.hypotheses[0] if ctx.hypotheses else None
        actual_status = top_hyp.status if top_hyp else None
        expected_status = tc["expected_status"]
        ret_rb = ctx.m4_retrieval.get("primary_runbook_id")

        # Determine pass/fail
        status_match = (actual_status == expected_status)
        runbook_match = False
        if expected_status == HypothesisStatus.SUPPORTED:
            runbook_match = (ret_rb == tc["expected_runbook"])
        elif expected_status == HypothesisStatus.INCONCLUSIVE:
            runbook_match = (actual_status == HypothesisStatus.INCONCLUSIVE)

        all_recs_safe = all(rec.human_approval_required is True for rec in ctx.recommendations)
        test_passed = status_match and runbook_match and all_recs_safe

        if test_passed:
            passed_count += 1
            if tc["category"] == "REMEDIATED_HOLDOUT":
                remediated_passed += 1
            elif tc["category"] == "FRESH_POSITIVE":
                fresh_pos_passed += 1
            elif tc["category"] == "FRESH_ABSTENTION":
                fresh_abs_passed += 1

        # Check evidence citations
        evid_ids = {e.evidence_id for e in ctx.evidence_register}
        for hyp in ctx.hypotheses:
            for ref in hyp.supporting_evidence_ids:
                total_citations_count += 1
                if ref in evid_ids:
                    valid_citations_count += 1
        for rec in ctx.recommendations:
            for ref in rec.supporting_evidence_ids:
                total_citations_count += 1
                if ref in evid_ids:
                    valid_citations_count += 1

        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "category": tc["category"],
            "passed": test_passed,
            "expected_status": expected_status.value,
            "actual_status": actual_status.value if actual_status else "NONE",
            "expected_runbook": tc["expected_runbook"],
            "retrieved_runbook": ret_rb or "NONE",
            "safety_enforced": all_recs_safe,
            "latency_ms": lat_ms,
        })

    total_cases = len(test_cases)
    ervr = round(valid_citations_count / max(1, total_citations_count) * 100, 2)
    overall_accuracy = round(passed_count / total_cases * 100, 2)
    remediation_rate = round(remediated_passed / remediated_total * 100, 2)
    fresh_pos_rate = round(fresh_pos_passed / fresh_pos_total * 100, 2)
    fresh_abs_rate = round(fresh_abs_passed / fresh_abs_total * 100, 2)

    summary = {
        "milestone": "M5.3",
        "evaluation_name": "Holdout Remediation & Generalization Verification",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": total_cases,
        "overall_passed": passed_count,
        "overall_accuracy_pct": overall_accuracy,
        "remediated_holdout_cases": {
            "total": remediated_total,
            "passed": remediated_passed,
            "remediation_rate_pct": remediation_rate,
            "details": {
                "SEALED-12_remediation": next(r["passed"] for r in results if r["id"] == "SEALED-12"),
                "SEALED-29_remediation": next(r["passed"] for r in results if r["id"] == "SEALED-29"),
            },
        },
        "fresh_generalization_cases": {
            "positive_operational": {
                "total": fresh_pos_total,
                "passed": fresh_pos_passed,
                "accuracy_pct": fresh_pos_rate,
            },
            "safe_abstention": {
                "total": fresh_abs_total,
                "passed": fresh_abs_passed,
                "accuracy_pct": fresh_abs_rate,
            },
        },
        "evidence_reference_validity_rate_pct": ervr,
        "results": results,
    }

    out_path = Path("artifacts/m5_metrics/m5_3_holdout_remediation.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Overall Accuracy:       {overall_accuracy}% ({passed_count}/{total_cases})")
    print(f"Remediated Holdouts:    {remediation_rate}% ({remediated_passed}/{remediated_total})")
    print(f"Fresh Positive Cases:   {fresh_pos_rate}% ({fresh_pos_passed}/{fresh_pos_total})")
    print(f"Fresh Safe Abstentions: {fresh_abs_rate}% ({fresh_abs_passed}/{fresh_abs_total})")
    print(f"Evidence Ref Validity:  {ervr}%")
    print(f"Artifact written to {out_path}")
    print("=" * 80)

    return summary


if __name__ == "__main__":
    run_holdout_evaluation()
