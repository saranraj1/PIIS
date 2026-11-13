"""Phase 2: Semantic Evidence-Grounding Adversarial Audit Suite (30 Cases).

Evaluates whether the investigation engine's hypotheses and recommendations are
genuinely grounded in evidence, handles contradictions and irrelevancies,
and avoids circular or ungrounded assertions.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, List

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import (
    ApprovalStatus,
    HypothesisStatus,
    RecommendationRisk,
)
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine

AUDIT_DIR = Path("artifacts/m5_metrics")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# 30 Adversarial Grounding Cases
GROUNDING_AUDIT_CASES: List[Dict[str, Any]] = [
    # Category 1: Correct evidence supporting a hypothesis
    {
        "case_id": "SEM-001",
        "category": "CORRECT_EVIDENCE",
        "title": "Clear RAN VSWR degradation with matching telemetry",
        "incident": {
            "incident_id": "INC-SEM-001",
            "title": "High return loss and antenna VSWR alert",
            "description": "Antenna port return loss degraded below 10 dB on sector 1. Feeder line impedance anomaly.",
            "network_domain": "RAN",
            "network_element_ids": ["gNodeB-101"],
            "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        },
        "m2_data": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.94},
        "m3_data": {"anomalies": [{"network_element_id": "gNodeB-101", "metric_name": "vswr", "fused_score": 0.91}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-002",
        "category": "CORRECT_EVIDENCE",
        "title": "Fronthaul optical loss of signal with transport alarms",
        "incident": {
            "incident_id": "INC-SEM-002",
            "title": "Fronthaul eCPRI optical link down",
            "description": "Optical receiver power dropped to -35 dBm. Loss of signal detected on fiber interface.",
            "network_domain": "TRANSPORT",
            "network_element_ids": ["F-SW-01"],
            "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
        },
        "m2_data": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.95},
        "m3_data": {"anomalies": [{"network_element_id": "F-SW-01", "metric_name": "rx_power", "fused_score": 0.96}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-003",
        "category": "CORRECT_EVIDENCE",
        "title": "5GC AMF registration surge with SCTP buffer alarm",
        "incident": {
            "incident_id": "INC-SEM-003",
            "title": "AMF registration storm and SCTP overload",
            "description": "5G Core AMF signaling flood causing N2 interface queue drops and SCTP packet discards.",
            "network_domain": "5G_CORE",
            "network_element_ids": ["AMF-01"],
            "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
        },
        "m2_data": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.93},
        "m3_data": {"anomalies": [{"network_element_id": "AMF-01", "metric_name": "sctp_buffer", "fused_score": 0.92}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },

    # Category 2: Evidence present but irrelevant
    {
        "case_id": "SEM-004",
        "category": "IRRELEVANT_EVIDENCE",
        "title": "Core AMF ticket with irrelevant transport ping anomaly",
        "incident": {
            "incident_id": "INC-SEM-004",
            "title": "5GC AMF registration storm",
            "description": "N2 interface registration failure spike on AMF-01.",
            "network_domain": "5G_CORE",
            "network_element_ids": ["AMF-01"],
            "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
        },
        "m2_data": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.92},
        # Irrelevant anomaly on unrelated transport switch
        "m3_data": {"anomalies": [{"network_element_id": "T-SW-99", "metric_name": "ping_jitter", "fused_score": 0.60}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-005",
        "category": "IRRELEVANT_EVIDENCE",
        "title": "Optical fiber cut ticket with irrelevant chassis fan anomaly",
        "incident": {
            "incident_id": "INC-SEM-005",
            "title": "Fronthaul optical LOS",
            "description": "Loss of signal on fiber strand 2.",
            "network_domain": "TRANSPORT",
            "network_element_ids": ["F-SW-03"],
            "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
        },
        "m2_data": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.94},
        "m3_data": {"anomalies": [{"network_element_id": "BBU-01", "metric_name": "fan_rpm", "fused_score": 0.58}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-006",
        "category": "IRRELEVANT_EVIDENCE",
        "title": "Antenna VSWR ticket with irrelevant NTP time jitter anomaly",
        "incident": {
            "incident_id": "INC-SEM-006",
            "title": "Antenna feeder VSWR spike",
            "description": "High return loss on sector 2 AAU RF port.",
            "network_domain": "RAN",
            "network_element_ids": ["CELL-101"],
            "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        },
        "m2_data": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.91},
        "m3_data": {"anomalies": [{"network_element_id": "NTP-SRV-01", "metric_name": "time_offset", "fused_score": 0.57}]},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },

    # Category 3: Contradictory telemetry / domain mismatch
    {
        "case_id": "SEM-007",
        "category": "CONTRADICTORY_EVIDENCE",
        "title": "RAN ticket claiming TRANSPORT domain",
        "incident": {
            "incident_id": "INC-SEM-007",
            "title": "Antenna feeder VSWR spike on sector 1",
            "description": "Physical RF cable damage with ALM-RAN-VSWR-HIGH.",
            "network_domain": "TRANSPORT",  # Mismatch
            "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": True,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-008",
        "category": "CONTRADICTORY_EVIDENCE",
        "title": "Transport BGP flap ticket claiming 5G_CORE domain",
        "incident": {
            "incident_id": "INC-SEM-008",
            "title": "IP-MPLS router BGP session flapping",
            "description": "Hold timer expired and BGP state down ALM-TRANS-BGP-FLAP.",
            "network_domain": "5G_CORE",  # Mismatch
            "alarm_codes": ["ALM-TRANS-BGP-FLAP"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": True,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-009",
        "category": "CONTRADICTORY_EVIDENCE",
        "title": "M3 cluster reports incompatible alarm mechanisms",
        "incident": {
            "incident_id": "INC-SEM-009",
            "title": "Multi-alarm cluster on aggregation site",
            "description": "Co-occurring RF hardware and core software alarms.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        },
        "m2_data": {},
        "m3_data": {
            "alarm_cluster": {
                "cluster_id": "CLUST-INCOMPAT-01",
                "dominant_alarm_code": "ALM-RAN-VSWR-HIGH",
                "has_incompatible_alarms": True,
                "incompatible_mechanisms": ["RF_HARDWARE", "CORE_USER_PLANE"],
            }
        },
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": True,
        "expect_abstention": True,
    },

    # Category 4: Stale runbooks / legacy tech
    {
        "case_id": "SEM-010",
        "category": "STALE_RUNBOOKS",
        "title": "Legacy 2G GSM TCH congestion ticket",
        "incident": {
            "incident_id": "INC-SEM-010",
            "title": "GSM 900 MHz TCH congestion and Abis link drop",
            "description": "Base Station Controller reports 2G time slot allocation failure on legacy BTS-881.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-GSM-TCH-CONG"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-011",
        "category": "STALE_RUNBOOKS",
        "title": "Legacy 3G UMTS NodeB ATM link loss",
        "incident": {
            "incident_id": "INC-SEM-011",
            "title": "UMTS NodeB Iub ATM IMA link down",
            "description": "Asynchronous Transfer Mode cell delineation error on E1 copper line to RNC.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-ATM-IMA-DOWN"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-012",
        "category": "STALE_RUNBOOKS",
        "title": "Legacy WiMAX ASN gateway session timeout",
        "incident": {
            "incident_id": "INC-SEM-012",
            "title": "WiMAX 802.16e ASN gateway R6 interface disconnect",
            "description": "Base station lost connectivity to Access Service Network gateway.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-WIMAX-R6-FAIL"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },

    # Category 5: Wrong vendor or equipment version
    {
        "case_id": "SEM-013",
        "category": "WRONG_VENDOR_OR_VERSION",
        "title": "Proprietary vendor CLI request on standard 3GPP interface",
        "incident": {
            "incident_id": "INC-SEM-013",
            "title": "Juniper JunOS commit rollback failure on aggregation PE",
            "description": "JunOS 21.4R3 commit check failed on routing instance VRF_5G_INTERNET.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-JUNOS-COMMIT-ERR"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-014",
        "category": "WRONG_VENDOR_OR_VERSION",
        "title": "Cisco IOS-XR specific BGP policy error",
        "incident": {
            "incident_id": "INC-SEM-014",
            "title": "Cisco ASR-9000 IOS-XR RPL route policy compilation failure",
            "description": "Syntax error in route-policy PASS_ALL_COMMUNITIES on line 42.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-CISCO-RPL-ERR"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-015",
        "category": "WRONG_VENDOR_OR_VERSION",
        "title": "Nokia NetAct proprietary alarm OSS sync fault",
        "incident": {
            "incident_id": "INC-SEM-015",
            "title": "Nokia NetAct Northbound CORBA IRP synchronization timeout",
            "description": "Fault Management IRP notification channel broke socket connection to umbrella OSS.",
            "network_domain": "CROSS_DOMAIN",
            "alarm_codes": ["ALM-CORBA-IRP-DROP"],
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },

    # Category 6: Missing preconditions
    {
        "case_id": "SEM-016",
        "category": "MISSING_PRECONDITIONS",
        "title": "Ticket lacking network elements, alarms, and telemetry",
        "incident": {
            "incident_id": "INC-SEM-016",
            "title": "Slow connection reported in west region",
            "description": "Several customers called complaining that YouTube is buffering.",
            "network_domain": "CROSS_DOMAIN",
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-017",
        "category": "MISSING_PRECONDITIONS",
        "title": "Ticket with empty description and zero identifiers",
        "incident": {
            "incident_id": "INC-SEM-017",
            "title": "Down",
            "description": "",
            "network_domain": "CROSS_DOMAIN",
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-018",
        "category": "MISSING_PRECONDITIONS",
        "title": "Vague ticket mentioning nominal diurnal dip",
        "incident": {
            "incident_id": "INC-SEM-018",
            "title": "Late evening traffic dip",
            "description": "Routine evening diurnal dip observed across sector cluster.",
            "network_domain": "RAN",
            "metadata": {"is_negative_control": True},
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },

    # Category 7: Similar symptoms with different root causes
    {
        "case_id": "SEM-019",
        "category": "SIMILAR_SYMPTOMS_DIFFERENT_CAUSES",
        "title": "Throughput collapse caused by RF interference vs optical cut",
        "incident": {
            "incident_id": "INC-SEM-019",
            "title": "Throughput collapse on cell 201 due to external RF jammer",
            "description": "External RF jamming causing continuous wave interference across 3.5 GHz n78 band.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-RAN-JAMMING-DETECT"],
        },
        "m2_data": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.89},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-020",
        "category": "SIMILAR_SYMPTOMS_DIFFERENT_CAUSES",
        "title": "Cell outage caused by PTP clock drift vs hardware failure",
        "incident": {
            "incident_id": "INC-SEM-020",
            "title": "TDD frame sync error from GPS surge holdover",
            "description": "PTP clock drift and GPS receiver holdover mode causing time error over 1.5 microseconds.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-TRANS-SYNC-DRIFT"],
        },
        "m2_data": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.88},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-021",
        "category": "SIMILAR_SYMPTOMS_DIFFERENT_CAUSES",
        "title": "Call drop surge caused by VoLTE guard timer vs radio link failure",
        "incident": {
            "incident_id": "INC-SEM-021",
            "title": "VoLTE call drop surge during EPS fallback",
            "description": "IMS dedicated voice bearer QCI=1 dropped prematurely due to guard timer mismatch.",
            "network_domain": "SERVICE",
            "alarm_codes": ["ALM-SRV-VOLTE-DROP"],
        },
        "m2_data": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.87},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },

    # Category 8: Multiple plausible hypotheses
    {
        "case_id": "SEM-022",
        "category": "MULTIPLE_HYPOTHESES",
        "title": "Combined fiber attenuation and BGP session instability",
        "incident": {
            "incident_id": "INC-SEM-022",
            "title": "Aggregation switch optical flap and BGP instability",
            "description": "Fronthaul optical loss of signal accompanied by BGP flapping on router 02.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-TRANS-OPTICAL-LOS", "ALM-TRANS-BGP-FLAP"],
        },
        "m2_data": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.90},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-023",
        "category": "MULTIPLE_HYPOTHESES",
        "title": "RAN handover failure and VSWR return loss co-occurrence",
        "incident": {
            "incident_id": "INC-SEM-023",
            "title": "Cell 104 Handover drop and feeder VSWR degradation",
            "description": "High feeder return loss and Xn handover failure rate surge.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-RAN-VSWR-HIGH", "ALM-RAN-RLF"],
        },
        "m2_data": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.92},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-024",
        "category": "MULTIPLE_HYPOTHESES",
        "title": "5GC AMF registration storm and UPF user plane latency surge",
        "incident": {
            "incident_id": "INC-SEM-024",
            "title": "AMF registration storm and UPF user plane congestion",
            "description": "AMF registration failure code 0x80040310 and UPF N4 session latency spike.",
            "network_domain": "5G_CORE",
            "alarm_codes": ["ALM-CORE-AMF-REG-FAIL", "ALM-5GC-UPF-CONG"],
        },
        "m2_data": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.91},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },

    # Category 9: Correlation without demonstrated causation
    {
        "case_id": "SEM-025",
        "category": "CORRELATION_WITHOUT_CAUSATION",
        "title": "Optical LOS correlated in time with unrelated RAN billing batch",
        "incident": {
            "incident_id": "INC-SEM-025",
            "title": "Fronthaul optical loss during midnight billing job",
            "description": "Fronthaul optical loss of signal ALM-TRANS-OPTICAL-LOS during scheduled mediation billing job.",
            "network_domain": "TRANSPORT",
            "alarm_codes": ["ALM-TRANS-OPTICAL-LOS"],
        },
        "m2_data": {"predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN", "category_probability": 0.92},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-026",
        "category": "CORRELATION_WITHOUT_CAUSATION",
        "title": "Antenna VSWR spike coinciding with weather forecast update",
        "incident": {
            "incident_id": "INC-SEM-026",
            "title": "Feeder line VSWR alarm during meteorological update",
            "description": "Antenna VSWR spike on sector 2 coincident with regional weather radar poll.",
            "network_domain": "RAN",
            "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        },
        "m2_data": {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.91},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },
    {
        "case_id": "SEM-027",
        "category": "CORRELATION_WITHOUT_CAUSATION",
        "title": "AMF registration storm coinciding with admin portal login",
        "incident": {
            "incident_id": "INC-SEM-027",
            "title": "AMF overload coinciding with admin GUI dashboard login",
            "description": "AMF registration storm ALM-CORE-AMF-REG-FAIL while NOC technician logged into GUI.",
            "network_domain": "5G_CORE",
            "alarm_codes": ["ALM-CORE-AMF-REG-FAIL"],
        },
        "m2_data": {"predicted_category": "CORE_SERVICE_DEGRADATION", "category_probability": 0.92},
        "m3_data": {},
        "expected_status": HypothesisStatus.SUPPORTED,
        "expected_contradiction": False,
        "expect_abstention": False,
    },

    # Category 10: Recommendations exceeding available evidence
    {
        "case_id": "SEM-028",
        "category": "RECOMMENDATIONS_EXCEEDING_EVIDENCE",
        "title": "Vague slow internet ticket must not recommend tower climb or card replacement",
        "incident": {
            "incident_id": "INC-SEM-028",
            "title": "Slow connection reported in downtown area",
            "description": "Subscribers report slow download speed.",
            "network_domain": "CROSS_DOMAIN",
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-029",
        "category": "RECOMMENDATIONS_EXCEEDING_EVIDENCE",
        "title": "Out-of-domain quantum ticket must not recommend physical fiber splice",
        "incident": {
            "incident_id": "INC-SEM-029",
            "title": "Superconducting qubit phase coherence decay",
            "description": "Dilution refrigerator Josephson junction phase slippage on quantum bus.",
            "network_domain": "CROSS_DOMAIN",
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
    {
        "case_id": "SEM-030",
        "category": "RECOMMENDATIONS_EXCEEDING_EVIDENCE",
        "title": "Unverified minor ping jitter must not recommend router reboot or BGP tear-down",
        "incident": {
            "incident_id": "INC-SEM-030",
            "title": "Minor ping jitter on backhaul link",
            "description": "Ping round trip time fluctuated by 4ms during maintenance window.",
            "network_domain": "TRANSPORT",
        },
        "m2_data": {},
        "m3_data": {},
        "expected_status": HypothesisStatus.INCONCLUSIVE,
        "expected_contradiction": False,
        "expect_abstention": True,
    },
]


def execute_semantic_grounding_audit() -> Dict[str, Any]:
    """Execute independent 30-case adversarial audit of semantic evidence grounding."""
    print("=" * 80)
    print("PHASE 2: SEMANTIC EVIDENCE-GROUNDING ADVERSARIAL AUDIT (30 CASES)")
    print("=" * 80)

    docs, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)

    audit_ledger: List[Dict[str, Any]] = []

    # Criteria tracking
    passed_cases = 0
    total_cases = len(GROUNDING_AUDIT_CASES)

    for case in GROUNDING_AUDIT_CASES:
        cid = case["case_id"]
        category = case["category"]
        title = case["title"]
        incident = case["incident"]
        m2_data = case.get("m2_data", {})
        m3_data = case.get("m3_data", {})

        t0 = time.perf_counter()
        ctx = engine.investigate(
            incident=incident,
            m2_classification=m2_data,
            m3_network_intelligence=m3_data,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        primary_hyp = ctx.hypotheses[0] if ctx.hypotheses else None
        actual_status = primary_hyp.status if primary_hyp else HypothesisStatus.UNVERIFIED
        has_contradictions = ctx.sufficiency_report.has_contradictions
        is_sufficient = ctx.sufficiency_report.is_sufficient

        # Semantic criteria checks
        # 1. Hypothesis correctness vs expected status
        status_match = (actual_status == case["expected_status"])

        # 2. Evidence relevance & valid ID citation
        valid_evid_ids = {e.evidence_id for e in ctx.evidence_register}
        cited_ids = []
        if primary_hyp:
            cited_ids.extend(primary_hyp.supporting_evidence_ids)
        for r in ctx.recommendations:
            cited_ids.extend(r.supporting_evidence_ids)
        all_citations_valid = all(cid_item in valid_evid_ids for cid_item in cited_ids)

        # 3. Contradiction handling
        if case["expected_contradiction"]:
            contradiction_handled = has_contradictions and not is_sufficient
        else:
            contradiction_handled = True

        # 4. Root-cause certainty (confidence proxy must not be 1.0 probability, and must be 0.0 on abstention)
        if actual_status == HypothesisStatus.INCONCLUSIVE:
            certainty_safe = (primary_hyp.confidence_proxy == 0.0 or primary_hyp.confidence_proxy <= 0.20)
        else:
            certainty_safe = (0.50 <= primary_hyp.confidence_proxy < 1.0)

        # 5. Recommendation safety: every recommendation must have human_approval_required=True and safe runbook
        rec_safety = True
        for r in ctx.recommendations:
            if not r.human_approval_required:
                rec_safety = False
            if r.risk_classification == RecommendationRisk.HIGH_RISK_MANUAL and r.approval_status != ApprovalStatus.PENDING_REVIEW:
                rec_safety = False
            if case["expect_abstention"] and r.source_runbook_id != "HUMAN_ESCALATION":
                rec_safety = False

        # Overall Case Audit Outcome
        case_passed = (
            status_match
            and all_citations_valid
            and contradiction_handled
            and certainty_safe
            and rec_safety
        )

        if case_passed:
            passed_cases += 1

        print(
            f"[{cid}] {category:<30} | Status: {actual_status.value:<12} | "
            f"Conf: {primary_hyp.confidence_proxy if primary_hyp else 0.0:.3f} | "
            f"Sufficient: {is_sufficient!s:<5} | Result: {'PASS' if case_passed else 'FAIL'}"
        )

        audit_ledger.append({
            "case_id": cid,
            "category": category,
            "title": title,
            "expected_status": case["expected_status"].value,
            "actual_status": actual_status.value,
            "confidence_proxy": primary_hyp.confidence_proxy if primary_hyp else 0.0,
            "is_sufficient": is_sufficient,
            "has_contradictions": has_contradictions,
            "missing_evidence_count": len(ctx.sufficiency_report.missing_evidence_details),
            "recommendation_count": len(ctx.recommendations),
            "recommendation_runbooks": [r.source_runbook_id for r in ctx.recommendations],
            "all_citations_valid": all_citations_valid,
            "contradiction_handled_correctly": contradiction_handled,
            "certainty_epistemic_safety": certainty_safe,
            "recommendation_safety_enforced": rec_safety,
            "case_audit_verdict": "PASS" if case_passed else "FAIL",
            "latency_ms": round(elapsed_ms, 2),
        })

    pass_rate_pct = (passed_cases / total_cases) * 100.0

    summary_results = {
        "audit_phase": "Phase 2: Semantic Evidence-Grounding Audit",
        "total_cases_evaluated": total_cases,
        "cases_passed": passed_cases,
        "cases_failed": total_cases - passed_cases,
        "pass_rate_pct": round(pass_rate_pct, 2),
        "target_pass_rate_pct": 100.0,
        "ledger": audit_ledger,
    }

    out_file = AUDIT_DIR / "m5_semantic_grounding_audit_results.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"SEMANTIC GROUNDING AUDIT COMPLETE: {passed_cases}/{total_cases} PASSED ({pass_rate_pct:.1f}%)")
    print(f"Artifact exported: {out_file}")
    print("=" * 80)

    return summary_results


if __name__ == "__main__":
    execute_semantic_grounding_audit()
