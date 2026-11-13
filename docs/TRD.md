# Technical Requirements Document (TRD)
## PIIS — Telecom Production Incident Intelligence System

- **Version:** 0.1
- **Status:** Initial technical baseline

## 1. Architecture decision

Use a modular monolith with explicit domain modules and adapter boundaries. Split services only when deployment, scaling, isolation or team ownership justifies it.

## 2. Logical components

1. Ingestion adapters — CSV, JSON, JSONL initially; later ITSM/NMS/OSS APIs.
2. Validation and normalization — schema validation, canonical IDs, units/time normalization.
3. Feature pipeline — ticket-time text/metadata and telemetry-window features.
4. ML inference — category, severity, routing and anomaly models as separate tasks.
5. Correlation — temporal, topology, shared entity and semantic relationships.
6. Retrieval — embeddings, vector search and metadata filters.
7. Recommendation orchestration — deterministic policy + retrieved evidence + LLM synthesis.
8. Human review — accept/reject/edit/override.
9. Audit — immutable event trail for decisions and evidence.
10. API/UI — operator-facing interface; integration adapters remain optional.

## 3. Canonical data contracts

The JSON Schemas in `/schemas` define initial contracts:
- incident.schema.json
- telemetry.schema.json
- alarm.schema.json
- resolution.schema.json
- evidence.schema.json
- recommendation.schema.json

Schema changes require versioning and migration notes. Unknown source fields should be retained in a source payload store where permitted, not silently discarded.

## 4. Data processing

- Raw source data is immutable.
- Normalize timestamps to UTC while retaining original timezone metadata when known.
- Preserve source units and define conversion functions explicitly.
- Distinguish missing, zero, not-applicable and unknown.
- Deduplicate only with a documented key and retain duplicate lineage.
- Use incident/scenario/network-element/time-aware splits.
- Do not join labels across datasets without semantic compatibility checks.

## 5. ML task contracts

### Ticket classification
Input: ticket fields available at creation.
Output: ranked fault categories + calibrated score/abstention.
Metrics: macro-F1, per-class recall, confusion matrix.

### Severity estimation
Input: impact, affected service/region/subscribers, symptoms and available telemetry.
Output: severity recommendation + policy rationale.
Metrics: macro-F1, high-severity recall, calibration.

### Support routing
Input: ticket-time evidence, documented troubleshooting state and operator policy.
Output: L1/L2/L3/HUMAN_REVIEW recommendation + rationale.
Labels must be annotated under a named operator policy. Fault labels are not substitutes.

### Anomaly detection
Input: time-indexed KPI windows.
Output: anomaly score, time range and affected entities.
Metrics: PR-AUC, event-level precision/recall, detection delay.

### Incident correlation
Input: tickets, alarms, telemetry, topology and time windows.
Output: candidate related-event groups with edge explanations.
Metrics: pairwise precision/recall, B-cubed or other cluster metrics, analyst review.

### Root-cause ranking
Input: incident evidence available at investigation time.
Output: ranked hypotheses with evidence for/against.
Metrics: top-k accuracy only where verified root-cause labels exist; otherwise blinded expert assessment.

## 6. RAG and LLM constraints

- Retrieve only from authorized sources.
- Return document/record IDs, source, timestamp and relevant excerpt.
- Apply metadata filters for domain, network generation, vendor, geography and time where available.
- LLM must not invent commands, thresholds, root causes or evidence.
- Prompt-injection content in tickets/runbooks is untrusted data.
- Output schema must separate observed_facts, model_predictions, hypotheses, recommendations, caveats and evidence_refs.
- If retrieval is empty or weak, abstain or ask for more evidence.
- LLM outage must not disable deterministic ingestion/classification/rules.

## 7. API direction

Initial endpoints (future implementation):
- POST /v1/ingest/incidents
- POST /v1/ingest/telemetry
- GET /v1/incidents/{incident_id}
- POST /v1/incidents/{incident_id}/analyze
- GET /v1/incidents/{incident_id}/evidence
- POST /v1/recommendations/{recommendation_id}/review
- GET /v1/health

All write operations require authentication, authorization, validation and audit events.

## 8. Persistence

Initial recommendation:
- PostgreSQL for incidents, metadata, decisions and audit records.
- Object storage/filesystem for approved source artifacts and larger payloads.
- FAISS for local research retrieval; abstract vector store interface for later replacement.
- Model artifacts stored with checksums and model cards.

## 9. Observability

Capture structured metrics/logs/traces:
- ingestion counts and failures
- schema validation failures
- model version and inference duration
- retrieval latency and hit count
- recommendation evidence coverage
- human override outcomes
- API error rates and p50/p95 latency

Never log credentials, subscriber PII or unrestricted raw ticket content.

## 10. Security

- RBAC: analyst, engineer, incident manager, data steward, administrator.
- Least-privilege service identities.
- Secrets from environment/secret manager, never source control.
- Encryption in transit and at rest for deployment.
- PII redaction/minimization and retention policy.
- Audit all access to sensitive incident records.
- No autonomous network actions in v1.

## 11. Testing

- Unit tests for schema, normalization, policies and feature generation.
- Contract tests for adapters.
- Integration tests for database/retrieval/API.
- Data tests for leakage, duplicates, drift and schema changes.
- Model tests for class coverage, calibration and subgroup performance.
- LLM evaluations for grounding, unsupported claims and prompt injection.
- Security tests for authorization, data exposure and malicious payloads.
- Load tests after workload profile is established.

## 12. Deployment evolution

Local research → Docker-based internal demo → controlled operator pilot → production readiness review.
No production deployment claim until security, reliability, data governance and operator acceptance gates pass.
