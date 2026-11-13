# Milestone 2 — Adversarial ML Validation Audit Report

**Audit Authority:** Independent ML Research Auditor & Scientific Review Lead  
**Specialization:** Dataset Leakage, Synthetic Benchmark Validity, Distribution Shift, and Statistical Methodology  
**Evaluation Target:** PIIS Milestone 2 Machine Learning Intelligence Baselines  
**Date:** 2026-10-31  
**Audit Verdict:** **NOT VALIDATED** (Performance claims are materially compromised by synthetic template memorization, cross-split text duplication, and circular routing evaluation)  

---

## 1. Executive Summary

Milestone 2 reported near-perfect performance across all evaluation dimensions:
- Fault Category Classification: **1.0000 Macro-F1**, **1.0000 Test Accuracy**
- Severity Prediction: **1.0000 Macro-F1**, **1.0000 High-Severity Recall**, **0.0089 Brier Score**
- Deterministic Support Routing: **1.0000 Macro-F1**, **0.0% False Escalation**, **100% Abstention Accuracy**
- Real Testbed OOD Transfer: **93/93** TelecomTS jamming incidents predicted as `ran_signal_degradation` by Random Forest.

This independent adversarial audit investigated whether these scores demonstrate genuine predictive intelligence or merely reconstruct trivial artifacts of the synthetic data generation and evaluation pipelines.

### Primary Audit Findings
1. **100.00% Verbatim Cross-Split Text Duplication:** The independent seed holdout (Seed 42 Train $\rightarrow$ Seed 101 Test) contained $110 / 110$ ($100\%$) verbatim duplicate incident titles and descriptions. The test set was an exact lexical clone of the training set.
2. **Severe Lexical Shortcuts (74.48% of vocabulary):** Out of 478 n-gram tokens, 356 tokens ($74.48\%$) appeared exclusively in a single scenario family with $100\%$ precision, allowing single-token lookup to achieve perfect scores.
3. **Catastrophic Generalization Failure on Unseen Families:** When evaluated on a genuine **Scenario-Family Holdout** (unseen scenario families), severity prediction accuracy collapsed from **$1.0000$ to $0.2850$ ($28.5\%$)**, worse than a trivial majority-class baseline ($54.55\%$).
4. **Tautological Support Routing Evaluation:** The routing evidence extractor contained a hardcoded shortcut inspecting `scenario_family_id`. When evaluated on realistic text evidence without this shortcut, policy routing accuracy collapsed from **$100.0\%$ to $45.5\%$**.
5. **TelecomTS OOD Transfer Was Not Measured Accuracy:** The true label `rf_jamming_interference` was not in the model's candidate label set (strict accuracy = $0.0\%$). Logistic Regression catastrophically classified $100\%$ ($93/93$) of real jamming incidents as `nominal_operation` (healthy traffic).

---

## 2. Stage 1 — Synthetic Generator Audit & Shortcut Analysis

### 2.1 Template Homogeneity Audit
Inspection of `src/piis/synthetic/generator.py` and the 220 records in `data/synthetic/synthetic_incidents_m2.jsonl` revealed extreme determinism:
- **Titles:** Exactly **1 unique title** per scenario family across all 20 variants and both seeds.
- **Descriptions:**
  - Families S05, S06, S07, S08, S09, S10: Exactly **1 unique description** across all 20 generated records.
  - Families S00, S01, S02, S03, S04: The description varied only by an arithmetic cell ID string (`GNB-CELL-{100+v}`). Because `v` ranged from 1 to 10 in both seed 42 and seed 101, the generated cell IDs were identical across seeds.
- **Attributes:** Each scenario family hardcoded a single static fault category, a single static severity tier, a single static support level, and a single static network domain.

```
Scenario Family S01 (RAN Signal Degradation):
   Title: "Severe downlink signal attenuation and elevated block error rate" [STATIC]
   Description: "Sector GNB-CELL-{100+v} reports progressive radio link degradation..."
   Fault Category: ran_signal_degradation [100% DETERMINISTIC]
   Severity: MAJOR [100% DETERMINISTIC]
   Support Level: L2 [100% DETERMINISTIC]
   Domain: RAN [100% DETERMINISTIC]
```

### 2.2 Feature-to-Label Shortcut Analysis
A vocabulary analysis of TF-IDF features ($1-2$ n-grams, stop-words removed) across the 220 synthetic benchmark records established:
- **Total Vocabulary Size:** 478 terms.
- **Single-Family Exclusive Shortcuts:** 356 terms ($74.48\%$).
- **Sample Direct Deterministic Shortcuts:**
  - S01: `attenuation`, `modulation`, `progressive`, `signal` $\rightarrow$ 100% precision for `ran_signal_degradation`
  - S02: `handover`, `boundary`, `frequency`, `preparation` $\rightarrow$ 100% precision for `handover_failure`
  - S03: `saturation`, `prb`, `delay`, `utilization` $\rightarrow$ 100% precision for `cell_congestion`
  - S04: `battery`, `unreachable`, `commercial power` $\rightarrow$ 100% precision for `base_station_outage`
  - S05: `ausf`, `5g aka`, `vector`, `register` $\rightarrow$ 100% precision for `subscriber_authentication_failure`
  - S06: `pdu`, `dnn`, `pool`, `exhaustion` $\rightarrow$ 100% precision for `session_establishment_failure`
  - S07: `dpdk`, `gtp-u`, `buffers`, `ring` $\rightarrow$ 100% precision for `user_plane_degradation`
  - S08: `crc`, `backhaul`, `optical`, `10ge` $\rightarrow$ 100% precision for `transport_link_failure`
  - S09: `dns`, `hostnames`, `resolver`, `query` $\rightarrow$ 100% precision for `dns_service_failure`
  - S10: `mtu`, `fragmentation`, `blackhole` $\rightarrow$ 100% precision for `configuration_regression`
  - S00: `nominal`, `diurnal`, `boundaries`, `routine` $\rightarrow$ 100% precision for `nominal_operation`

**Conclusion:** The classification baseline did not learn generalizable semantic relationships. It solved an exact-match keyword lookup table generated by the synthetic script.

---

## 3. Stage 2 — Split Integrity & Scenario-Family Holdout

### 3.1 Audit of Seed-Based Group Splitting
The M2 training pipeline implemented `StratifiedGroupKFold` using:
```python
groups = targets["split_group_id"].to_numpy() # e.g. "S01-seed-42", "S01-seed-101"
```
Because the group identifier included the random seed rather than the scenario family, instances of every scenario family were placed in both training and testing partitions.
- Cross-split text duplication audit:
  - Total test samples: 110
  - Samples with exact verbatim text match in training set: **110 / 110 (100.00%)**
- The holdout evaluation was in reality a **train-set memorization test**, not an independent generalization test.

### 3.2 Genuine Scenario-Family Holdout Experiment
To measure actual out-of-distribution generalization, an adversarial holdout experiment was executed where **entire scenario families were held out from training**.
A 5-Fold cross-validation was conducted over the 11 scenario families for Severity Prediction (holding out 2–3 unseen families in each fold):

| Evaluation Scheme | Test Accuracy | Macro-F1 | High-Severity Accuracy |
| :--- | :--- | :--- | :--- |
| **Original Seed Holdout (Duplicate Text)** | **1.0000** | **1.0000** | **1.0000** |
| **Scenario-Family Holdout (Unseen Families)**| **0.2850 $\pm$ 0.1934** | **0.1995 $\pm$ 0.1253**| **0.6333** |
| Fold 1 (Holdout S01, S04) | 0.2500 | 0.1818 | 0.6667 |
| Fold 2 (Holdout S02, S06) | 0.5000 | 0.3333 | 0.5000 |
| Fold 3 (Holdout S03, S07) | **0.0000** | **0.0000** | 0.5000 |
| Fold 4 (Holdout S05, S08) | 0.1750 | 0.1489 | 1.0000 |
| Fold 5 (Holdout S09, S10) | 0.5000 | 0.3333 | 0.5000 |

**Finding:** On unseen scenario families, model accuracy collapsed to **$28.5\%$**, and in Fold 3 dropped to **$0.0\%$**. This proves that the original $1.0000$ performance was an artifact of family-level keyword memorization.

---

## 4. Stage 3 — Negative Controls, Baselines & Modality Ablations

To isolate the source of predictive power, rigorous ablation tests were performed:

### 4.1 Summary of Ablation Results
| Experiment Condition | Accuracy | Macro-F1 | Finding & Interpretation |
| :--- | :--- | :--- | :--- |
| **M2 Full Multimodal Baseline** | **1.0000** | **1.0000** | Original reported baseline on seed holdout. |
| **Label Permutation Test (5 runs)** | **0.0873** | **0.0771** | Collapses to random chance ($1/11 = 0.0909$). Confirms pipeline has no static leak; scores depend on text-label binding. |
| **Text-Only (No domain, no subscribers)** | **1.0000** | **1.0000** | Text alone achieves 100% accuracy due to static title/description shortcuts. |
| **Title-Only (Description deleted)** | **1.0000** | **1.0000** | Title alone achieves 100% accuracy (11 static titles). |
| **Description-Only (Title deleted)** | **1.0000** | **1.0000** | Description alone achieves 100% accuracy. |
| **Metadata-Only (Text deleted entirely)** | **0.8000** | **0.7794** | Domain + subscriber count alone achieve 80% accuracy without reading a single word of text. |
| **Scenario Keyword Masking (29 tokens)** | **1.0000** | **1.0000** | Secondary correlated tokens maintain 100% accuracy due to total template uniformity. |
| **Dummy: Majority Class (Fault)** | **0.0909** | **0.0152** | Non-informative lower bound (11 balanced classes). |
| **Dummy: Majority Class (Severity)** | **0.5455** | **0.1765** | MAJOR class comprises 54.55% of synthetic dataset. |
| **Dummy: Uniform Random (Fault)** | **0.1364** | **0.1283** | Random guessing lower bound. |

**Key Takeaway:** The metadata-only ablation proves that even if text is completely deleted, the model achieves **$80\%$ accuracy** simply because subscriber impact ranges and network domains were deterministically tied to scenario families in the synthetic generator.

---

## 5. Stage 4 — Severity Prediction Audit

### 5.1 Mechanistic Determinism
In the synthetic generator:
$$\text{Severity} = f(\text{Scenario Family})$$
- `base_station_outage`, `dns_service_failure`, `subscriber_authentication_failure` $\rightarrow$ ALWAYS `CRITICAL`
- `ran_signal_degradation`, `handover_failure`, `session_establishment_failure`, `user_plane_degradation`, `transport_link_failure`, `configuration_regression` $\rightarrow$ ALWAYS `MAJOR`
- `cell_congestion` $\rightarrow$ ALWAYS `MINOR`
- `nominal_operation` $\rightarrow$ ALWAYS `WARNING`

Because the mapping is completely deterministic and injective, predicting severity in this dataset was not an operational severity assessment task; it was merely a coarse clustering of the 11 synthetic scenario families.

### 5.2 Real-World Operational Divergence
In live telecom NOC operations, severity is **never** a constant property of a fault category:
- A cell congestion incident during peak hours in an emergency zone is `CRITICAL`, while the same congestion on a rural site at 03:00 is `MINOR`.
- A transport link failure on a dual-homed optical ring with automatic protection switching is `MINOR`, while the same failure on a single-feed backhaul to an air traffic controller is `CRITICAL`.
The synthetic dataset fails to model operational context, blast radius, or service-level agreements (SLAs).

---

## 6. Stage 5 — Support-Level Routing Policy Audit

### 6.1 Discovery of Tautological Evaluation Logic
Inspection of [`scripts/evaluate_routing.py`](file:///c:/Production%20level%20projects/PIIS/scripts/evaluate_routing.py#L40-L75) revealed that the evidence extractor used to test the `PolicyEngine` contained explicit scenario family overrides:

```python
# Lines 40-75 of scripts/evaluate_routing.py:
is_negative = meta.get("negative_control", False) or fam == "S00"
known_issue = bool(has_runbook or ... or fam in ["S03", "S04", "S06", "S09", "S10"])
advanced = bool(... or fam in ["S01", "S02", "S05", "S07", "S08", "RF-JAMMING-01"])
```

The evaluation script read the synthetic generator's internal `scenario_family_id` to assign the boolean evidence flags, and then passed those flags to `PolicyEngine`, which simply checked the same flags.

### 6.2 Empirical Evaluation Without Circular Shortcuts
When `extract_routing_evidence` was re-evaluated using realistic text-based heuristics (extracting SOP indicators, diagnostic keywords, and symptom phrases without accessing `scenario_family_id`):
- Routing Accuracy dropped from **$100.0\%$ to $45.5\%$ ($100 / 220$)**.
- The reported $1.0000$ Macro-F1 was entirely an artifact of circular label injection.

---

## 7. Stage 6 — TelecomTS Out-of-Distribution (OOD) Audit

### 7.1 Absence of True Ground-Truth Overlap
Inspection of the 93 normalized TelecomTS records in `data/processed/incidents/telecomts_incidents.jsonl` revealed:
- Normalized Ground-Truth Label: `fault_category: "rf_jamming_interference"`
- Model Candidate Vocabulary: The 11 synthetic classes did NOT include `rf_jamming_interference`.
- Under strict multi-class classification scoring, the model's accuracy on TelecomTS was **$0.0000$ ($0 / 93$)**.

### 7.2 Post-Hoc Rationalization vs. Model Reality
- Random Forest predicted `ran_signal_degradation` for all 93 records. While qualitatively defensible as a related RAN failure, this was a post-hoc semantic relabeling rather than a formal validation of classification accuracy.
- **Catastrophic Failure of Logistic Regression:** Logistic Regression classified **$100\%$ ($93/93$)** of the TelecomTS jamming incidents as `nominal_operation` (the healthy negative control).
- If deployed in production, the primary linear baseline would have suppressed alarms and reported ongoing active RF jamming as normal network behavior.

---

## 8. Summary of Adversarial Validation Findings

```
========================================================================================
AUDIT DIMENSION              ORIGINAL CLAIM         AUDIT FINDING          VERDICT
========================================================================================
Cross-Split Isolation       Seed Holdout           100% Duplicate Text    COMPROMISED
Lexical Feature Integrity    Generalized NLP        74.5% Exclusive Keys   COMPROMISED
Severity Generalization     1.0000 Macro-F1        28.5% on Unseen Fams   NOT VALIDATED
Routing Policy Validity     100% Policy Accuracy   45.5% w/o Cheat Tag    NOT VALIDATED
OOD Predictive Accuracy     93/93 Transfer         0% Strict Accuracy     QUALITATIVE ONLY
========================================================================================
OVERALL AUDIT VERDICT: NOT VALIDATED
========================================================================================
```

---

## 9. Required Remediation & Engineering Roadmap for M3

Before proceeding to Milestone 3 (Historical Retrieval, Cross-Domain Correlation, and Hybrid RAG Intelligence), the following engineering remediations are required:

1. **Synthetic Generator Paraphrasing Engine:**
   - Implement dynamic prompt-based or multi-template linguistic diversity in `src/piis/synthetic/generator.py`.
   - Ensure every scenario family has at least 50 distinct syntactic and lexical descriptions.
   - Decouple subscriber count and severity from static generator functions.
2. **Mandatory Scenario-Family Holdout Protocol:**
   - Grouping in `StratifiedGroupKFold` must be performed strictly on `scenario_family_id`, never on `split_group_id` that shares family identity across seeds.
   - Formalize an unseen-family evaluation benchmark in `src/piis/classification/`.
3. **Decoupled NLP Routing Evidence Extractor:**
   - Remove all `scenario_family_id` branches from `extract_routing_evidence`.
   - Build a defensible entity-extraction / rule-matching parser that extracts SOPs and diagnostic needs strictly from raw text and alarms.
4. **Independent OOD Taxonomy Alignment:**
   - Map external real datasets (e.g. TelecomTS, LCORE-D) into a formal hierarchical ontology (e.g. `RAN -> Interference -> Jamming`) before evaluation, rather than post-hoc qualitative matching.
5. **Preservation of Audit Artifacts:**
   - Machine-readable audit results have been preserved in [`artifacts/m2_metrics/adversarial_validation_results.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m2_metrics/adversarial_validation_results.json).
   - Original M2 metrics remain preserved as historical baseline records.
