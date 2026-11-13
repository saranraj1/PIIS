# M7 End-to-End Portfolio Demonstration Walkthrough

## Production Incident Intelligence System (PIIS — Telecom Edition)
**Milestone:** M7 Portfolio Edition (Release Candidate v1.0.0-rc2)  
**Script Path:** `scripts/demonstrate_m7_portfolio_flow.py`  
**Execution Runtime:** ~15 Seconds | **Target Exit Code:** 0

---

## 1. Overview of the 18 Demonstration Stages

The demonstration script executes the complete incident lifecycle from multi-source ingestion through epistemic investigation to cryptographic audit sign-off and tamper detection.

```
Stage 01: System Initialization & Local Health Check
Stage 02: Local Enterprise OIDC Provider Startup & JWKS Publication
Stage 03: Token Acquisition (NOC_L1, NOC_L2, NOC_L3, Service Principal)
Stage 04: Token Validation & RBAC Permission Mapping
Stage 05: Enterprise Adapter Registration & Capability Flag Check
Stage 06: Multi-Source Incident Ingestion (ServiceNow, Jira)
Stage 07: Deduplication & Idempotency Check
Stage 08: Security Inspection & Adversarial Input Defanging
Stage 09: Dead-Letter Queue (DLQ) Quarantine
Stage 10: Cross-Domain Telemetry & Alarm Correlation
Stage 11: M2-M5 Evidence-Grounded Investigation Pipeline
Stage 12: Epistemic Boundary Verification ([FACT], [PRED], [HYPO], [RECO])
Stage 13: Human Approval Workflow Registration
Stage 14: Non-Human Lockout (Service Principal Rejection)
Stage 15: Authorized Operator Approval (NOC Tier-2 Sign-Off)
Stage 16: Cryptographic Audit Ledger & Anchor Verification
Stage 17: Disk Tamper Detection & Fail-Closed Behavior
Stage 18: Final System Summary & Portfolio Readiness
```

---

## 2. Stage-by-Stage Detailed Narrative

### Stage 1: System Initialization
- **Action:** Initializes the FastAPI application factory, mounts all routers, and calls `GET /api/v1/health`.
- **Expected Output:**
  ```
  -> Python Runtime: 3.11.5
  -> Platform: win32
  -> Health Endpoint Status: OK
  [PASS] System initialized and healthy.
  ```

### Stage 2: Local Enterprise OIDC Provider Startup
- **Action:** Boots `LocalTestOIDCProvider` without external network access. Publishes RFC 8414 discovery endpoint and dynamic JWKS with real RS256/ES256 asymmetric keys.
- **Expected Output:**
  ```
  -> RFC 8414 Discovery Issuer: https://idp.telecom-corp.local/oauth2/v1
  -> JWKS Endpoint: https://idp.telecom-corp.local/oauth2/v1/.well-known/jwks.json
  -> Active Key IDs (JWKS): ['test-key-rsa-v1', 'test-key-ec-v1']
  [PASS] Local enterprise IdP active and publishing discovery.
  ```

### Stage 3: Token Acquisition
- **Action:** Mints cryptographically signed JWT tokens for human operators (`OP-TIER1-01`, `OP-TIER2-01`, `OP-TIER3-01`) and a service principal daemon (`SVC-SNOW-POLLER`).
- **Expected Output:**
  ```
  -> Minted NOC_L1 Token: OP-TIER1-01 (RS256)
  -> Minted NOC_L2 Token: OP-TIER2-01 (RS256)
  -> Minted NOC_L3 Token: OP-TIER3-01 (RS256)
  -> Minted Service Principal: SVC-SNOW-POLLER
  [PASS] All role-specific tokens minted successfully.
  ```

### Stage 4: Token Validation & RBAC Permission Mapping
- **Action:** Verifies JWT signatures against JWKS, checks expiration, and evaluates permission grants.
- **Verification:** `OP-TIER2-01` has `APPROVE_MEDIUM_RISK_REVIEW=True`; `OP-TIER1-01` does not. `SVC-SNOW-POLLER` is marked `is_service=True`.
- **Expected Output:**
  ```
  -> Validated OP-TIER1-01: Roles=['NOC_L1']
  -> Validated OP-TIER2-01: APPROVE_MEDIUM_RISK=True
  -> Validated SVC-SNOW-POLLER: is_service=True
  [PASS] Cryptographic JWT signature and permission checks validated.
  ```

### Stage 5: Enterprise Adapter Registration
- **Action:** Registers all 6 enterprise adapters: ServiceNow, Jira JSM, Generic REST, Prometheus, OTLP, and OSS/NMS.
- **Verification:** Checks `READ_ONLY=True` and `status_labels=['LOCALLY VERIFIED', 'SIMULATED', ...]`.
- **Expected Output:**
  ```
  -> Registered SNOW-ITSM-01 [ITSM] READ_ONLY=True Labels=LOCALLY VERIFIED
  -> Registered JIRA-ITSM-01 [ITSM] READ_ONLY=True Labels=LOCALLY VERIFIED
  ...
  [PASS] All 6 enterprise adapters registered with strict read-only boundary.
  ```

### Stage 6: Multi-Source Incident Ingestion
- **Action:** Ingests synthetic tickets from ServiceNow (`INC0089201`) and Jira (`NOC-452`).
- **Expected Output:**
  ```
  -> ServiceNow Ingestion: Canonical ID=INC-SNOW-INC0089201 (Status=SUCCESS)
  -> Jira JSM Ingestion: Canonical ID=INC-JIRA-NOC-452 (Status=SUCCESS)
  [PASS] Multi-source ITSM ingestion succeeded.
  ```

### Stage 7: Deduplication & Idempotency Demonstration
- **Action:** Re-submits the identical ServiceNow ticket payload.
- **Verification:** `IdempotencyEngine` detects identical payload hash and returns `DUPLICATE` with the existing canonical ID.
- **Expected Output:**
  ```
  -> Duplicate Submission Detected: Status=DUPLICATE
  -> Matched Existing Incident: Canonical ID=INC-SNOW-INC0089201
  [PASS] Exact-once idempotent ingestion verified.
  ```

### Stage 8: Security Inspection & Defanging
- **Action:** Ingests ticket containing adversarial prompt injection and `<script>` XSS payload.
- **Verification:** Text is decoded and neutralized: `<script>` tags are removed, and imperative override keywords are neutralized.
- **Expected Output:**
  ```
  -> Ingested Adversarial Ticket: INC-SNOW-INC0099999
  -> Sanitized Description: '[NEUTRALIZED_DIRECT_PROMPT_INJECTION]: Override human review...'
  [PASS] Dangerous script tags defanged and neutral storage confirmed.
  ```

### Stage 9: Dead-Letter Queue (DLQ) Demonstration
- **Action:** Submits malformed payload violating JSON schema.
- **Verification:** Ingestion fails with `NORMALIZATION_ERROR` and is automatically quarantined in the DLQ.
- **Expected Output:**
  ```
  -> Ingestion Rejected: Status=FAILED
  -> Routed to DLQ: Reason=NORMALIZATION_ERROR (Attempts=1)
  [PASS] DLQ routing and quarantine verified.
  ```

### Stage 10: Telemetry & Alarm Correlation
- **Action:** Ingests active Nokia VSWR alarm (`ALM-RAN-VSWR-HIGH`) and Prometheus RF metric vector for element `GNB-RAN-701`.
- **Expected Output:**
  ```
  -> Ingested Nokia Alarm: Canonical ID=ALM-... (Element: GNB-RAN-701)
  -> Ingested RF Telemetry: Canonical ID=OBS-PROM-... (Element: GNB-RAN-701)
  [PASS] Cross-domain alarms and telemetry ingested and topologically mapped.
  ```

### Stage 11: M2-M5 Investigation Execution
- **Action:** Runs investigation engine on incident `INC-SNOW-INC0089201`.
- **Expected Output:**
  ```
  -> Investigated Incident: INC-SNOW-INC0089201
  -> Network Domain: RAN
  -> Evidence Sufficiency: is_sufficient=False
  -> Candidate Hypotheses: 1 generated
  -> Recommendations: 1 generated
  [PASS] Full multi-stage investigation completed.
  ```

### Stage 12: Epistemic Boundary Verification
- **Action:** Verifies that hypothesis text is marked `[HYPOTHESIS]` and `epistemic_status` does not claim confirmed ground truth.
- **Expected Output:**
  ```
  -> Verified Epistemic Categories:
     [OBSERVED FACT] Confirmed from source telemetry & alarms
     [MODEL PREDICTION] Fault category and priority classified
     [HYPOTHESIS] Candidate root cause (NOT confirmed)
     [RECOMMENDATION] Proposed diagnostic procedure (REQUIRES SIGN-OFF)
     [CONFIRMED ROOT CAUSE] NEVER claimed autonomously (Ground Truth Locked)
  [PASS] Epistemic distinctions preserved.
  ```

### Stage 13: Human Approval Workflow Registration
- **Action:** Registers diagnostic recommendation in `HumanApprovalWorkflow`. Initial status is `PENDING_REVIEW`.
- **Expected Output:**
  ```
  -> Registered Recommendation: REC-001 (Status: PENDING_REVIEW)
  [PASS] Recommendation registered in approval workflow.
  ```

### Stage 14: Non-Human Lockout (Service Principal Rejection)
- **Action:** Submits approval request signed with service account token (`SVC-SNOW-POLLER`).
- **Verification:** Rejected with `UnauthenticatedReviewerError: Token subject belongs to a service principal workload identity`.
- **Expected Output:**
  ```
  -> Expected Security Rejection: Token subject 'SVC-SNOW-POLLER' belongs to a service principal workload identity...
  [PASS] Service principal correctly blocked from approving actions.
  ```

### Stage 15: Authorized Operator Approval
- **Action:** NOC Tier-2 operator (`OP-TIER2-01`) reviews and signs recommendation.
- **Expected Output:**
  ```
  -> Approved by Operator: OP-TIER2-01
  -> Recommendation ID: REC-001
  -> Canonical Entry Hash: cfeec0327ed93b25d3dd...
  -> HMAC Signature: ca9de822d7359238e5fd...
  [PASS] Authorized human operator approval cryptographically notarized.
  ```

### Stage 16: Cryptographic Audit Ledger & Anchor Verification
- **Action:** Re-computes SHA-256 hash pointer chain and validates monotonic checkpoint anchor.
- **Expected Output:**
  ```
  -> Audit Entries Verified: 2
  -> Monotonic Anchor State: Sequence=2
  [PASS] RFC 8785 JCS hash chain and anchor integrity verified.
  ```

### Stage 17: Tamper Detection Simulation
- **Action:** Mutates a log record directly on disk (simulating unauthorized modification).
- **Verification:** `load_from_ledger()` detects digest mismatch and raises `AuditTrailDiscontinuityError`.
- **Expected Output:**
  ```
  -> Tamper Detected on Disk Load: Tampered record digest at line 2 (AUD-0002)...
  [PASS] Audit ledger fail-closed on disk tampering confirmed.
  ```

### Stage 18: Final System Summary
- **Action:** Outputs final metrics and readiness summary.
- **Expected Output:**
  ```
  * Execution Status: ALL 18 DEMO STAGES PASSED [OK]
  * Total Demonstration Time: 14.04 seconds (<60s target)
  * Operational Safety Boundary: STRICTLY READ-ONLY (Hard-locked)
  * Automated Test Fleet: 388 / 388 PASSING (0 regressions)
  RESULT: SUCCESS -- PIIS M7 PORTFOLIO RELEASE IS OPERATIONAL AND READY.
  ```

---

## 3. Interpreting Epistemic Tags in the UI

When browsing the dashboard at `http://localhost:8000/ui`:

| Badge | Meaning | Operator Action |
| :--- | :--- | :--- |
| `[OBSERVED FACT]` | Raw telemetry or alarm received from network equipment. | Treat as verified telemetry observation. |
| `[MODEL PREDICTION]` | Supervised machine learning output (domain / severity). | Review classification probability. |
| `[HYPOTHESIS]` | AI/RAG-generated potential cause of the incident. | Evaluate supporting and refuting evidence. |
| `[RECOMMENDATION]` | Suggested diagnostic procedure (read-only safe). | Authorize or reject in Human Review tab. |
| `[HUMAN-APPROVED DECISION]` | Authorized by verified human NOC engineer. | Recorded permanently in audit ledger. |
| `[CONFIRMED ROOT CAUSE]` | Validated ground truth post-resolution. | NEVER claimed automatically by PIIS. |
