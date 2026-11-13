# Product Requirements Document (PRD)
## PIIS — Telecom Production Incident Intelligence System

- **Version:** 0.1
- **Status:** Draft for engineering baseline
- **Audience:** Product, telecom operations, data science, ML engineering, platform/security
- **Primary users:** NOC analysts, L1 support engineers, L2 support engineers, incident managers

## 1. Product vision

Help telecom operations teams understand production incidents faster and more consistently by combining ticket intelligence, network telemetry, alarm correlation, historical incident retrieval and evidence-grounded recommendations.

PIIS is an assistive decision-support layer over existing operational workflows. It does not replace an ITSM/NMS/OSS platform and does not require migration.

## 2. Problem statement

Telecom operations generate heterogeneous tickets, alarms, telemetry and change records. Engineers may need to correlate multiple symptoms, determine impact, identify prior incidents, choose the correct support path and communicate an investigation plan. Manual triage can be inconsistent, slow and difficult to audit.

## 3. Goals

1. Normalize incident records from heterogeneous sources.
2. Classify incidents into configurable telecom domains and fault categories.
3. Estimate severity/impact using available evidence and operator policy.
4. Recommend L1/L2/L3 or human-review routing with rationale.
5. Correlate related tickets, alarms and telemetry observations.
6. Retrieve similar historical incidents and approved knowledge.
7. Generate investigation recommendations grounded in cited evidence.
8. Record human decisions, overrides and confirmed outcomes for evaluation.

## 4. Non-goals for initial release

- Autonomous configuration changes or network-element commands.
- Autonomous ticket closure or customer communication.
- Replacing ServiceNow, Jira Service Management, OSS, NMS or SIEM.
- Claiming definitive root cause from ticket text alone.
- Guaranteeing SLA outcomes.
- Training on private operator data without authorization.
- Treating synthetic data as proof of production effectiveness.

## 5. Personas and jobs-to-be-done

### NOC / L1 analyst
Needs a concise incident summary, known-issue lookup, safe first-line checks and clear escalation rationale.

### L2 network engineer
Needs correlated alarms/telemetry, relevant historical cases, competing fault hypotheses and a prioritized investigation plan.

### Incident manager
Needs impact overview, incident grouping, timeline, severity rationale, SLA risk indicators and audit history.

### Knowledge/data steward
Needs source provenance, annotation review, data quality reports and controlled knowledge updates.

## 6. Core user journeys

1. **Ticket triage:** ingest ticket → normalize → classify → estimate severity → recommend support tier → human accepts/overrides.
2. **Incident investigation:** select incident → view correlated alarms/telemetry → retrieve similar cases → inspect evidence → review ranked hypotheses.
3. **L1 assistance:** retrieve approved runbook → present safe diagnostic checklist → capture results → recommend escalation if unresolved.
4. **L2 assistance:** correlate cross-domain evidence → rank possible causes → propose next checks → record engineer feedback.
5. **Incident review:** inspect timeline, decisions, evidence references, resolution and audit log.

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Import CSV/JSON/JSONL ticket and telemetry files | P0 |
| FR-02 | Validate records against versioned schemas | P0 |
| FR-03 | Preserve source IDs and provenance | P0 |
| FR-04 | Produce data quality profiles | P0 |
| FR-05 | Classify network domain and fault category | P1 |
| FR-06 | Recommend severity with evidence and policy | P1 |
| FR-07 | Recommend L1/L2/L3 or human review | P1 |
| FR-08 | Retrieve similar incidents with source references | P1 |
| FR-09 | Correlate related alarms and tickets | P1 |
| FR-10 | Generate evidence-grounded investigation guidance | P1 |
| FR-11 | Capture human approval, correction and override | P1 |
| FR-12 | Display incident analytics and audit trail | P2 |
| FR-13 | Support ITSM/NMS integrations | P2 |

## 8. Non-functional requirements

- **Safety:** read-only by default; no production actions in v1.
- **Traceability:** each recommendation links to evidence and model/policy versions.
- **Security:** role-based access, least privilege, secrets management and PII minimization.
- **Reliability:** deterministic policy behavior; graceful degradation when LLM/vector retrieval is unavailable.
- **Performance:** establish baselines in M1/M2; do not invent latency targets before workload characterization.
- **Maintainability:** modular monolith with stable domain interfaces.
- **Portability:** local Docker development; deployment target selected later.
- **Explainability:** separate facts, predictions, hypotheses and recommended actions.

## 9. Product success measures

Establish baselines before setting targets.

- Ticket classification macro-F1 and per-class recall.
- Routing macro-F1, L2 escalation recall and false-escalation rate.
- Severity calibration and high-severity recall.
- Incident correlation pairwise precision/recall and cluster quality.
- Retrieval Recall@K and MRR.
- Recommendation usefulness and factuality from blinded engineer review.
- Human override rate and reasons.
- Median and p95 end-to-end processing latency.
- Percentage of outputs with complete provenance/evidence links.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Public data differs from operator reality | Cross-source tests and later authorized pilot data |
| Synthetic label shortcuts | Scenario-held-out evaluation and real-data test sets |
| Incorrect L1/L2 policy | Operator-configurable policy and reviewed labels |
| Hallucinated RCA | Evidence citations, uncertainty and human review |
| Data leakage | Prediction-time feature contracts and grouped splits |
| Sensitive subscriber data | Minimize, redact, restrict and audit |
| Alarm storms | Correlation and deduplication with explainable grouping |

## 11. Release gates

- **Research prototype:** public data, reproducible baselines, no production integrations.
- **Internal pilot:** approved operator data, security review, human-in-the-loop workflow.
- **Production consideration:** reliability, access controls, audit, monitoring, incident response, model governance and operator acceptance demonstrated.
