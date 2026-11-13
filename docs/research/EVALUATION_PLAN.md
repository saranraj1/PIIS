# Evaluation plan

## Evaluation tracks
1. Public-real source holdout.
2. Synthetic scenario-family holdout.
3. Cross-source transfer.
4. Temporal holdout where timestamps support it.
5. Human-reviewed recommendation evaluation.

## Metrics
- Classification: macro-F1, per-class precision/recall, confusion matrix.
- Routing: macro-F1, L2 escalation recall, false escalation rate, abstention coverage.
- Severity: macro-F1, critical/major recall, calibration/Brier score.
- Anomaly: PR-AUC, event-level recall/precision, detection delay.
- Correlation: pairwise precision/recall and cluster metrics.
- Retrieval: Recall@K, MRR, nDCG@K.
- Recommendations: blinded expert rating for correctness, evidence sufficiency, safety and usefulness.
- System: p50/p95 latency, throughput, error rate, retrieval availability.

## Leakage checklist
- Exclude resolution summary and confirmed root cause from ticket-time routing.
- Exclude telemetry recorded after prediction timestamp.
- Group repeated samples from one incident/scenario together.
- Check near-duplicate ticket text across splits.
- Fit vectorizers/scalers only on training data.
- Do not tune on final test set.

## Reporting
Report sample counts, class support, confidence intervals where appropriate, data provenance, split method, model version and limitations. Never report synthetic-only results as field performance.
