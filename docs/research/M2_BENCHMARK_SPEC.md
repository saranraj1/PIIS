# PIIS-TelcoBench-v2 — Synthetic Benchmark Specification

**Specification Version:** 2.0  
**Target Milestone:** M2.1 Adversarial Remediation  
**Status:** APPROVED & LOCKED  
**Date:** 2026-10-31  

---

## 1. Overview & Objectives

PIIS-TelcoBench-v2 is an independently authored, linguistically diverse, and causally decoupled benchmark designed specifically to eliminate the template memorization and leakage defects discovered in v1.

### Key Benchmark Enhancements over v1
- **Decoupled Architecture:** `fault_category`, `scenario_family_id`, `causal_configuration_id`, `template_id`, `severity`, and `support_level` vary independently.
- **Linguistic Diversity:** 3 distinct structural templates per fault family (NOC Machine Synopsis, Field Operations Log, Service Impact Statement) with lexical synonym randomization.
- **Context-Aware Operational Severity:** Severity is calculated using a multi-attribute utility model incorporating subscriber scale, service criticality, topological redundancy, and operational timing.
- **Zero Train-Test Text Duplication:** Template T3 is strictly withheld for holdout evaluation, guaranteeing $0.00\%$ cross-split text duplication.
- **Expanded Negative Controls:** Includes both routine nominal diurnal variation (FAM-11) and ambiguous below-threshold telemetry jitter (FAM-12).

---

## 2. Scenario Family & Causal Taxonomy

| Family ID | Canonical Fault Category | Fault Subtype | Primary Network Domain | Causal Variables & Variations |
| :--- | :--- | :--- | :--- | :--- |
| **FAM-01** | `ran_signal_degradation` | `feeder_attenuation` | `RAN` | Feeder line VSWR ($1.8 - 3.2$), attenuation ($12 - 28$ dB), RRH overheating |
| **FAM-02** | `handover_failure` | `xn_preparation_timeout` | `RAN` | Neighbor offset mismatch, Xn delay ($80 - 320$ ms), ping-pong oscillation |
| **FAM-03** | `cell_congestion` | `prb_saturation` | `RAN` | PRB utilization ($92 - 99\%$), active UE count ($150 - 900$), queue latency |
| **FAM-04** | `base_station_outage` | `mains_power_loss` | `RAN` | AC loss, DC voltage ($41 - 44$V), CPRI optical transceiver link break |
| **FAM-05** | `subscriber_authentication_failure` | `ausf_sbi_timeout` | `5G_CORE` | HTTP/2 SBI latency ($2.5 - 8.0$s), UDM mTLS cert expiration, AKA vector drop |
| **FAM-06** | `session_establishment_failure` | `ip_pool_exhaustion` | `5G_CORE` | SMF dynamic subnet pool allocation ($98 - 100\%$), UPF N4 reject code |
| **FAM-07** | `user_plane_degradation` | `dpdk_buffer_drop` | `5G_CORE` | DPDK ring overflow ($15 - 45\%$ packet drop), GTP-U jitter, CPU core affinity |
| **FAM-08** | `transport_link_failure` | `optical_crc_errors` | `TRANSPORT` | Optical Rx power ($-23$ to $-28$ dBm), framing errors, BGP route flap |
| **FAM-09** | `dns_service_failure` | `resolver_timeout` | `SERVICE` | Named worker thread exhaustion, DNS query timeout ($85 - 99\%$), UDP socket drop |
| **FAM-10** | `configuration_regression` | `mtu_blackhole` | `CROSS_DOMAIN` | Path MTU mismatch ($1420$ vs $1500$ B), QoS queue starvation, ACL drop |
| **FAM-11** | `nominal_operation` | `diurnal_fluctuation` | `RAN` | Routine off-peak traffic decline, healthy PRB utilization ($15 - 35\%$) |
| **FAM-12** | `ambiguous_low_evidence`| `transient_jitter` | `CROSS_DOMAIN` | Sub-threshold latency spike, self-clearing alarm, insufficient evidence |

---

## 3. Structural Template Taxonomy

Each fault family is realized across 3 structurally distinct templates:

### Template T1: NOC Automated Alarm Synopsis
- **Structure:** `[ALARM_CODE] <Network Element> <Physical/Logical Fault Summary>. Metrics: <Primary KPI> exceeded threshold.`
- **Audience:** Automated monitoring dashboards and central OSS ingestion collectors.
- **Style:** Terse, identifier-centric, KPI-dense.

### Template T2: Field Engineering / Tier-1 Triage Log
- **Structure:** `Dispatch ticket for <Network Element>. Technician notes: observed <Symptom Description>. Investigated <Subsystem>; runbook <SOP_ID> attempted.`
- **Audience:** Operational NOC engineers and field dispatch queues.
- **Style:** Procedural, operational narrative, mentions diagnostic steps and SOPs.

### Template T3: End-User & Service SLA Impact Statement
- **Structure:** `Subscribers in <Region> reporting <User Experience Degradation>. Service impact: <Business Function> unavailable. Associated with <Network Domain> failure.`
- **Audience:** Customer care escalations, SLA management, and executive NOC commanders.
- **Style:** High-level, customer-centric, impact-oriented, vocabulary strictly disjoint from T1/T2.

---

## 4. Multi-Attribute Severity Assignment Rules

Severity is assigned deterministically based on operational blast radius, topology redundancy, and service criticality:

```python
score = (
    subscribers_factor(affected_subscribers)       # 1 to 4
    + criticality_factor(service_criticality)     # 1 to 4 (Emergency=4, Enterprise=3, eMBB=2, IoT=1)
    + redundancy_factor(redundancy_state)         # 1 to 4 (SPOF=4, Degraded=2, Fully Protected=1)
    + timing_factor(operational_timing)           # 1 to 3 (Peak=3, Business=2, Maintenance=1)
)

if service_criticality == "EMERGENCY_PSAP" or (redundancy_state == "SPOF" and affected_subscribers > 500):
    severity = "CRITICAL"
elif score >= 11:
    severity = "CRITICAL"
elif score >= 8:
    severity = "MAJOR"
elif score >= 5:
    severity = "MINOR"
else:
    severity = "WARNING"
```

### Verified Multi-Severity Coverage
Across the 360 generated benchmark records:
- `CRITICAL`: 92 records ($25.6\%$)
- `MAJOR`: 168 records ($46.7\%$)
- `MINOR`: 70 records ($19.4\%$)
- `WARNING`: 30 records ($8.3\%$)
Every fault category spans at least 2 distinct severity tiers.

---

## 5. Independent Support Routing Rules

Ground-truth support levels are assigned independently of the model:
- **L1:** `runbook_available is True` AND `requires_specialist is False` AND `requires_advanced_diag is False`.
- **L2:** `requires_advanced_diag is True` AND `requires_specialist is False`.
- **L3:** `requires_specialist is True` (e.g. vendor software fix, field fiber optic splicing).
- **HUMAN_REVIEW:** `is_negative_control is True` OR `evidence_sufficient is False`.

### Distribution
- `L1`: 132 records ($36.7\%$)
- `L2`: 136 records ($37.8\%$)
- `L3`: 42 records ($11.7\%$)
- `HUMAN_REVIEW`: 50 records ($13.9\%$)

---

## 6. Dataset Partitioning & Holdout Specification

### Overall Volume
- **Total Records:** 360 incidents (30 records per family across 12 families).

### Partition Strategy
- **Train Set (240 records):**
  - Templates: `T1` (NOC Alarm Synopsis) and `T2` (Field Operations Log).
  - Causal Configurations: `C1` and `C2`.
  - Seeds: Deterministic seed 42.
- **Holdout Test Set (120 records):**
  - Template: `T3` (Service SLA Impact Statement) exclusively.
  - Causal Configuration: `C3` exclusively.
  - Seeds: Deterministic seed 101.
- **Mathematical Duplicate Guarantee:**
  - `Train \cap Test` exact string equality = **$0.00\%$** ($0 / 120$).
  - N-gram overlap strictly restricted to common English stop words and domain abbreviations.
