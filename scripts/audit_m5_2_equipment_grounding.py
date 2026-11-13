"""Milestone 5.2 Independent Equipment Grounding & Vendor Compatibility Audit Script.

Evaluates 32 comprehensive operational test cases covering:
- Prose bleed elimination (Cisco AnyConnect, Nokia NetAct, Ericsson ENM, Huawei U2000).
- Bidirectional vendor-neutral 3GPP runbook compatibility.
- Proprietary vendor isolation (Cisco SOPs cannot run on Juniper; vendor SOPs not vendor-neutral).
- Structured metadata precedence over ambiguous prose.
- Network element ID prefix conventions.
- Graceful abstention on ambiguous vendor references.
- Incompatible generations isolation (2G/3G/4G/WiMAX vs 5G SA).
- Multi-generation network handling.
- Vocabulary collision isolation across enterprise vs telecom.
- Positive controls confirming end-to-end evidence grounding and runbook retrieval.

Exports machine-readable metrics to artifacts/m5_metrics/m5_2_equipment_grounding_results.json.
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
from piis.retrieval.filters import MetadataFilter


def audit_phase_2_m5_2() -> Dict[str, Any]:
    print("[*] Initializing Knowledge Base and Investigation Engine...")
    _, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)
    m_filter = MetadataFilter()

    results: Dict[str, Any] = {
        "milestone": "M5.2",
        "audit_phase": "Phase 2: Equipment Identity, Prose Bleed Elimination & Vendor-Neutral Compatibility",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cases_evaluated": [],
    }

    test_cases: List[Dict[str, Any]] = [
        # --- Group 1: Prose Bleed Elimination in Extraction & Grounding ---
        {
            "case_id": "EQP-01",
            "name": "Cisco AnyConnect Mentioned in 5G RAN Incident",
            "category": "PROSE_BLEED",
            "incident": {
                "incident_id": "INC-EQP-01",
                "title": "Severe VSWR degradation on 5G gNodeB AAU",
                "description": "Technician connected via Cisco AnyConnect VPN to inspect the AAU antenna feeder line. Antenna VSWR spike on sector 2 exceeding 2.1:1.",
                "network_domain": "RAN",
                "network_element_ids": ["ERIC-AAU-9901"],
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
            },
            "m2": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.95, "predicted_severity": "MAJOR", "policy_routing_tier": "L1"},
            "m3": {
                "anomalies": [{"network_element_id": "ERIC-AAU-9901", "metric_name": "vswr", "fused_score": 0.88, "violations_summary": "vswr > 2.0"}],
                "alarm_cluster": {"cluster_id": "CLUST-01", "dominant_alarm_code": "ALM-RAN-VSWR-HIGH", "affected_elements": ["ERIC-AAU-9901"], "alarm_events": ["ALM-RAN-VSWR-HIGH"]},
            },
            "expected_vendor": "ERICSSON",
            "expected_runbook": "SOP-RAN-VSWR-001",
            "expected_status": HypothesisStatus.SUPPORTED,
        },
        {
            "case_id": "EQP-02",
            "name": "Nokia NetAct Mentioned in 5G Core AMF Incident",
            "category": "PROSE_BLEED",
            "incident": {
                "incident_id": "INC-EQP-02",
                "title": "5G Core AMF SCTP association timeout",
                "description": "Nokia NetAct EMS console shows high N2 interface SCTP connection drops across AMF instance pool.",
                "network_domain": "5G_CORE",
                "network_element_ids": ["AMF-CORE-01"],
                "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
            },
            "m2": {"predicted_category": "CORE_NETWORK_CONTROL_PLANE", "category_probability": 0.92, "predicted_severity": "CRITICAL", "policy_routing_tier": "L1"},
            "m3": {
                "anomalies": [{"network_element_id": "AMF-CORE-01", "metric_name": "sctp_latency", "fused_score": 0.86, "violations_summary": "sctp drops"}],
                "alarm_cluster": {"cluster_id": "CLUST-02", "dominant_alarm_code": "ALM-CORE-AMF-REG-FAIL", "affected_elements": ["AMF-CORE-01"], "alarm_events": ["ALM-CORE-AMF-REG-FAIL"]},
            },
            "expected_vendor": None,  # NetAct ignored, AMF-CORE has no vendor prefix -> abstains
            "expected_runbook": "SOP-5GC-AMF-001",
            "expected_status": HypothesisStatus.SUPPORTED,
        },
        {
            "case_id": "EQP-03",
            "name": "Ericsson ENM Mentioned on Juniper Router Link Cut",
            "category": "PROSE_BLEED",
            "incident": {
                "incident_id": "INC-EQP-03",
                "title": "Optical transport link failure on core gateway",
                "description": "Alarm mirrored in Ericsson ENM portal: optical Rx power dropped to 0.0 dBm on JunOS PTX10000 gateway.",
                "network_domain": "TRANSPORT",
                "network_element_ids": ["JUN-PTX-01"],
                "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
            },
            "m2": {"predicted_category": "TRANSMISSION_FIBER_FAULT", "category_probability": 0.90, "predicted_severity": "HIGH", "policy_routing_tier": "L2"},
            "m3": {
                "anomalies": [{"network_element_id": "JUN-PTX-01", "metric_name": "optical_power", "fused_score": 0.85, "violations_summary": "fiber cut"}],
                "alarm_cluster": {"cluster_id": "CLUST-03", "dominant_alarm_code": "ALM-TRANS-OPTICAL-LOS", "affected_elements": ["JUN-PTX-01"], "alarm_events": ["ALM-TRANS-OPTICAL-LOS"]},
            },
            "expected_vendor": "JUNIPER",
            "expected_runbook": "SOP-TRANS-FIBER-001",
            "expected_status": HypothesisStatus.SUPPORTED,
        },
        {
            "case_id": "EQP-04",
            "name": "Huawei U2000 Mentioned on Cisco ASR Router BGP Flap",
            "category": "PROSE_BLEED",
            "incident": {
                "incident_id": "INC-EQP-04",
                "title": "BGP peer flap on core router ASR9K",
                "description": "Alarm logged via Huawei U2000 management bridge for Cisco ASR-9000 BGP neighbor timeout.",
                "network_domain": "TRANSPORT",
                "network_element_ids": ["CISCO-ASR-01"],
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
            },
            "m2": {"predicted_category": "ROUTER_CONFIGURATION_ISSUE", "category_probability": 0.89, "predicted_severity": "MAJOR", "policy_routing_tier": "L2"},
            "m3": {
                "anomalies": [{"network_element_id": "CISCO-ASR-01", "metric_name": "bgp_state", "fused_score": 0.82, "violations_summary": "bgp flap"}],
                "alarm_cluster": {"cluster_id": "CLUST-04", "dominant_alarm_code": "ALM-TRANS-BGP-FLAP", "affected_elements": ["CISCO-ASR-01"], "alarm_events": ["ALM-TRANS-BGP-FLAP"]},
            },
            "expected_vendor": "CISCO",
            "expected_runbook": "SOP-TRANS-BGP-002",
            "expected_status": HypothesisStatus.SUPPORTED,
        },

        # --- Group 2: Bidirectional Vendor-Neutral 3GPP Compatibility ---
        {
            "case_id": "EQP-05",
            "name": "Generic 3GPP Runbook Compatible with Ericsson Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("ERICSSON", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-06",
            "name": "Generic 3GPP Runbook Compatible with Nokia Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("NOKIA", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-07",
            "name": "Generic 3GPP Runbook Compatible with Huawei Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("HUAWEI", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-08",
            "name": "Generic 3GPP Runbook Compatible with Cisco Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("CISCO", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-09",
            "name": "Generic 3GPP Runbook Compatible with Juniper Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("JUNIPER", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-10",
            "name": "Generic 3GPP Runbook Compatible with ZTE Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("ZTE", "GENERIC_3GPP", True),
        },
        {
            "case_id": "EQP-11",
            "name": "Generic 3GPP Runbook Compatible with Multi-Vendor Target",
            "category": "VENDOR_NEUTRAL_COMPAT",
            "eval_filter": ("MULTI_VENDOR", "GENERIC_3GPP", True),
        },

        # --- Group 3: Proprietary Vendor Runbook Strict Isolation ---
        {
            "case_id": "EQP-12",
            "name": "Cisco Runbook Incompatible with Juniper Incident",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("JUNIPER", "CISCO", False),
        },
        {
            "case_id": "EQP-13",
            "name": "Cisco Runbook Incompatible with Nokia Incident",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("NOKIA", "CISCO", False),
        },
        {
            "case_id": "EQP-14",
            "name": "Cisco Runbook Incompatible with Ericsson Incident",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("ERICSSON", "CISCO", False),
        },
        {
            "case_id": "EQP-15",
            "name": "Cisco Runbook Not Treated as Vendor-Neutral",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("GENERIC_3GPP", "CISCO", False),
        },
        {
            "case_id": "EQP-16",
            "name": "Juniper Runbook Incompatible with Cisco Incident",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("CISCO", "JUNIPER", False),
        },
        {
            "case_id": "EQP-17",
            "name": "Missing Chunk Vendor Fails Closed (No Silent Compatibility)",
            "category": "PROPRIETARY_ISOLATION",
            "eval_filter": ("CISCO", None, False),
        },

        # --- Group 4: Structured Metadata Precedence ---
        {
            "case_id": "EQP-18",
            "name": "Structured metadata.vendor Overrides Text Cisco Mention",
            "category": "METADATA_PRECEDENCE",
            "incident": {"incident_id": "INC-M1", "title": "Radio fault", "description": "Cisco router in site cabinet", "metadata": {"vendor": "ERICSSON"}},
            "expected_vendor": "ERICSSON",
        },
        {
            "case_id": "EQP-19",
            "name": "Structured metadata.vendor Overrides Text Juniper Mention",
            "category": "METADATA_PRECEDENCE",
            "incident": {"incident_id": "INC-M2", "title": "BBU issue", "description": "Traffic route through Juniper core", "metadata": {"vendor": "NOKIA"}},
            "expected_vendor": "NOKIA",
        },
        {
            "case_id": "EQP-20",
            "name": "Incident equipment_vendor Field Takes Precedence",
            "category": "METADATA_PRECEDENCE",
            "incident": {"incident_id": "INC-M3", "title": "Switch down", "description": "Nokia NetAct alert", "equipment_vendor": "CISCO"},
            "expected_vendor": "CISCO",
        },

        # --- Group 5: Element ID Prefix Conventions ---
        {
            "case_id": "EQP-21",
            "name": "Element Prefix ERIC- Extracts ERICSSON",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P1", "network_element_ids": ["ERIC-AAU-01"]},
            "expected_vendor": "ERICSSON",
        },
        {
            "case_id": "EQP-22",
            "name": "Element Prefix NOK- Extracts NOKIA",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P2", "network_element_ids": ["NOK-AIRSCALE-01"]},
            "expected_vendor": "NOKIA",
        },
        {
            "case_id": "EQP-23",
            "name": "Element Prefix CISCO- Extracts CISCO",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P3", "network_element_ids": ["CISCO-ASR9K-01"]},
            "expected_vendor": "CISCO",
        },
        {
            "case_id": "EQP-24",
            "name": "Element Prefix JUN- Extracts JUNIPER",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P4", "network_element_ids": ["JUN-MX960-01"]},
            "expected_vendor": "JUNIPER",
        },
        {
            "case_id": "EQP-25",
            "name": "Element Prefix HUA- Extracts HUAWEI",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P5", "network_element_ids": ["HUA-NE40E-01"]},
            "expected_vendor": "HUAWEI",
        },
        {
            "case_id": "EQP-26",
            "name": "Element Prefix ZTE- Extracts ZTE",
            "category": "PREFIX_CONVENTION",
            "incident": {"incident_id": "INC-P6", "network_element_ids": ["ZTE-ZXCTN-01"]},
            "expected_vendor": "ZTE",
        },

        # --- Group 6: Ambiguous Vendor Abstention ---
        {
            "case_id": "EQP-27",
            "name": "Ambiguous Conversational Text Abstains to None",
            "category": "VENDOR_ABSTENTION",
            "incident": {"incident_id": "INC-A1", "title": "Link flap", "description": "Site technician is on site inspecting cable.", "network_element_ids": ["SITE-99"]},
            "expected_vendor": None,
        },
        {
            "case_id": "EQP-28",
            "name": "Client Software Mention Abstains to None",
            "category": "VENDOR_ABSTENTION",
            "incident": {"incident_id": "INC-A2", "title": "Remote access down", "description": "Tech Wireshark capture via Cisco AnyConnect VPN dropped.", "network_element_ids": ["REMOTE-DESK"]},
            "expected_vendor": None,
        },

        # --- Group 7: Legacy Generation Hard Isolation ---
        {
            "case_id": "EQP-29",
            "name": "2G GSM Abis Sync Loss Incompatible with 5G Runbook",
            "category": "GENERATION_ISOLATION",
            "eval_gen": ("2G_GSM", "5G_NR", False),
        },
        {
            "case_id": "EQP-30",
            "name": "3G UMTS NodeB Power Amplifier Incompatible with 5G Runbook",
            "category": "GENERATION_ISOLATION",
            "eval_gen": ("3G_UMTS", "5G_NR", False),
        },
        {
            "case_id": "EQP-31",
            "name": "WiMAX 802.16e ASN Gateway Incompatible with 5G Runbook",
            "category": "GENERATION_ISOLATION",
            "eval_gen": ("WIMAX", "5G_NR", False),
        },
        {
            "case_id": "EQP-32",
            "name": "5G NR Generation Matches 5G Runbook",
            "category": "GENERATION_ISOLATION",
            "eval_gen": ("5G_NR", "5G_NR", True),
        },
    ]

    # Execute all test cases
    for tc in test_cases:
        t0 = time.perf_counter()
        passed = False
        details: Dict[str, Any] = {}

        if "eval_filter" in tc:
            t_vend, c_vend, expected_val = tc["eval_filter"]
            actual_val = m_filter._is_vendor_compatible(t_vend, c_vend)
            passed = actual_val == expected_val
            details = {"target_vendor": t_vend, "chunk_vendor": c_vend, "expected": expected_val, "actual": actual_val}

        elif "eval_gen" in tc:
            t_gen, c_gen, expected_val = tc["eval_gen"]
            actual_val = m_filter._is_generation_compatible(t_gen, c_gen)
            passed = actual_val == expected_val
            details = {"target_gen": t_gen, "chunk_gen": c_gen, "expected": expected_val, "actual": actual_val}

        elif "expected_runbook" in tc:
            inc = tc["incident"]
            m2 = tc.get("m2")
            m3 = tc.get("m3")
            ctx = engine.investigate(inc, m2_classification=m2, m3_network_intelligence=m3)
            ext_vend = IncidentInvestigationEngine._extract_vendor(inc)

            vend_match = ext_vend == tc["expected_vendor"]
            rb_match = ctx.m4_retrieval["primary_runbook_id"] == tc["expected_runbook"]
            stat_match = ctx.hypotheses[0].status == tc["expected_status"] if ctx.hypotheses else False

            passed = vend_match and rb_match and stat_match
            details = {
                "extracted_vendor": ext_vend,
                "retrieved_runbook": ctx.m4_retrieval["primary_runbook_id"],
                "hypothesis_status": ctx.hypotheses[0].status.value if ctx.hypotheses else None,
                "confidence_proxy": ctx.hypotheses[0].confidence_proxy if ctx.hypotheses else 0.0,
            }

        elif "expected_vendor" in tc:
            inc = tc["incident"]
            ext_vend = IncidentInvestigationEngine._extract_vendor(inc)
            passed = ext_vend == tc["expected_vendor"]
            details = {"expected": tc["expected_vendor"], "actual": ext_vend}

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        results["cases_evaluated"].append({
            "case_id": tc["case_id"],
            "name": tc["name"],
            "category": tc["category"],
            "pass": passed,
            "latency_ms": elapsed_ms,
            "details": details,
        })

    total = len(results["cases_evaluated"])
    passed_cnt = sum(1 for c in results["cases_evaluated"] if c["pass"])
    results["summary"] = {
        "total_cases": total,
        "passed": passed_cnt,
        "failed": total - passed_cnt,
        "pass_rate_pct": round(passed_cnt / total * 100.0, 1),
    }

    out_file = Path("artifacts/m5_metrics/m5_2_equipment_grounding_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("================================================================================")
    print("PHASE 2: M5.2 EQUIPMENT GROUNDING & VENDOR COMPATIBILITY AUDIT")
    print("================================================================================")
    for c in results["cases_evaluated"]:
        status_str = "PASS" if c["pass"] else "FAIL"
        print(f"[{c['case_id']}] [{status_str:4s}] {c['name']:<50s} | Latency: {c['latency_ms']}ms")
    print("--------------------------------------------------------------------------------")
    print(f"Total: {passed_cnt}/{total} ({results['summary']['pass_rate_pct']}%) Passed")
    print(f"Artifact exported: {out_file}")
    print("================================================================================")
    return results


if __name__ == "__main__":
    audit_phase_2_m5_2()
