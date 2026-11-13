# PIIS UI-0 — API & Data-Contract Inventory

> [!IMPORTANT]
> **Inventory Status:** VERIFIED AGAINST RUNTIME BACKEND
> **Base URL:** `/api/v1`
> **Schema Standard:** Pydantic v2 Models ([`src/piis/api/schemas.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/api/schemas.py))
> **Authentication:** `Authorization: Bearer <JWT>` ([`src/piis/auth/dependencies.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/auth/dependencies.py))

---

## 1. Complete Existing Endpoint Inventory

The backend exposes 12 operational REST endpoints across 4 functional routers:

| HTTP Method | Route Path | Purpose | Auth Required | Required Permission / Role | State Mutation | Frontend Suitability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Kubernetes Liveness Probe | None | Public | No (Read-Only) | Excellent (Status pill) |
| `GET` | `/api/v1/ready` | Kubernetes Readiness Probe | None | Public | No (Read-Only) | Excellent (System health) |
| `GET` | `/metrics` | Prometheus Metrics Exposition | None | Public | No (Read-Only) | Admin only |
| `POST` | `/api/v1/incidents/ingest` | Ingest ITSM Incident Envelope | Bearer JWT | `ingest:events` | Yes (Stores incident) | Ingestion Simulator tool |
| `GET` | `/api/v1/incidents` | List Canonical Incidents | Bearer JWT | `view:incidents` | No (Read-Only) | Primary (Incident Explorer) |
| `GET` | `/api/v1/incidents/{id}` | Get Incident Details & Lineage | Bearer JWT | `view:incidents` | No (Read-Only) | Primary (Incident Detail) |
| `POST` | `/api/v1/incidents/{id}/investigate`| Execute Multi-Stage Investigation | Bearer JWT | `trigger:investigation` | Yes (Synthesizes Context) | Primary (Investigation Tab) |
| `GET` | `/api/v1/incidents/{id}/evidence` | Get Investigation Evidence | Bearer JWT | `view:evidence` | No (Read-Only) | Primary (Evidence Register) |
| `GET` | `/api/v1/incidents/{id}/recommendations`| Get Diagnostic Recommendations | Bearer JWT | `view:recommendations` | No (Read-Only) | Primary (Recommendation List) |
| `POST` | `/api/v1/incidents/{id}/reviews`| Submit Human Review Decision | Bearer JWT | Human Operator (`require_human_operator`) | Yes (Audit Sign-off) | Primary (Review Modal) |
| `GET` | `/api/v1/integrations/health` | List Adapter Connectivity States| Bearer JWT | `view:incidents` | No (Read-Only) | Primary (Adapter Monitor) |
| `GET` | `/api/v1/integrations/dead-letter` | Inspect Dead-Letter Queue | Bearer JWT | `PIIS_ADMIN`, `INCIDENT_MANAGER` | No (Read-Only) | Admin (DLQ Inspector) |
| `POST` | `/api/v1/integrations/dead-letter/{id}/retry`| Retry Failed Ingestion Item | Bearer JWT | `PIIS_ADMIN` | Yes (Re-ingestion) | Admin (DLQ Actions) |
| `GET` | `/api/v1/audit/records` | List Cryptographic Audit Trail | Bearer JWT | `view:audit_logs` | No (Read-Only) | Primary (Audit Timeline) |
| `GET` | `/api/v1/audit/verify` | Verify Audit Hash Chain | Bearer JWT | `verify:audit_ledger` | No (Read-Only) | Primary (Integrity Badge) |

---

## 2. Detailed Endpoint Contracts

### 2.1 Incident Management

#### `GET /api/v1/incidents`
- **Purpose:** Retrieve a paginated list of ingested canonical telecom incidents.
- **Query Parameters:**
  - `limit`: int (default: 20, min: 1, max: 100)
  - `offset`: int (default: 0, min: 0)
  - `domain`: Optional string (`RAN`, `CORE`, `TRANSPORT`, `SERVICE`)
  - `severity`: Optional string (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`)
- **Response Schema:** `PaginatedResponse[Dict[str, Any]]`
  ```json
  {
    "items": [
      {
        "incident_id": "INC-SNOW-INC0089201",
        "title": "High VSWR on 5G NR Cell-1",
        "description": "Sector degraded: High VSWR on 5G NR Cell-1. Tower: GNB-RAN-701.",
        "network_domain": "RAN",
        "severity": "MAJOR",
        "source_system": "ServiceNow",
        "source_type": "PUBLIC_REAL",
        "created_at": "2026-11-02T18:00:00Z"
      }
    ],
    "total_count": 42,
    "limit": 20,
    "offset": 0
  }
  ```
- **Error Codes:** 401 Unauthorized, 403 Forbidden.

#### `GET /api/v1/incidents/{incident_id}`
- **Purpose:** Retrieve full details and raw source envelope lineage for a single incident.
- **Path Parameter:** `incident_id` (str)
- **Response Schema:**
  ```json
  {
    "incident": { ...canonical_incident_record... },
    "lineage": {
      "envelope_id": "ENV-65D977A7DA2B",
      "source_system": "ServiceNow",
      "external_event_id": "INC0089201",
      "ingested_at": "2026-11-02T18:00:05.123Z",
      "raw_payload_checksum": "a8f3b2..."
    }
  }
  ```
- **Error Codes:** 401, 403, 404 Not Found.

---

### 2.2 Investigation & Reasoning Engine

#### `POST /api/v1/incidents/{incident_id}/investigate`
- **Purpose:** Execute the multi-stage investigation pipeline: feature extraction, classification, anomaly correlation, and RAG runbook retrieval.
- **Response Schema:** `InvestigationResponse`
  ```json
  {
    "incident_id": "INC-SNOW-INC0089201",
    "title": "High VSWR on 5G NR Cell-1",
    "network_domain": "RAN",
    "created_at": "2026-11-02T18:00:00Z",
    "is_sufficient": false,
    "missing_evidence": ["Historical feeder trace within 60 minutes missing"],
    "contradictions": [],
    "stale_evidence": [],
    "is_transient_event": false,
    "hypotheses_count": 1,
    "recommendations": [
      {
        "recommendation_id": "REC-001",
        "description": "Dispatch Tier 2 NOC Field Support for on-site visual inspection and manual trace capture.",
        "reason": "Automated evidence is insufficient or contradictory. Prohibiting ungrounded configuration changes.",
        "supporting_evidence_ids": ["EVID-ANOM-01"],
        "source_runbook_id": "RB-RAN-ANT-001",
        "risk_classification": "READ_ONLY_SAFE",
        "human_approval_required": true,
        "approval_status": "PENDING_REVIEW",
        "reviewed_by": null,
        "review_timestamp": null
      }
    ],
    "epistemic_status": "READ_ONLY_DECISION_SUPPORT",
    "correlation_id": "corr-50ec906edecd"
  }
  ```

---

### 2.3 Human Review & Authorization

#### `POST /api/v1/incidents/{incident_id}/reviews`
- **Purpose:** Cryptographically notarize an authenticated human operator's approval or rejection.
- **Security Check:** Strictly enforces `require_human_operator`. Automated service accounts are rejected with HTTP 403.
- **Request Schema:** `ReviewSubmissionRequest`
  ```json
  {
    "recommendation_id": "REC-001",
    "decision": "APPROVED",
    "review_notes": "Telemetry confirms VSWR ratio above threshold. Verified safe for field dispatch."
  }
  ```
- **Response Schema:** `ReviewResponse`
  ```json
  {
    "incident_id": "INC-SNOW-INC0089201",
    "recommendation_id": "REC-001",
    "decision": "APPROVED",
    "reviewed_by": "operator_sarah",
    "review_timestamp": "2026-11-02T18:05:12.441Z",
    "audit_entry_hash": "f9be276f61a277111c46fbfaffb39f4ec56f4e577879b9b4acda88bdcf58c20d",
    "ledger_sequence": 2,
    "status": "RECORDED_IN_AUDIT_CHAIN",
    "receipt_id": "RCPT-F9BE276F61A27711"
  }
  ```

---

### 2.4 Cryptographic Audit Ledger

#### `GET /api/v1/audit/records`
- **Purpose:** Paginated inspection of tamper-evident RFC 8785 JCS audit trail records.
- **Query Parameters:** `limit` (1-200), `offset` (>=0)
- **Response Schema:** `PaginatedResponse[AuditRecordItem]`

#### `GET /api/v1/audit/verify`
- **Purpose:** Real-time mathematical verification of the SHA-256 hash chain and monotonic anchor sequence.
- **Response Schema:**
  ```json
  {
    "is_valid": true,
    "total_records": 14,
    "latest_sequence": 14,
    "latest_hash": "386f76359b9cd69c34b9ad05feb6de39...",
    "error": null,
    "verification_status": "TAMPER_EVIDENT_INTACT"
  }
  ```

---

## 3. Analysis of Missing APIs Needed for Complete UI

To deliver the complete 9-section NOC experience outlined in Phase E without compromising architecture or inventing unbacked services, the following 4 endpoints are proposed for implementation in Phase UI-1:

### 3.1 Proposed Endpoint 1: Operator Identity & Session Profile
- **Route:** `GET /api/v1/auth/me`
- **Purpose:** Allow React frontend to inspect verified token metadata (operator ID, assigned roles, permissions, expiration) without parsing client-side unverified claims.
- **Underlying Service:** Calls `auth_manager.authenticate_token(credentials.credentials)`.
- **Proposed Response Schema:**
  ```json
  {
    "principal_id": "operator_sarah",
    "is_service_principal": false,
    "roles": ["NOC_L2", "OPERATOR"],
    "permissions": ["view:incidents", "trigger:investigation", "review:approve_medium_risk"],
    "issuer": "https://idp.telecom-corp.local/oauth2/v1",
    "expires_at": "2026-11-02T19:00:00Z"
  }
  ```

### 3.2 Proposed Endpoint 2: Network Topology & Adjacency
- **Route:** `GET /api/v1/network/topology`
- **Purpose:** Return node and edge representation for interactive topology visualization.
- **Underlying Service:** Calls existing `TelecomTopologyGraph` in [`src/piis/correlation/topology.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/correlation/topology.py).
- **Proposed Response Schema:**
  ```json
  {
    "nodes": [
      {"id": "GNB-RAN-701", "domain": "RAN", "element_type": "GNB", "status": "DEGRADED"},
      {"id": "UPF-CORE-01", "domain": "CORE", "element_type": "UPF", "status": "HEALTHY"}
    ],
    "edges": [
      {"source": "GNB-RAN-701", "target": "UPF-CORE-01", "relation": "n3_dataplane"}
    ]
  }
  ```

### 3.3 Proposed Endpoint 3: Telemetry Time-Series History
- **Route:** `GET /api/v1/telemetry/timeseries`
- **Purpose:** Feed Recharts line/area charts with rolling RF metric observations for a specific network element.
- **Query Parameters:** `element_id=GNB-RAN-701&metric_name=vswr_ratio&window_minutes=60`
- **Underlying Service:** Queries normalized telemetry records in `UnifiedIngestionPipeline`.

### 3.4 Proposed Endpoint 4: Active Alarms Query
- **Route:** `GET /api/v1/alarms`
- **Purpose:** Feed the Alarm Correlation and Impact matrices in Network Intelligence view.
- **Underlying Service:** Queries active alarms from `OSSAlarmAdapter` and `UnifiedIngestionPipeline`.
