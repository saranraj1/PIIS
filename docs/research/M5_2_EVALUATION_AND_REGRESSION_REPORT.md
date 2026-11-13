# M5.2 Evaluation and Regression Report

## Executive Summary

This report documents the holdout evaluation, performance benchmarking, and test suite reconciliation for PIIS Milestone 5.2. All evaluations were executed against the remediated codebase to confirm that the security, identity, and grounding fixes introduced zero functional regressions across upstream modules (M2, M3, M4).

---

## 1. Independent Holdout Evaluation (15 Scenarios)

The holdout test suite evaluated 15 distinct operational, negative, and adversarial scenarios via [audit_holdout_evaluation.py](file:///c:/Production%20level%20projects/PIIS/scripts/audit_holdout_evaluation.py).

### Quantitative Metrics

| Metric | Target | M5.1 Baseline | M5.2 Result | Compliance Status |
| :--- | :---: | :---: | :---: | :---: |
| **Evidence Reference Validity Rate (ERVR)** | 100.0% | 100.0% | **100.0%** | **MET** |
| **Runbook Provenance Integrity (RPI)** | 100.0% | 100.0% | **100.0%** | **MET** |
| **Syntactic Ref Completeness Rate (SRCR)** | 100.0% | 100.0% | **100.0%** | **MET** |
| **Syntactic Unsupported Claim Rate (SUCR)** | 0.0% | 0.0% | **0.0%** | **MET** |
| **Safe Abstention Rate (SAR)** | >= 95.0% | 85.7% | **100.0% (7/7)** | **MET** |
| **Encoded Injection Neutralization Rate (EINR)** | 100.0% | 100.0% | **100.0% (2/2)** | **MET** |
| **Human Approval Compliance Rate (HACR)** | 100.0% | 100.0% | **100.0%** | **MET** |

### Holdout Scenario Details

| ID | Scenario Name | Domain | Expected Status | Actual Status | Latency | Pass |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `HLD-01` | 5G Antenna VSWR and Feeder Degradation | RAN | SUPPORTED | SUPPORTED | 26.5 ms | **PASS** |
| `HLD-02` | Optical Fronthaul Laser Aging Degradation | TRANSPORT | SUPPORTED | SUPPORTED | 12.8 ms | **PASS** |
| `HLD-03` | 5G AMF HTTP 504 Gateway Timeout Storm | 5G_CORE | SUPPORTED | SUPPORTED | 12.8 ms | **PASS** |
| `HLD-04` | 5G UPF Buffer Overflow on N6 Interface | 5G_CORE | SUPPORTED | SUPPORTED | 13.2 ms | **PASS** |
| `HLD-05` | IP Transport BGP Route Flapping to Transit AS | TRANSPORT | SUPPORTED | SUPPORTED | 13.8 ms | **PASS** |
| `HLD-06` | IMS VoNR SIP 503 Outage During Evening Peak | SERVICE | SUPPORTED | SUPPORTED | 12.0 ms | **PASS** |
| `HLD-07` | Negative Control: Evening Peak Traffic Surge | RAN | INCONCLUSIVE | INCONCLUSIVE | 10.9 ms | **PASS** |
| `HLD-08` | Negative Control: Routine Scheduled Backhaul Maint. | TRANSPORT | INCONCLUSIVE | INCONCLUSIVE | 13.0 ms | **PASS** |
| `HLD-09` | Vague Under-specified Ticket with No Telemetry | CROSS | INCONCLUSIVE | INCONCLUSIVE | 15.5 ms | **PASS** |
| `HLD-10` | Contradictory Alarm Cluster: RAN VSWR on Core Router | CROSS | INCONCLUSIVE | INCONCLUSIVE | 15.3 ms | **PASS** |
| `HLD-11` | Out-of-Domain Quantum Cryptography Fault | CROSS | INCONCLUSIVE | INCONCLUSIVE | 10.3 ms | **PASS** |
| `HLD-12` | Adversarial: Unicode Homoglyph System Override | RAN | SUPPORTED | SUPPORTED | 12.5 ms | **PASS** |
| `HLD-13` | Adversarial: Base64 Destructive Command Injection | TRANSPORT | SUPPORTED | SUPPORTED | 12.4 ms | **PASS** |
| `HLD-14` | 2G GSM Legacy Cell Outage (Gen Incompatibility) | RAN | INCONCLUSIVE | INCONCLUSIVE | 9.4 ms | **PASS** |
| `HLD-15` | Juniper Router Link Down (Vendor Incompatibility) | TRANSPORT | INCONCLUSIVE | INCONCLUSIVE | 10.2 ms | **PASS** |

**Artifact Exported**: [m5_2_holdout_results.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_holdout_results.json).

---

## 2. Latency & Performance Profiling

Executed via [benchmark_latency_profile.py](file:///c:/Production%20level%20projects/PIIS/scripts/benchmark_latency_profile.py) across 50 measured repetitions following 10 warm-up cycles.

- **Operating System**: Windows 11 Enterprise (x86_64)
- **Python Version**: 3.11.5
- **Pipeline Scope**: Full End-to-End (`Input Inspection` -> `Security Guard` -> `Hybrid Retrieval` -> `Evidence Registration` -> `Sufficiency Assessment` -> `Hypothesis Synthesis` -> `Recommendation Construction`).

### Latency Distribution

| Metric | Latency (ms) | Production SLA Requirement | Status |
| :--- | :---: | :---: | :---: |
| **P50 (Median)** | **14.99 ms** | < 100.0 ms | **PASS** |
| **P90** | **17.87 ms** | < 150.0 ms | **PASS** |
| **P95** | **18.57 ms** | < 200.0 ms | **PASS** |
| **P99** | **19.19 ms** | < 300.0 ms | **PASS** |
| **Mean ± Std** | **15.16 ± 1.70 ms** | - | **PASS** |
| **Min / Max** | **12.00 / 19.22 ms** | - | **PASS** |

**Artifact Exported**: [m5_2_latency_results.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_latency_results.json).

---

## 3. Test Suite Reconciliation

The entire unit test suite was executed via pytest:
- **Total Tests Collected**: 216 tests
- **Tests Passed**: 216 tests (100.0%)
- **Tests Failed / Skipped**: 0
- **Duration**: 59.71 seconds

### Module-by-Module Test Breakdown

| Test Suite File | Domain / Functionality | Test Count | Pass Rate |
| :--- | :--- | :---: | :---: |
| `test_m5_2_approval_auth.py` | Token verifiers, RBAC, key governance, JSONL ledger | 15 | **100.0%** |
| `test_m5_2_equipment_grounding.py`| Prose bleed, 3GPP compatibility, vendor isolation | 34 | **100.0%** |
| `test_m5_2_unicode_security.py` | European accents, CJK punctuation, combining marks | 17 | **100.0%** |
| `test_m5_approval.py` | Base approval workflow and state transitions | 7 | **100.0%** |
| `test_m5_1_approval_tamper.py` | Tamper-evidence and hash integrity | 11 | **100.0%** |
| `test_m5_1_equipment_grounding.py`| M5.1 equipment compatibility baseline | 7 | **100.0%** |
| `test_m5_1_unicode_security.py` | M5.1 Unicode security baseline | 9 | **100.0%** |
| `test_m5_investigation.py` | Investigation engine end-to-end integration | 4 | **100.0%** |
| `test_m5_schemas.py` | Pydantic contracts and epistemic validation | 6 | **100.0%** |
| `test_m5_adversarial.py` | Injection neutralization in investigation | 5 | **100.0%** |
| `test_retrieval_*.py` | M4 hybrid retrieval subsystem | 18 | **100.0%** |
| `test_anomaly_*.py`, `test_correlation.py`, `test_impact_*.py` | M3 network intelligence subsystem | 17 | **100.0%** |
| `test_classifier.py`, `test_severity.py`, `test_routing_*.py` | M2 fault categorization and routing | 20 | **100.0%** |
| `test_synthetic_generator.py`, `test_contracts.py`, etc. | Data generation and core contracts | 46 | **100.0%** |
| **Total Codebase Tests** | **All PIIS Milestones** | **216** | **100.0%** |

### Linter Verification
- **Tool**: Ruff 0.8.2
- **Command**: `python -m ruff check src tests scripts`
- **Result**: `All checks passed!` (0 errors).
