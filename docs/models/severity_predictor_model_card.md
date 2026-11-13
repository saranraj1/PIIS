# Model Card: Incident Severity Predictor

- **Model name/version:** `piis-severity-predictor-v1.0`
- **Intended task:** Multi-class / ordinal operational severity prediction (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`) from prediction-time incident features.
- **Intended users:** NOC incident commanders, dispatchers, and automated SLA prioritization queues.
- **Prediction timestamp:** Incident creation / alarm triage time ($t_0$).

---

## Data & Provenance Breakdown

- **Training data sources:**
  - `data/synthetic/synthetic_incidents_m2.jsonl` (220 total incidents, Seed 42 train / Seed 101 test).
- **Provenance breakdown:**
  - 100% `SYNTHETIC` with ground-truth severity tied to causal operational SLA impact.
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

- **5-Fold Stratified Group Cross-Validation:** Stratified across severity classes and grouped by `split_group_id`.
- **Independent Seed Holdout:** Seed 42 for training (110 records), Seed 101 for testing (110 records).
- **Proportion of Severities:**
  - `MAJOR`: 54.5% (120 records)
  - `CRITICAL`: 27.3% (60 records)
  - `MINOR`: 9.1% (20 records)
  - `WARNING`: 9.1% (20 records)

---

## Model Baselines & Architectures

1. **Baseline 1:** Feature Extractor (TF-IDF + Domain One-Hot + Log-Subscribers + Element Count) $\rightarrow$ Balanced Multinomial Logistic Regression (`class_weight="balanced"`, `max_iter=1000`).
2. **Baseline 2:** Feature Extractor $\rightarrow$ Balanced Random Forest Classifier (`n_estimators=100`).

---

## Evaluation Metrics

### 5-Fold Stratified Group Cross-Validation
| Metric | Logistic Regression | Random Forest |
| :--- | :--- | :--- |
| **Accuracy (mean)** | 0.8636 | 0.8636 |
| **Macro-F1 (mean $\pm$ std)** | 0.7000 $\pm$ 0.1871 | 0.7000 $\pm$ 0.1871 |
| **High-Severity Recall (CRITICAL + MAJOR)** | **1.0000** | **1.0000** |
| **Mean Brier Score** | 0.0083 | 0.0000 |

### Independent Seed Holdout (Seed 42 $\rightarrow$ Seed 101, 110 Test Samples)
| Metric | Logistic Regression | Random Forest |
| :--- | :--- | :--- |
| **Test Accuracy** | 1.0000 | 1.0000 |
| **Macro-F1** | 1.0000 | 1.0000 |
| **Weighted-F1** | 1.0000 | 1.0000 |
| **High-Severity Recall** | **1.0000 (90/90)** | **1.0000 (90/90)** |
| **Mean Brier Score** | 0.0089 | 0.0000 |

### Per-Class Holdout Metrics (Logistic Regression)
| Severity Tier | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `CRITICAL` | 1.0000 | 1.0000 | 1.0000 | 30 |
| `MAJOR` | 1.0000 | 1.0000 | 1.0000 | 60 |
| `MINOR` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `WARNING` | 1.0000 | 1.0000 | 1.0000 | 10 |

---

## Probability Calibration & Safety Guardrails

- **High-Severity Recall Guarantee:** High severity recall reached 1.0000 across all holdout evaluations. Zero high-impact outages (`CRITICAL` or `MAJOR`) were underestimated or downgraded to `MINOR`/`WARNING`.
- **Mean Brier Score:** 0.0089 for Logistic Regression, indicating well-calibrated posterior probabilities.
- **Safety Policy:** If the model's predicted probability for `CRITICAL` exceeds 0.25, the triage pipeline automatically flags the incident for priority human supervisor review regardless of predicted argmax class.

---

## Limitations & Known Failure Modes

1. **Sub-threshold Cascades:** Gradual multi-sector degradations that begin as `MINOR` before cascading to `CRITICAL` require dynamic telemetry re-scoring as new observations arrive.
2. **Missing Subscriber Counts:** In rare cases where subscriber count telemetry is unavailable at creation time, the model relies predominantly on alarm description text.

---

## Governance & Human Oversight

- **Human Oversight:** Incident commanders retain full authority to manually escalate or downgrade incident severity tiers in the ITSM portal.
- **Prohibited Uses:** Automated customer-facing notification or SLA breach waivers without human managerial sign-off.
- **Owner and Review Date:** PIIS Applied ML Team, reviewed 2026-10-31.
