# PIIS UI-8.1 — Independent Runtime Health, Security & Regression Integrity Audit Report

**Auditor:** Independent Principal SRE, Security Engineer, Backend Architect & Verification Auditor  
**Subsystem:** Production Incident Intelligence System (PIIS — Telecom Edition)  
**Target Milestone:** UI-8 System Health & Operations Workspace  
**Audit Milestone:** UI-8.1 Independent Adversarial Audit & Final Milestone Freeze  
**Audit Date:** November 4, 2026  
**Final Audit Verdict:** **ACCEPTED WITH LIMITATIONS**  
**Operational Security Level:** STRICTLY READ-ONLY DECISION SUPPORT — PORTFOLIO EDITION  

---

## 1. Executive Verdict & Core Architecture Integrity

### 1.1 Formal Verdict: ACCEPTED WITH LIMITATIONS

Following an adversarial, independent verification across the codebase, runtime execution paths, failure-injection tests, frontend interface, and architectural claims of UI-8, the System Health & Operations Workspace is graded **ACCEPTED WITH LIMITATIONS**.

The verdict is governed by the ironclad PIIS principles:
> **EVIDENCE BEFORE INTELLIGENCE. INTELLIGENCE BEFORE AUTOMATION.**  
> **OPERATIONAL VISIBILITY WITHOUT OPERATIONAL EXECUTION AUTHORITY.**  
> **EXISTING TELECOM WORKFLOW + PIIS = ADDITIONAL OBSERVABILITY, INTEGRITY AND PROVENANCE.**

### 1.2 Summary of Limitations
The workspace is accepted for portfolio demonstration and decision-support environments subject to four explicit, documented operational limitations:
1. **Ephemeral In-Memory Health Event History:** The health observations timeline (`/api/v1/system-health/events`) stores events in an in-memory circular ring buffer (capacity: 500 records). It resets upon process restart and is **not** persisted to the durable RFC 8785 JSONL cryptographic audit ledger.
2. **Disconnected Portfolio Boundary:** The two external dependencies (`enterprise-oidc` and `external-worm-storage`) are disconnected in portfolio edition mode. They honestly report `UNKNOWN` health status and `REFERENCE_ONLY` implementation mode with zero synthetic health claims.
3. **Passive Prometheus Telemetry Endpoint:** PIIS exposes a standardized OpenMetrics scrape endpoint (`GET /metrics`), but does not include a built-in polling Prometheus scraper daemon or push gateway. External scraping requires user-configured telemetry collectors.
4. **Single-Process In-Memory Worker Architecture:** The distributed task worker (`background-worker`) is marked `NOT_INSTRUMENTED` / `UNKNOWN` because PIIS operates synchronously in-process.

---

## 2. Component Inventory & Grounding Verification (All 17 Components)

Every one of the 17 components exposed by the health registry was inspected against physical Python and TypeScript sources. The audit verified whether each component exists, its implementation nature, its failure isolation behavior, and its epistemic grounding.

| # | Component ID | Subsystem Name | Category | Criticality | Implementation Nature | Code Grounding & Physical Source | Verified Failure Mode |
|---|---|---|---|---|---|---|---|
| 1 | `api-gateway` | FastAPI Application Gateway | `API` | `CRITICAL` | `REAL_LOCAL` | `piis.api.app:app` & Uvicorn loop | Returns 503 if event loop stalls or unhandled exception occurs |
| 2 | `auth-manager` | Enterprise Auth & Access Manager | `AUTH` | `CRITICAL` | `REAL_LOCAL` | `piis.auth.manager.AuthManager` | Reports `DEGRADED` if local provider fallback active; `UNAVAILABLE` if key missing |
| 3 | `ingestion-pipeline` | Unified Telecom Ingestion Pipeline | `INGESTION` | `CRITICAL` | `REAL_LOCAL` | `piis.ingestion.pipeline.UnifiedIngestionPipeline` | Reports `DEGRADED` if any adapter degraded; `UNAVAILABLE` if pipeline uninitialized |
| 4 | `idempotency-engine` | SHA-256 Idempotency Cache | `DEDUPLICATION` | `STANDARD` | `REAL_LOCAL` | `pipeline.idempotency` (`IdempotencyStore`) | Reports `DEGRADED` if hash collision rate anomalies occur |
| 5 | `dead-letter-quarantine` | Dead-Letter Quarantine (DLQ) | `DLQ` | `STANDARD` | `REAL_LOCAL` | `pipeline.dlq` (`DeadLetterQueue`) | Reports `DEGRADED` if quarantine depth > 0; `HEALTHY` when DLQ is clean (0 items) |
| 6 | `knowledge-retrieval-bm25` | BM25 Okapi Lexical Index | `RETRIEVAL` | `STANDARD` | `REAL_LOCAL` | `piis.retrieval.bm25.BM25OkapiIndex` | Reports `DEGRADED` if indexed SOP/runbook chunks == 0 |
| 7 | `knowledge-retrieval-dense` | Dense Bi-Encoder Vector Index | `RETRIEVAL` | `STANDARD` | `REAL_LOCAL` | `piis.retrieval.dense.DenseBiEncoderIndex` | Reports `DEGRADED` when operating in deterministic lexical fallback mode |
| 8 | `investigation-engine` | Multi-Stage Investigation Engine | `INVESTIGATION` | `CRITICAL` | `REAL_LOCAL` | `piis.investigation.engine.IncidentInvestigationEngine` | Reports `DEGRADED` if deterministic SOP rules < 15 |
| 9 | `human-review-hub` | Human Review & Approval Subsystem | `REVIEW` | `CRITICAL` | `REAL_LOCAL` | `piis.investigation.approval.HumanApprovalWorkflow` | Reports `DEGRADED` if pending queue count exceeds threshold (>50) |
| 10 | `audit-ledger-jcs` | RFC 8785 JCS Cryptographic Ledger | `AUDIT` | `CRITICAL` | `REAL_LOCAL` | `data/approval_ledger.jsonl` | Reports `UNAVAILABLE` if file missing; `DEGRADED` if hash-chain broken |
| 11 | `checkpoint-anchor` | File-Based Monotonic Checkpoint Anchor | `AUDIT` | `CRITICAL` | `REAL_LOCAL` | `FileBasedCheckpointAnchor` | Reports `DEGRADED` / `UNAVAILABLE` if sequence out of parity or anchor absent |
| 12 | `trust-boundary-hmac` | HMAC-SHA256 Key Provider | `AUDIT` | `CRITICAL` | `REAL_LOCAL` | `LocalDevKeyProvider` / `signing_key` | Reports `DEGRADED` when using local development test key; `UNAVAILABLE` if missing |
| 13 | `integration-adapters` | Protocol Integration Adapters Pool | `INTEGRATIONS` | `STANDARD` | `REAL_LOCAL` | `pipeline.list_adapters()` (6 adapters) | Reports `DEGRADED` if any adapter is disabled or disconnected |
| 14 | `telemetry-anomaly` | Telemetry Anomaly Detection Model | `TELEMETRY` | `STANDARD` | `REAL_LOCAL` | `piis.telemetry.anomaly` (Z-Score & IF) | Reports `HEALTHY` with 2 registered deterministic evaluators |
| 15 | `enterprise-oidc` | Enterprise OIDC Provider | `AUTH` | `INFORMATIONAL` | `REFERENCE_ONLY` | RFC 8414 Discovery / Mock Local IdP | Reports `UNKNOWN` (Portfolio boundary: no live Okta/Ping/Entra ID) |
| 16 | `external-worm-storage` | External WORM Storage Trust Anchor | `AUDIT` | `INFORMATIONAL` | `REFERENCE_ONLY` | SEC 17a-4 compliance stub | Reports `UNKNOWN` (Portfolio boundary: no live AWS S3 Object Lock/Cohesity) |
| 17 | `background-worker` | Distributed Background Task Queue | `BACKGROUND` | `INFORMATIONAL` | `NOT_INSTRUMENTED` | In-process execution model | Reports `NOT_INSTRUMENTED` / `UNKNOWN` (Synchronous in-process model) |

---

## 3. Adversarial Failure-Injection Verification

Independent tests in `tests/integration/test_ui8_system_health.py` were executed against simulated hardware, filesystem, and subsystem failures to verify that health states accurately degrade and do not mask faults:

### 3.1 Simulated Missing Ledger File
- **Test:** `test_audit_ledger_unavailable_reflection`
- **Method:** Patched `workflow._ledger_path` to point to a non-existent filesystem path (`non_existent_ledger_test.jsonl`).
- **Observed Behavior:** Component `audit-ledger-jcs` transitioned immediately to `UNAVAILABLE` with reason `"Audit ledger file not found on disk"`. Under hierarchical aggregation, the overall system status transitioned to `UNAVAILABLE`.
- **Verdict:** PASS (Accurate fail-closed reporting).

### 3.2 Simulated Checkpoint Anchor Absence
- **Test:** `test_missing_checkpoint_anchor_handling`
- **Method:** Patched `workflow._checkpoint_anchor` to `None`.
- **Observed Behavior:** Component `checkpoint-anchor` reported `DEGRADED` with failure reason `"Checkpoint anchor not configured"`. The endpoint `GET /api/v1/system-health/persistence` returned `checkpoint_anchor_status: "MISSING"`.
- **Verdict:** PASS (Accurate failure isolation).

### 3.3 Simulated Subsystem Crash (Adapter Evaluation Failure)
- **Test:** `test_failure_isolation_per_component`
- **Method:** Injected an unhandled `RuntimeError("Simulated unexpected adapters crash")` into `pipeline.list_adapters`.
- **Observed Behavior:** The individual component health evaluator caught the exception via defensive per-component try-catch boundary. Component `integration-adapters` safely reported `UNAVAILABLE` with error diagnostics, while remaining 16 components evaluated normally. The API request returned HTTP 200 without cascading into a 500 error.
- **Verdict:** PASS (Subsystem fault isolation verified).

### 3.4 Dead-Letter Queue Non-Empty State
- **Test:** `test_ingestion_health_metrics` & `test_components_health_list`
- **Method:** Evaluated with non-zero quarantined envelopes in DLQ.
- **Observed Behavior:** Component `dead-letter-quarantine` reported `DEGRADED` with failure reason noting quarantined payload count.
- **Verdict:** PASS (Accurate operational degradation).

---

## 4. Read-Only Security & Operational Boundaries

### 4.1 Zero Production Mutation Verification
The audit performed a complete static and dynamic route scan on all endpoints under `/api/v1/system-health/*`:
- `GET /api/v1/system-health/overview` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/components` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/components/{id}` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/ingestion` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/intelligence` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/persistence` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/events` — **READ-ONLY** (No side-effects)
- `GET /api/v1/system-health/dependencies` — **READ-ONLY** (No side-effects)

**Findings:**
1. Zero mutative HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`) exist in the system health router.
2. Zero telecom mutations: No commands, SSH/NETCONF/RESTCONF calls, or routing modifications can be dispatched through this workspace.
3. Zero ticket mutations: No ITSM tickets are created, updated, or closed.
4. Zero subprocess calls: No `subprocess.Popen`, `os.system`, or CLI executions are invoked by health probes.
5. Zero outbound network egress: No unauthorized external HTTP requests are made.

### 4.2 Secret Redaction & Key Protection
- **Test:** `test_secret_redaction`
- **Verification:** System health responses across all 8 endpoints were scanned for regex patterns matching HMAC secret keys, JWT private signing keys, and raw authentication bearer tokens.
- **Result:** 0 credentials exposed. Cryptographic status reports only key presence (`key_available: true`), algorithm (`"HMAC-SHA256"`), and key provider type (`"LocalDevKeyProvider"`), with zero raw key bytes.

### 4.3 Authentication & Authorization
- **Test:** `test_health_endpoint_authorization`
- **Verification:** All 8 `/api/v1/system-health/*` endpoints require an authenticated principal possessing `Permission.VIEW_INCIDENTS`. Unauthenticated requests receive HTTP 401 Unauthorized.
- **Liveness & Readiness Probes:** The standard probe endpoints (`/api/v1/health`, `/api/v1/ready`, `/metrics`) are unauthenticated by design to allow process orchestrators and telemetry collectors to probe process status without credential management overhead.

---

## 5. Terminology & Epistemic Corrections Applied (UI-8.1 Hardening)

During the independent audit, three terminology and bias issues were identified and corrected:

### 5.1 HMAC-SHA256 Authentication Code vs Digital Signature
- **Issue:** `src/piis/api/routers/system.py` previously labeled the edge between `audit-ledger-jcs` and `trust-boundary-hmac` as `"RFC 8785 HMAC-SHA256 Signature"`, with relationship type `"SIGNS"`.
- **Correction:** An HMAC is a symmetric Message Authentication Code (MAC), not an asymmetric digital signature. The edge label was updated to `"RFC 8785 HMAC-SHA256 Message Authentication Code"`, and relationship type updated to `"AUTHENTICATES"`.

### 5.2 De-biasing Infrastructure Claims (Kubernetes & Prometheus)
- **Issue:** Header in Section C of `SystemHealthPage.tsx` and route docstrings referenced "Kubernetes Platform Probes", despite the absence of Kubernetes manifests in the repository. The Prometheus card displayed `"REGISTRY: ACTIVE"`, which could imply an active background scraping daemon.
- **Correction:**
  - Header in Section C updated to `"Process Runtime Probes & Telemetry Export"`.
  - Route descriptions updated from `"Kubernetes liveness probe..."` to `"Runtime process liveness probe confirming API responsiveness."`.
  - Prometheus card updated from `"Prometheus Scraper / REGISTRY: ACTIVE"` to `"Prometheus Metrics Exporter / ENDPOINT EXPOSED (PASSIVE)"`, with explicit note: `"Passive target"`.

### 5.3 Health Event History Ephemeral Disclaimer
- **Issue:** The Health Events timeline displays past state transitions, which could be mistaken for an immutable, durable audit log.
- **Correction:** Added an explicit amber disclosure banner to Tab 5 in `SystemHealthPage.tsx`:
  > *"Ephemeral In-Memory Observation Buffer: Health state transitions and diagnostic observations are recorded in an in-memory ring buffer (up to 500 records) for operational session monitoring. This buffer resets on application process restart and is distinct from the durable, append-only RFC 8785 JSONL cryptographic audit ledger."*

---

## 6. Static Dependency Graph Grounding

The dependency topology endpoint (`GET /api/v1/system-health/dependencies`) returns 17 nodes and 15 directional edges. Every edge was verified against code imports:

```mermaid
flowchart TD
    APIGateway["api-gateway"] -->|"Bearer Auth"| AuthManager["auth-manager"]
    APIGateway -->|"Webhook Dispatch"| Ingestion["ingestion-pipeline"]
    APIGateway -->|"Review Coordination"| ReviewHub["human-review-hub"]
    Ingestion -->|"Payload Consumption"| Adapters["integration-adapters"]
    Ingestion -->|"Deduplication"| Idempotency["idempotency-engine"]
    Ingestion -->|"Quarantine Isolation"| DLQ["dead-letter-quarantine"]
    Ingestion -->|"Trigger Investigation"| Engine["investigation-engine"]
    Engine -->|"Lexical SOP Search"| BM25["knowledge-retrieval-bm25"]
    Engine -->|"Dense Vector Search"| Dense["knowledge-retrieval-dense"]
    Engine -->|"Anomaly Evaluation"| Telemetry["telemetry-anomaly"]
    ReviewHub -->|"Cryptographic Commit"| AuditLedger["audit-ledger-jcs"]
    ReviewHub -->|"Sequence Parity"| CheckpointAnchor["checkpoint-anchor"]
    AuditLedger -->|"HMAC-SHA256 Auth"| HMACProvider["trust-boundary-hmac"]
    AuthManager -.->|"Planned Federation"| EnterpriseOIDC["enterprise-oidc (External)"]
    CheckpointAnchor -.->|"Planned WORM Parity"| WORM["external-worm-storage (External)"]

    classDef critical fill:#1e293b,stroke:#ef4444,stroke-width:2px,color:#f8fafc;
    classDef standard fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef informational fill:#1e293b,stroke:#64748b,stroke-width:1px,stroke-dasharray: 4 4,color:#94a3b8;

    class APIGateway,AuthManager,Ingestion,Engine,ReviewHub,AuditLedger,CheckpointAnchor,HMACProvider critical;
    class Adapters,Idempotency,DLQ,BM25,Dense,Telemetry standard;
    class EnterpriseOIDC,WORM informational;
```

---

## 7. Full Regression & Test Reconciliation

### 7.1 Historical Regression Counts
| Milestone | Backend Pytest Fleet | Frontend Vitest Fleet | M7 Demonstration Stages | Linter Findings |
|---|---|---|---|---|
| **UI-6.1.2** (Audit Freeze) | 545 tests (67 files) | 76 tests (12 files) | 18/18 stages passed | 0 errors |
| **UI-7.1** (Integrations Freeze) | 569 tests (70 files) | 83 tests (13 files) | 18/18 stages passed | 0 errors |
| **UI-8** (System Health Initial) | 592 tests (71 files) | 92 tests (14 files) | 18/18 stages passed | 0 errors |
| **UI-8.1** (Adversarial Audit) | **592 tests (71 files)** | **92 tests (14 files)** | **18/18 stages passed** | **0 errors** |

- **Backend delta:** Exactly +23 tests added for UI-8 (`tests/integration/test_ui8_system_health.py`), 0 regressions across historical suites.
- **Frontend delta:** Exactly +9 tests added for UI-8 (`frontend/src/test/SystemHealthWorkspace.test.tsx`), 0 regressions across historical suites.
- **Ruff check:** 0 errors across `src`, `tests`, `scripts`.
- **ESLint:** 0 errors across `frontend/src`.
- **TypeScript build:** 0 errors, build successful.
- **M7 End-to-End Portfolio Flow:** All 18 stages verified in 19.72 seconds.

---

## 8. Frontend Verification & Accessibility

### 8.1 Visual Evidence Artifacts Captured
The visual verification suite (`scripts/capture_ui8_screenshots.py`) confirmed all 9 workspace states:
1. `ui8_01_top_banner_and_metrics.png` — Aggregate health banner, active tab navigation, limitation notice.
2. `ui8_02_component_registry_grid.png` — Component cards with status badges and uninstrumented disclaimers.
3. `ui8_03_component_diagnostics_drawer.png` — Slide-over drawer with observation metadata, timestamps, and dependencies.
4. `ui8_04_ingestion_pipeline_tab.png` — Ingestion throughput, DLQ depth, and adapter registry metrics.
5. `ui8_05_intelligence_retrieval_tab.png` — BM25 index status, Dense vector fallback mode, and 15 deterministic SOP rules.
6. `ui8_06_persistence_audit_tab.png` — RFC 8785 ledger file status, HMAC signing key availability, and checkpoint sequence parity.
7. `ui8_07_health_events_timeline_tab.png` — Ephemeral observation event log with component and state filters.
8. `ui8_08_dependency_graph_topology_tab.png` — Codebase-grounded architecture layers and directed communication edges.
9. `ui8_09_component_filter_search.png` — Component search query and state filtering response.

### 8.2 WCAG Accessibility Compliance
- **Color Contrast:** Passed minimum 4.5:1 ratio for text and status indicators across dark theme (`var(--bg-canvas): #090d16`).
- **Semantic HTML & ARIA:** Table containers have explicit `aria-label` attributes (`"System Health Components Registry"`, `"Health Events Timeline"`).
- **Keyboard Navigation:** Tab selectors and slide-over close buttons are fully accessible via Tab and Escape keys.

---

## 9. Final Milestone Freeze

With this independent verification report, **Milestone UI-8 System Health & Operations Workspace is formally frozen and accepted with limitations**.

- **STOP CONDITION HONORED:**
  - UI-8 is completed and validated.
  - Zero features from UI-9 or future milestones have been started.
  - No claims of live enterprise production readiness are made.
  - Read-only telecom decision support boundary remains inviolate.
