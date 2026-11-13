# Milestone 2 — Data Suitability Assessment

**Author:** PIIS Applied ML & Research Team  
**Date:** 2026-10-31  
**Status:** Approved for M2 Baseline Engineering  
**Governance:** Zero-Target Leakage, Group-Aware Split Standard, Provenance Isolation  

---

## 1. Executive Summary

Milestone 2 requires establishing defensible, leakage-safe machine learning baselines for telecom incident intelligence. Before training any model, this assessment inspects all available normalized datasets, establishes task-to-dataset suitability, audits label provenance, and specifies strict prediction-time feature contracts.

---

## 2. Dataset Inventory & Provenance Mapping

| Dataset ID | Local Storage Path | Source Type | Raw Volume | Target Entities | Primary Operational Domains |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SRC-002** | `data/processed/incidents/telecomts_incidents.jsonl` | `PUBLIC_REAL` (derived) | 93 tickets | Incident Tickets | RAN (5G Testbed Jamming) |
| **SRC-002-TEL** | `data/processed/telemetry/telecomts_jammer_telemetry.jsonl` | `PUBLIC_REAL` | 5,000 observations | 10 Hz Physical/MAC | RAN (PHY/MAC KPIs) |
| **SRC-005** | `data/processed/telemetry/ucc5g_drive_telemetry.jsonl` | `PUBLIC_REAL` | 3,000 observations | Drive-test Telemetry | Client/Application QoS |
| **SYN-BENCH** | `data/synthetic/synthetic_incidents_seed42.jsonl` | `SYNTHETIC` | 33 tickets (base) | Canonical Incidents | RAN, Core, Transport, Service |
| **SYN-BENCH-M2**| `data/synthetic/synthetic_incidents_m2.jsonl` | `SYNTHETIC` | 220 tickets (expanded) | Multi-family Incidents | All 11 scenario families (S00–S10) |

---

## 3. Prediction Task Suitability Matrix

| Prediction Task | Candidate Dataset | Label Type | Suitability Verdict | Justification & Methodological Constraints |
| :--- | :--- | :--- | :--- | :--- |
| **Task 1: Fault Category Classification** (Multi-class) | `synthetic_incidents_m2.jsonl` | Ground-truth causal injection | **SUITABLE** | 11 balanced scenario families with distinct causal mechanisms and technical indicators. |
| **Task 1: Fault Category Classification** (OOD / Transfer) | `telecomts_incidents.jsonl` | Testbed diagnostic annotation | **HOLD-OUT ONLY** | Single fault category (`rf_jamming_interference`). Cannot be used for multi-class training; serves as real-world zero-shot / transfer test for RAN interference detection. |
| **Task 1: Fault Category Classification** | `ucc5g_drive_telemetry.jsonl` | None (pure telemetry) | **UNSUPPORTED** | Lacks incident tickets, descriptions, and fault category labels. |
| **Task 2: Severity Prediction** (Multi-class/Ordinal) | `synthetic_incidents_m2.jsonl` | Defined operational SLA impact | **SUITABLE** | 4 severity tiers (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`) correlated with subscriber impact and service outage. |
| **Task 2: Severity Prediction** | `telecomts_incidents.jsonl` | Static `MAJOR` label | **UNSUPPORTED FOR TRAINING** | Zero intra-dataset severity variance (all 93 records labeled `MAJOR`). Cannot train severity discriminator. |
| **Task 3: Telemetry Anomaly Detection** (Binary) | `telecomts_jammer_telemetry.jsonl` | Physical hardware ground-truth | **SUITABLE** | Ground-truth `Jamming` flag (81% normal, 19% anomalous) from physical RF jammer state. |
| **Task 4: Support-Level Routing** (L1/L2/L3/Human) | Any available dataset | Operational tier | **POLICY-ONLY (NO ML)** | Per architectural constraint ADR-0002 and prompt mandate: ML must NOT be trained on support-level routing without human-reviewed operator-specific labels. Routing is evaluated via the deterministic `PolicyEngine`. |

---

## 4. Label Provenance & Semantics Audit

1. **Fault Category Semantics:**
   - Technical fault classification denotes *what physical or logical subsystem failed* (e.g. `ran_signal_degradation`, `dns_service_failure`, `fiber_cut_link_down`).
   - Fault category is fundamentally orthogonal to organizational support tier.
2. **Severity Semantics:**
   - Denotes operational urgency and business impact (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`).
   - Must be predicted using pre-resolution telemetry, subscriber impact, and symptom description.
3. **Support Level Routing:**
   - Denotes *who possesses permissions, runbooks, and skills to resolve*.
   - Governed strictly by deterministic operational policy rules based on runbook availability, permissions, and diagnostic complexity.

---

## 5. Prediction-Time Feature Contracts & Leakage Quarantine

To guarantee zero target leakage, all model feature extractors must strictly adhere to `src/piis/normalization/contracts.py`:

### Prohibited Fields (Quarantined at Triage Time)
The following fields are generated during or after incident resolution and MUST NEVER enter prediction feature vectors:
- `resolution_summary` (Contains verbatim root cause and fix steps)
- `resolved_at` (Indicates resolution duration)
- `root_cause_confirmed` (Post-facto boolean confirmation)
- `actual_resolution_steps`
- `post_incident_telemetry`
- `confirmed_root_cause`
- `troubleshooting_tickets`

### Permitted Prediction-Time Fields
- `title`: Short alarm/ticket summary available at ingress.
- `description`: Preliminary symptom description reported by monitoring agents or users.
- `network_domain`: Reported network tier (`RAN`, `CORE`, `TRANSPORT`, `SERVICE`, `CROSS_DOMAIN`).
- `affected_region`: Operational geography.
- `affected_subscribers`: Estimated impacted subscriber count at triage time.
- `network_element_ids`: Reported failing topology nodes.
- `created_at`: Incident creation timestamp.

---

## 6. Group-Aware Splitting Strategy

To avoid optimistic bias and row-level data leakage:
1. **Never perform random row-level splitting**: Repeated observations from the same incident, topology element, or scenario run must not span both train and test splits.
2. **Group Holdout Scheme**:
   - `split_group_id` groups together incidents from identical seed/simulation runs.
   - Cross-validation: 5-Fold Stratified Group K-Fold where groups are disjoint across folds.
   - Out-of-Distribution (OOD) Holdout: Real testbed records (`telecomts_incidents.jsonl`) held out completely from training to test zero-shot transfer on real RAN degradation symptoms.
