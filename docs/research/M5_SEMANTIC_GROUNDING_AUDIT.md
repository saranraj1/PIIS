# PIIS Milestone 5: Semantic Evidence-Grounding Adversarial Audit

- **Document Version:** 1.0.0
- **Auditor:** Independent ML Research and Telecom Systems Auditor
- **Status:** COMPLETED — AUDIT EVIDENCE RECORD
- **Date:** 2026-11-01
- **Evaluation Suite:** `scripts/audit_semantic_grounding.py` (30 Adversarial Cases)
- **Results Artifact:** `artifacts/m5_metrics/m5_semantic_grounding_audit_results.json`

---

## 1. Executive Summary & Audit Methodology

An independent audit was conducted to evaluate whether the M5 Incident Investigation Engine (`src/piis/investigation/engine.py`) performs genuine semantic evidence grounding or merely satisfies syntactic schema existence checks.

The implementation completion report claimed:
- **Evidence Attribution Precision (EAP):** $100.0\%$
- **Runbook Provenance Integrity (RPI):** $100.0\%$
- **Unsupported Claim Rate (UCR):** $0.0\%$
- **Safe Abstention Rate on Negatives (SAR):** $100.0\%$

To independently stress-test these claims, the audit constructed and executed **30 adversarial test cases** across 10 critical failure modes:
1. Correct evidence supporting a hypothesis (Cases 1–3)
2. Evidence present but irrelevant (Cases 4–6)
3. Contradictory telemetry and domain mismatches (Cases 7–9)
4. Stale runbooks / legacy generation technologies (Cases 10–12)
5. Wrong vendor or proprietary equipment versions (Cases 13–15)
6. Missing preconditions / under-specified tickets (Cases 16–18)
7. Similar symptoms with different physical root causes (Cases 19–21)
8. Multiple plausible competing hypotheses (Cases 22–24)
9. Temporal correlation without physical causation (Cases 25–27)
10. Recommendations exceeding available evidence (Cases 28–30)

Across this 30-case adversarial suite, **27 out of 30 cases passed (90.0% pass rate)**. Three cases failed due to semantic vocabulary overlap on unindexed legacy (2G GSM) and third-party vendor (Juniper JunOS, Nokia NetAct) technologies.

---

## 2. Adversarial Evaluation Ledger (30 Cases)

| Case ID | Category | Incident Title | Expected Status | Actual Status | Conf Proxy | Sufficiency | Verdict | Audit Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **SEM-001** | Correct Evidence | High return loss & antenna VSWR alert | `SUPPORTED` | `SUPPORTED` | $0.971$ | `SUFFICIENT` | **PASS** | RAN feeder degradation accurately grounded in `SOP-RAN-VSWR-001`. |
| **SEM-002** | Correct Evidence | Fronthaul eCPRI optical link down | `SUPPORTED` | `SUPPORTED` | $0.980$ | `SUFFICIENT` | **PASS** | Optical LOS correctly grounded in `SOP-TRANS-FIBER-001`. |
| **SEM-003** | Correct Evidence | AMF registration storm & SCTP overload | `SUPPORTED` | `SUPPORTED` | $0.972$ | `SUFFICIENT` | **PASS** | N2 queue drops grounded in `SOP-5GC-AMF-001`. |
| **SEM-004** | Irrelevant Evidence | Core AMF ticket + transport ping anomaly | `SUPPORTED` | `SUPPORTED` | $0.968$ | `SUFFICIENT` | **PASS** | Ignores unrelated T-SW ping anomaly; grounds AMF symptoms correctly. |
| **SEM-005** | Irrelevant Evidence | Optical fiber cut + chassis fan anomaly | `SUPPORTED` | `SUPPORTED` | $0.976$ | `SUFFICIENT` | **PASS** | Fiber cut diagnosis unaffected by minor chassis fan fluctuation. |
| **SEM-006** | Irrelevant Evidence | Antenna VSWR + NTP time jitter anomaly | `SUPPORTED` | `SUPPORTED` | $0.964$ | `SUFFICIENT` | **PASS** | RF return loss correctly identified despite background NTP noise. |
| **SEM-007** | Contradictory Evidence | RAN VSWR ticket claiming TRANSPORT | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Detects domain mismatch (RAN alarm vs Transport domain); abstains. |
| **SEM-008** | Contradictory Evidence | BGP flap ticket claiming 5G_CORE | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Detects domain mismatch (Transport alarm vs 5GC domain); abstains. |
| **SEM-009** | Contradictory Evidence | M3 cluster incompatible alarm mechanisms | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Ingests M3 incompatible flag (`RF_HARDWARE` vs `CORE_USER_PLANE`); abstains. |
| **SEM-010** | Stale Runbooks | Legacy 2G GSM TCH congestion ticket | `INCONCLUSIVE`| `SUPPORTED` | $0.858$ | `SUFFICIENT` | **FAIL** | **Finding FIND-M5-002:** Generic terms ("congestion", "drop") matched 5G RAN SOP. |
| **SEM-011** | Stale Runbooks | Legacy 3G UMTS NodeB ATM link loss | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | ATM E1 copper line terms not indexed; safely abstains. |
| **SEM-012** | Stale Runbooks | Legacy WiMAX ASN gateway timeout | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | WiMAX R6 protocol not indexed; safely abstains. |
| **SEM-013** | Wrong Vendor/Version | Juniper JunOS commit rollback failure | `INCONCLUSIVE`| `SUPPORTED` | $0.766$ | `SUFFICIENT` | **FAIL** | **Finding FIND-M5-002:** "Routing instance", "aggregation" matched IP-MPLS BGP SOP. |
| **SEM-014** | Wrong Vendor/Version | Cisco IOS-XR RPL route policy compile | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Syntax compile terms lack matching SOP; safely abstains. |
| **SEM-015** | Wrong Vendor/Version | Nokia NetAct Northbound CORBA IRP sync | `INCONCLUSIVE`| `SUPPORTED` | $0.853$ | `SUFFICIENT` | **FAIL** | **Finding FIND-M5-002:** "Synchronization timeout" matched PTP clock sync case. |
| **SEM-016** | Missing Preconditions | Vague "slow connection" in west region | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Zero alarms, zero elements, zero telemetry; safely abstains. |
| **SEM-017** | Missing Preconditions | Empty ticket description ("Down") | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Description $< 4$ words, zero telemetry; safely abstains. |
| **SEM-018** | Missing Preconditions | Routine evening diurnal traffic dip | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | `is_negative_control=True` flag detected; safely abstains. |
| **SEM-019** | Similar Symptoms Diff Root | RF jammer vs optical fiber cut | `SUPPORTED` | `SUPPORTED` | $0.956$ | `SUFFICIENT` | **PASS** | Dispatches RF van per `INC-TELTS-JAMMER-0000`; avoids fiber SOP. |
| **SEM-020** | Similar Symptoms Diff Root | PTP clock drift vs hardware failure | `SUPPORTED` | `SUPPORTED` | $0.942$ | `SUFFICIENT` | **PASS** | Recommends GPS surge inspection per `INC-TELTS-SYNC-0001`. |
| **SEM-021** | Similar Symptoms Diff Root | VoLTE drop timer vs radio link failure | `SUPPORTED` | `SUPPORTED` | $0.948$ | `SUFFICIENT` | **PASS** | Recommends EPS fallback timer audit per `INC-TELTS-VOLTE-0002`. |
| **SEM-022** | Multiple Hypotheses | Optical LOS + BGP flap on router | `SUPPORTED` | `SUPPORTED` | $0.960$ | `SUFFICIENT` | **PASS** | Generates primary optical LOS and secondary BGP flap hypotheses. |
| **SEM-023** | Multiple Hypotheses | RAN handover failure + VSWR spike | `SUPPORTED` | `SUPPORTED` | $0.968$ | `SUFFICIENT` | **PASS** | Generates primary VSWR and secondary Xn handover hypotheses. |
| **SEM-024** | Multiple Hypotheses | AMF storm + UPF latency surge | `SUPPORTED` | `SUPPORTED` | $0.964$ | `SUFFICIENT` | **PASS** | Generates primary AMF and secondary UPF user-plane hypotheses. |
| **SEM-025** | Correlation Not Causation | Optical LOS during midnight billing job| `SUPPORTED` | `SUPPORTED` | $0.968$ | `SUFFICIENT` | **PASS** | Grounds in physical optical fiber fault; ignores billing mention. |
| **SEM-026** | Correlation Not Causation | VSWR spike during weather radar poll | `SUPPORTED` | `SUPPORTED` | $0.954$ | `SUFFICIENT` | **PASS** | Grounds in RF return loss; ignores radar weather poll. |
| **SEM-027** | Correlation Not Causation | AMF storm during admin GUI login | `SUPPORTED` | `SUPPORTED` | $0.968$ | `SUFFICIENT` | **PASS** | Grounds in SCTP association exhaustion; ignores technician login. |
| **SEM-028** | Recs Exceeding Evidence | Vague download speed complaint | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Recommends only `HUMAN_ESCALATION`; prohibits tower climb/card reboot. |
| **SEM-029** | Recs Exceeding Evidence | Qubit Josephson junction phase slip | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Recommends only `HUMAN_ESCALATION`; prohibits optical splice. |
| **SEM-030** | Recs Exceeding Evidence | Minor 4ms ping jitter | `INCONCLUSIVE`| `INCONCLUSIVE`| $0.000$ | `INSUFFICIENT`| **PASS** | Recommends only `HUMAN_ESCALATION`; prohibits BGP reset. |

---

## 3. Deep Dive into Semantic Audit Findings

### 3.1. Finding FIND-M5-002: Semantic Vocabulary Overlap on Unindexed Tech
- **Observed Defect:** In Cases `SEM-010` (Legacy 2G GSM), `SEM-013` (Juniper JunOS), and `SEM-015` (Nokia NetAct), the system returned `HypothesisStatus.SUPPORTED` with high confidence proxies ($0.766$ to $0.858$) and generated runbook recommendations for 5G RAN or Transport.
- **Root Cause Analysis:**
  1. Dense embeddings and BM25 match general telecom terms ("congestion", "link drop", "routing instance", "synchronization timeout").
  2. The ticket's domain (`RAN`, `TRANSPORT`, `CROSS_DOMAIN`) matched the domain metadata of the retrieved runbooks.
  3. Because the ticket included an alarm code (`ALM-GSM-TCH-CONG`), the sufficiency engine considered alarms to be present (`has_alarms = True`).
  4. The engine lacks an equipment generation filter (e.g. 2G vs 5G) and vendor-specific dictionary.
- **Operational Impact:** If an unindexed 2G GSM cell drops a channel, an automated investigation engine might recommend a 5G gNodeB AAU tilt sweep!
- **Auditor Recommendation:** Enhance `MetadataFilter` and sufficiency analysis to evaluate generation compatibility (`2G_GSM`, `3G_UMTS`, `4G_LTE`, `5G_NR`) and vendor hardware family before confirming a hypothesis.

### 3.2. Verification of Epistemic Honesty Principles
1. **Valid ID vs Unrelated Claim:** In all 30 cases, hypotheses and recommendations strictly cited registered evidence IDs (`EVID-xxx`). However, as shown by `SEM-010`, syntactic citation integrity does not prevent semantic misapplication when the retrieval stage returns an unindexed technology match.
2. **Prediction vs Observation Separation:** Verified that ML predictions (`predicted_category`, `predicted_severity`) are registered as `EvidenceType.ML_CLASSIFICATION` and `EvidenceType.SEVERITY_PREDICTION`, while telemetry violations are registered as `EvidenceType.TELEMETRY_ANOMALY`.
3. **Hypothesis vs Confirmed Root Cause:** All hypotheses are explicitly prefixed with *"Primary Diagnostic Hypothesis: Incident symptoms consistent with..."* and never declare certainty.
4. **Historical Similarity vs Causal Proof:** In `SEM-025`, `SEM-026`, and `SEM-027`, coincidental timing (billing job, weather poll, GUI login) was correctly filtered out in favor of the physical alarm evidence.

---

## 4. Conclusion

The semantic evidence-grounding audit confirms that the M5 investigation engine is substantially robust against irrelevant telemetry, missing signals, coincidental correlations, and domain contradictions (27/30 passed). However, the engine exhibits a real semantic gap when exposed to unindexed legacy generations and unsupported vendor CLI syntaxes. This finding directly informs the audit verdict of **ACCEPTED WITH LIMITATIONS**.
