# Architecture overview

## Context

PIIS sits alongside existing telecom operational systems. It consumes authorized records and provides recommendations back to engineers. Existing ITSM/NMS/OSS remains the system of record.

## Main data flow

1. Source adapter receives ticket/alarm/telemetry.
2. Ingestion assigns ingestion metadata and source provenance.
3. Validator checks schema and required semantics.
4. Normalizer maps source fields to canonical contracts.
5. Feature builders produce prediction-time-safe features.
6. ML models and correlation services generate structured results.
7. Retrieval fetches historical evidence and approved runbooks.
8. Policy layer checks whether a recommendation is permitted.
9. LLM may synthesize a human-readable explanation from structured evidence.
10. Human reviews and records outcome.
11. Audit service records all inputs, versions, evidence references and decisions.

## Trust boundaries

- External source data is untrusted.
- Ticket text and documents may contain prompt injection.
- Model output is untrusted until validated.
- LLM has no production credentials or network-control tools.
- Human approval does not bypass operator authorization policy.

## Failure behavior

- If LLM unavailable: show ML/policy output and evidence.
- If vector retrieval unavailable: disclose retrieval unavailable; do not fabricate similar cases.
- If schema invalid: quarantine record and return actionable validation errors.
- If model confidence is low or inputs are out of distribution: recommend human review.
