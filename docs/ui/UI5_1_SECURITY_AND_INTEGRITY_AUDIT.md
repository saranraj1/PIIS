# PIIS UI-5.1 — Human Review Security, Persistence & Integrity Closure Audit

**Project:** Production Incident Intelligence System (PIIS — Telecom Edition)  
**Milestone:** UI-5.1 — Human Review Security, Persistence & Integrity Closure Audit  
**Date:** November 3, 2026  
**Status:** COMPLETE & CERTIFIED  
**Operational Scope:** Strictly Read-Only Decision Support with Authenticated Audit Notarization  

---

## 1. Executive Summary

Milestone UI-5.1 executes a rigorous independent security, persistence, concurrency, and integrity audit of the completed PIIS UI-5 Human Review Hub. The audit establishes whether human review operations remain dependable under adversarial inputs, high-concurrency contention, server restarts, storage failures, and malicious client tampering.

### Audit Verdict Summary
- **Authentication & Identity (Critical Audit A):** **CERTIFIED**. The FastAPI backend operates as the final authorization boundary. Bearer tokens are cryptographically verified; service principals are strictly blocked (HTTP 403); client-side body tampering of reviewer identity is rejected/ignored.
- **Approval State Machine & Concurrency (Critical Audit B):** **CERTIFIED**. State transitions are protected by `threading.RLock()`. In a 10-thread concurrent race condition, exactly 1 thread succeeds (HTTP 200) and 9 fail (HTTP 409 Conflict). Terminal states cannot be replayed or overwritten.
- **Persistence & Restart Recovery (Critical Audit C):** **CERTIFIED WITH QUALIFIED SPECIFICATION**. The durable JSONL audit ledger writes entries to disk upon approval/rejection. Re-instantiating the workflow with `load_from_ledger()` reconstructs terminal states, operator identities, and incident associations while preserving terminal lockout.
- **Atomicity & Failure Injection (Critical Audit D):** **CERTIFIED**. Memory mutations are wrapped in rollback guards. If disk write or ledger append fails, in-memory state reverts to `PENDING_REVIEW`, preventing state/ledger divergence.
- **Cryptographic Integrity (Critical Audit E):** **CERTIFIED**. RFC 8785 canonical JSON serialization deterministically binds incident ID, recommendation ID, operator ID, timestamp, decision, and operator technical rationale notes. HMAC-SHA256 provides symmetric authenticated tamper-evidence.

---

## 2. Classified Security & Reliability Findings

| Finding ID | Severity | Category | Description | Original Behavior | Remediated Behavior & Evidence |
|---|---|---|---|---|---|
| **FIND-UI5.1-001** | **HIGH** | Concurrency / Exception Ordering | `IllegalStateTransitionError` caught as generic `ValueError` | `IllegalStateTransitionError` inherits from `ValueError`. When caught after `except ValueError:`, duplicate reviews returned HTTP 400 Bad Request instead of HTTP 409 Conflict. | Reordered exception handlers in `submit_human_review`: `IllegalStateTransitionError` and `InsufficientPrivilegeError` are handled before `ValueError`. Test `test_audit_b2_terminal_state_replay_fails_with_409` passes with HTTP 409. |
| **FIND-UI5.1-002** | **HIGH** | Atomicity / State Divergence | State and ledger diverged on disk write failure | In `approve_recommendation` and `reject_recommendation`, `rec.approval_status` was updated in memory *before* calling `_create_and_append_entry`. If disk append failed, in-memory state was permanently terminal without an audit record. | Implemented transactional rollback in `approval.py`: if `_create_and_append_entry` fails, `rec.approval_status`, reviewer ID, timestamp, and notes revert to prior values. Verified via `test_audit_d1_atomicity_failure_injection_rolls_back_memory_state`. |
| **FIND-UI5.1-003** | **MEDIUM** | Integrity / Data Binding | Incident ID association mismatch silently accepted | If an operator called `POST /api/v1/incidents/INC-AAA/reviews` with a recommendation belonging to `INC-BBB`, the recommendation's incident association was silently overwritten. | Added explicit check in `approval.py`: `existing_incident != incident_id` raises `ValueError` mapped to HTTP 400 Bad Request. Verified via `test_audit_b6_incident_association_mismatch_returns_400`. |
| **FIND-UI5.1-004** | **MEDIUM** | Accountability / Schema | Whitespace-only reviewer notes accepted | `ReviewSubmissionRequest` allowed blank or whitespace-only `review_notes` for approvals, violating accountability requirements. | Added `@field_validator("review_notes")` in `src/piis/api/schemas.py` rejecting empty/whitespace strings with HTTP 422. Verified via `test_audit_b4_missing_or_whitespace_notes_rejected_with_422`. |
| **FIND-UI5.1-005** | **LOW** | Persistence / Reconciliation | Missing incident restoration in `load_from_ledger` | `load_from_ledger()` populated `self._recommendations` from JSONL entries but omitted `self._recommendation_incidents` and `rec.incident_id`. | Added `self._recommendation_incidents[entry.recommendation_id] = entry.incident_id` and `rec.incident_id = entry.incident_id` in `load_from_ledger()`. Verified via `test_audit_c1_durable_ledger_append_and_restart_recovery`. |
| **FIND-UI5.1-006** | **LOW** | Terminology / Documentation | HMAC-SHA256 described as digital signature | Prior reports occasionally referred to HMAC-SHA256 as a "cryptographic signature" without specifying symmetric MAC characteristics. | Clarified across all artifacts: HMAC-SHA256 is a symmetric Message Authentication Code providing authenticated tamper-evidence, not asymmetric public-key non-repudiation. |

---

## 3. Critical Audit A: Authentication & Identity

### Verification Scope
Audit A inspects `require_human_operator` ([`src/piis/auth/dependencies.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/auth/dependencies.py)), `AuthManager` ([`src/piis/auth/manager.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/auth/manager.py)), and token verifiers ([`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py)).

### Test Evidence Table
| Sub-Test | Condition | Expected Response | Observed Response | Result |
|---|---|---|---|---|
| **A1** | Missing Authorization Header | HTTP 401 Unauthorized | HTTP 401 (`Missing or malformed Bearer authorization token`) | **PASS** |
| **A2** | Forged / Corrupted JWT Signature | HTTP 401 Unauthorized | HTTP 401 (`Authentication failed: Cryptographic signature verification failed`) | **PASS** |
| **A3** | Expired JWT (`exp` in past) | HTTP 401 Unauthorized | HTTP 401 (`Authentication failed: Token expired`) | **PASS** |
| **A4.1** | Untrusted Issuer (`iss`) | HTTP 401 Unauthorized | HTTP 401 (`Authentication failed: Wrong token issuer`) | **PASS** |
| **A4.2** | Untrusted Audience (`aud`) | HTTP 401 Unauthorized | HTTP 401 (`Authentication failed: Wrong token audience`) | **PASS** |
| **A5** | Non-NOC Role (`SECURITY_AUDITOR`) | HTTP 403 Forbidden | HTTP 403 (`Forbidden: Operator lacks review authorization`) | **PASS** |
| **A6** | Service Principal (`is_service=True`) | HTTP 403 Forbidden | HTTP 403 (`Forbidden: Principal is an automated service account`) | **PASS** |
| **A7** | Request Body Spoofing (`operator_id="HACKER"`) | Body Ignored, Token Bound | HTTP 200, `reviewed_by` bound strictly to token subject | **PASS** |
| **A8** | Malformed / Garbled Token String | HTTP 401 Unauthorized | HTTP 401 (`Authentication failed: Invalid token format`) | **PASS** |
| **A9** | Distinct Concurrent Reviewers | Independent Attestations | HTTP 200 on all 5 distinct concurrent operator threads | **PASS** |

**Conclusion:** The backend strictly enforces the authentication boundary. Client-side identity attributes in JSON payloads are completely disregarded in favor of cryptographically verified token claims.

---

## 4. Critical Audit B: Approval State Machine & Concurrency

### Verification Scope
Audit B verifies the state transitions of `DiagnosticRecommendation` across `PENDING_REVIEW`, `APPROVED`, and `REJECTED`, testing thread safety under race conditions.

### Concurrency Race Test Execution
In `test_audit_b1_conflicting_concurrent_submissions_exactly_one_succeeds`:
- A single recommendation `REC-RACE-001` in `PENDING_REVIEW` was subjected to 10 simultaneous threads in a `ThreadPoolExecutor`.
- Alternating threads submitted `APPROVED` and `REJECTED`.
- **Results:**
  - Exactly **1 thread succeeded** (`HTTP 200 OK`).
  - Exactly **9 threads failed** with `HTTP 409 Conflict` (`IllegalStateTransitionError: Cannot approve recommendation in terminal state`).
  - The recommendation in memory reached exactly one final state matching the winning thread's decision.
  - Zero state corruption, zero duplicate audit append.

### State Transition Validation Matrix
| Initial State | Action | Request Condition | Outcome | HTTP Status |
|---|---|---|---|---|
| `PENDING_REVIEW` | `APPROVED` | Valid token + notes | Transitions to `APPROVED` | 200 OK |
| `PENDING_REVIEW` | `REJECTED` | Valid token + notes | Transitions to `REJECTED` | 200 OK |
| `APPROVED` | `APPROVED` | Duplicate replay | Rejected: already terminal | 409 Conflict |
| `APPROVED` | `REJECTED` | Conflicting replay | Rejected: already terminal | 409 Conflict |
| `REJECTED` | `APPROVED` | Conflicting replay | Rejected: already terminal | 409 Conflict |
| `PENDING_REVIEW` | `REQUEST_MORE_EVIDENCE` | Non-supported decision | Rejected: invalid value | 400 Bad Request |
| `PENDING_REVIEW` | `APPROVED` | Empty notes (`""` / `"   "`) | Rejected: schema validation | 422 Unprocessable |
| Any | Any | Unknown recommendation ID | Rejected: not found | 404 Not Found |
| Any | Any | Incident mismatch (`INC-AAA` vs `INC-BBB`) | Rejected: association mismatch | 400 Bad Request |

---

## 5. Critical Audit E: Cryptographic Integrity & Tamper Evidence

### 1. Canonicalization Standard (RFC 8785)
PIIS uses `canonical_json_dumps()` implementing the RFC 8785 JSON Canonicalization Scheme (JCS):
- Lexicographically sorted dictionary keys at all nesting levels.
- Strict whitespace elimination (no whitespace after `:` or `,`).
- UTF-8 string encoding without non-ASCII escape sequences.
- Deterministic output: independent re-serializations produce identical byte sequences.

### 2. Payload Structure & Cryptographic Coverage
The canonical payload covers all security-relevant metadata:
```json
{
  "action": "APPROVED",
  "audit_id": "AUD-0002",
  "authorization_scope": "NOC_L2",
  "incident_id": "INC-SNOW-INC0089201",
  "key_id": "piis-audit-key-2026-v2",
  "new_status": "APPROVED",
  "notes": "Reviewed BGP flap timestamps; verified safe read-only query.",
  "operator_id": "OP-TIER2-01",
  "previous_entry_sha256": "8f9a2b...",
  "previous_status": "PENDING_REVIEW",
  "principal_type": "HUMAN",
  "recommendation_content_hash": "c4d5e6...",
  "recommendation_id": "REC-001",
  "reviewer_auth_hash": "1a2b3c...",
  "reviewer_role": "NOC_L2",
  "schema_version": "2.0",
  "sequence_number": 2,
  "timestamp_utc": "2026-11-03T10:15:00.000000+00:00"
}
```

### 3. Terminology & Cryptographic Classification
- **HMAC-SHA256:** A symmetric Message Authentication Code. It provides **authenticated tamper-evidence** using a shared secret key (minimum 32 bytes). It proves that the record was created by an entity holding the secret key and that no field has been altered since creation.
- **Asymmetric Signature Distinction:** HMAC-SHA256 does **not** provide mathematical non-repudiation against an entity that possesses the secret key. Full asymmetric digital signatures (e.g. ECDSA P-256) and external WORM timestamps represent future production roadmap items (`DEP-M5.5.1-001a`, `DEP-M5.5.1-001b`).

---

## 6. Audit Conclusion

Milestone UI-5.1 confirms that the PIIS Human Review Hub enforces all architectural and epistemic invariants. The system fails closed under adversarial input, preserves concurrency safety under multi-threaded races, guarantees atomicity between in-memory state and the cryptographic ledger, and accurately reports its operational boundaries.
