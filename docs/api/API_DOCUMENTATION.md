# PIIS REST API Documentation

> [!IMPORTANT]
> **API Governance & Operational Principles**
> - **Base URL:** `/api/v1`
> - **Operational Boundary:** Strictly Read-Only Telecom Decision Support.
> - **Zero Production Execution:** No endpoint can issue configuration commands to network elements.
> - **Human Review Invariant:** The `/approve` and `/reject` endpoints strictly require authenticated human operator credentials (`ROLE_OPERATOR` or `ROLE_ADMIN`). Automated service principals are strictly rejected with HTTP 403 Forbidden.

---

## 1. Overview & Architecture

The PIIS REST API provides a standardized, secure, and observable HTTP interface for integrating external telecom operational platforms (ServiceNow, Jira, OSS/NMS alarm managers, Prometheus/OTLP telemetry engines) with the PIIS intelligence, investigation, and audit subsystems.

### Standard Request & Response Headers

| Header | Direction | Description | Example |
| :--- | :---: | :--- | :--- |
| `Authorization` | Inbound | Bearer JWT token issued by corporate OIDC IdP or test verifier. | `Bearer eyJhbGci...` |
| `X-Correlation-ID` | Bidirectional | Unique transaction identifier propagated across logs, traces, and audit logs. | `c-89a1-4321-f09b` |
| `Content-Type` | Bidirectional | Machine-readable MIME type. Must be `application/json`. | `application/json` |
| `Retry-After` | Outbound | Number of seconds to wait before retrying when rate-limited (HTTP 429). | `60` |

---

## 2. Authentication & Role-Based Access Control (RBAC)

All endpoints (except public health checks and UI assets) enforce HTTP Bearer token authentication via the `AuthManager` (`src/piis/auth/manager.py`).

### 2.1 Role Definitions & Permission Matrix

| Role (`ApplicationRole`) | Description | Allowed Endpoints |
| :--- | :--- | :--- |
| `viewer` | Read-only auditor or monitoring dashboard. | Health, status, metrics, incident query, audit ledger query. |
| `operator` | Human NOC Tier 1/2 engineer. | All viewer endpoints + incident investigation, cryptographic review approval/rejection. |
| `admin` | System administrator / governance officer. | All operator endpoints + DLQ replay, adapter management, anchor inspection. |
| `service_principal` | Automated ingestion worker or webhook pipeline. | Ingestion endpoints (`/integrations/{system}/ingest`, `/incidents`). **Prohibited from review endpoints.** |

---

## 3. Endpoints Catalog

### 3.1 System & Observability

#### `GET /api/v1/system/health` (also `GET /healthz`)
Evaluates the real-time operational readiness of all core subsystems.
- **Access:** Public / Unauthenticated
- **Response 200 OK:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-11-02T12:00:00Z",
  "components": {
    "pipeline": "healthy",
    "ledger": "healthy",
    "cache": "healthy",
    "auth": "healthy"
  }
}
```

#### `GET /api/v1/system/status`
Detailed operational status, including uptime, memory usage, and registered adapters.
- **Access:** Requires `viewer` role
- **Response 200 OK:** Returns component statuses, registered adapter list, and active ledger sequence.

#### `GET /metrics` (also `GET /api/v1/metrics`)
Prometheus scrape target exposing Golden Signals, ingestion counters, and request latencies.
- **Access:** Public / Prometheus Scraper
- **Response 200 OK (`text/plain; version=0.0.4`):**
```text
# HELP piis_requests_total Total HTTP requests handled by the PIIS API
# TYPE piis_requests_total counter
piis_requests_total{endpoint="/api/v1/incidents",method="POST",status="200"} 124.0
```

#### `GET /ui` (also `GET /`)
Serves the responsive Single-Page Application (SPA) operator dashboard for NOC engineers.
- **Access:** Public (API interactions within UI enforce Bearer token authentication)

---

### 3.2 Ingestion & Enterprise Integrations

#### `POST /api/v1/integrations/{source_system}/ingest`
Ingests, normalizes, sanitizes, and triages an external ticket, alarm, or telemetry payload.
- **Access:** Requires `service_principal`, `operator`, or `admin`
- **Supported `source_system` values:** `servicenow`, `jira`, `generic_rest`, `oss_nms`, `prometheus`, `otlp`
- **Request Body (Example: ServiceNow):**
```json
{
  "sys_id": "99b821a8f0923",
  "number": "INC0982341",
  "short_description": "RAN gNodeB Cell Unavailable - VSWR Alarm",
  "description": "Cell gNB-501-A reporting critical VSWR mismatch on RF branch B.",
  "category": "RAN",
  "urgency": "1",
  "impact": "1",
  "assignment_group": "Tier-1 RAN Operations"
}
```
- **Response 200 OK:**
```json
{
  "status": "success",
  "source_system": "servicenow",
  "external_id": "INC0982341",
  "canonical_id": "CANON-SN-INC0982341",
  "message": "Event successfully ingested and normalized",
  "correlation_id": "c-48f9-9021-ba34"
}
```
- **Response 422 Unprocessable Entity:** Payload schema failure; event safely isolated to Dead-Letter Queue.

#### `GET /api/v1/integrations/adapters`
Returns status, version, and throughput metrics for all registered integration adapters.
- **Access:** Requires `viewer` role

#### `GET /api/v1/integrations/dlq`
Lists quarantined events in the Dead-Letter Queue with failure classifications.
- **Access:** Requires `operator` or `admin` role

#### `POST /api/v1/integrations/dlq/{dlq_id}/replay`
Triggers an audited reprocessing attempt for a quarantined dead-letter event.
- **Access:** Requires `admin` role

---

### 3.3 Incidents & Investigation Lifecycle

#### `POST /api/v1/incidents`
Direct ingestion of a pre-normalized canonical incident conforming to `schemas/incident.schema.json`.
- **Access:** Requires `service_principal`, `operator`, or `admin` role

#### `GET /api/v1/incidents`
Lists canonical incidents with pagination, filtering by `network_domain`, `severity`, and `status`.
- **Access:** Requires `viewer` role
- **Query Parameters:** `domain`, `severity`, `status`, `limit` (default 50), `offset` (default 0)

#### `GET /api/v1/incidents/{incident_id}`
Retrieves full incident details, raw provenance, sanitized fields, and current investigation result.
- **Access:** Requires `viewer` role

#### `POST /api/v1/incidents/{incident_id}/investigate`
Executes the evidence-grounded investigation pipeline:
1. Multilingual prompt-injection sanitization (`BoundedRecursiveDecoder` & `RetrievalSecurityGuard`).
2. Anomaly detection and observation freshness evaluation (`TemporalEvidenceEvaluator`).
3. DAG blast radius topological correlation (`TopologicalCorrelator`).
4. Hybrid sparse/dense runbook retrieval (`HybridRetriever`).
5. Safe recommendation synthesis (`InvestigationEngine`).
- **Access:** Requires `operator` or `admin` role

#### `POST /api/v1/incidents/{incident_id}/approve`
Records a cryptographic human operator approval for a pending investigation recommendation.
- **Access:** **STRICTLY RESTRICTED TO AUTHENTICATED HUMAN OPERATORS (`operator`, `admin`).** Service principals are barred with HTTP 403 Forbidden.
- **Request Body:**
```json
{
  "operator_id": "noc_operator_42",
  "notes": "Verified VSWR telemetry on branch B. Runbook SOP-RAN-VSWR-001 approved for manual technician dispatch."
}
```
- **Response 200 OK:** Returns updated incident status (`APPROVED`), signed audit entry ID, and checkpoint hash.

#### `POST /api/v1/incidents/{incident_id}/reject`
Records a cryptographic human operator rejection for a pending recommendation.
- **Access:** Strictly restricted to authenticated human operators.

---

### 3.4 Governance & Audit Ledger

#### `GET /api/v1/audit/ledger`
Queries the immutable, RFC 8785 canonical JSONL audit ledger.
- **Access:** Requires `viewer` role
- **Query Parameters:** `incident_id`, `operator_id`, `limit`, `offset`

#### `GET /api/v1/audit/verify`
Recomputes and verifies the complete cryptographic SHA-256 hash chain and external checkpoint anchor.
- **Access:** Requires `viewer` role
- **Response 200 OK:**
```json
{
  "is_valid": true,
  "total_entries": 38,
  "head_sequence": 38,
  "head_hash": "a1f9e80234c...",
  "anchor_status": "synced"
}
```

---

## 4. Error Codes & Exception Handling

All API errors return RFC 7807-compatible structured JSON responses:

```json
{
  "error": "Forbidden",
  "detail": "Automated service principals are strictly barred from approving recommendations. Human review required.",
  "status_code": 403,
  "correlation_id": "c-48f9-9021-ba34"
}
```

| HTTP Status | Error Name | Common Cause |
| :---: | :--- | :--- |
| `400` | Bad Request | Missing required parameters or malformed JSON syntax. |
| `401` | Unauthorized | Missing, expired, or cryptographically invalid Bearer token. |
| `403` | Forbidden | Insufficient RBAC role, token revoked, or service principal attempting human review. |
| `404` | Not Found | Incident ID, DLQ entry ID, or route does not exist. |
| `422` | Unprocessable Entity | Payload violates canonical schema or no adapter registered. Safe DLQ quarantine initiated. |
| `429` | Too Many Requests | Token bucket rate limit exhausted. Check `Retry-After` header. |
| `500` | Internal Server Error | Unhandled exception. Logged with correlation ID; no state corrupted. |

---

## 5. Concrete Curl Examples

### 5.1 Ingest ServiceNow Ticket
```bash
curl -X POST http://localhost:8000/api/v1/integrations/servicenow/ingest \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: curl-ingest-001" \
  -d '{
    "sys_id": "sn-8901",
    "number": "INC0982341",
    "short_description": "gNodeB Cell VSWR High",
    "description": "High VSWR alarm on sector alpha branch B.",
    "category": "RAN",
    "urgency": "1",
    "impact": "1",
    "assignment_group": "Tier-1 RAN Operations"
  }'
```

### 5.2 Cryptographic Human Approval
```bash
curl -X POST http://localhost:8000/api/v1/incidents/CANON-SN-INC0982341/approve \
  -H "Authorization: Bearer <OPERATOR_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: curl-approve-001" \
  -d '{
    "operator_id": "noc_engineer_12",
    "notes": "Reviewed VSWR metrics. Approved SOP-RAN-VSWR-001 for field maintenance."
  }'
```

### 5.3 Audit Ledger Chain Verification
```bash
curl -X GET http://localhost:8000/api/v1/audit/verify \
  -H "Authorization: Bearer <VIEWER_TOKEN>"
```
