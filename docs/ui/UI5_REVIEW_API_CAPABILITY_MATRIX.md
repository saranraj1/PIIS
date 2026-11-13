# PIIS UI-5 — Review API Capability Matrix & Backend Audit

**Milestone:** UI-5 Human Review Hub  
**Status:** COMPLETE & GROUNDED  
**Date:** 2026-11-03  
**Operational Scope:** Strictly Read-Only Decision Support  

---

## 1. Executive Summary

Before introducing the UI-5 Human Review Hub, an exhaustive audit of the existing PIIS backend review and approval capabilities was conducted. This audit inspected:
- `src/piis/investigation/approval.py` (`HumanApprovalWorkflow`, `AuditLogEntry`, `AuthenticatedReviewer`, `AuthenticatedServicePrincipal`)
- `src/piis/investigation/schemas.py` (`ApprovalStatus`, `DiagnosticRecommendation`, `RecommendationRisk`)
- `src/piis/auth/manager.py` & `src/piis/auth/dependencies.py` (`require_human_operator`, `ApplicationRole`, `Permission`)
- `src/piis/api/routers/incidents.py` (`submit_human_review`, `get_incident_recommendations`, `investigate_incident`)
- `src/piis/api/routers/audit.py` (`list_audit_records`, `verify_audit_ledger`)
- `src/piis/pipeline/unified.py` (`UnifiedIngestionPipeline`, `_investigations`)

This matrix provides definitive, evidence-backed answers to the 8 core operational questions required by the UI-5 specification.

---

## 2. Definitive Backend Capability Analysis

### 2.1 What review operations are actually supported?
- **`approve_recommendation` (`HumanApprovalWorkflow`):**
  Transitions a recommendation from `ApprovalStatus.PENDING_REVIEW` to `ApprovalStatus.APPROVED`. Records authenticated operator identity, UTC timestamp, and technical justification notes. Creates and appends an immutable `APPROVED` entry to the cryptographic audit trail with HMAC signature and hash chain pointer.
- **`reject_recommendation` (`HumanApprovalWorkflow`):**
  Transitions a recommendation from `ApprovalStatus.PENDING_REVIEW` to `ApprovalStatus.REJECTED`. Enforces a mandatory, non-empty rejection justification reason. Creates and appends an immutable `REJECTED` entry to the cryptographic audit trail.
- **`register_recommendation` (`HumanApprovalWorkflow`):**
  Registers a newly generated recommendation awaiting operator review with initial status `PENDING_REVIEW`. Strictly restricted to authenticated internal service principals possessing the `SCOPE_INTERNAL_REGISTRATION` authorization scope. Appends a `SUBMITTED` entry to the audit ledger.
- **`modify_recommendation` (`HumanApprovalWorkflow`):**
  Supports operator-approved parameter modifications in the underlying state machine. *Note: This operation is currently internal to the workflow engine and is not exposed on the REST gateway.*
- **REST Gateway Submission (`POST /api/v1/incidents/{incident_id}/reviews`):**
  Exposes human operator approval and rejection to HTTP clients. Validates caller credentials, bars automated service accounts, validates operator role authorization, invokes workflow approval or rejection, appends to the audit ledger, and returns a cryptographic audit receipt.

### 2.2 Which decisions are accepted by the backend?
- **Accepted decisions:** Exactly two decision strings:
  1. **`APPROVED`**
  2. **`REJECTED`**
  Input is case-insensitive on the REST gateway and normalized via `.upper().strip()`.
- **Unsupported decisions:**
  - **`REQUEST_MORE_EVIDENCE` is NOT supported** by the backend API.
  - Passing any value other than `"APPROVED"` or `"REJECTED"` (e.g., `"REQUEST_MORE_EVIDENCE"`, `"HOLD"`, `"DEFER"`, `"PASS"`) immediately triggers HTTP 400 Bad Request:
    ```json
    {
      "error": "HTTP_ERROR",
      "detail": "Review decision must be 'APPROVED' or 'REJECTED'"
    }
    ```
- **Operator guidance for insufficient evidence:**
  When evidence is insufficient or contradictory, the operator must either:
  1. Reject the recommendation with an explicit note (e.g., *"Rejected: telemetry signals contradictory; awaiting additional feeder sweep"*), or
  2. Withhold action until additional telemetry is ingested and re-investigated.

### 2.3 How is reviewer identity established?
- **Server-Side Extraction:** Reviewer identity is established **exclusively** from verified cryptographic claims extracted from the HTTP `Authorization: Bearer <token>` header.
- **Zero Client Spoofing:** The client request schema (`ReviewSubmissionRequest`) contains only:
  - `recommendation_id: str`
  - `decision: str`
  - `review_notes: str`
  There is no client-controllable `operator_id`, `user_id`, or `reviewer_name` field.
- **Human vs. Service Principal Separation:**
  The `require_human_operator` FastAPI dependency inspects `principal.is_service_principal`. If true, the request is immediately rejected with HTTP 403 Forbidden:
  > *"Forbidden: Principal '...' is an automated service account. Human approval is legally and architecturally mandatory."*
- **Role Tiering:**
  `submit_human_review` verifies that the caller holds at least one of: `NOC_L1`, `NOC_L2`, `NOC_L3`, or `INCIDENT_MANAGER`. Non-operational roles (such as `SECURITY_AUDITOR` or `PIIS_ADMIN`) receive HTTP 403 Forbidden.
- **High-Risk Elevation:**
  For recommendations classified as `HIGH_RISK_MANUAL`, `HumanApprovalWorkflow.approve_recommendation` enforces that `reviewer.role` must be `NOC_LEAD` or `SYSADMIN`. Lower tiers receive `InsufficientPrivilegeError` (mapped to HTTP 409 Conflict).

### 2.4 Are notes and rejection reasons included in integrity protection?
- **Yes.** In schema version 2.0 (`AuditLogEntry`), reviewer notes are explicitly included in `get_canonical_payload()`:
  ```python
  canonical_payload = {
      "action": action,
      "audit_id": audit_id,
      "authorization_scope": authorization_scope,
      "incident_id": incident_id,
      "key_id": self._key_id,
      "new_status": new_status.value,
      "notes": notes or "",  # Cryptographically bound
      "operator_id": operator_id,
      "previous_entry_sha256": prev_hash,
      "previous_status": prev_status.value,
      "principal_type": principal_type,
      "recommendation_content_hash": content_hash,
      "recommendation_id": rec.recommendation_id,
      "reviewer_auth_hash": reviewer_auth_hash,
      "reviewer_role": reviewer_role,
      "schema_version": "2.0",
      "sequence_number": seq,
      "timestamp_utc": timestamp,
  }
  ```
- **Cryptographic Binding:**
  - Serialized via RFC 8785 JSON Canonicalization Scheme (JCS).
  - SHA-256 hashed into `entry_sha256`.
  - HMAC-SHA256 signed into `hmac_signature`.
  - Field `notes_cryptographically_covered = True` is guaranteed.
- Tampering with notes after the fact breaks both the hash chain and HMAC verification.

### 2.5 Are review records immutable?
- **Yes.**
  - **In-Memory Ledger:** Records are appended to a monotonic, lock-protected list (`_audit_trail`). No update or delete methods exist.
  - **Hash Chain:** Each record embeds `previous_entry_sha256` pointing to the immediately preceding record, forming a cryptographic Merkle-like chain starting at `GENESIS_CHECKPOINT`.
  - **Disk Persistence:** When configured with a `ledger_path`, entries are appended as immutable JSONL lines (`open("a")`).
  - **Monotonic External Anchor:** `FileBasedCheckpointAnchor` or `ExternalKMSCheckpointAnchor` stores state outside the ledger, immediately detecting truncation, rollback, or deletion.
  - **In-Memory Mutation Guard:** `_approved_content_hashes` caches the canonical content hash of approved recommendations; if mutated in memory, `verify_recommendation_binding()` raises `RecommendationTamperedError`.

### 2.6 How do duplicate submissions and retries behave?
- **Terminal State Lockout:**
  Once a recommendation transitions to `APPROVED` or `REJECTED`, its state is terminal.
  ```python
  if rec.approval_status != ApprovalStatus.PENDING_REVIEW:
      raise IllegalStateTransitionError(
          f"Cannot approve recommendation '{recommendation_id}' in terminal state '{rec.approval_status.value}'. "
          f"Replays and duplicate approvals are strictly prohibited."
      )
  ```
- **HTTP 409 Conflict:**
  The REST gateway catches `IllegalStateTransitionError` and returns **HTTP 409 Conflict**:
  ```json
  {
    "error": "HTTP_ERROR",
    "detail": "Approval workflow rejected review: Cannot approve recommendation '...' in terminal state 'APPROVED'. Replays and duplicate approvals are strictly prohibited."
  }
  ```
- **Fail-Closed Retries:** Retrying an already approved or rejected recommendation will **never** create a duplicate audit entry or overwrite the initial decision.

### 2.7 Which review states can actually be retrieved?
- **Supported Review States:**
  1. `PENDING_REVIEW`: Recommendation registered and awaiting human review.
  2. `APPROVED`: Recommendation approved by an authorized human operator.
  3. `REJECTED`: Recommendation rejected with recorded justification.
- **Retrieval Endpoints:**
  - `GET /api/v1/incidents/reviews/queue`: Aggregated review queue across incidents.
  - `GET /api/v1/incidents/{incident_id}/recommendations`: Returns recommendations for an investigated incident.
  - `GET /api/v1/incidents/{incident_id}/investigation`: Returns full investigation context with recommendations.
  - `GET /api/v1/incidents/{incident_id}/reviews`: Returns decision audit history for an incident.
  - `GET /api/v1/audit/records`: Returns global audit ledger records.

### 2.8 Which information is unavailable?
1. **`REQUEST_MORE_EVIDENCE` State:** Not present in `ApprovalStatus` enum or state machine.
2. **Individual Reviewer Pre-Assignment:** PIIS recommendations are not pre-assigned to individual users; they exist in a shared NOC pool accessible to authorized operators.
3. **Multi-Party Simultaneous Dual Sign-Off:** While role tiering exists (`NOC_LEAD` for high risk), multi-signature (M-of-N) simultaneous approval is not implemented.
4. **Automated Remediation Execution Status:** PIIS is strictly read-only decision support. Recommendations have no downstream execution plane.

---

## 3. Review Capability Matrix Summary

| Capability | Backend Support | REST Endpoint | Authorization Requirement | Epistemic Category |
| :--- | :---: | :--- | :--- | :--- |
| **List Review Queue** | **YES** | `GET /api/v1/incidents/reviews/queue` | `Permission.VIEW_RECOMMENDATIONS` | `RECOMMENDATION` |
| **Inspect Incident Recommendations** | **YES** | `GET /api/v1/incidents/{id}/recommendations` | `Permission.VIEW_RECOMMENDATIONS` | `RECOMMENDATION` |
| **Inspect Incident Review History** | **YES** | `GET /api/v1/incidents/{id}/reviews` | `Permission.VIEW_RECOMMENDATIONS` | `HUMAN_APPROVED_DECISION` |
| **Submit Operator Approval** | **YES** | `POST /api/v1/incidents/{id}/reviews` (`decision: "APPROVED"`) | Human Operator (`NOC_L1`, `L2`, `L3`, `INCIDENT_MANAGER`) | `HUMAN_APPROVED_DECISION` |
| **Submit Operator Rejection** | **YES** | `POST /api/v1/incidents/{id}/reviews` (`decision: "REJECTED"`) | Human Operator (`NOC_L1`, `L2`, `L3`, `INCIDENT_MANAGER`) | `HUMAN_APPROVED_DECISION` |
| **Request More Evidence** | **NO** | *None (Returns 400 Bad Request)* | N/A | N/A |
| **Modify Procedure** | **PARTIAL** | Internal state machine only | Internal only | `HUMAN_APPROVED_DECISION` |
| **Pre-assigned Reviewer** | **NO** | *None* | N/A | N/A |
| **Automated Command Execution** | **FORBIDDEN** | *None (Strictly Read-Only)* | N/A | N/A |

---

## 4. Architectural Grounding & Conclusion

The capability matrix confirms that PIIS possesses robust, cryptographically sound approval and audit primitives. The frontend Human Review Hub must strictly align with these realities:
1. Provide only `APPROVED` and `REJECTED` decision pathways.
2. Rely entirely on server-side identity extraction without client-supplied operator fields.
3. Transparently present contradictory evidence and missing telemetry before allowing sign-off.
4. Display cryptographic audit receipts immediately upon backend confirmation.
5. Reiterate that human review decisions do not trigger or authorize automated production execution.
