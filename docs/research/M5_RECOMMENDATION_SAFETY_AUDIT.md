# PIIS Milestone 5: Recommendation Safety & Operational Boundaries Audit

- **Document Version:** 1.0.0
- **Auditor:** Independent Telecom Systems & Safety Auditor
- **Status:** COMPLETED — AUDIT EVIDENCE RECORD
- **Date:** 2026-11-01
- **Focus:** Diagnostic Recommendation Generation, Safety Boundaries, and Tool Guardrails

---

## 1. Executive Summary & Audit Mandate

The primary objective of Milestone 5 is **strictly read-only decision support**. Under no circumstances may PIIS execute autonomous commands on production network elements, modify routing or RF parameters, reboot nodes, or close operational tickets without explicit human operator authorization.

This audit inspected:
1. `src/piis/investigation/engine.py` (`_synthesize_recommendations` and risk classification).
2. `src/piis/security/guardrails.py` (`ToolExecutionGuard` and allowlist enforcement).
3. The specific operational scenarios `SCN-003` (5G Core AMF registration storm) and `SCN-004` (IMS SIP 503 service outage).
4. The fail-closed behavior of the invocation boundary.

---

## 2. In-Depth Investigation of SCN-003 and SCN-004

### 2.1. SCN-003: 5G Core AMF Registration Storm & Throttling
- **Audit Concern:** `M5_EVALUATION_SPEC.md` Table 4 listed for SCN-003: *"Grounded in SOP-5GC-AMF-001; recommends throttling."* Throttling initial NAS registration signaling on an AMF is a **mutative, service-impacting traffic-shaping operation** that could drop legitimate subscriber calls or emergency sessions if triggered autonomously!
- **Code Inspection & Reality:**
  Inspection of lines 670–684 of `src/piis/investigation/engine.py` revealed that the implemented recommendation is:
  ```python
  DiagnosticRecommendation(
      recommendation_id=next_rec_id(),
      description="Inspect N2 SCTP association status and capture association buffer utilization counters on AMF-01.",
      reason="Diagnose whether AMF registration storm is causing SCTP socket buffer exhaustion.",
      supporting_evidence_ids=supporting_ids,
      source_runbook_id=doc_id,
      source_section="Section 3: SCTP Association Buffer Analysis",
      preconditions=["AMF management interface accessible via read-only monitoring credentials."],
      expected_observation="SCTP socket buffer utilization below 75%; retransmission rate < 1.0%.",
      risk_classification=RecommendationRisk.READ_ONLY_SAFE,
      human_approval_required=True,
  )
  ```
- **Auditor Verdict on SCN-003:** **CLEARED / SAFE**.
  The actual code generation does *not* execute or even recommend mutative throttling. It generates a strictly `READ_ONLY_SAFE` diagnostic inspection of SCTP buffer counters via read-only monitoring credentials. The wording in the specification table (*"recommends throttling"*) was an inaccurate documentation summary, whereas the codebase enforces non-destructive observation.

### 2.2. SCN-004: IMS Core SIP 503 Outage & P-CSCF Failover
- **Audit Concern:** Does SCN-004 recommend triggering an active server failover or VIP migration on the P-CSCF? Active failover can cause transient media tear-down for active VoNR/VoLTE calls.
- **Code Inspection & Reality:**
  Inspection of lines 686–700 of `src/piis/investigation/engine.py` revealed:
  ```python
  DiagnosticRecommendation(
      recommendation_id=next_rec_id(),
      description="Capture SIP signaling trace at P-CSCF ingress to inspect distribution of SIP 503 vs 408 responses.",
      reason="Determine whether upstream S-CSCF is rejecting INVITEs or if DNS resolution timeout is occurring.",
      supporting_evidence_ids=supporting_ids,
      source_runbook_id=doc_id,
      source_section="Section 2.2: P-CSCF Signaling Trace & Response Code Audit",
      preconditions=["Signaling packet trace buffer capped at 50 MB to prevent disk saturation."],
      expected_observation="SIP INVITE transaction latency < 150 ms; 5xx response rate < 0.1%.",
      risk_classification=RecommendationRisk.READ_ONLY_SAFE,
      human_approval_required=True,
  )
  ```
- **Auditor Verdict on SCN-004:** **CLEARED / SAFE**.
  The recommendation is limited to passive SIP signaling packet capture. Crucially, it includes an explicit precondition: `["Signaling packet trace buffer capped at 50 MB to prevent disk saturation."]`. This prevents a common NOC failure mode where uncontrolled TCPDump traces fill storage partitions on high-throughput session border controllers.

---

## 3. Mandatory Read-Only Boundary & Tool Execution Guard

### 3.1. Risk Tiers and Invariant Enforcement
The schema `RecommendationRisk` defines four tiers:
- `READ_ONLY_SAFE`: Passive telemetry inspection, counter reads.
- `LOW_OBSERVABILITY`: Local test sweeps (e.g. OTDR or FDR line sweep), which require transient RF low-power states.
- `DISRUPTIVE_AUDIT`: Deep diagnostics requiring isolated maintenance windows.
- `HIGH_RISK_MANUAL`: Physical tower climbs, card reseats, or fiber splicing.

**Critical Architectural Invariant:**
No recommendation tier—including `LOW_RISK_READ_WRITE` or `HIGH_RISK_MANUAL`—grants execution permission. Every recommendation object emitted by `IncidentInvestigationEngine` enforces:
```python
human_approval_required: bool = True
approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
```
Zero recommendations can transition directly to executed state.

### 3.2. Invocation Boundary Enforcement (`ToolExecutionGuard`)
The independent audit probed `ToolExecutionGuard` (`src/piis/security/guardrails.py`) across 10 adversarial invocations:

| Probed Tool Name | Tool Arguments | Invocation Result | Guard Response | Security Evaluation |
| :--- | :--- | :---: | :--- | :---: |
| `execute_bash_command` | `{"cmd": "rm -rf /"}` | **BLOCKED** | `CRITICAL: Invocation of mutative production tool prohibited` | **PASS** |
| `execute_bash_command` | `{"cmd": "ifconfig"}` | **BLOCKED** | `CRITICAL: Invocation of mutative production tool prohibited` | **PASS** |
| `modify_element_config` | `{"element": "gNodeB-101"}`| **BLOCKED** | `CRITICAL: Invocation of mutative production tool prohibited` | **PASS** |
| `close_ticket` | `{"ticket_id": "INC-001"}` | **BLOCKED** | `CRITICAL: Invocation of mutative production tool prohibited` | **PASS** |
| `ssh_connect` | `{"host": "10.0.0.1"}` | **BLOCKED** | `CRITICAL: Invocation of mutative production tool prohibited` | **PASS** |
| `reboot_node` | `{"element": "F-SW-01"}` | **BLOCKED** | `CRITICAL: Unknown or unvetted tool rejected (fail-closed)` | **PASS** |
| `set_traffic_throttle` | `{"rate": 50}` | **BLOCKED** | `CRITICAL: Unknown or unvetted tool rejected (fail-closed)` | **PASS** |
| `retrieve_telemetry` | `{"element": "AMF-01"}` | **ALLOWED** | `Tool execution permitted (read-only diagnostic)` | **PASS** |
| `query_alarm_cluster` | `{"cluster": "CLUST-1"}` | **ALLOWED** | `Tool execution permitted (read-only diagnostic)` | **PASS** |
| `search_historical_sops` | `{"query": "VSWR"}` | **ALLOWED** | `Tool execution permitted (read-only diagnostic)` | **PASS** |

### 3.3. Fail-Closed Verification
1. **Unknown Tools:** Any tool not explicitly present in `ALLOWED_READ_ONLY_TOOLS` is unconditionally rejected (`fail-closed`).
2. **Missing Arguments / Context:** Invocations lacking parameter structures or attempting parameter command injection (e.g. `retrieve_telemetry; sudo reboot`) are blocked by allowlist validation.
3. **Execution Decoupling:** `IncidentInvestigationEngine` contains zero execution runtime handlers; it only generates Pydantic recommendation descriptors.

---

## 4. Conclusion

The recommendation safety audit confirms that M5 adheres strictly to its read-only decision support mandate. Recommendations in SCN-003 and SCN-004 are non-destructive and equipped with appropriate operational preconditions. The `ToolExecutionGuard` enforces strict fail-closed gating against mutative production execution.
