"""Corpus loader and knowledge base builder for approved SOPs, historical tickets, and 3GPP specs."""

from __future__ import annotations

import hashlib
from typing import List, Tuple

from piis.knowledge.chunker import StructureAwareChunker
from piis.knowledge.models import KnowledgeChunk, KnowledgeDocument
from piis.knowledge.sources import KnowledgeSourceRegistry, SourceType, TrustClassification
from piis.provenance import ProvenanceRecord


# Curated Standard Operating Procedures (SOP Runbooks)
SOP_DOCUMENTS = [
    {
        "doc_id": "SOP-RAN-VSWR-001",
        "source_id": "SRC-SOP-RAN-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "Antenna VSWR and RF Feeder Degradation Resolution",
        "version": "1.2.0",
        "network_domain": "RAN",
        "target_subsystems": ["gNodeB", "AAU", "Feeder", "Antenna"],
        "severity_applicability": ["CRITICAL", "MAJOR"],
        "technology_generation": "5G_NR",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "gNodeB",
        "content": """# SOP-RAN-VSWR-001: Antenna VSWR and RF Feeder Degradation Resolution

## 1. Symptoms & Alarm Correlation
High Voltage Standing Wave Ratio (VSWR) exceeds 1.5:1 on antenna port.
Active Alarm: ALM-RAN-VSWR-HIGH (Alarm Code: 0x80040111).
Associated symptoms: Downlink RSRP drops by 12-18 dB, Uplink BLER surges above 15%, throughput collapse.

> [!WARNING]
> DANGER: High RF Radiation. De-energize sector radio power via OSS command before physical inspection on tower.

## 2. Initial Diagnostic Verification
Access gNodeB Element Manager or OSS CLI:
```bash
sri -rru 1 get vswr
sri -rru 1 get tx-power
show alarm active | grep -i vswr
```
1. Verify return loss on affected RF branch. Standard nominal return loss is >= 18 dB. If return loss is < 14 dB, impedance mismatch is confirmed.
2. Check weather logs for heavy rain or lightning activity preceding alarm trigger.

## 3. Physical Inspection & Rectification Procedure
1. Inspect jumper cable DIN/4.3-10 connectors for water ingress, corrosion, or loose torque.
2. Connect Site Master frequency domain reflectometer (FDR) to pinpoint distance-to-fault (DTF).
3. Replace damaged RF jumper or surge arrestor. Ensure connector is torqued to 25 Nm.
4. Weatherproof all outdoor RF connections with butyl mastic tape and UV-resistant tape.

## 4. Post-Repair Verification & Rollback
1. Power on sector transmitter via OSS CLI:
```bash
sri -rru 1 set tx-power --enable
```
2. Confirm VSWR return loss improves to > 18 dB (VSWR < 1.3:1).
3. Clear alarm ALM-RAN-VSWR-HIGH in OSS.
Rollback: If replacement jumper does not clear fault, re-seat original with dust caps and escalate to Antenna Rigging Team.
""",
    },
    {
        "doc_id": "SOP-RAN-HANDOVER-002",
        "source_id": "SRC-SOP-RAN-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "gNodeB Handover Failure and Radio Link Failure (RLF) Triage",
        "version": "1.1.0",
        "network_domain": "RAN",
        "target_subsystems": ["gNodeB", "Xn-Interface", "NR-Cell"],
        "severity_applicability": ["MAJOR", "MODERATE"],
        "technology_generation": "5G_NR",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "gNodeB",
        "content": """# SOP-RAN-HANDOVER-002: gNodeB Handover Failure and Radio Link Failure (RLF) Triage

## 1. Symptoms & Alarm Indicators
Elevated Xn or N2 handover drop rate exceeding 5% SLA threshold.
Active Alarm: ALM-RAN-RLF (Radio Link Failure surge) or ALM-RAN-XN-FAIL.
Symptoms: Users experience call drops during inter-cell mobility, DL throughput collapses.

## 2. Diagnostic Investigation
Execute trace analysis across source and target cells:
```bash
nr-cli cell status --all
nr-cli xn-interface show-peers
show pm counter | grep -E "HO_Fail_Out|RLF_Count"
```
1. Check Xn-C SCTP association status between neighboring gNodeBs.
2. Verify neighbor relation table (NRT) consistency: check for missing ARFCN or PCI collisions.
3. Review A3 event offset configuration (hysteresis and time-to-trigger).

## 3. Remediation Workflow
1. If PCI collision detected: Re-plan target cell PCI using OSS automated frequency management.
2. If Xn SCTP association flapping: Restart Xn transport link or re-route mobility via N2 (NG-RAN to 5G Core).
3. If A3 ping-pong handover observed: Increase time-to-trigger from 40ms to 80ms and increase A3 offset by 2 dB.

## 4. Verification Steps
1. Monitor HO Success Rate KPI for 30 minutes; target > 98.5%.
2. Confirm RLF count returns to baseline (< 0.1 per connected user hour).
""",
    },
    {
        "doc_id": "SOP-TRANS-FIBER-001",
        "source_id": "SRC-SOP-TRANS-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "Fronthaul Optical Loss of Signal and Fiber Cut Restoration",
        "version": "1.3.0",
        "network_domain": "TRANSPORT",
        "target_subsystems": ["Switch", "Router", "eCPRI", "Optical-SFP"],
        "severity_applicability": ["CRITICAL"],
        "technology_generation": "OPTICAL_IP_TRANSPORT",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "FIBER_SWITCH",
        "content": """# SOP-TRANS-FIBER-001: Fronthaul Optical Loss of Signal and Fiber Cut Restoration

## 1. Symptoms & Alarms
Total loss of optical carrier on access fronthaul link.
Active Alarm: ALM-TRANS-OPTICAL-LOS (Loss of Signal) or ALM-TRANS-SFP-TX-FAIL.
Topological Blast Radius: Baseband loses connection to all child cells; site enters total outage.

> [!WARNING]
> CAUTION: Class 1M Laser Radiation. Do not look directly into disconnected optical fiber ends or SFP optical ports.

## 2. Diagnostic Procedure
From Access Switch CLI:
```bash
show interfaces transceiver detail
show log | grep -i optical
test optical-diagnostics interface eth1/1
```
1. Check RX optical power. Nominal is -8 dBm to -14 dBm. If RX power is <= -30 dBm, physical break is present.
2. Connect Optical Time Domain Reflectometer (OTDR) to identify exact kilometer distance to fiber cut.

## 3. Cable Restoration Procedure
1. Dispatch fiber restoration field technician to OTDR break coordinates.
2. Fusion splice severed optical strands. Maximum splice loss must not exceed 0.05 dB per splice.
3. Clean all optical ferrule connectors with lint-free solvent wipe before re-mating.

## 4. Return to Service
1. Re-seat SFP+ optical module.
2. Verify RX optical power returns to nominal range (-10 dBm +/- 2 dBm).
3. Clear ALM-TRANS-OPTICAL-LOS alarm and verify eCPRI synchronization locking.
""",
    },
    {
        "doc_id": "SOP-TRANS-BGP-002",
        "source_id": "SRC-SOP-TRANS-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "IP-MPLS Aggregation Router BGP Session Flapping Triage",
        "version": "1.0.0",
        "network_domain": "TRANSPORT",
        "target_subsystems": ["Router", "IP-MPLS", "BGP", "BFD"],
        "severity_applicability": ["CRITICAL", "MAJOR"],
        "technology_generation": "OPTICAL_IP_TRANSPORT",
        "vendor": "CISCO",
        "equipment_family": "IP_MPLS_ROUTER",
        "content": """# SOP-TRANS-BGP-002: IP-MPLS Aggregation Router BGP Session Flapping Triage

## 1. Symptoms & Alarms
BGP peer transitions rapidly between ESTABLISHED and IDLE states.
Active Alarm: ALM-TRANS-BGP-FLAP or ALM-TRANS-BFD-DOWN.
Impact: Intermittent packet loss across 5G Core N3 and N6 interfaces; user session resets.

## 2. Diagnostic Steps
From IP-MPLS Aggregation Router console:
```bash
show bgp summary
show bfd session
show route flap-statistics
ping <peer-ip> size 1500 df-bit
```
1. Verify MTU mismatch: ensure DF-bit ping passes at 1500 bytes without packet fragmentation.
2. Check BFD hold timer versus BGP keepalive interval.
3. Inspect interface CRC error counters for micro-burst optical attenuation.

## 3. Remediation Workflow
1. If MTU mismatch: Standardize interface MTU to 9216 (Jumbo frames) across all transit hops.
2. If BFD timer too aggressive under network jitter: Increase BFD multiplier from 3 to 5 (detect multiplier 250ms).
3. If route flapping due to flapping sub-interface: Enable BGP route dampening on aggregation peer.
""",
    },
    {
        "doc_id": "SOP-5GC-AMF-001",
        "source_id": "SRC-SOP-CORE-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "5G Core AMF Registration Storm & SCTP Association Exhaustion",
        "version": "2.0.0",
        "network_domain": "5G_CORE",
        "target_subsystems": ["AMF", "N2-Interface", "SCTP", "NRF"],
        "severity_applicability": ["CRITICAL"],
        "technology_generation": "5G_CORE",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "AMF",
        "content": """# SOP-5GC-AMF-001: 5G Core AMF Registration Storm & SCTP Association Exhaustion

## 1. Symptoms & Alarms
AMF CPU utilization surges above 90%; 5G UE registration success rate collapses below 60%.
Active Alarm: ALM-CORE-AMF-REG-FAIL or ALM-CORE-SCTP-EXHAUSTION.
Triggers: Mass reconnection after major RAN cell recovery, or synchronized IoT burst retry.

## 2. Diagnostics
From Core Orchestrator CLI:
```bash
amf-admin show stats registration-rate
amf-admin show sctp connections --status
amf-admin show overload-control
```
1. Measure incoming Registration Requests per second (RPS). Nominal is < 5,000 RPS.
2. Check N2 SCTP association buffer queue depth and drop counters.

## 3. Emergency Mitigation
1. Enable AMF Overload Control (3GPP TS 23.501 Clause 5.19.5):
```bash
amf-admin set overload-protection --reject-percentage 20 --priority emergency-only
```
2. Scale out secondary AMF container instances via Kubernetes HPA:
```bash
kubectl scale deployment amf-service --replicas=6 -n 5gcore
```
3. Throttle RAN back-off timer: configure gNodeB `t3502` to 12 minutes to distribute UE retry bursts.

## 4. Verification & Recovery
1. Verify Registration Success Rate recovers to >= 99.2%.
2. Disable emergency reject percentage once CPU drops below 65%.
""",
    },
    {
        "doc_id": "SOP-5GC-UPF-002",
        "source_id": "SRC-SOP-CORE-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "5G Core UPF GTP-U Buffer Overflow and N4 Disconnect",
        "version": "1.2.0",
        "network_domain": "5G_CORE",
        "target_subsystems": ["UPF", "SMF", "N4-Interface", "GTP-U"],
        "severity_applicability": ["CRITICAL"],
        "technology_generation": "5G_CORE",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "UPF",
        "content": """# SOP-5GC-UPF-002: 5G Core UPF GTP-U Buffer Overflow and N4 Disconnect

## 1. Symptoms & Alarms
UPF user plane packet drop rate spikes; N4 association heartbeats timeout.
Active Alarm: ALM-CORE-UPF-BUFFER-OVERFLOW or ALM-CORE-N4-HEARTBEAT-FAIL.
Symptoms: Data stall across entire APN/DNN slice; streaming video and browsing fail completely.

## 2. Diagnostic Investigation
From UPF operations terminal:
```bash
upf-cli show buffers
upf-cli show n4 association
upf-cli show throughput --dnn internet
```
1. Check ring buffer utilization. If TX/RX ring buffers exceed 98%, memory pool starvation is occurring.
2. Check SMF N4 PFCP session count against hardware profile limit.

## 3. Remediation Workflow
1. Clear stagnant GTP-U tunnels with stale teardowns:
```bash
upf-cli session prune --stale-seconds 300
```
2. Trigger secondary UPF failover via SMF re-selection:
```bash
smf-cli n4 failover --source upf-core-primary --target upf-core-secondary
```
3. Increase DPDK hugepages allocation from 16GB to 32GB on primary node.
""",
    },
    {
        "doc_id": "SOP-IMS-SIP-001",
        "source_id": "SRC-SOP-IMS-VETTED",
        "doc_type": SourceType.APPROVED_RUNBOOK,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "IMS Core SIP 503 Service Unavailable and VoNR Degradation",
        "version": "1.0.0",
        "network_domain": "SERVICE",
        "target_subsystems": ["IMS", "P-CSCF", "S-CSCF", "SIP"],
        "severity_applicability": ["CRITICAL", "MAJOR"],
        "technology_generation": "5G_CORE",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "P_CSCF",
        "content": """# SOP-IMS-SIP-001: IMS Core SIP 503 Service Unavailable and VoNR Degradation

## 1. Symptoms & Alarms
Voice over New Radio (VoNR) and VoLTE call setup failure rate spikes above 10%.
Active Alarm: ALM-SRV-SIP-503 (SIP 503 Service Unavailable).
Symptoms: Fast busy tone on voice call initiation; IMS registration rejects.

## 2. Diagnostics
From IMS Core telemetry:
```bash
pcscf-cli show sip-stats --code 503
pcscf-cli show tls-cert status
dns-query _sip._udp.ims.mnc001.mcc001.3gppnetwork.org
```
1. Verify whether 503 is originating from P-CSCF or upstream S-CSCF / HSS.
2. Check ENUM / DNS resolution latency for target SIP URIs.
3. Verify TLS certificate expiration date on Gm and Mw interfaces.

## 3. Remediation Procedure
1. If DNS resolution failure: Switch DNS resolver to secondary core IP.
2. If S-CSCF overloaded: Re-balance user registrations across secondary S-CSCF pool in NRF.
3. If TLS certificate expired: Deploy renewed certificate secret and reload P-CSCF daemon:
```bash
pcscf-cli cert update --reload
```
""",
    },
]

# Curated Historical Incident Tickets
HISTORICAL_INCIDENTS = [
    {
        "doc_id": "INC-TELTS-JAMMER-0000",
        "source_id": "SRC-HIST-TELECOMTS",
        "doc_type": SourceType.HISTORICAL_INCIDENT,
        "trust_classification": TrustClassification.MEDIUM_TRUST_VERIFIED,
        "title": "Severe Wireless Communication Degradation From External RF Jamming",
        "version": "1.0.0",
        "network_domain": "RAN",
        "target_subsystems": ["gNodeB", "AAU", "Air-Interface"],
        "severity_applicability": ["MAJOR"],
        "technology_generation": "5G_NR",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "gNodeB",
        "content": """# Incident INC-TELTS-JAMMER-0000: Severe RF Jamming & Link Interference

## Incident Description
High DL/UL block error rate and sudden drop in uplink modulation (UL_MCS dropped from 18 to 9).
External wideband radio frequency jammer detected operating in vicinity of testbed gNodeB.
Affected Elements: GNB-TESTBED-5G-01, CELL-101.

## Root Cause
Active RF jammer generating continuous continuous-wave interference across 3.5 GHz n78 band, crushing uplink SNR and driving BLER over 15%.

## Verified Resolution Summary
1. Dispatched RF field spectrum analysis van equipped with directional Yagi antenna.
2. Triangulated source of rogue emitter at boundary perimeter.
3. Isolated rogue transmission source and re-evaluated cell telemetry.
4. Uplink MCS recovered from 9 to 18; DL BLER dropped back to < 0.01.
""",
    },
    {
        "doc_id": "INC-TELTS-SYNC-0001",
        "source_id": "SRC-HIST-TELECOMTS",
        "doc_type": SourceType.HISTORICAL_INCIDENT,
        "trust_classification": TrustClassification.MEDIUM_TRUST_VERIFIED,
        "title": "Clock Synchronization Drift and GPS Holdover in Rural Cluster",
        "version": "1.0.0",
        "network_domain": "TRANSPORT",
        "target_subsystems": ["gNodeB", "PTP-Clock", "GPS-Receiver"],
        "severity_applicability": ["MAJOR"],
        "technology_generation": "OPTICAL_IP_TRANSPORT",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "PTP_CLOCK",
        "content": """# Incident INC-TELTS-SYNC-0001: PTP Clock Drift and GPS Holdover in Rural Cluster

## Incident Description
Rural cell site cluster experienced degraded TDD frame sync and inter-cell interference.
GPS receiver antenna suffered lightning surge, entering local oscillator holdover mode.
Time error accumulated past 1.5 microseconds, causing frame slip with neighboring macro cells.

## Root Cause
Damaged GPS surge arrestor prevented satellite signal reception; PTP boundary clock fallback had incorrect domain ID.

## Verified Resolution Summary
1. Replaced blown lightning surge arrestor on GPS antenna feeder line.
2. Corrected PTP boundary clock domain ID from 24 to telecom profile default 44.
3. Locked phase to grandmaster server via SyncE/PTP backup; time error dropped below 150 ns.
""",
    },
    {
        "doc_id": "INC-TELTS-VOLTE-0002",
        "source_id": "SRC-HIST-TELECOMTS",
        "doc_type": SourceType.HISTORICAL_INCIDENT,
        "trust_classification": TrustClassification.MEDIUM_TRUST_VERIFIED,
        "title": "VoLTE Call Drop Surge During Inter-RAT LTE to 5G Handover",
        "version": "1.0.0",
        "network_domain": "SERVICE",
        "target_subsystems": ["IMS", "P-CSCF", "VoLTE", "eNodeB"],
        "severity_applicability": ["CRITICAL"],
        "technology_generation": "5G_CORE",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "IMS",
        "content": """# Incident INC-TELTS-VOLTE-0002: VoLTE Call Drop Surge During Inter-RAT Handover

## Incident Description
VoLTE call drop rate increased to 4.8% during busy hour along suburban highway corridor.
Subscribers executing inter-RAT handover from LTE anchor to standalone 5G NR experienced silence and dropped calls.

## Root Cause
IMS dedicated voice bearer QCI=1 was torn down prematurely due to guard timer mismatch during EPS fallback.

## Verified Resolution Summary
1. Adjusted RAN handover execution timer `t_reloc_prep` from 200ms to 500ms.
2. Verified P-CSCF Gm interface session timer to prevent early SIP BYE generation.
3. Handover success rate restored to 99.4%; VoLTE drop rate dropped to 0.12%.
""",
    },
]

# Curated Technical Reference Excerpts
TECHNICAL_SPECS = [
    {
        "doc_id": "REF-3GPP-TS38300",
        "source_id": "SRC-SPEC-3GPP",
        "doc_type": SourceType.PUBLIC_TECHNICAL_REFERENCE,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "3GPP TS 38.300 NR Radio Link Failure and Handover Procedures",
        "version": "Rel-17",
        "network_domain": "RAN",
        "target_subsystems": ["gNodeB", "UE", "RRC"],
        "severity_applicability": ["MAJOR", "MODERATE"],
        "technology_generation": "5G_NR",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "gNodeB",
        "content": """# 3GPP TS 38.300 Clause 9.2: Radio Link Failure & Mobility Execution

## Clause 9.2.1: Radio Link Failure (RLF) Detection
The UE monitors downlink radio quality based on reference signals (CSI-RS / SSB).
Upon detecting out-of-sync indications from lower layers consecutively reaching N310, timer T310 is started.
If N311 in-sync indications are not received before T310 expires, RLF is declared.
Subsequent action: UE enters RRC Re-establishment procedure on best candidate cell.

## Clause 9.2.2: Xn Handover Execution
During Xn-based handover, source gNodeB coordinates directly with target gNodeB via Xn-C SCTP connection.
Data forwarding occurs via Xn-U GTP-U tunnels to prevent downlink packet loss while UE executes random access on target cell.
If target cell rejects handover due to admission control, source gNodeB initiates fallback to S1/N2 mobility.
""",
    },
    {
        "doc_id": "REF-3GPP-TS23501",
        "source_id": "SRC-SPEC-3GPP",
        "doc_type": SourceType.PUBLIC_TECHNICAL_REFERENCE,
        "trust_classification": TrustClassification.HIGH_TRUST_APPROVED,
        "title": "3GPP TS 23.501 5G System Architecture, AMF/SMF/UPF Interfaces",
        "version": "Rel-17",
        "network_domain": "5G_CORE",
        "target_subsystems": ["AMF", "SMF", "UPF", "N2", "N4"],
        "severity_applicability": ["MAJOR", "MODERATE"],
        "technology_generation": "5G_CORE",
        "vendor": "GENERIC_3GPP",
        "equipment_family": "5GC_NF",
        "content": """# 3GPP TS 23.501 Clause 5: 5G System Architecture Principles

## Clause 5.2: Control and User Plane Separation (CUPS)
The 5G core decouples session management (SMF) from packet routing and forwarding (UPF).
Interaction occurs across the N4 reference point using Packet Forwarding Control Protocol (PFCP).
Heartbeat procedures monitor peer viability; consecutive unacknowledged requests trigger association reset.

## Clause 5.19: Overload Control and Congestion Management
When AMF reaches high processor load thresholds, it activates AMF Overload Control via N2 signaling.
NGAP Overload Start messages instruct gNodeB to throttle non-emergency initial NAS signaling, preventing total core collapse.
""",
    },
]


def build_knowledge_base() -> Tuple[KnowledgeSourceRegistry, List[KnowledgeChunk]]:
    """Build and register all curated knowledge documents, producing indexed chunks."""
    registry = KnowledgeSourceRegistry()
    chunker = StructureAwareChunker(target_tokens=350, max_tokens=500, overlap_tokens=50)

    # 1. Register Sources
    registry.register_source(
        source_id="SRC-SOP-RAN-VETTED",
        source_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="Vetted RAN Standard Operating Procedures",
        original_location="data/knowledge/sops/ran_sops.md",
    )
    registry.register_source(
        source_id="SRC-SOP-TRANS-VETTED",
        source_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="Vetted Transport Standard Operating Procedures",
        original_location="data/knowledge/sops/transport_sops.md",
    )
    registry.register_source(
        source_id="SRC-SOP-CORE-VETTED",
        source_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="Vetted 5G Core Standard Operating Procedures",
        original_location="data/knowledge/sops/core_sops.md",
    )
    registry.register_source(
        source_id="SRC-SOP-IMS-VETTED",
        source_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="Vetted IMS Core Standard Operating Procedures",
        original_location="data/knowledge/sops/ims_sops.md",
    )
    registry.register_source(
        source_id="SRC-HIST-TELECOMTS",
        source_type=SourceType.HISTORICAL_INCIDENT,
        trust_classification=TrustClassification.MEDIUM_TRUST_VERIFIED,
        title="TelecomTS Real-World 5G Incident Resolutions",
        original_location="data/raw/SRC-002/jammer_chunked.jsonl",
    )
    registry.register_source(
        source_id="SRC-SPEC-3GPP",
        source_type=SourceType.PUBLIC_TECHNICAL_REFERENCE,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="3GPP TS 38.300 NR Overall Architecture",
        original_location="https://www.3gpp.org/DynaReport/38300.htm",
    )

    all_raw_docs = SOP_DOCUMENTS + HISTORICAL_INCIDENTS + TECHNICAL_SPECS
    all_chunks: List[KnowledgeChunk] = []

    for raw in all_raw_docs:
        doc = KnowledgeDocument(
            doc_id=raw["doc_id"],
            source_id=raw["source_id"],
            doc_type=raw["doc_type"],
            trust_classification=raw["trust_classification"],
            title=raw["title"],
            version=raw["version"],
            network_domain=raw["network_domain"],
            target_subsystems=raw["target_subsystems"],
            severity_applicability=raw["severity_applicability"],
            technology_generation=raw.get("technology_generation"),
            vendor=raw.get("vendor"),
            equipment_family=raw.get("equipment_family"),
            raw_content=raw["content"],
            checksum_sha256=hashlib.sha256(raw["content"].encode()).hexdigest(),
            provenance=ProvenanceRecord(
                source_type=raw["doc_type"],
                source_dataset=raw["source_id"],
                source_record_id=raw["doc_id"],
                transformation_version=raw["version"],
                checksum_sha256=hashlib.sha256(raw["content"].encode()).hexdigest(),
            ),
        )
        chunks = chunker.chunk_document(doc)
        all_chunks.extend(chunks)

    return registry, all_chunks
