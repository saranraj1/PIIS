# PIIS UI-5 — Identity & Approval Security Audit

**Milestone:** UI-5 Human Review Hub  
**Status:** COMPLETE & GROUNDED  
**Date:** 2026-11-03  
**Security Baseline:** 4-Ring Defense-in-Depth, Zero-Trust Identity, RFC 8785 Audit Trail  

---

## 1. Executive Summary

This audit assesses the identity verification, authorization gating, tamper-evidence, and session integrity mechanisms governing the UI-5 Human Review Hub. Consequential operational decisions require strict human accountability; therefore, PIIS enforces uncompromising cryptographic boundaries to ensure that automated bots, service accounts, and unprivileged callers can never masquerade as human reviewers.

---

## 2. Reviewer Identity Verification & Extraction

### 2.1 Server-Side Context Isolation
- **Mechanism:** In `src/piis/api/routers/incidents.py`, the endpoint `submit_human_review` relies on FastAPI dependency injection:
  ```python
  principal: AuthenticatedPrincipal = Depends(require_human_operator),
  credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
  workflow: HumanApprovalWorkflow = Depends(get_workflow)
  ```
- **Trust Anchor:** The caller's identity is extracted directly from the signed JSON Web Token (JWT) in the `Authorization: Bearer <token>` header, verified against trusted enterprise JWKS keys (`ProductionOIDCVerifier`) or isolated development test keys (`IsolatedTestTokenVerifier`).
- **No Client-Supplied Identity:** The client JSON schema (`ReviewSubmissionRequest`) intentionally omits `operator_id`, `user_id`, or `reviewer_name`:
  ```python
  class ReviewSubmissionRequest(BaseModel):
      recommendation_id: str
      decision: str
      review_notes: str
  ```
  An attacker attempting to inject `{"operator_id": "OP-LEAD-999"}` in the request body achieves nothing; Pydantic either ignores or disallows extraneous fields, and the endpoint exclusively uses `principal.principal_id`.

### 2.2 Frontend Token Handling
- **Non-Authoritative Frontend:** In `frontend/src/auth/AuthContext.tsx`, client-side JWT decoding is utilized solely for user interface customization (e.g., displaying the operator username and role badge).
- **Zero Frontend Authorization:** The frontend never performs client-side permission checks to grant access to secure operations. Every backend call independently validates token cryptographic signatures, expiration (`exp`), issuer (`iss`), audience (`aud`), and revocation status before permitting any review decision.

---

## 3. Human Operator vs. Service Principal Separation

### 3.1 The Service Principal Bypass Defense
In telecom automation, automated poller daemons, monitoring bots, and ETL pipelines frequently interact with the API. However, allowing automated systems to sign off on diagnostic checks defeats human accountability.

- **FastAPI Guard (`require_human_operator`):**
  ```python
  async def require_human_operator(
      principal: AuthenticatedPrincipal = Depends(get_current_principal),
  ) -> AuthenticatedPrincipal:
      if principal.is_service_principal:
          raise HTTPException(
              status_code=status.HTTP_403_FORBIDDEN,
              detail=(
                  f"Forbidden: Principal '{principal.principal_id}' is an automated service account. "
                  "Human approval is legally and architecturally mandatory."
              ),
          )
      return principal
  ```
- **Workflow State Machine Guard (`HumanApprovalWorkflow._resolve_reviewer`):**
  Even if an internal caller bypasses the REST layer and calls Python methods directly:
  ```python
  if isinstance(reviewer, AuthenticatedServicePrincipal):
      raise InsufficientPrivilegeError(
          f"Service principal '{reviewer.service_id}' cannot approve, reject, or modify human recommendations. "
          "Consequential decisions require authenticated human operator credentials."
      )
  ```
- **Prohibited Operator Names:**
  Identities matching `{"SYSTEM", "ANONYMOUS", "UNKNOWN", "NONE", "ROOT", "ADMIN", "NULL", "SERVICE"}` are rejected immediately by `AuthenticatedReviewer.validate_operator_id()`.

---

## 4. Role-Based Access Control (RBAC) & Privilege Tiering

### 4.1 Endpoint Privilege Enforcement
`submit_human_review` strictly checks that the authenticated operator possesses an operational review role:
```python
allowed_roles = {
    ApplicationRole.NOC_L1,
    ApplicationRole.NOC_L2,
    ApplicationRole.NOC_L3,
    ApplicationRole.INCIDENT_MANAGER,
}
if not any(r in allowed_roles for r in principal.roles):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Forbidden: Operator '{principal.principal_id}' lacks review authorization",
    )
```
Principals with roles such as `SECURITY_AUDITOR` or `PIIS_ADMIN` are rejected with HTTP 403 Forbidden.

### 4.2 High-Risk Action Privilege Tiering
Certain diagnostic checks involve intrusive network testing (e.g., feeder sweeps, active packet injection). These are categorized as `HIGH_RISK_MANUAL`.
- `HumanApprovalWorkflow.approve_recommendation` enforces:
  ```python
  if rec.risk_classification == RecommendationRisk.HIGH_RISK_MANUAL:
      if reviewer.role not in ("NOC_LEAD", "SYSADMIN"):
          raise InsufficientPrivilegeError(
              f"Operator '{reviewer.operator_id}' with role '{reviewer.role}' is not authorized "
              f"to approve HIGH_RISK_MANUAL action '{recommendation_id}'. Requires NOC_LEAD or SYSADMIN."
          )
  ```
- Lower-tier operators (`NOC_L1`, `NOC_L2`) cannot approve high-risk operations even if authenticated.

---

## 5. Cryptographic Audit Ledger Protection

### 5.1 RFC 8785 Canonical JSON Binding
Every human decision (approval or rejection) is encapsulated in an `AuditLogEntry` adhering to schema version 2.0. The canonical payload covers:
- `action`: `"APPROVED"` or `"REJECTED"`
- `audit_id`: Monotonic ID (`AUD-0001`, `AUD-0002`, ...)
- `incident_id`: Canonical incident identifier
- `recommendation_id`: Recommendation identifier
- `previous_status` & `new_status`: State transition
- `operator_id`: Verified human operator identifier
- `reviewer_role`: Verified role
- `reviewer_auth_hash`: SHA-256 digest of session token
- `notes`: **Reviewer notes or rejection justification**
- `recommendation_content_hash`: SHA-256 digest of recommendation content
- `previous_entry_sha256`: Pointer to preceding ledger record

### 5.2 Cryptographic Guarantees
1. **RFC 8785 Canonicalization:** Enforces deterministic sorting of JSON keys and IEEE 754 floating-point normalization.
2. **SHA-256 Hash Chaining:** Any alteration of past records breaks `previous_entry_sha256` in all descendant entries.
3. **HMAC-SHA256 Signature:** Protects every record with an HMAC key (`PIIS_AUDIT_HMAC_KEY`), preventing unauthorized creation of synthetic valid records.
4. **External Monotonic Checkpoint Anchor:** `FileBasedCheckpointAnchor` (or cloud KMS anchor) records `(sequence_number, entry_sha256, hmac_signature)` outside the ledger, preventing truncation and rollback attacks.

---

## 6. Duplicate Submission & Replay Resistance

- **Terminal State Lockout:** `ApprovalStatus` transitions from `PENDING_REVIEW` to either `APPROVED` or `REJECTED`. Once in a terminal state, subsequent submissions raise `IllegalStateTransitionError`.
- **HTTP 409 Conflict:** The REST gateway maps `IllegalStateTransitionError` to HTTP 409 Conflict with a clear error explanation.
- **Client Duplicate Prevention:** The frontend UI disables action buttons immediately upon submission, preventing double-clicks, and renders a terminal locked panel once approved/rejected.

---

## 7. Security Audit Ledger

| Security Control | Threat Mitigated | Implementation | Verification Status |
| :--- | :--- | :--- | :---: |
| **Server-Side Identity Extraction** | Identity spoofing / Impersonation | `require_human_operator` + JWT claims | **VERIFIED** |
| **No Client Operator Field** | Client parameter tampering | Pydantic `ReviewSubmissionRequest` | **VERIFIED** |
| **Service Account Block** | Automated bot approval | `principal.is_service_principal` check | **VERIFIED** |
| **Role Tiering (NOC_L1-L3)** | Privilege escalation | `ApplicationRole` checks | **VERIFIED** |
| **Lead Tiering for High Risk** | Unsafe manual diagnostic approval | `RecommendationRisk.HIGH_RISK_MANUAL` check | **VERIFIED** |
| **Notes Integrity Binding** | Justification tampering | RFC 8785 canonical hash coverage | **VERIFIED** |
| **Terminal State Machine** | Replay & duplicate approval | `IllegalStateTransitionError` -> 409 | **VERIFIED** |
| **Monotonic External Anchor** | Ledger truncation / Rollback | `ExternalCheckpointAnchor` | **VERIFIED** |

---

## 8. Conclusion

Milestone UI-5 preserves all existing security invariants and cryptographic guarantees. The Human Review Hub establishes an airtight chain of custody from authenticated human login to immutable audit record generation, with zero production network execution privileges.
