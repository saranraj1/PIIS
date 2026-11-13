# M7 Architecture and Implementation Specification

## Production Incident Intelligence System (PIIS — Telecom Edition)
**Milestone:** M7 Portfolio Edition (Release Candidate v1.0.0-rc2)  
**Classification:** Portfolio & Research Release  
**Operational Scope:** Strictly Read-Only Telecom Decision Support (Zero Autonomous Mutations)

---

## 1. Executive Architectural Overview

PIIS is engineered as a resilient, security-hardened **modular monolith** tailored specifically for telecommunications Network Operations Centers (NOC). The core objective is to synthesize noisy, high-volume telemetry, multi-vendor alarm cascades, and ITSM incident tickets into evidence-grounded root cause hypotheses and ordered diagnostic checklists for human operator authorization.

The architecture strictly adheres to a **read-only decision support boundary**: PIIS is architecturally barred from issuing outbound commands to live telecom network elements, mutating operational tickets, modifying router configurations, or executing autonomous remediation.

```
+---------------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE INGESTION BOUNDARY (READ-ONLY)                            |
|                                                                                                         |
|  +--------------------+  +--------------------+  +--------------------+  +---------------------------+  |
|  | ServiceNow ITSM    |  | Jira Service Mgmt  |  | Generic REST/Hooks |  | OSS/NMS Alarm Stream      |  |
|  | (Contract Tested)  |  | (Contract Tested)  |  | (Contract Tested)  |  | (3GPP / Vendor Code Map)  |  |
|  +---------+----------+  +---------+----------+  +---------+----------+  +-------------+-------------+  |
|            |                       |                       |                           |                |
|            +-----------------------+-----------+-----------+---------------------------+                |
|                                                |                                                        |
|                                                v                                                        |
|                             +-------------------------------------+                                     |
|                             |    Unified Ingestion Pipeline       |                                     |
|                             |  - IngestionEnvelope Normalization  |                                     |
|                             |  - Token Bucket Rate Limiter        |                                     |
|                             |  - SHA-256 Idempotency Engine       |                                     |
|                             |  - Bounded Recursive Text Defanger  |                                     |
|                             |  - Dead-Letter Queue (DLQ) Fallback |                                     |
|                             +------------------+------------------+                                     |
+------------------------------------------------|--------------------------------------------------------+
                                                 |
                                                 v
+---------------------------------------------------------------------------------------------------------+
|                                 CANONICAL REPOSITORIES & CORRELATION ENGINE                             |
|                                                                                                         |
|  +------------------------+  +----------------------------+  +---------------------------------------+  |
|  | Canonical Incidents    |  | Telemetry Observations     |  | Network Alarms (3GPP Lifecycle)       |  |
|  | (RAN, 5G Core, Trans)  |  | (Prometheus, OTLP Metric)  |  | (Active, Ack, Cleared States)         |  |
|  +-----------+------------+  +--------------+-------------+  +-------------------+-------------------+  |
|              |                              |                                    |                      |
|              +------------------------------+------------------------------------+                      |
|                                             |                                                           |
|                                             v                                                           |
|                            +---------------------------------+                                          |
|                            | Incident Investigation Engine   |                                          |
|                            | (Classification, RAG, Reasoning)|                                          |
|                            +----------------+----------------+                                          |
+---------------------------------------------|-----------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------------------+
|                                   EPISTEMIC SEPARATION & HUMAN APPROVAL                                 |
|                                                                                                         |
|     [OBSERVED FACT]         [MODEL PREDICTION]         [HYPOTHESIS]            [RECOMMENDATION]         |
|   Telemetry / Alarms   -->  Domain / Severity    -->   Ranked Causes    -->    Safe SOP Actions         |
|                                                                                       |                 |
|                                                                                       v                 |
|                                                                            +--------------------+       |
|                                                                            |  Human Review      |       |
|                                                                            |  Sign-Off Gateway  |       |
|                                                                            +----------+---------+       |
|                                                                                       |                 |
|                                   +---------------------------------------------------+                 |
|                                   v                                                                     |
|                   +-------------------------------+                                                     |
|                   | Authenticated Human Operator  | <--- Production OIDC / RS256/ES256 Token            |
|                   | (NOC L2 / L3 Engineer)        |      (Bots & Service Accounts Strictly Blocked)     |
|                   +---------------+---------------+                                                     |
+-----------------------------------|---------------------------------------------------------------------+
                                    v
+---------------------------------------------------------------------------------------------------------+
|                                  CRYPTOGRAPHIC AUDIT LEDGER (RFC 8785 JCS)                              |
|                                                                                                         |
|    +--------------------+       +--------------------+       +--------------------+                     |
|    | Ledger Entry #1    | <---- | Ledger Entry #2    | <---- | Ledger Entry #3    |                     |
|    | Prev: GENESIS      |       | Prev: SHA256(#1)   |       | Prev: SHA256(#2)   |                     |
|    | HMAC: KeyProvider  |       | HMAC: KeyProvider  |       | HMAC: KeyProvider  |                     |
|    +--------------------+       +--------------------+       +----------+---------+                     |
|                                                                         |                               |
|                                                                         v                               |
|                                                      +--------------------------------------+           |
|                                                      | Monotonic Checkpoint Anchor (Disk)   |           |
|                                                      | (Rollback & Snapshot Tamper Defense) |           |
|                                                      +--------------------------------------+           |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Component Inventory & Directory Layout

| Component Path | Responsibility | Key Interfaces & Exports |
| :--- | :--- | :--- |
| `src/piis/api/app.py` | FastAPI application factory, lifespan management, middleware registration | `create_app()` |
| `src/piis/api/ui.py` | Self-contained NOC Operator Dashboard SPA with epistemic tagging | `serve_operator_workspace()`, `UI_HTML` |
| `src/piis/api/routers/` | REST endpoints for health, incidents, review, audit, integrations, DLQ | `incidents_router`, `audit_router`, `integrations_router` |
| `src/piis/auth/manager.py` | Production OIDC verification, JWT validation, RBAC permission resolution | `AuthManager`, `ProductionOIDCVerifier`, `ApplicationRole` |
| `src/piis/auth/test_oidc_provider.py` | Local standalone enterprise IdP with RFC 8414 discovery and dynamic JWKS | `LocalTestOIDCProvider` |
| `src/piis/integrations/contracts.py` | Base adapter class, capability flags, status labels, envelope models | `IntegrationAdapter`, `IntegrationStatusLabel`, `IngestionEnvelope` |
| `src/piis/integrations/itsm/` | ServiceNow, Jira JSM, and Generic REST ITSM adapters | `ServiceNowAdapter`, `JiraServiceManagementAdapter`, `GenericRestITSMAdapter` |
| `src/piis/integrations/telemetry/` | Prometheus vector query and OpenTelemetry OTLP metric adapters | `PrometheusAdapter`, `OpenTelemetryMetricsAdapter` |
| `src/piis/integrations/alarms/` | OSS/NMS alarm feed adapter with multi-vendor code translation and 3GPP states | `OSSAlarmAdapter`, `AlarmLifecycleState` |
| `src/piis/integrations/simulators/` | High-fidelity mock platforms generating realistic telecom telemetry & tickets | `SimulatedITSMPlatform`, `SimulatedAlarmBroker`, `SimulatedTelemetryPlatform` |
| `src/piis/pipeline/unified.py` | Multi-source ingestion pipeline, rate limiting, deduplication, schema validation | `UnifiedIngestionPipeline` |
| `src/piis/pipeline/dead_letter.py` | Dead-Letter Queue (DLQ) for malformed, rate-limited, and invalid payloads | `DeadLetterQueue` |
| `src/piis/pipeline/deduplication.py` | In-memory and persistent SHA-256 event deduplication engine | `IdempotencyEngine` |
| `src/piis/investigation/engine.py` | End-to-end evidence-grounded incident investigation orchestrator | `IncidentInvestigationEngine` |
| `src/piis/investigation/approval.py` | Human review workflow, cryptographic RFC 8785 JCS audit ledger, anchors | `HumanApprovalWorkflow`, `FileBasedCheckpointAnchor` |
| `src/piis/audit/trust_boundary.py` | Key provider and trusted timestamp abstractions for enterprise transition | `LocalDevKeyProvider`, `ExternalKMSProvider`, `LocalUtcTimestampProvider` |
| `src/piis/security/guardrails.py` | Adversarial prompt injection scanner and text neutralizing engine | `RetrievalSecurityGuard` |
| `src/piis/security/decoder.py` | Bounded recursive multi-encoding decoder (URL, Base64, Hex, Homoglyphs) | `BoundedRecursiveDecoder` |

---

## 3. Core Architectural Design Patterns

### 3.1. Strict Read-Only Boundary Pattern
All integration adapters subclass `IntegrationAdapter` and enforce:
```python
READ_ONLY = True
MUTATION_ALLOWED = False
SAFE_HTTP_METHODS = frozenset(["GET", "HEAD"])
```
Any call to mutative HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) or forbidden operational actions (`CREATE_TICKET`, `REBOOT_ELEMENT`, `EXECUTE_COMMAND`) immediately raises `ReadOnlyBoundaryViolationError`.

### 3.2. Epistemic Separation of Knowledge States
PIIS enforces a strict six-tier epistemic data model to prevent AI hallucination from being mistaken for verified ground truth:
1. `[OBSERVED FACT]`: Verifiable telemetry observations, hardware alarms, and raw ticket fields ingested from network sources.
2. `[MODEL PREDICTION]`: ML-derived classifications, predicted severity, and fault domain groupings.
3. `[HYPOTHESIS]`: RAG/LLM-generated root cause candidate theories grounded in historical correlation.
4. `[RECOMMENDATION]`: Proposed read-only diagnostic checks requiring operator authorization.
5. `[HUMAN-APPROVED DECISION]`: Explicit authorization cryptographically signed by an authenticated human operator.
6. `[CONFIRMED ROOT CAUSE]`: Post-incident ground truth validated by field engineering (never asserted autonomously).

### 3.3. RFC 8785 JSON Canonicalization Scheme (JCS)
All audit ledger entries are canonicalized via RFC 8785 before hashing to guarantee that dictionary key ordering, whitespace differences, and float representation quirks across platforms never compromise hash chain verification.

### 3.4. Fail-Closed Cryptographic Checkpoint Anchoring
To prevent replay attacks and snapshot rollbacks (where an attacker restores an earlier valid ledger backup to wipe out disciplinary actions or evidence), `HumanApprovalWorkflow` checks each loaded log entry against an independent, monotonic checkpoint anchor. If the ledger's sequence number is lower than the anchor's recorded sequence, restore fails closed with `LedgerRollbackDetectedError`.

---

## 4. End-to-End Data Flow (18 Demonstration Stages)

The 18-stage demonstration script (`scripts/demonstrate_m7_portfolio_flow.py`) exercises the entire architectural pipeline sequentially:

1. **System Initialization:** Verifies Python 3.11+ environment, FastAPI router binding, and health probes.
2. **Local IdP Startup:** Starts `LocalTestOIDCProvider` and publishes RFC 8414 `.well-known/openid-configuration` and JWKS.
3. **Token Minting:** Mints RS256/ES256 bearer tokens for human operator roles (`NOC_L1`, `NOC_L2`, `NOC_L3`) and service principals (`snow-ingestion-daemon`).
4. **Token Verification:** Validates signatures, expiration, issuer, audience, and maps claims to `ApplicationRole` and `Permission`.
5. **Adapter Registration:** Registers ServiceNow, Jira, REST, Prometheus, OTLP, and OSS/NMS adapters with explicit `IntegrationStatusLabel`.
6. **Multi-Source Ingestion:** Ingests incidents from simulated ServiceNow and Jira platforms into canonical schema format.
7. **Deduplication Check:** Submits identical ticket twice; pipeline detects duplicate SHA-256 payload and returns `DUPLICATE` without duplicating state.
8. **Security Inspection:** Submits ticket containing adversarial prompt injection and `<script>` tags; pipeline neutralizes inputs before persistence.
9. **Dead-Letter Quarantine:** Ingests malformed payload; schema validator rejects it and safely quarantines it into the DLQ.
10. **Telemetry & Alarm Ingestion:** Ingests high VSWR Nokia radio alarms and RF telemetry, mapping them to gNodeB `GNB-RAN-701`.
11. **Investigation Engine Execution:** Correlates alarms and telemetry, retrieves runbooks, and generates ranked hypotheses.
12. **Epistemic Classification:** Verifies that hypothesis text is explicitly tagged `[HYPOTHESIS]` and recommendations remain unconfirmed.
13. **Human Review Registration:** Registers diagnostic recommendations into `HumanApprovalWorkflow` in state `PENDING_REVIEW`.
14. **Service Principal Lockout:** Attempts to approve recommendation using service principal token; system rejects with `UnauthenticatedReviewerError`.
15. **Authorized Operator Approval:** NOC Tier-2 engineer reviews and cryptographically signs approval with bearer token.
16. **Ledger Hash Chain Verification:** Computes canonical SHA-256 digests and HMAC signatures for every log entry; validates monotonic anchor.
17. **Tamper Detection Simulation:** Mutates an audit entry on disk; reloading fails closed with `AuditTrailDiscontinuityError`.
18. **Final Portfolio Summary:** Compiles execution metrics, verifying that all 18 stages completed in under 20 seconds.
