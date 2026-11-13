# PIIS Milestone 2.1 — Adversarial Remediation & Benchmark Reconstruction Design

**Author:** Principal ML Research Engineer, Synthetic Data Architect, Telecom Domain Specialist & Evaluation Lead  
**Status:** APPROVED FOR BENCHMARK RECONSTRUCTION  
**Date:** 2026-10-31  
**Audit Context:** Remediation of findings in `docs/research/M2_ADVERSARIAL_VALIDATION_REPORT.md` (Verdicts: NOT VALIDATED)  
**Governance:** Strict Non-Circularity, Independence of Attributes, Group-Aware Disjoint Splits  

---

## 1. Executive Context & Objectives

The M2 Adversarial Validation Audit established that the reported $1.0000$ Macro-F1 scores across fault classification, severity prediction, and support routing were artifacts of:
1. **100% Cross-Split Text Duplication:** Identical templates and cell IDs across seeds.
2. **74.5% Lexical Shortcut Density:** Single tokens uniquely identifying scenario families.
3. **Severe Generalization Collapse:** Severity accuracy collapsing to $28.5\%$ on unseen families.
4. **Tautological Routing Evidence Extraction:** Direct branch checking `scenario_family_id`.
5. **Unmeasured OOD Claims:** Real testbed true label absent from candidate classes.

The objective of **Milestone 2.1 (M2.1)** is to reconstruct the synthetic data generator, rebuild the severity and routing ground truth on defensible telecom operational principles, establish a 6-track generalization evaluation protocol, and produce verified, non-circular baseline models.

Historical M2 records in `artifacts/m2_metrics/` and `docs/research/M2_ADVERSARIAL_VALIDATION_REPORT.md` are strictly preserved as baseline evidence.

---

## 2. Decoupled Multi-Attribute Generation Architecture

In M2, `fault_category`, `scenario_family_id`, `severity`, and `support_level` were deterministically bound to a single generator function. In M2.1, each generated incident is governed by 7 independent, orthogonal dimensions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 M2.1 INCIDENT GENERATION                                │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
        ┌───────────────────────────────────┼────────────────────────────────────┐
        ▼                                   ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐                 ┌──────────────────┐
│   Fault Domain   │              │   Causal State   │                 │ Operational Risk │
│ & Classification │              │  Configuration   │                 │     Calculus     │
├──────────────────┤              ├──────────────────┤                 ├──────────────────┤
│ fault_category   │              │ causal_config_id │                 │ severity         │
│ fault_subtype    │              │ physical params  │                 │ blast radius     │
│ scenario_family  │              │ topology params  │                 │ subscriber scale │
└────────┬─────────┘              └────────┬─────────┘                 └────────┬─────────┘
         │                                 │                                    │
         └────────────────────────┬────────┴────────────────────────────────────┘
                                  ▼
                 ┌──────────────────────────────────┐
                 │       Linguistic Surface         │
                 │          Realization             │
                 ├──────────────────────────────────┤
                 │ template_id (T1, T2, T3)         │
                 │ linguistic_style (NOC, Field, OSS)│
                 │ lexical_variant (synonyms/jargon)│
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │   Support Tier Ground Truth      │
                 │     (Independent Case Card)      │
                 ├──────────────────────────────────┤
                 │ support_level_label              │
                 │ SOP runbook availability         │
                 │ required tool permissions        │
                 │ specialist vendor dependency     │
                 └──────────────────────────────────┘
```

### Orthogonality Invariants
1. **Fault Category $\neq$ Severity:** Every fault category must appear across at least 2 distinct severity levels depending on blast radius and operational context.
2. **Fault Category $\neq$ Support Level:** Technically identical faults must have different support levels when operational runbooks or access permissions differ.
3. **Template $\neq$ Scenario Family:** Every fault category must be realized through at least 3 structurally distinct syntactic templates.
4. **No Semantic Leaks in Text:** Model-facing text (`title`, `description`) must NEVER contain class label strings, scenario IDs, template IDs, or rule tags.

---

## 3. Operational Severity Decision Calculus

Severity is no longer a static attribute of a scenario family. It is determined by an explicit, documented **Telecom SLA Impact Matrix**:

$$\text{SeverityScore} = w_{\text{sub}} \cdot S_{\text{sub}} + w_{\text{crit}} \cdot C_{\text{crit}} + w_{\text{red}} \cdot R_{\text{red}} + w_{\text{time}} \cdot T_{\text{time}}$$

Where:
- **Subscriber Scale ($S_{\text{sub}}$):**
  - $> 1,000$ subscribers $\rightarrow 4$
  - $200 - 1,000$ subscribers $\rightarrow 3$
  - $20 - 200$ subscribers $\rightarrow 2$
  - $< 20$ subscribers $\rightarrow 1$
- **Service Criticality ($C_{\text{crit}}$):**
  - Emergency / Public Safety / PSAP E911 $\rightarrow 4$
  - Enterprise Dedicated Core / VIP SLA $\rightarrow 3$
  - Commercial Mobile Broadband (eMBB) $\rightarrow 2$
  - Best-Effort / IoT Slice $\rightarrow 1$
- **Redundancy State ($R_{\text{red}}$):**
  - Single Point of Failure (SPOF / Unprotected) $\rightarrow 4$
  - Degraded Redundancy (Active/Standby failover active) $\rightarrow 2$
  - Fully Protected (Automatic Protection Switching / Multi-homed) $\rightarrow 1$
- **Operational Timing ($T_{\text{time}}$):**
  - Busy Hour (Peak Traffic 18:00–22:00) $\rightarrow 3$
  - Business Hours (09:00–17:00) $\rightarrow 2$
  - Maintenance Window (01:00–05:00) $\rightarrow 1$

### Decision Thresholds
- **CRITICAL:** Composite Score $\ge 11$ OR Emergency Slice Affected OR Outage on SPOF with $>500$ subscribers.
- **MAJOR:** Composite Score $8 - 10$ OR Single Site Failure during Peak Hours.
- **MINOR:** Composite Score $5 - 7$ OR Partial degradation with active redundancy.
- **WARNING:** Composite Score $< 5$ OR Negative control / Routine traffic variation.

### Multi-Severity Distribution by Fault Category
| Fault Category | Can be CRITICAL? | Can be MAJOR? | Can be MINOR? | Can be WARNING? |
| :--- | :--- | :--- | :--- | :--- |
| `ran_signal_degradation` | Yes (Emergency/VIP site) | Yes (Standard cell) | Yes (Low-traffic sector) | No |
| `cell_congestion` | Yes (Stadium/Event SLA) | Yes (Peak business) | Yes (Routine suburban) | No |
| `base_station_outage` | Yes (SPOF Macro site) | Yes (N+1 redundant small cell)| No | No |
| `core_access_failure` | Yes (Enterprise slice) | Yes (Regional pool) | Yes (Single tenant lab) | No |
| `transport_link_failure` | Yes (Unprotected backhaul)| Yes (Dual-homed link) | Yes (Protected optical ring) | No |
| `nominal_operation` | No | No | No | Yes (Always WARNING) |

---

## 4. Independent Support Routing Ground Truth

To eliminate circularity, ground truth for operational support tiering is authored independently of the evaluated `PolicyEngine`:

### Independent Operational Triage Conditions
- **L1 (Operational NOC Tier-1):**
  - Documented Standard Operating Procedure (SOP) exists AND
  - Tier-1 engineer holds automated portal execution permissions (e.g. cell lock/unlock, PRB capacity balancing, mobile generator dispatch, configuration rollback) AND
  - Requires no specialized physical diagnostic instruments.
- **L2 (Specialized Network Engineering Tier-2):**
  - Requires physical radio frequency (RF) measurements (VSWR, spectrum analyzer) OR
  - Optical Time Domain Reflectometer (OTDR) fiber fault location OR
  - Virtualization kernel / DPDK core buffer optimization OR
  - Cross-domain root-cause investigation across multiple network layers.
- **L3 (Specialist / Vendor TAC / Field Splicing):**
  - Proprietary vendor software/firmware defect OR
  - Physical optical fiber cable cut requiring field fiber splicing crew OR
  - Hardware chassis replacement.
- **HUMAN_REVIEW (Operational Abstention Gate):**
  - Telemetry is within normal boundaries (negative control) OR
  - Conflicting alarms with below-threshold confidence OR
  - Novel symptom pattern lacking documented runbook and diagnostic signature.

### Natural Language Evidence Extraction (No Family ID Shortcuts)
The routing evaluation pipeline must extract evidence exclusively from raw text descriptions, reported alarms, and telemetry indicators using standard regex and entity extraction:
- `known_runbook`: Extracted via SOP pattern matching (`SOP-[A-Z]+-[0-9]+`, "standard operating procedure", "runbook").
- `advanced_diagnostics`: Extracted via technical symptom terms ("vswr", "spectrum analyzer", "otdr", "packet capture", "dpdk ring", "mtls certificate").
- `specialist_dependency`: Extracted via vendor escalation terms ("vendor tac", "chassis rma", "cable splice", "firmware patch").
- `insufficient_evidence`: Triggered when zero anomaly indicators or nominal traffic phrases are detected.

---

## 5. Six-Track Generalization Evaluation Protocol

To prevent train/test duplication and measure true machine learning capabilities, the evaluation harness implements 6 isolated generalization tracks:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        EVALUATION TRACK MATRIX                         │
├─────────┬─────────────────────────┬────────────────────────────────────┤
│ Track   │ Evaluation Focus        │ Holdout Partition Strategy         │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track A │ Linguistic Generalization│ Hold out Template T3 completely;   │
│         │                         │ Train on T1 & T2.                  │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track B │ Causal Generalization   │ Hold out Causal Config C3;         │
│         │                         │ Train on C1 & C2.                  │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track C │ Hierarchical Generalize │ Predict Parent Domain & Subtype;   │
│         │                         │ Hold out specific leaf subtypes.   │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track D │ Unknown Fault Detection │ Hold out entire novel fault class; │
│         │ (OOD & Abstention)      │ Measure abstention & false accept. │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track E │ Severity Generalization │ Hold out unseen causal/blast-radius│
│         │                         │ combinations; compare vs rules.    │
├─────────┼─────────────────────────┼────────────────────────────────────┤
│ Track F │ Routing Generalization  │ Evaluate independently authored    │
│         │                         │ case cards without family ID tags. │
└─────────┴─────────────────────────┴────────────────────────────────────┘
```

---

## 6. Dataset Plan & Human Annotation Sampling

### Volume & Scenario Coverage
- **Total Synthetic Benchmark v2:** 360 incidents.
- **Scenario Families:** 12 families (10 fault types, 2 negative controls/ambiguous).
- **Per Family:** 30 incidents spanning:
  - 3 Causal Configurations (C1, C2, C3)
  - 3 Linguistic Templates (T1: NOC Alarm Syntax, T2: Field Tech Log, T3: Customer/Service Impact Summary)
  - 3 Linguistic Styles (Standard, Jargon-dense, Terse)
- **Partitions:**
  - Training Partition: 240 incidents (T1, T2; C1, C2).
  - Independent Holdout Test Partition: 120 incidents (T3; C3).
  - Target Verbatim Text Duplicate Rate: **0.00%** (mathematically verified).

### Human-Review-Ready Sampling Plan
- A random stratified sample of 10% (36 records) will be exported with explicit provenance cards to `docs/data/M2_HUMAN_REVIEW_SAMPLE.jsonl`.
- Reviewers assess: (1) Technical realism, (2) Symptom-to-severity consistency, (3) Support tier correctness, (4) Absence of label leaks.

---

## 7. Acceptance Criteria for M2.1

1. **Zero Text Duplication:** $0.00\%$ train/test verbatim duplication at the holdout split.
2. **Zero Single-Token Shortcuts:** No individual token has $>90\%$ mutual information or $>85\%$ exclusive recall for any class.
3. **Severity Decoupling:** Every fault class exhibits $>1$ severity level across variants.
4. **Independent Routing:** `extract_routing_evidence` contains zero references to `scenario_family_id`.
5. **Ablations & Negative Controls:** Permutation tests, dummy baselines, and negative control abstentions reported.
6. **Programmatic Verification:** Full suite of regression tests passing with 0 lint errors.
7. **Disclaimers:** Production readiness claims omitted; limitations on synthetic benchmark validity explicitly stated.
