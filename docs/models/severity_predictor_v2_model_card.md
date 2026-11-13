# Model Card: Incident Severity Predictor v2

- **Model name/version:** `piis-severity-predictor-v2.0`
- **Intended task:** Multi-class operational severity estimation (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`) from prediction-time incident features and operational context indicators.
- **Intended users:** NOC dispatchers and automated SLA prioritization queues.
- **Prediction timestamp:** Incident creation / alarm triage time ($t_0$).

---

## Data & Provenance Breakdown

- **Benchmark Dataset:** `PIIS-TelcoBench-v2` (`data/synthetic/synthetic_incidents_v2_combined.jsonl`).
- **Severity Independence:** Severity is computed via a multi-attribute operational risk calculus (subscriber scale, service criticality, topological redundancy, and operational timing). Every fault category exhibits multiple severity tiers.
- **Training Set (240 records):** Moderate causal configurations (C1, C2).
- **Holdout Test Set (120 records):** High-impact / extreme causal configuration C3 (emergency PSAP, high blast radius, single point of failure).
- **Exact Train-Test Duplicate Text:** **0.00%** ($0 / 120$).

---

## Evaluation Across Generalization Tracks (Track E)

| Model / Baseline | Test Accuracy | Macro-F1 | Mean Brier Score | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Operational Rule Baseline** | **0.8333 (83.3%)** | 0.4545 | 0.0450 | Rule heuristic checking subscriber count and emergency SLA tags |
| **Multinomial Logistic Regression** | 0.1667 (16.7%) | 0.3333 | 0.2773 | ML extrapolation on unseen high-severity ranges |
| **Balanced Random Forest** | 0.0000 (0.0%) | 0.0000 | 0.1899 | Fails to extrapolate beyond seen training subscriber ranges |
| **Majority Class Baseline** | 0.0000 (0.0%) | 0.0000 | N/A | Predicts training majority (`MAJOR`), while C3 is predominantly `CRITICAL` |

*Empirical Finding:* Under extreme causal shift (training on moderate suburban loads C1/C2 and testing on emergency/SPOF outages C3), pure ML models struggle with range extrapolation. The simple **Operational Rule Baseline** achieves **$83.3\%$ accuracy**, proving that production severity prediction must employ a hybrid rule-assisted architecture.

---

## Safety Guardrails & Recommendations

- **Hybrid Severity Ensemble:** Always enforce hard operational override rules:
  - If `affected_subscribers > 800` OR `EMERGENCY_PSAP` slice $\rightarrow$ Force minimum severity of `CRITICAL`.
  - If `single_point_of_failure` with $>200$ subscribers $\rightarrow$ Force minimum severity of `MAJOR`.
- **Confidence Abstention:** If predicted posterior probability for the top severity tier is below $0.40$, default to supervisor human review.

---

## Governance & Human Oversight

- **Human Authority:** Incident commanders retain unilateral authority to adjust severity levels.
- **Review Date:** 2026-10-31.
