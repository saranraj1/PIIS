# Milestone 3 — Independent Verification Gate Audit Report

**Audit Authority:** Independent Telecom ML Systems Auditor & Technical Gate Auditor  
**Specialization:** Online Anomaly Detection, Temporal Data Leakage, Alarm Correlation, Graph Impact Analysis & Evaluation Methodology  
**Target:** PIIS Milestone 3 (Network Intelligence) Implementation & Metrics  
**Date:** 2026-10-31  
**Audit Verdict:** **ACCEPTED WITH LIMITATIONS**  

---

## 1. Executive Summary & Verdict

Milestone 3 (Network Intelligence) of the Production Incident Intelligence System (PIIS) was audited against operational realism, temporal causality, adversarial alarm scenarios, and topological impact validity.

### Final Verdict: ACCEPTED WITH LIMITATIONS
Milestone 3 delivers functional, tested, and mathematically rigorous network intelligence primitives across telemetry anomaly detection, temporal alarm correlation, and topological blast radius analysis. The test suite passes 100% (61/61 tests), linter is clean (0 errors), and strict provenance is maintained.

However, independent adversarial auditing revealed **two implementation defects** and **two operational limitations** that must be recorded in the defect register and carried forward as explicit boundary constraints before proceeding to Milestone 4 (Historical Retrieval & Hybrid RAG):

1. **Defect DEF-M3-001 (Reporting / Metric Inaccuracy - LOW):** The reported ROC-AUC of $0.7291$ for the hybrid pipeline was an erroneous copy-paste of the component Isolation Forest score. Independent re-scoring of the continuous fused score array reveals the true hybrid ROC-AUC is **$0.8051$** ($+0.0760$) and PR-AUC is **$0.2423$**.
2. **Defect DEF-M3-002 (Causal Lookahead Leakage in Conditioning - HIGH):** `TelemetryAnomalyPipeline._denoise_and_impute` uses a centered rolling window (`center=True`) and backward fill (`.bfill()`), which leaks observations from $t+1$ into the cleaning of observation $t$. An adversarial causal mutation test proved that changing future data altered past anomaly predictions.
3. **Limitation LIM-M3-001 (Semantic Alarm Blindness in Correlation):** The correlation engine clusters events based on temporal proximity, graph distance, and domain pairs, but does not inspect alarm semantics. Simultaneous, independent faults on the same base station or adjacent cells (e.g. antenna VSWR vs BGP license expiry) result in a **$100\%$ False Merge Rate**.
4. **Limitation LIM-M3-002 (Directional Asymmetry in Impact Traversal):** Because `TelecomTopologyGraph` represents adjacency edges as undirected, neighbor traversal propagates blast radius both downstream (subscribers/cells) and upstream (parent baseband and transport switches), causing an overestimation of inferred blast radius on leaf node failures.

---

## 2. Inventory of Inspected Files and Functions

| Module / File Path | Functions / Classes Inspected | Audit Role |
| :--- | :--- | :--- |
| [`src/piis/anomaly/models.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/anomaly/models.py) | `TelemetryAnomaly`, `MetricViolation`, `AnomalySeverity` | Data contracts & schemas |
| [`src/piis/anomaly/statistical.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/anomaly/statistical.py) | `StatisticalThresholdDetector.update_and_evaluate`, `detect_batch` | Online EWMA & asymmetric Z-score |
| [`src/piis/anomaly/isolation_forest.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/anomaly/isolation_forest.py) | `IsolationForestDetector.fit`, `score`, `_prepare_feature_matrix` | Unsupervised multivariate ML scoring |
| [`src/piis/anomaly/pipeline.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/anomaly/pipeline.py) | `TelemetryAnomalyPipeline.process_dataframe`, `_denoise_and_impute` | Conditioning, denoising, score fusion |
| [`src/piis/correlation/models.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/correlation/models.py) | `CorrelatedIncidentCluster`, `CorrelationRationale` | Correlation contracts & rationales |
| [`src/piis/correlation/topology.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/correlation/topology.py) | `TelecomTopologyGraph.shortest_path_distance`, `get_k_hop_neighbors` | BFS graph traversal & adjacency |
| [`src/piis/correlation/engine.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/correlation/engine.py) | `TemporalAlarmCorrelator.correlate`, `compute_pairwise_affinity` | Multi-kernel affinity & clustering |
| [`src/piis/impact/models.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/impact/models.py) | `ImpactAssessment` | Blast radius data contract |
| [`src/piis/impact/analyzer.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/impact/analyzer.py) | `NetworkImpactAnalyzer.assess_impact`, `assess_batch` | Blast radius calculation & risk scoring |
| [`scripts/evaluate_anomaly_detection.py`](file:///c:/Production%20level%20projects/PIIS/scripts/evaluate_anomaly_detection.py) | `evaluate_telecomts`, `main` | Evaluation pipeline & scoring paths |
| [`scripts/evaluate_correlation.py`](file:///c:/Production%20level%20projects/PIIS/scripts/evaluate_correlation.py) | `generate_benchmark_scenarios`, `evaluate_correlation` | Baseline alarm correlation test harness |
| [`scripts/evaluate_impact_analysis.py`](file:///c:/Production%20level%20projects/PIIS/scripts/evaluate_impact_analysis.py) | `evaluate_impact_analysis` | Baseline impact analysis test harness |
| [`scripts/audit_m3_adversarial.py`](file:///c:/Production%20level%20projects/PIIS/scripts/audit_m3_adversarial.py) | `audit_anomaly_detection`, `audit_correlation_scenarios`, `audit_network_impact` | Independent adversarial audit harness |
| [`artifacts/m3_metrics/*.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m3_metrics) | Machine-readable metrics artifacts | Historical evidence files |

---

## 3. Anomaly Detection Forensic Audit

### 3.1. Denominator & Metric Reconciliation (Finding AUD-M3-001)
The apparent discrepancy between 5,000 observations and 500 timesteps was audited and reconciled:
- **Observation-Level ($N = 5,000$):** 10 parallel radio/MAC KPIs sampled at 10 Hz across 500 time slices.
- **Timestep / Window-Level ($N = 500$):** The operational decision point in PIIS evaluates all KPIs arriving in time slice $t$.
- **Ground Truth ($Y = 1$):** 40 contiguous timesteps ($t = 330 \dots 369$) during active RF jamming.
- **Ground Truth ($Y = 0$):** 460 nominal operating timesteps (330 pre-attack, 130 post-attack).

**Exact Contingency Table:**
- **True Positives (TP):** $25$ timesteps
- **False Positives (FP):** $73$ timesteps ($69$ in pre-attack nominal phase, $4$ in post-attack recovery)
- **False Negatives (FN):** $15$ timesteps
- **True Negatives (TN):** $387$ timesteps
- **Timestep Precision:** $\frac{TP}{TP + FP} = \frac{25}{25 + 73} = \frac{25}{98} = \mathbf{25.51\%}$
- **Timestep Recall:** $\frac{TP}{TP + FN} = \frac{25}{25 + 15} = \frac{25}{40} = \mathbf{62.50\%}$
- **Nominal False Alarm Rate (FAR):** $\frac{FP_{\text{pre-onset}}}{N_{\text{pre-onset}}} = \frac{69}{330} = \mathbf{20.91\%}$
- **Detection Delay:** **0 timesteps** (triggered at exact attack onset $t = 330$, `2025-01-01T00:00:33.000Z`).

### 3.2. ROC-AUC Investigation & Defect DEF-M3-001
In `M3_COMPLETION_REPORT.md`, the hybrid pipeline and Isolation Forest were both listed with an identical ROC-AUC of $0.7291$.
- **Audit Investigation:** Inspection of `scripts/evaluate_anomaly_detection.py` revealed that `roc_auc_score` was computed once on line 48 using `if_scores` ($0.7291$). The evaluation function never calculated the ROC-AUC on the fused score array $s_{\text{fused}} = \max(s_{\text{stat}}, s_{\text{IF}})$.
- **Empirical Recomputation:** Evaluating the actual continuous fused score array against the ground-truth binary label yields:
  - Isolation Forest ROC-AUC: **$0.7291$** (PR-AUC: $0.1793$)
  - Statistical Dynamic EWMA ROC-AUC: **$0.7474$** (PR-AUC: $0.2172$)
  - **True Hybrid Ensemble ROC-AUC:** **$0.8051$** (PR-AUC: **$0.2423$**)
- **Verdict:** Defect confirmed. The pipeline was erroneously reported as matching Isolation Forest, when in fact the fused ensemble outperforms both components.

### 3.3. Causal Online Evaluation & Defect DEF-M3-002 (Lookahead Leakage)
A strict causal test was conducted to verify whether prediction at timestamp $t$ depends strictly on $x_{\le t}$.
- **Mechanisms of Leakage:**
  1. `pipeline._denoise_and_impute` line 59: `med = group["metric_value"].rolling(3, center=True, min_periods=1).median()`. The `center=True` parameter on window 3 computes `median(x_{t-1}, x_t, x_{t+1})`, directly referencing future observation $x_{t+1}$.
  2. Line 56: `group["metric_value"].ffill(limit=3).bfill(limit=3)`. The `.bfill()` propagates values from future timesteps into missing past timesteps.
- **Empirical Stress Test:** We held telemetry constant for $t \le 340$ and mutated all future data ($t > 340$) to extreme outliers. The centered rolling median caused anomaly predictions at earlier timestamps ($t \le 340$) to flip, violating temporal invariance.
- **Verdict:** Defect DEF-M3-002 confirmed. Denoising must be converted to non-centered rolling filters (`center=False`) and forward-only imputation before live deployment.

---

## 4. Correlation Engine Adversarial Audit

The M3 completion report cited $1.0000$ (100%) Pairwise Precision and Recall on a 13-alarm scenario. The independent audit executed **10 adversarial stress scenarios** to determine general operational reliability:

| Adversarial Scenario | Alarms | Expected Clusters | Actual Clusters | Pairwise F1 | False Merges | Missed Corrs | Operational Audit Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S1: Same site, simultaneous unrelated alarms** | 2 | 2 | 1 | **0.0000** | 1 | 0 | **FAIL:** Conflates independent hardware and software faults on same node (100% false merge). |
| **S2: Same domain, unrelated causes on adjacent cells** | 2 | 2 | 1 | **0.0000** | 1 | 0 | **FAIL:** Conflates independent cell faults on same site (100% false merge). |
| **S3: Multi-domain cascading failure** | 3 | 1 | 1 | **1.0000** | 0 | 0 | **PASS:** Accurately correlates Transport $\to$ RAN $\to$ Core cascade. |
| **S4: Missing intermediate alarm** | 2 | 1 | 1 | **1.0000** | 0 | 0 | **PASS:** 2-hop topology link maintains valid correlation without intermediate gNB alarm. |
| **S5: Out-of-order alarm arrival** | 2 | 1 | 1 | **1.0000** | 0 | 0 | **PASS:** Pre-sorting by timestamp ensures robust correlation despite packet arrival jitter. |
| **S6: Duplicate alarm retransmissions** | 2 | 1 | 1 | **1.0000** | 0 | 0 | **PASS:** Successfully deduplicates elements and groups duplicate retransmissions. |
| **S7: Transitive shared node merge** | 3 | 2 | 1 | **0.5000** | 2 | 0 | **PARTIAL:** Connected components links independent incidents sharing an intermediate gNB. |
| **S8: Unknown network element** | 2 | 2 | 2 | **1.0000** | 0 | 0 | **PASS:** Unknown router forms isolated cluster without crashing. |
| **S9: Incomplete topology graph** | 3 | 3 | 3 | N/A | 0 | 2 | **PARTIAL:** Missing edges suppress false correlations but miss genuine physical cascades. |
| **S10: Clock drift window timeout** | 2 | 1 | 2 | **0.0000** | 0 | 1 | **FAIL:** Device NTP drift $> 15$ min causes split clusters (missed correlation). |

### Core Vulnerabilities Identified
1. **Semantic Blindness:** The engine does not inspect alarm text or probable cause codes. Any two alarms occurring within 15 minutes on the same node or adjacent cells are merged unconditionally.
2. **Evaluation Overfitting:** The 13-alarm scenario used in M3 was hand-crafted such that all co-occurring alarms on the same site belonged to the same incident. It cannot be cited as evidence of production immunity to false merges.

---

## 5. Network Impact Analysis Audit

### 5.1. Directional Asymmetry Defect (Defect DEF-M3-003)
- **Root Cause:** In `src/piis/correlation/topology.py`, graph edges are undirected (`bidirectional=True`). When `NetworkImpactAnalyzer` queries 1-hop neighbors via `get_k_hop_neighbors`, it traverses bidirectional links equally:
  - If leaf antenna `CELL-101` suffers an impedance mismatch (VSWR), the engine infers that parent base station `GNB-TESTBED-5G-01` and upstream switch `SW-ACCESS-SITE01` are affected.
  - This artificially inflates the blast radius and spreads the reported domain impact from `['RAN']` to `['RAN', 'TRANSPORT']`.
- **Recommendation:** Implement a directed dependency DAG: blast radius must traverse **downstream** (toward subscribers/cells), while root-cause analysis traverses **upstream** (toward transmission/core).

### 5.2. Zero-Fabrication Subscriber Audit (Finding AUD-M3-003 — PASS)
The subscriber quantification logic was audited against data fabrication:
- When elements have registered nominal capacity in topology metadata, capacity is summed and clearly labeled: `"Aggregated nominal capacity across N elements from registered topology metadata. Not dynamically observed from active UE counters."`
- When unmapped or unknown elements appear without metadata, `estimated_affected_subscribers` evaluates to `None` with zero hallucinations.

---

## 6. Provenance & Epistemic Audit (PASS)

- **Source Traceability:** Every `TelemetryAnomaly` retains `source_observation_ids` pointing to specific raw JSONL records. Every `CorrelatedIncidentCluster` retains `direct_alarm_ids`.
- **Epistemic Classification:**
  - Anomaly detections: strictly `STATISTICAL_INFERENCE`.
  - Correlation clusters: strictly `HYPOTHESIS`.
  - Impact assessments: strictly `DERIVED_ESTIMATE`.
- **No Causal Overreach:** Proposed root causes are explicitly qualified as hypotheses (`Candidate root event: ...`) without asserting definitive unverified causation.

---

## 7. Defect Register

| Defect ID | Severity | Category | Description | Empirical Evidence | Remediation Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-M3-001** | LOW | Reporting | Erroneous reporting of Hybrid Ensemble ROC-AUC ($0.7291$ reported vs $0.8051$ actual). | `evaluate_telecomts` copied Isolation Forest ROC-AUC without scoring continuous fused scores. | Correct documentation to reflect true $0.8051$ ROC-AUC. |
| **DEF-M3-002** | HIGH | Algorithmic | Causal lookahead leakage in telemetry conditioning via `center=True` rolling median and `.bfill()`. | Mutating future observations at $t > 340$ altered anomaly flags at $t \le 340$. | Replace centered rolling windows with causal rolling median (`center=False`) and forward-only fill. |
| **DEF-M3-003** | MEDIUM | Architectural | Directional blast radius overestimation due to undirected graph neighbor traversal. | Leaf cell VSWR alarm infers failure of parent gNodeB and upstream transport switch. | Convert topology to directed dependency DAG for downstream blast radius traversal. |
| **DEF-M3-004** | MEDIUM | Algorithmic | Semantic blindness in alarm correlation causing false merges of concurrent unrelated same-site faults. | Scenario 1 & 2 produced 100% false merge rate on independent simultaneous faults. | Incorporate semantic alarm code compatibility matrix in Milestone 5/6. |

---

## 8. Final Audit Verdict & Progression Gate

### Verdict: ACCEPTED WITH LIMITATIONS

Milestone 3 is accepted with the explicit condition that its deliverables and limitations are bounded as follows:

1. **Defect Remediation Status:**
   - Defect DEF-M3-001 (ROC-AUC reporting) is resolved and documented herein.
   - Defect DEF-M3-002 (Causal conditioning leakage) is documented in the defect register. Because M4 is purely focused on **Historical Retrieval & Hybrid RAG** (offline corpus indexing and retrieval), DEF-M3-002 does not block M4. It is scheduled for remediation prior to real-time integration in M6.
2. **Boundary Enforcement for Milestone 4:**
   - Milestone 4 must remain strictly focused on **retrieval**: chunking SOP runbooks, bi-encoder embeddings, BM25 indexing, and domain-filtered retrieval.
   - Milestone 4 must **NOT** attempt autonomous incident resolution or unverified automated network changes.

**Recommendation:** **AUTHORIZE PROGRESSION TO MILESTONE 4 (Historical Retrieval & Hybrid RAG).**
