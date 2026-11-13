"""Independent Audit Script: Phase 2 - Equipment-Aware Retrieval & Grounding Generalization.

Evaluates at least 25 NEW test cases not present in the original 30-case semantic suite.
Covers:
- 2G, 3G, 4G, and 5G equipment.
- Multi-generation environments.
- Ericsson, Nokia, Huawei, Cisco, Juniper equipment.
- Unknown vendors (ZTE, Mavenir, Altiostar, Casa Systems).
- Software version variations.
- Vendor-neutral procedures vs vendor-specific procedures.
- Legacy-to-modern migration environments.
- Similar fault vocabulary across incompatible platforms.
- Conflicting vendor and generation metadata.
- Missing or unreliable metadata.
- Prose false-matching vs authoritative equipment identity.
- Positive controls for valid retrieval coverage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import HypothesisStatus
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


def get_generalization_test_cases() -> List[Dict[str, Any]]:
    return [
        # --- Group 1: Legacy Generations & Incompatibilities ---
        {
            "case_id": "GEN-01",
            "name": "3G UMTS NodeB Power Amplifier Overheat",
            "category": "LEGACY_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-01",
                "title": "NodeB Cell 3409 Power Amplifier High Temperature",
                "description": "3G NodeB WCDMA carrier in rack R02 experiencing PA thermal shutdown and Iub link degradation.",
                "alarm_codes": ["PA_OVERTEMP", "IUB_CONGESTION"],
                "network_domain": "RAN",
                "metadata": {"technology_generation": "3G_UMTS", "vendor": "ERICSSON"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001", "SOP-RAN-SYNC-006"],
            "rationale": "3G UMTS has no approved runbook in corpus; must abstain rather than cite 5G gNodeB SOP.",
        },
        {
            "case_id": "GEN-02",
            "name": "2G GSM Abis Interface Sync Loss",
            "category": "LEGACY_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-02",
                "title": "GSM BTS Abis T1/E1 Framing Error",
                "description": "2G legacy BTS experiencing framing slip and sync loss on TDM Abis interface to BSC.",
                "alarm_codes": ["ABIS_SYNC_FAIL", "TDM_SLIP"],
                "network_domain": "RAN",
                "metadata": {"technology_generation": "2G_GSM", "vendor": "NOKIA"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-SYNC-006"],
            "rationale": "2G GSM TDM sync failure must not match 5G IEEE-1588 PTP synchronization SOP.",
        },
        {
            "case_id": "GEN-03",
            "name": "WiMAX 802.16e ASN Gateway Keepalive Failure",
            "category": "LEGACY_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-03",
                "title": "WiMAX ASN-GW Session Teardown",
                "description": "Legacy 802.16e ASN Gateway dropping mobile subscriber GRE tunnels across WiMAX radio nodes.",
                "alarm_codes": ["ASN_KEEPALIVE_EXP", "GRE_DROP"],
                "network_domain": "CORE",
                "metadata": {"technology_generation": "WIMAX"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-CORE-AMF-003", "SOP-CORE-UPF-007"],
            "rationale": "Deprecated WiMAX must not match 5G AMF or UPF runbooks.",
        },
        {
            "case_id": "GEN-04",
            "name": "4G LTE MME S1-MME Path Drop",
            "category": "LEGACY_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-04",
                "title": "4G eNodeB S1-C SCTP Disconnect",
                "description": "LTE eNodeB disconnected from MME pool due to SCTP heartbeat failure on S1-MME interface.",
                "alarm_codes": ["S1_SCTP_DOWN", "ENB_UNREACHABLE"],
                "network_domain": "CORE",
                "metadata": {"technology_generation": "4G_LTE", "vendor": "ERICSSON"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-CORE-AMF-003"],
            "rationale": "4G LTE MME failure must not match 5G Service-Based Architecture AMF SOP.",
        },

        # --- Group 2: Vendor Incompatibilities (Proprietary NOS & Hardware) ---
        {
            "case_id": "GEN-05",
            "name": "Huawei U2020 Core Signaling Storm",
            "category": "VENDOR_INCOMPATIBILITY",
            "incident": {
                "incident_id": "INC-GEN-05",
                "title": "Huawei USN9810 Signaling Overload",
                "description": "Huawei U2020 reports signaling processing board processor utilization at 99% under heavy registration burst.",
                "alarm_codes": ["SIGNALING_OVERLOAD", "CPU_SPIKE"],
                "network_domain": "CORE",
                "metadata": {"vendor": "HUAWEI", "technology_generation": "4G_LTE"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-CORE-AMF-003"],
            "rationale": "Huawei proprietary core has no approved SOP; must abstain.",
        },
        {
            "case_id": "GEN-06",
            "name": "Juniper PTX10008 BGP Route Flap",
            "category": "VENDOR_INCOMPATIBILITY",
            "incident": {
                "incident_id": "INC-GEN-06",
                "title": "Juniper PTX JunOS BGP Peer Reset",
                "description": "JunOS 21.4R3 BGP session to remote peer reset due to BFD timeout on ae1 interface.",
                "alarm_codes": ["BGP_PEER_DOWN", "BFD_DOWN"],
                "network_domain": "TRANSPORT",
                "metadata": {"vendor": "JUNIPER", "technology_generation": "OPTICAL_IP_TRANSPORT"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-TRAN-BGP-005"],
            "rationale": "SOP-TRAN-BGP-005 is strictly Cisco ASR-9000 IOS-XR; must not match Juniper JunOS.",
        },
        {
            "case_id": "GEN-07",
            "name": "Nokia 7750 SR OS BGP Session Drop",
            "category": "VENDOR_INCOMPATIBILITY",
            "incident": {
                "incident_id": "INC-GEN-07",
                "title": "Nokia 7750 SR-12e BGP Flap",
                "description": "Nokia TiMOS/SROS 7750 router experiencing hold-timer expired on eBGP peer to transit provider.",
                "alarm_codes": ["BGP_HOLD_TIMER", "PEER_RESET"],
                "network_domain": "TRANSPORT",
                "metadata": {"vendor": "NOKIA", "technology_generation": "OPTICAL_IP_TRANSPORT"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-TRAN-BGP-005"],
            "rationale": "Nokia SROS transport failure must not match Cisco ASR9k SOP.",
        },
        {
            "case_id": "GEN-08",
            "name": "Nokia AirScale gNodeB VSWR Spike",
            "category": "VENDOR_INCOMPATIBILITY",
            "incident": {
                "incident_id": "INC-GEN-08",
                "title": "Nokia AirScale gNB Radio Frequency High Reflected Power",
                "description": "Nokia AirScale sub-6GHz gNodeB radio unit reports high VSWR alarm on port 2.",
                "alarm_codes": ["VSWR_HIGH", "RF_MISMATCH"],
                "network_domain": "RAN",
                "metadata": {"vendor": "NOKIA", "technology_generation": "5G_NR"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001"],
            "rationale": "SOP-RAN-VSWR-001 is vendor-locked to Ericsson Radio System and ENM.",
        },

        # --- Group 3: Unknown / Unindexed Third-Party Vendors ---
        {
            "case_id": "GEN-09",
            "name": "ZTE ZXUN Core NRF Service Registration Failure",
            "category": "UNKNOWN_VENDOR",
            "incident": {
                "incident_id": "INC-GEN-09",
                "title": "ZTE NRF NF Service Registration Failure",
                "description": "ZTE 5GC network function registration timeout towards ZXUN central repository.",
                "alarm_codes": ["NRF_REG_TIMEOUT"],
                "network_domain": "CORE",
                "metadata": {"vendor": "ZTE", "technology_generation": "5G_CORE"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-CORE-AMF-003"],
            "rationale": "ZTE is not in repository; must abstain and not silently assign Nokia AMF SOP.",
        },
        {
            "case_id": "GEN-10",
            "name": "Mavenir OpenRAN CU/DU F1-C Connection Timeout",
            "category": "UNKNOWN_VENDOR",
            "incident": {
                "incident_id": "INC-GEN-10",
                "title": "Mavenir vDU F1 Interface Disconnect",
                "description": "Mavenir containerized vDU lost SCTP association with vCU on virtualized Kubernetes pod.",
                "alarm_codes": ["F1C_LOST", "O_RAN_DISCONNECT"],
                "network_domain": "RAN",
                "metadata": {"vendor": "MAVENIR", "technology_generation": "5G_NR"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001", "SOP-RAN-SYNC-006"],
            "rationale": "Mavenir OpenRAN software architecture not covered by Ericsson bare-metal gNB SOP.",
        },
        {
            "case_id": "GEN-11",
            "name": "Altiostar Open vRAN Timing Drift",
            "category": "UNKNOWN_VENDOR",
            "incident": {
                "incident_id": "INC-GEN-11",
                "title": "Altiostar vRAN Sync Loss",
                "description": "Altiostar baseband software timing drift on virtualized distribution unit.",
                "alarm_codes": ["SYNC_DRIFT", "PTP_UNSTABLE"],
                "network_domain": "RAN",
                "metadata": {"vendor": "ALTIOSTAR", "technology_generation": "5G_NR"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-SYNC-006"],
            "rationale": "Altiostar vRAN sync failure must not match Ericsson gNodeB synchronization SOP.",
        },
        {
            "case_id": "GEN-12",
            "name": "Casa Systems Small Cell HeNB Security Gateway Drop",
            "category": "UNKNOWN_VENDOR",
            "incident": {
                "incident_id": "INC-GEN-12",
                "title": "Casa Systems Apex Small Cell IPSec Tunnel Drop",
                "description": "Small cell gateway reports IPSec tunnel timeout across public backhaul.",
                "alarm_codes": ["IPSEC_DOWN", "HENB_OFFLINE"],
                "network_domain": "RAN",
                "metadata": {"vendor": "CASA_SYSTEMS", "technology_generation": "4G_LTE"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001"],
            "rationale": "Casa Systems residential small cell not covered by macro gNB runbooks.",
        },

        # --- Group 4: Multi-Generation & Hybrid Environments ---
        {
            "case_id": "GEN-13",
            "name": "5G NSA Dual-Connectivity Radio Failure",
            "category": "MULTI_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-13",
                "title": "NSA Option 3x Secondary Node Addition Failure",
                "description": "4G LTE anchor eNodeB reports SgNB addition failure on X2-C interface towards 5G gNodeB.",
                "alarm_codes": ["SGNB_ADD_FAIL", "X2C_TIMEOUT"],
                "network_domain": "RAN",
                "metadata": {"technology_generation": "MULTI_GEN", "vendor": "ERICSSON"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001"],
            "rationale": "5G NSA X2-C signaling failure has no dedicated NSA SOP; must abstain rather than cite feeder cable VSWR.",
        },
        {
            "case_id": "GEN-14",
            "name": "Legacy 2G/4G Shared Antenna Feeder Issue",
            "category": "MULTI_GENERATION",
            "incident": {
                "incident_id": "INC-GEN-14",
                "title": "Shared Diplexer Feeder High VSWR on 2G/4G Colocated Site",
                "description": "Colocated 2G GSM and 4G LTE site sharing cross-band combiner reports elevated return loss.",
                "alarm_codes": ["VSWR_HIGH", "COMBINER_FAULT"],
                "network_domain": "RAN",
                "metadata": {"technology_generation": "2G_GSM", "vendor": "ERICSSON"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001"],
            "rationale": "Ticket tagged 2G_GSM must abstain from 5G NR SOP-RAN-VSWR-001.",
        },

        # --- Group 5: Similar Fault Vocabulary Across Incompatible Domains ---
        {
            "case_id": "GEN-15",
            "name": "Storage Area Network Fibre Channel Link Down (IT/Storage vs Telecom)",
            "category": "VOCABULARY_FALSE_MATCH",
            "incident": {
                "incident_id": "INC-GEN-15",
                "title": "Brocade SAN Switch FC Port Loss of Signal",
                "description": "Data center SAN switch port 16 reports optical loss of signal to NetApp storage array.",
                "alarm_codes": ["OPTICAL_LOS", "LINK_DOWN"],
                "network_domain": "IT_ENTERPRISE",
                "metadata": {"vendor": "BROCADE", "technology_generation": "ENTERPRISE_SAN"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-OPT-FIBER-002"],
            "rationale": "Data center Fibre Channel storage failure must not match telecom long-haul DWDM transponder SOP.",
        },
        {
            "case_id": "GEN-16",
            "name": "Database Connection Pool Exhaustion (SIP 503 similarity)",
            "category": "VOCABULARY_FALSE_MATCH",
            "incident": {
                "incident_id": "INC-GEN-16",
                "title": "PostgreSQL Backend HTTP 503 Service Unavailable",
                "description": "Web portal backend reporting HTTP 503 due to database connection pool saturation.",
                "alarm_codes": ["HTTP_503", "DB_CONN_FAIL"],
                "network_domain": "IT_ENTERPRISE",
                "metadata": {"vendor": "POSTGRESQL"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-IMS-SIP-004"],
            "rationale": "Enterprise web HTTP 503 must not match Telecom IMS Core SIP 503 outage SOP.",
        },

        # --- Group 6: Conflicting & Unreliable Metadata ---
        {
            "case_id": "GEN-17",
            "name": "Conflicting Metadata: Header says 5G Nokia, Text describes Cisco Router",
            "category": "CONFLICTING_METADATA",
            "incident": {
                "incident_id": "INC-GEN-17",
                "title": "5G Nokia gNB Core Gateway Alarm",
                "description": "Cisco ASR-9000 router at IP transport hub experiencing BGP session reset on TenGigE0/1/0/0.",
                "alarm_codes": ["BGP_PEER_DOWN"],
                "network_domain": "TRANSPORT",
                "metadata": {"technology_generation": "5G_NR", "vendor": "NOKIA"},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001", "SOP-CORE-AMF-003"],
            "rationale": "Conflicting metadata (Nokia 5G vs Cisco BGP) creates contradiction; must abstain.",
        },
        {
            "case_id": "GEN-18",
            "name": "Blank / Unreliable Metadata with Vague Description",
            "category": "MISSING_METADATA",
            "incident": {
                "incident_id": "INC-GEN-18",
                "title": "Network Degradation",
                "description": "Site alarms active, throughput dropped.",
                "alarm_codes": ["GENERIC_DEGRADATION"],
                "network_domain": "RAN",
                "metadata": {},
            },
            "expected_status": HypothesisStatus.INCONCLUSIVE,
            "expected_runbook_forbidden": ["SOP-RAN-VSWR-001", "SOP-OPT-FIBER-002", "SOP-CORE-AMF-003"],
            "rationale": "Under-specified ticket lacking equipment generation and failure mechanism must abstain.",
        },

        # --- Group 7: Prose False Matching (Mentions vendor in conversational context) ---
        {
            "case_id": "GEN-19",
            "name": "Prose False Match: Customer on Cisco VPN reporting 5G Ericsson Cell Down",
            "category": "PROSE_FALSE_MATCH",
            "incident": {
                "incident_id": "INC-GEN-19",
                "title": "gNodeB GNB-NYC-042 Antenna Return Loss Fault",
                "description": "Subscriber using Cisco AnyConnect VPN on laptop called NOC to report 5G NR cell site GNB-NYC-042 antenna feeder VSWR high.",
                "alarm_codes": ["VSWR_HIGH", "ANTENNA_FAULT"],
                "network_domain": "RAN",
                "metadata": {"technology_generation": "5G_NR", "vendor": "ERICSSON"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-RAN-VSWR-001",
            "rationale": "Authoritative metadata is Ericsson 5G; prose mention of Cisco VPN must NOT trigger vendor mismatch rejection.",
        },
        {
            "case_id": "GEN-20",
            "name": "Prose False Match: Tech mentions Nokia tool while working on Cisco ASR",
            "category": "PROSE_FALSE_MATCH",
            "incident": {
                "incident_id": "INC-GEN-20",
                "title": "Cisco ASR9k BGP Flap on Core Link",
                "description": "Field tech comparing telemetry against Nokia NetAct dashboard observed Cisco ASR-9000 BGP neighbor flap.",
                "alarm_codes": ["BGP_PEER_DOWN", "BFD_TIMEOUT"],
                "network_domain": "TRANSPORT",
                "metadata": {"technology_generation": "OPTICAL_IP_TRANSPORT", "vendor": "CISCO"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-TRAN-BGP-005",
            "rationale": "Authoritative metadata is Cisco; conversational mention of Nokia NetAct must not block Cisco BGP runbook.",
        },

        # --- Group 8: Vendor-Neutral Runbook Verification ---
        {
            "case_id": "GEN-21",
            "name": "Vendor-Neutral Optical Runbook on Juniper DWDM Link",
            "category": "VENDOR_NEUTRAL",
            "incident": {
                "incident_id": "INC-GEN-21",
                "title": "Optical Fiber Cut on Metro Transport Ring",
                "description": "DWDM transponder reports loss of signal and 0.0 dBm Rx power on physical fiber pair between Ring Nodes A and B.",
                "alarm_codes": ["OPTICAL_LOS", "FIBER_CUT"],
                "network_domain": "TRANSPORT",
                "metadata": {"technology_generation": "OPTICAL_IP_TRANSPORT", "vendor": "GENERIC_3GPP"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-OPT-FIBER-002",
            "rationale": "SOP-OPT-FIBER-002 is vendor-neutral and must be retrieved when query vendor is GENERIC_3GPP or unconstrained.",
        },
        {
            "case_id": "GEN-22",
            "name": "Vendor-Neutral IMS SIP 503 Outage on Multi-Vendor Core",
            "category": "VENDOR_NEUTRAL",
            "incident": {
                "incident_id": "INC-GEN-22",
                "title": "IMS Telephony Application Server SIP 503 Surge",
                "description": "Multi-vendor IMS core TAS returning SIP 503 Service Unavailable responses during call setup surge.",
                "alarm_codes": ["SIP_503_SURGE", "CALL_DROP_SPIKE"],
                "network_domain": "CORE",
                "metadata": {"technology_generation": "CORE", "vendor": "GENERIC_3GPP"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-IMS-SIP-004",
            "rationale": "SOP-IMS-SIP-004 is vendor-neutral standard RFC-3261 procedure; must be cited.",
        },

        # --- Group 9: Positive Controls (Testing retrieval coverage with full pipeline inputs) ---
        {
            "case_id": "GEN-23",
            "name": "Positive Control: 5G gNodeB VSWR Outage (Generic 3GPP SOP)",
            "category": "POSITIVE_CONTROL",
            "incident": {
                "incident_id": "INC-GEN-23",
                "title": "5G NR gNodeB Antenna Feeder High Return Loss",
                "description": "ALM-RAN-VSWR-HIGH active on sector 2 AAU. VSWR ratio measured at 2.4:1.",
                "alarm_codes": ["ALM-RAN-VSWR-HIGH", "0x80040111"],
                "network_domain": "RAN",
                "network_element_ids": ["gNodeB-101", "AAU-02"],
                "metadata": {"technology_generation": "5G_NR", "vendor": "GENERIC_3GPP"},
            },
            "m2_data": {
                "predicted_category": "HARDWARE_OR_LINK_DEGRADATION",
                "category_probability": 0.94,
                "predicted_severity": "CRITICAL",
                "policy_routing_tier": "L1",
            },
            "m3_data": {
                "anomalies": [{"network_element_id": "gNodeB-101", "metric_name": "vswr_ratio", "fused_score": 0.89}],
                "alarm_cluster": {"cluster_id": "CLUST-RAN-01", "dominant_alarm_code": "ALM-RAN-VSWR-HIGH"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-RAN-VSWR-001",
            "rationale": "Valid nominal 5G NR RAN incident with generic vendor must be fully supported.",
        },
        {
            "case_id": "GEN-24",
            "name": "Positive Control: 5G AMF Registration Storm",
            "category": "POSITIVE_CONTROL",
            "incident": {
                "incident_id": "INC-GEN-24",
                "title": "5G SA AMF Registration Storm and CPU Saturation",
                "description": "ALM-CORE-AMF-REG-FAIL active. N1/N2 signaling storm with HTTP 504 gateway timeouts.",
                "alarm_codes": ["ALM-CORE-AMF-REG-FAIL", "HTTP_504_GATEWAY_TIMEOUT"],
                "network_domain": "5G_CORE",
                "network_element_ids": ["AMF-01"],
                "metadata": {"technology_generation": "5G_CORE", "vendor": "GENERIC_3GPP"},
            },
            "m2_data": {
                "predicted_category": "CORE_SERVICE_DEGRADATION",
                "category_probability": 0.95,
                "predicted_severity": "CRITICAL",
                "policy_routing_tier": "L1",
            },
            "m3_data": {
                "anomalies": [{"network_element_id": "AMF-01", "metric_name": "amf_cpu_utilization", "fused_score": 0.94}],
                "alarm_cluster": {"cluster_id": "CLUST-CORE-01", "dominant_alarm_code": "ALM-CORE-AMF-REG-FAIL"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-5GC-AMF-001",
            "rationale": "Valid nominal 5G Core AMF registration storm with full telemetry must be fully supported.",
        },
        {
            "case_id": "GEN-25",
            "name": "Positive Control: Cisco ASR9k IP Transport BGP Flap",
            "category": "POSITIVE_CONTROL",
            "incident": {
                "incident_id": "INC-GEN-25",
                "title": "Cisco ASR9k Core BGP Neighbor Reset",
                "description": "ALM-TRANS-BGP-FLAP active. Cisco ASR-9000 router BGP session dropped on interface TenGigE0/1/0/0.",
                "alarm_codes": ["ALM-TRANS-BGP-FLAP", "BGP_SESSION_DOWN"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["ASR9K-PE-01"],
                "metadata": {"technology_generation": "OPTICAL_IP_TRANSPORT", "vendor": "CISCO"},
            },
            "m2_data": {
                "predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN",
                "category_probability": 0.96,
                "predicted_severity": "MAJOR",
                "policy_routing_tier": "L1",
            },
            "m3_data": {
                "anomalies": [{"network_element_id": "ASR9K-PE-01", "metric_name": "bgp_prefixes_received", "fused_score": 0.92}],
                "alarm_cluster": {"cluster_id": "CLUST-TX-02", "dominant_alarm_code": "ALM-TRANS-BGP-FLAP"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-TRANS-BGP-002",
            "rationale": "Valid nominal Cisco ASR9k BGP incident with matching Cisco SOP must be fully supported.",
        },
        {
            "case_id": "GEN-26",
            "name": "Positive Control: Optical Transport Fiber Cut (Generic SOP)",
            "category": "POSITIVE_CONTROL",
            "incident": {
                "incident_id": "INC-GEN-26",
                "title": "Fronthaul optical loss of signal between BBU and AAU",
                "description": "ALM-TRANS-OPTICAL-LOS active. eCPRI framing synchronization lost. Zero optical power on Rx.",
                "alarm_codes": ["ALM-TRANS-OPTICAL-LOS", "0x80040201"],
                "network_domain": "TRANSPORT",
                "network_element_ids": ["BBU-POOL-01", "F-SW-03"],
                "metadata": {"technology_generation": "OPTICAL_IP_TRANSPORT", "vendor": "GENERIC_3GPP"},
            },
            "m2_data": {
                "predicted_category": "TRANSPORT_CONGESTION_OR_LINK_DOWN",
                "category_probability": 0.96,
                "predicted_severity": "CRITICAL",
                "policy_routing_tier": "L1",
            },
            "m3_data": {
                "anomalies": [{"network_element_id": "F-SW-03", "metric_name": "rx_optical_power", "fused_score": 0.95}],
                "alarm_cluster": {"cluster_id": "CLUST-TX-01", "dominant_alarm_code": "ALM-TRANS-OPTICAL-LOS"},
            },
            "expected_status": HypothesisStatus.SUPPORTED,
            "expected_runbook_required": "SOP-TRANS-FIBER-001",
            "rationale": "Valid nominal optical fiber cut incident with generic vendor must be fully supported.",
        },
    ]


def run_equipment_generalization_audit() -> Dict[str, Any]:
    print("[*] Initializing Knowledge Base and Hybrid Retrieval Engine...")
    docs, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)
    test_cases = get_generalization_test_cases()

    results: List[Dict[str, Any]] = []
    passed_count = 0
    failed_count = 0

    print("=" * 80)
    print("PHASE 2: EQUIPMENT-AWARE RETRIEVAL GENERALIZATION AUDIT (26 NEW CASES)")
    print("=" * 80)

    for tc in test_cases:
        cid = tc["case_id"]
        cname = tc["name"]
        cat = tc["category"]
        inc = tc["incident"]
        exp_status = tc["expected_status"]
        exp_forbidden = tc.get("expected_runbook_forbidden", [])
        exp_required = tc.get("expected_runbook_required")

        # Execute investigation with optional M2/M3 signals
        m2_cls = tc.get("m2_data")
        m3_intel = tc.get("m3_data")
        context = engine.investigate(
            incident=inc,
            m2_classification=m2_cls,
            m3_network_intelligence=m3_intel,
        )
        top_hyp = context.hypotheses[0] if context.hypotheses else None
        actual_status = top_hyp.status if top_hyp else HypothesisStatus.INCONCLUSIVE
        
        # Check cited runbooks
        cited_runbooks = []
        for rec in context.recommendations:
            if rec.source_runbook_id:
                cited_runbooks.append(rec.source_runbook_id)

        # Verification logic
        is_pass = True
        failure_reasons = []

        if actual_status != exp_status:
            is_pass = False
            failure_reasons.append(f"Status mismatch: expected {exp_status.value}, got {actual_status.value}")

        for forbidden in exp_forbidden:
            if forbidden in cited_runbooks:
                is_pass = False
                failure_reasons.append(f"Cited forbidden incompatible runbook '{forbidden}'")

        if exp_required and exp_required not in cited_runbooks:
            is_pass = False
            failure_reasons.append(f"Failed to cite required compatible runbook '{exp_required}'")

        if is_pass:
            passed_count += 1
            verdict = "PASS"
        else:
            failed_count += 1
            verdict = "FAIL"

        print(f"[{cid}] [{verdict}] {cname:<45} | Status: {actual_status.value:<12} | Cited: {cited_runbooks}")
        if failure_reasons:
            for fr in failure_reasons:
                print(f"      -> VIOLATION: {fr}")

        results.append({
            "case_id": cid,
            "name": cname,
            "category": cat,
            "expected_status": exp_status.value,
            "actual_status": actual_status.value,
            "cited_runbooks": cited_runbooks,
            "expected_forbidden": exp_forbidden,
            "expected_required": exp_required,
            "passed": is_pass,
            "failure_reasons": failure_reasons,
        })

    pass_rate = (passed_count / len(test_cases)) * 100.0
    print("=" * 80)
    print(f"PHASE 2 SUMMARY: {passed_count}/{len(test_cases)} Passed ({pass_rate:.1f}%)")
    print("=" * 80)

    summary = {
        "audit_phase": "Phase 2: Equipment-Aware Retrieval Generalization",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cases_evaluated": len(test_cases),
        "cases_passed": passed_count,
        "cases_failed": failed_count,
        "pass_rate_pct": round(pass_rate, 2),
        "case_evaluations": results,
    }

    out_file = Path("artifacts/m5_metrics/m5_1_audit_phase2_equipment.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Artifact exported: {out_file}")

    return summary


if __name__ == "__main__":
    run_equipment_generalization_audit()
