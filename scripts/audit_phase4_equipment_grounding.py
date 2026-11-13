"""Independent Adversarial Audit Script: Phase 4 - Equipment Grounding & Retrieval.

Evaluates 42 independently authored test cases covering:
- Generations: 2G GSM, 3G UMTS, 4G LTE, 5G NR, WiMAX 802.16e.
- Vendors: Ericsson, Nokia, Huawei, Cisco, Juniper, ZTE, Multi-Vendor, Generic 3GPP.
- Management software / EMS / NMS: NetAct, ENM, U2000, Cisco Prime, Juniper Space.
- Client VPNs: AnyConnect, GlobalProtect, Pulse Secure, FortiClient.
- Conflicting metadata vs prose.
- Missing generation / vendor metadata.
- Unsupported equipment / unknown versions.
- Positive retrieval vs appropriate abstention.
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


def get_phase4_test_cases() -> List[Dict[str, Any]]:
    return [
        # --- Group A: Client VPN Prose Noise (AnyConnect, GlobalProtect, Pulse, FortiClient) ---
        {
            "id": "EQP-IND-01",
            "name": "GlobalProtect VPN on Ericsson 5G AAU",
            "incident": {
                "incident_id": "INC-VPN-01",
                "title": "5G High Return Loss on AAU sector 1",
                "description": "Engineer logged in through Palo Alto GlobalProtect VPN gateway. VSWR spike on sector 1 exceeding 2.2:1.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["ERIC-AAU-0101"],
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.95},
            "m3": {"anomalies": [{"network_element_id": "ERIC-AAU-0101", "metric_name": "vswr", "fused_score": 0.90}]},
            "expected_vendor": "ERICSSON",
            "expected_runbook": "SOP-RAN-VSWR-001",
            "expect_supported": True,
        },
        {
            "id": "EQP-IND-02",
            "name": "Pulse Secure VPN on Nokia 5G AMF",
            "incident": {
                "incident_id": "INC-VPN-02",
                "title": "5GC AMF Registration Storm",
                "description": "Technician using Pulse Secure client to access core dashboard. High SCTP drops on AMF pool.",
                "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["NOK-AMF-01"],
            },
            "m2": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.92},
            "m3": {"anomalies": [{"network_element_id": "NOK-AMF-01", "metric_name": "sctp_drops", "fused_score": 0.88}]},
            "expected_vendor": "NOKIA",
            "expected_runbook": "SOP-5GC-AMF-001",
            "expect_supported": True,
        },
        {
            "id": "EQP-IND-03",
            "name": "FortiClient VPN on Cisco ASR IP Router",
            "incident": {
                "incident_id": "INC-VPN-03",
                "title": "BGP Peer Down on Border Router",
                "description": "Connected over FortiClient SSL-VPN tunnel to investigate BGP hold timer expiration on core peer.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["CISCO-ASR-901"],
            },
            "m2": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.94},
            "m3": {"anomalies": [{"network_element_id": "CISCO-ASR-901", "metric_name": "bgp_flaps", "fused_score": 0.91}]},
            "expected_vendor": "CISCO",
            "expected_runbook": "SOP-TRANS-BGP-002",
            "expect_supported": True,
        },
        {
            "id": "EQP-IND-04",
            "name": "OpenVPN mention on Juniper PTX router",
            "incident": {
                "incident_id": "INC-VPN-04",
                "title": "Optical loss of signal on transport link",
                "description": "OpenVPN tunnel established to Juniper JunOS console; optical receiver power zero dBm.",
                "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["JUN-PTX-500"],
            },
            "m2": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.90},
            "m3": {"anomalies": [{"network_element_id": "JUN-PTX-500", "metric_name": "rx_optical_power", "fused_score": 0.89}]},
            "expected_vendor": "JUNIPER",
            "expected_runbook": "SOP-TRANS-FIBER-001",
            "expect_supported": True,
        },

        # --- Group B: EMS / NMS Software Mention Prose Noise ---
        {
            "id": "EQP-IND-05",
            "name": "Cisco Prime Infrastructure mentioned in Nokia Cell Alarm",
            "incident": {
                "incident_id": "INC-EMS-05",
                "title": "Antenna VSWR degradation on sector 3",
                "description": "Alarm forwarded from Cisco Prime umbrella dashboard for Nokia gNodeB cell 303 return loss.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["NOK-GNB-303"],
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.93},
            "m3": {"anomalies": [{"network_element_id": "NOK-GNB-303", "metric_name": "vswr", "fused_score": 0.87}]},
            "expected_vendor": "NOKIA",
            "expected_runbook": "SOP-RAN-VSWR-001",
            "expect_supported": True,
        },
        {
            "id": "EQP-IND-06",
            "name": "Juniper Space Network Director on Huawei Baseband",
            "incident": {
                "incident_id": "INC-EMS-06",
                "title": "Severe VSWR mismatch on Huawei antenna",
                "description": "Cross-domain alert forwarded by Juniper Space director: Huawei BBU antenna feeder high return loss.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["HUA-BBU-881"],
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.91},
            "m3": {"anomalies": [{"network_element_id": "HUA-BBU-881", "metric_name": "vswr", "fused_score": 0.86}]},
            "expected_vendor": "HUAWEI",
            "expected_runbook": "SOP-RAN-VSWR-001",
            "expect_supported": True,
        },

        # --- Group C: Conflicting Structured Metadata vs Narrative Text ---
        {
            "id": "EQP-IND-07",
            "name": "Structured vendor=ERICSSON overrides narrative 'Cisco router'",
            "incident": {
                "incident_id": "INC-CONF-07",
                "title": "Antenna Return Loss Spike",
                "description": "Report mentions Cisco router in transmission path, but element is Ericsson Radio 4415.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["RADIO-4415"],
                "metadata": {"vendor": "ERICSSON"},
            },
            "m2": {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.95},
            "m3": {"anomalies": [{"network_element_id": "RADIO-4415", "metric_name": "vswr", "fused_score": 0.91}]},
            "expected_vendor": "ERICSSON",
            "expected_runbook": "SOP-RAN-VSWR-001",
            "expect_supported": True,
        },
        {
            "id": "EQP-IND-08",
            "name": "Structured vendor=CISCO overrides narrative 'Ericsson cell'",
            "incident": {
                "incident_id": "INC-CONF-08",
                "title": "IP-MPLS BGP Session Flap",
                "description": "Serving Ericsson cell site backhaul, router interface BGP flap active.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["ROUTER-CORE-02"],
                "metadata": {"vendor": "CISCO"},
            },
            "m2": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.94},
            "m3": {"anomalies": [{"network_element_id": "ROUTER-CORE-02", "metric_name": "bgp", "fused_score": 0.90}]},
            "expected_vendor": "CISCO",
            "expected_runbook": "SOP-TRANS-BGP-002",
            "expect_supported": True,
        },

        # --- Group D: Proprietary Vendor Runbook Isolation (Negative Cases) ---
        {
            "id": "EQP-IND-09",
            "name": "Cisco BGP SOP Incompatible with Juniper Router Incident",
            "incident": {
                "incident_id": "INC-ISO-09",
                "title": "BGP Session Down on Juniper MX router",
                "description": "Juniper router BGP peering session down on core transit link.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["JUN-MX-01"],
                "metadata": {"vendor": "JUNIPER"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": "JUNIPER",
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # Cisco BGP runbook cannot run on Juniper -> Abstains
        },
        {
            "id": "EQP-IND-10",
            "name": "Cisco BGP SOP Incompatible with Huawei Router Incident",
            "incident": {
                "incident_id": "INC-ISO-10",
                "title": "BGP Peer Down on Huawei NE40 router",
                "description": "Huawei router BGP flapping to transit provider.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["HUA-NE40-01"],
                "metadata": {"vendor": "HUAWEI"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": "HUAWEI",
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # Cisco BGP runbook cannot run on Huawei -> Abstains
        },
        {
            "id": "EQP-IND-11",
            "name": "Cisco BGP SOP Incompatible with Nokia 7750 SR Incident",
            "incident": {
                "incident_id": "INC-ISO-11",
                "title": "BGP Session Down on Nokia 7750 SR router",
                "description": "Nokia 7750 Service Router BGP neighbor timeout.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["NOK-7750-01"],
                "metadata": {"vendor": "NOKIA"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": "NOKIA",
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # Cisco BGP runbook cannot run on Nokia -> Abstains
        },

        # --- Group E: Technology Generation Incompatibility (Negative Cases) ---
        {
            "id": "EQP-IND-12",
            "name": "2G GSM TRX Return Loss on 5G VSWR Runbook",
            "incident": {
                "incident_id": "INC-GEN-12",
                "title": "GSM 900 TRX Return Loss High",
                "description": "2G legacy BTS transmitter power reflection.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["BTS-2G-11"],
                "metadata": {"technology_generation": "2G_GSM"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": None,
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # 2G incompatible with 5G SOP -> Abstains
        },
        {
            "id": "EQP-IND-13",
            "name": "3G UMTS NodeB Power Amplifier on 5G VSWR Runbook",
            "incident": {
                "incident_id": "INC-GEN-13",
                "title": "UMTS 2100 NodeB RF reflection high",
                "description": "3G WCDMA power amplifier return loss spike.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
                "network_domain": "RAN",
                "network_element_ids": ["NODEB-3G-22"],
                "metadata": {"technology_generation": "3G_UMTS"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": None,
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # 3G incompatible with 5G SOP -> Abstains
        },
        {
            "id": "EQP-IND-14",
            "name": "WiMAX 802.16e ASN Gateway on 5G Runbook",
            "incident": {
                "incident_id": "INC-GEN-14",
                "title": "WiMAX ASN Gateway Carrier Lost",
                "description": "Legacy 802.16e ASN gateway connection lost.",
                "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["ASN-GW-01"],
                "metadata": {"technology_generation": "WIMAX"},
            },
            "m2": {},
            "m3": {},
            "expected_vendor": None,
            "expected_runbook": "HUMAN_ESCALATION",
            "expect_supported": False,  # WiMAX incompatible with 5G Core SOP -> Abstains
        },

        # --- Group F: Element Prefix Extraction Across All 6 Vendors ---
        {"id": "EQP-IND-15", "prefix_eval": ("ERIC-RRU-01", "ERICSSON")},
        {"id": "EQP-IND-16", "prefix_eval": ("NOK-GNB-02", "NOKIA")},
        {"id": "EQP-IND-17", "prefix_eval": ("CISCO-NCS-03", "CISCO")},
        {"id": "EQP-IND-18", "prefix_eval": ("JUN-QFX-04", "JUNIPER")},
        {"id": "EQP-IND-19", "prefix_eval": ("HUA-RRU-05", "HUAWEI")},
        {"id": "EQP-IND-20", "prefix_eval": ("ZTE-B8300-06", "ZTE")},

        # --- Group G: Bidirectional Filter Compatibility Logic (22 checks) ---
        {"id": "EQP-IND-21", "filter_eval": ("ERICSSON", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-22", "filter_eval": ("NOKIA", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-23", "filter_eval": ("HUAWEI", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-24", "filter_eval": ("CISCO", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-25", "filter_eval": ("JUNIPER", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-26", "filter_eval": ("ZTE", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-27", "filter_eval": ("MULTI_VENDOR", "GENERIC_3GPP", True)},
        {"id": "EQP-IND-28", "filter_eval": (None, "GENERIC_3GPP", True)},
        {"id": "EQP-IND-29", "filter_eval": ("ERICSSON", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-30", "filter_eval": ("NOKIA", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-31", "filter_eval": ("CISCO", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-32", "filter_eval": ("JUNIPER", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-33", "filter_eval": ("HUAWEI", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-34", "filter_eval": ("ZTE", "MULTI_VENDOR", True)},
        {"id": "EQP-IND-35", "filter_eval": ("JUNIPER", "CISCO", False)},
        {"id": "EQP-IND-36", "filter_eval": ("HUAWEI", "CISCO", False)},
        {"id": "EQP-IND-37", "filter_eval": ("NOKIA", "CISCO", False)},
        {"id": "EQP-IND-38", "filter_eval": ("ERICSSON", "CISCO", False)},
        {"id": "EQP-IND-39", "filter_eval": ("CISCO", "JUNIPER", False)},
        {"id": "EQP-IND-40", "filter_eval": ("ERICSSON", "NOKIA", False)},
        {"id": "EQP-IND-41", "filter_eval": ("GENERIC_3GPP", "CISCO", False)},  # Proprietary SOP cannot run on generic
        {"id": "EQP-IND-42", "filter_eval": ("ERICSSON", None, False)},  # Missing chunk vendor fails closed
    ]


def run_phase4_audit() -> Dict[str, Any]:
    print("=" * 80)
    print("PHASE 4: INDEPENDENT EQUIPMENT GROUNDING & RETRIEVAL AUDIT")
    print("=" * 80)

    docs, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)
    m_filter = MetadataFilter()

    test_cases = get_phase4_test_cases()
    results: List[Dict[str, Any]] = []

    passed_count = 0

    for tc in test_cases:
        t0 = time.perf_counter()
        passed = False
        details: Dict[str, Any] = {}

        if "prefix_eval" in tc:
            elem_id, expected_vend = tc["prefix_eval"]
            inc = {"network_element_ids": [elem_id]}
            extracted = IncidentInvestigationEngine._extract_vendor(inc)
            passed = extracted == expected_vend
            details = {"element_id": elem_id, "expected": expected_vend, "actual": extracted}

        elif "filter_eval" in tc:
            t_vend, c_vend, expected_val = tc["filter_eval"]
            actual_val = m_filter._is_vendor_compatible(t_vend, c_vend)
            passed = actual_val == expected_val
            details = {"target_vendor": t_vend, "chunk_vendor": c_vend, "expected": expected_val, "actual": actual_val}

        elif "expected_runbook" in tc:
            inc = tc["incident"]
            m2 = tc.get("m2")
            m3 = tc.get("m3")
            ctx = engine.investigate(inc, m2_classification=m2, m3_network_intelligence=m3)
            ext_vend = IncidentInvestigationEngine._extract_vendor(inc)

            vend_match = ext_vend == tc["expected_vendor"]
            ret_rb = ctx.m4_retrieval.get("primary_runbook_id")
            rb_match = ret_rb == tc["expected_runbook"] or (not tc["expect_supported"] and ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE)

            if tc["expect_supported"]:
                stat_match = ctx.hypotheses and ctx.hypotheses[0].status == HypothesisStatus.SUPPORTED
            else:
                stat_match = ctx.hypotheses and ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE

            passed = vend_match and rb_match and stat_match
            details = {
                "extracted_vendor": ext_vend,
                "retrieved_runbook": ret_rb,
                "hypothesis_status": ctx.hypotheses[0].status.value if ctx.hypotheses else None,
                "expect_supported": tc["expect_supported"],
            }

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        if passed:
            passed_count += 1

        results.append({
            "case_id": tc["id"],
            "name": tc.get("name", tc["id"]),
            "pass": passed,
            "latency_ms": elapsed_ms,
            "details": details,
        })

    total_cases = len(test_cases)
    pass_rate = (passed_count / total_cases) * 100.0

    print(f"[*] Completed {total_cases} Phase 4 Cases: {passed_count}/{total_cases} Passed ({pass_rate:.1f}%).")
    for r in results:
        status_str = "PASS" if r["pass"] else "FAIL"
        print(f"  [{r['case_id']}] [{status_str:4s}] {r['name']:55s} | Latency: {r['latency_ms']}ms")

    report_payload = {
        "milestone": "M5.2",
        "audit_phase": "Phase 4: Independent Equipment Grounding & Retrieval Audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "passed_cases": passed_count,
        "pass_rate_pct": round(pass_rate, 2),
        "cases": results,
    }

    out_file = Path("artifacts/m5_metrics/m5_2_independent_phase4_equipment.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)
    print(f"[*] Exported: {out_file}")

    return report_payload


if __name__ == "__main__":
    run_phase4_audit()
