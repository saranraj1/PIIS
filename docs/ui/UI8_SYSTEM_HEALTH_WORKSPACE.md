# PIIS UI-8 — System Health & Operations Workspace Specification

**System:** Production Incident Intelligence System (PIIS — Telecom Edition)  
**Milestone:** UI-8 System Health & Operations  
**Evaluation Date:** November 4, 2026  
**Status:** In Progress — Reconnaissance Complete  
**Classification:** READ-ONLY DECISION SUPPORT — PORTFOLIO EDITION  

---

## 1. Executive Summary & Architectural Scope

The **System Health & Operations Workspace (UI-8)** provides Tier 1 and Tier 2 Network Operations Center (NOC) engineers, reliability engineers, and compliance auditors with complete, evidence-grounded visibility into the operational health, subsystem availability, ingestion throughput, intelligence pipelines, and cryptographic audit persistence of **PIIS — Telecom Edition**.

In accordance with locked PIIS principles:
- **Evidence before intelligence. Intelligence before automation.**
- **Operational visibility without operational execution authority.**
- **No invented operational facts, metrics, or health states.**
- **Read-only decision support by default.**
- **Portfolio edition boundary:** No live external enterprise infrastructure (OIDC, WORM, external KMS, live carrier brokers) is connected.

The System Health Workspace answers:
1. Is PIIS running and responsive?
2. Are backend services and readiness probes available?
3. What is the verified operational status of internal components?
4. Is the ingestion pipeline processing events, deduplicating alerts, or quarantining malformed payloads in DLQ?
5. Are AI retrieval (BM25, dense bi-encoder, RRF fusion) and investigation engines operational or in local fallback mode?
6. Are the cryptographic audit ledger and checkpoint anchor synchronized and verifiable?
7. What concrete evidence and timestamps support each reported health determination?

---

## 2. Reconnaissance & Subsystem Inventory

### 2.1 Existing Health & Observability Endpoints

| Existing Endpoint | Router | Current Behavior | UI-8 Utilization |
| :--- | :--- | :--- | :--- |
| `GET /api/v1/health` | `system.py` | Returns `{"status": "ok", "service": "piis-core", "mode": "read_only_decision_support"}` | Liveness probe card (API service) |
| `GET /api/v1/ready` | `system.py` | Returns `{"status": "ready"|"degraded", "registered_adapters_count", "degraded_adapters", "incidents_count", "dead_letter_count", "audit_ledger_records"}` | Readiness probe card |
| `GET /metrics` | `system.py` | Exports Prometheus metrics from `PIIS_REGISTRY` | Diagnostic telemetry source |
| `GET /api/v1/integrations/summary` | `integrations.py` | Returns adapter counts, available/degraded breakdown, disconnected portfolio mode | Integration subsystem health |
| `GET /api/v1/integrations/health` | `integrations.py` | Returns individual adapter health states, last heartbeat, consecutive failures | Protocol adapter registry items |
| `GET /api/v1/integrations/activity` | `integrations.py` | Paginated in-memory activity ring buffer | Health events timeline source |
| `GET /api/v1/audit/verify` | `audit.py` | Two-layer RFC 8785 + HMAC ledger verification returning 5-state result | Audit ledger health |

### 2.2 Genuine Observable Internal Subsystems

| Subsystem Component | Category | Criticality | Observable Source / Implementation |
| :--- | :--- | :--- | :--- |
| **`api-gateway`** | `API` | `CRITICAL` | FastAPI process lifecycle, uvicorn event loop responsive. |
| **`auth-manager`** | `AUTH` | `CRITICAL` | `AuthManager()`, in-memory token verifier, active revoked tokens table. |
| **`ingestion-pipeline`** | `INGESTION` | `CRITICAL` | `UnifiedIngestionPipeline`, incident repository, event counters. |
| **`idempotency-engine`** | `DEDUPLICATION`| `STANDARD` | `pipeline.idempotency`, SHA-256 fingerprint cache. |
| **`dead-letter-quarantine`** | `DLQ` | `STANDARD` | `pipeline.dlq.count()`, attempt tracking, JSONL persistence snapshot. |
| **`knowledge-retrieval-bm25`**| `RETRIEVAL` | `STANDARD` | `BM25OkapiIndex`, inverted index total chunks count. |
| **`knowledge-retrieval-dense`**| `RETRIEVAL` | `STANDARD` | `DenseBiEncoderIndex`, `is_fallback_mode` (TF-IDF vs SentenceTransformer). |
| **`investigation-engine`** | `INVESTIGATION`| `CRITICAL` | `IncidentInvestigationEngine`, `DETERMINISTIC_SOP_MAP` (15 rules). |
| **`human-review-hub`** | `REVIEW` | `CRITICAL` | `HumanApprovalWorkflow`, pending queue, approved/rejected states. |
| **`audit-ledger-jcs`** | `AUDIT` | `CRITICAL` | `approval_ledger.jsonl`, RFC 8785 canonical hash chain verification. |
| **`checkpoint-anchor`** | `AUDIT` | `CRITICAL` | `FileBasedCheckpointAnchor`, monotonic checkpoint persistence parity. |
| **`trust-boundary-hmac`** | `AUDIT` | `CRITICAL` | `LocalDevKeyProvider`, HMAC-SHA256 key availability. |
| **`integration-adapters`** | `INTEGRATIONS` | `STANDARD` | 6 configured adapters (`ITSM-SERVICENOW-01`, `ITSM-JIRA-01`, etc.). |
| **`telemetry-anomaly`** | `TELEMETRY` | `STANDARD` | `TelemetryAnomalyPipeline`, statistical and isolation forest models. |
| **`enterprise-oidc`** | `AUTH` | `INFORMATIONAL`| Not configured in portfolio edition (`LocalTestOIDCProvider` reference). |
| **`external-worm-storage`**| `AUDIT` | `INFORMATIONAL`| Not configured (`DEP-M5.3-001` enterprise prerequisite). |
| **`background-worker`** | `BACKGROUND` | `INFORMATIONAL`| Not instrumented (PIIS runs synchronously in-process). |

### 2.3 Missing Observability Capabilities & Honest Disclosures

- **No Distributed Background Workers:** PIIS does not run Celery, Redis Queue, or RabbitMQ. Background tasks are in-process Python tasks or immediate synchronous pipeline executions. The workspace will explicitly label background processing as `NOT INSTRUMENTED (IN-PROCESS SYNCHRONOUS RUNTIME)`.
- **No Remote Hardware Sensors:** Telemetry is simulated or loaded from local reference time-series. The workspace will disclose `REFERENCE DATA`.
- **No Coordinated Rollback Detection Without External Anchor:** A local coordinated rollback where both the ledger file and checkpoint file are rewound to an earlier sequence cannot be detected without an external trust anchor (e.g. cloud KMS, external timestamp authority). This is explicitly labeled in Section F.
- **No Synthetic Latency Generation:** If a component latency is not actively tracked by Prometheus histograms, it will display `NOT MEASURED`, never fabricated numbers.

---

## 3. Deterministic Health-State Policy

### 3.1 Four Primary Health States

| State | Semantic Definition | Color Token | Critical Component Impact |
| :--- | :--- | :--- | :--- |
| **`HEALTHY`** | Verified operational via recent heartbeat, responsive probe, or valid verification. | Emerald (`text-emerald-400`, `bg-emerald-500/10`) | Contributes to operational readiness. |
| **`DEGRADED`** | Verified operational but experiencing non-fatal impairment (e.g., dense index in local TF-IDF fallback, adapter missing heartbeat, DLQ contains quarantined items). | Amber (`text-amber-400`, `bg-amber-500/10`) | Causes overall system to become `DEGRADED`. |
| **`UNAVAILABLE`** | Required component confirmed unreachable, failed probe, corrupted ledger, or missing key. | Rose (`text-rose-400`, `bg-rose-500/10`) | If component is `CRITICAL`, forces overall system to `UNAVAILABLE`. |
| **`UNKNOWN`** | Insufficient evidence, missing timestamp, or probe timed out. | Zinc/Gray (`text-zinc-400`, `bg-zinc-500/10`) | If component is `CRITICAL`, forces overall system to `UNKNOWN`. |

### 3.2 Aggregate Health Evaluation Policy

The aggregate status is determined by strict hierarchical precedence:

```python
def compute_aggregate_health(components: List[ComponentHealthItem]) -> str:
    critical_components = [c for c in components if c.criticality == "CRITICAL"]
    standard_components = [c for c in components if c.criticality == "STANDARD"]

    # 1. Any critical component UNAVAILABLE -> Overall UNAVAILABLE
    if any(c.health_state == "UNAVAILABLE" for c in critical_components):
        return "UNAVAILABLE"

    # 2. Any critical component UNKNOWN -> Overall UNKNOWN
    if any(c.health_state == "UNKNOWN" for c in critical_components):
        return "UNKNOWN"

    # 3. Any critical component DEGRADED -> Overall DEGRADED
    if any(c.health_state == "DEGRADED" for c in critical_components):
        return "DEGRADED"

    # 4. Standard components: Any UNAVAILABLE or DEGRADED -> Overall DEGRADED
    if any(c.health_state in {"UNAVAILABLE", "DEGRADED"} for c in standard_components):
        return "DEGRADED"

    # 5. All critical and standard components are healthy
    return "HEALTHY"
```

---

## 4. Proposed Backend Endpoints & API Contracts

All endpoints are hosted in `src/piis/api/routers/system.py` under the prefix `/api/v1/system-health`:

1. `GET /api/v1/system-health/overview`: Aggregate status, breakdown counts, uptime, readiness state.
2. `GET /api/v1/system-health/components`: Complete searchable registry of the 17 verified components with statuses, criticalities, timestamps, and failure notes.
3. `GET /api/v1/system-health/components/{component_id}`: Deep diagnostic inspection of a single component.
4. `GET /api/v1/system-health/ingestion`: Real-time ingestion counters, DLQ depth, rate-limiting stats.
5. `GET /api/v1/system-health/intelligence`: AI subsystem availability (BM25 chunks, dense encoder fallback state, SOP rules).
6. `GET /api/v1/system-health/events`: Chronological health events timeline sourced from activity stream.
7. `GET /api/v1/system-health/dependencies`: Visual component dependency graph (nodes and edges) grounded in verified codebase imports.

---

## 5. Security & Boundary Guarantees

1. **Read-Only Invariant:** Zero POST/PUT/PATCH/DELETE endpoints.
2. **Zero Execution Authority:** No service restart, command execution, or configuration mutation buttons.
3. **Zero Automated DLQ Replay:** DLQ items can only be inspected; retries require manual operator action via UI-7 DLQ modal with human reviewer gating.
4. **Zero Expensive Inference:** Health checks read in-memory properties and flags; no LLM prompts or heavy embedding generation.
5. **Zero Credential Exposure:** Secrets strictly stripped; auth headers and keys masked.
