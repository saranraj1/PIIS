# Model Card: Fault Category Classifier

- **Model name/version:** `piis-fault-classifier-v1.0`
- **Intended task:** Multi-class classification of incoming telecom production incidents into 11 canonical fault categories at triage time.
- **Intended users:** Network Operations Centre (NOC) Tier-1 triage engineers and automated incident routing pipelines.
- **Prediction timestamp:** Incident creation / alarm triage time ($t_0$).

---

## Data & Provenance Breakdown

- **Training data sources:**
  - `data/synthetic/synthetic_incidents_m2.jsonl` (Seed 42 holdout train: 110 records; 5-Fold Stratified Group CV: 220 records).
- **Out-of-Distribution (OOD) Test Source:**
  - `data/processed/incidents/telecomts_incidents.jsonl` (93 real testbed records from AliMaatouk/TelecomTS).
- **Provenance breakdown:**
  - Synthetic training: 100% `SYNTHETIC` (PIIS-TelcoBench-Synthetic S00–S10).
  - OOD Testbed: 100% `PUBLIC_REAL` (derived from testbed RF jamming experiments).
- **Excluded/leakage-prone fields (Strict Quarantine via `PredictionTimeFeatureContract`):**
  - `resolution_summary`
  - `resolved_at`
  - `root_cause_confirmed`
  - `actual_resolution_steps`
  - `post_incident_telemetry`
  - `confirmed_root_cause`
  - `troubleshooting_tickets`

---

## Split Methodology

- **5-Fold Stratified Group Cross-Validation:** Disjoint groups partitioned by `split_group_id` (`f"{fam}-seed-{seed}"`), preventing sample leakage across folds.
- **Independent Seed Holdout:** Seed 42 instances strictly used for training; Seed 101 instances strictly used for holdout testing.
- **Out-of-Distribution Transfer Test:** 93 real testbed incidents from TelecomTS completely isolated from training.

---

## Model Baselines & Architectures

1. **Baseline 1 (Primary):** TF-IDF (1-2 ngrams, 500 features, sublinear TF) + Domain One-Hot + Log-Subscribers + Scaled Element Count $\rightarrow$ Multinomial Logistic Regression (`class_weight="balanced"`, `max_iter=1000`).
2. **Baseline 2 (Non-linear):** Same feature extraction $\rightarrow$ Balanced Random Forest Classifier (`n_estimators=100`).

---

## Evaluation Metrics

### 5-Fold Stratified Group Cross-Validation
| Metric | Logistic Regression | Random Forest |
| :--- | :--- | :--- |
| **Accuracy (mean $\pm$ std)** | 1.0000 $\pm$ 0.0000 | 1.0000 $\pm$ 0.0000 |
| **Macro-F1 (mean $\pm$ std)** | 1.0000 $\pm$ 0.0000 | 1.0000 $\pm$ 0.0000 |
| **Weighted-F1 (mean $\pm$ std)**| 1.0000 $\pm$ 0.0000 | 1.0000 $\pm$ 0.0000 |

### Independent Seed Holdout (Seed 42 $\rightarrow$ Seed 101, 110 Test Samples)
| Metric | Logistic Regression | Random Forest |
| :--- | :--- | :--- |
| **Test Accuracy** | 1.0000 | 1.0000 |
| **Macro-F1** | 1.0000 | 1.0000 |
| **Weighted-F1** | 1.0000 | 1.0000 |
| **Mean Brier Score** | 0.0046 | 0.0000 |

### Per-Class Holdout Metrics (Logistic Regression)
| Class Label | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `base_station_outage` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `cell_congestion` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `configuration_regression` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `dns_service_failure` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `handover_failure` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `nominal_operation` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `ran_signal_degradation` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `session_establishment_failure`| 1.0000 | 1.0000 | 1.0000 | 10 |
| `subscriber_authentication_failure`| 1.0000 | 1.0000 | 1.0000 | 10 |
| `transport_link_failure` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `user_plane_degradation` | 1.0000 | 1.0000 | 1.0000 | 10 |

---

## Out-of-Distribution (OOD) Behavior on Real Testbed (TelecomTS)

- **Input:** 93 real testbed incidents documenting RF jamming interference.
- **Random Forest Prediction:** 100% (93/93) classified as `ran_signal_degradation`.
  - *Analysis:* Perfectly captured the physical RAN domain and signal degradation symptoms (high BLER, modulation drops) without having seen TelecomTS training data.
- **Logistic Regression Prediction:** 100% (93/93) classified as `nominal_operation`.
  - *Analysis:* Linear decision boundary was dominated by the absence of synthetic keywords, falling back to the negative control class. Random Forest exhibited far superior out-of-distribution transfer capability.

---

## Limitations & Failure Modes

1. **Synthetic-to-Real Domain Gap:** Models trained on controlled synthetic scenarios have high confidence on structured wording but require fine-tuning or domain adaptation when faced with unstructured operator notes.
2. **Lexical Drift:** If monitoring systems alter alarm message templates, TF-IDF n-grams may drop in mutual information.
3. **Multi-fault Incidents:** Currently models assume single primary fault category per incident.

---

## Governance & Human Oversight

- **Human Oversight:** Predictions serve as decision support in NOC triage dashboards; no automated destructive actions are taken without human confirmation.
- **Prohibited Uses:** Autonomous cell shutdown, unvalidated configuration deployment, or safety-critical emergency service override without human approval.
- **Owner and Review Date:** PIIS Machine Learning Team, reviewed 2026-10-31.
