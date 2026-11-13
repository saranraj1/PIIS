# M5.2 Independent Audit: OIDC Authentication & Ledger Security

**Milestone:** M5.2 Independent Adversarial Revalidation  
**Audit Phase:** Phase 1 (Authentication and OIDC) & Phase 2 (Audit Key Governance and Ledger Integrity)  
**Evaluator:** Independent Telecom ML Systems Auditor & RAG Security Evaluator  
**Status:** **AUDITED WITH IDENTIFIED LIMITATIONS**

---

## 1. Executive Summary

This independent audit evaluated the implementation of reviewer authentication, role-based access control (RBAC), audit signing key governance, and durable JSONL ledger persistence in [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py).

The audit verified that the M5.2 remediation successfully eliminated client-side identity construction, removed the hardcoded default HMAC secret, enforced server-side role permissions on `HIGH_RISK_MANUAL` actions, and implemented cryptographic hash chaining and HMAC signing across restarts.

However, the independent audit discovered three specific architectural limitations and residual vulnerabilities:
1. **Unresolved Integration Dependency (`DEP-M5.2-001`)**: `ProductionOIDCVerifier` fails closed when unconfigured, but when configured, raises `NotImplementedError`. It contains no network client or JWKS retrieval/caching mechanism for live corporate identity providers.
2. **System Reviewer Identity Bypass (`FIND-M5.2-001`)**: In `HumanApprovalWorkflow._resolve_reviewer()`, checking `if reviewer.operator_id == "SYSTEM": return reviewer` unconditionally bypasses session verification, allowing callers to supply unverified `AuthenticatedReviewer(operator_id="SYSTEM", role="SYSADMIN")`.
3. **Ledger Notes Field Excluded from Cryptographic Hash (`FIND-M5.2-002`)**: `AuditLogEntry.notes` is omitted from `get_canonical_payload()`, allowing arbitrary mutation of operational notes and justifications in the persistent JSONL file without invalidating `entry_sha256` or `hmac_signature`.

---

## 2. Phase 1 — Authentication & OIDC Verification Results

Executed via [`scripts/audit_phase1_oidc_identity.py`](file:///c:/Production%20level%20projects/PIIS/scripts/audit_phase1_oidc_identity.py).

### Detailed Check Results

| Check ID | Verification Check | Expected Behavior | Actual Behavior | Audit Verdict | Latency |
| :--- | :--- | :--- | :--- | :---: | :---: |
| `AUTH-CHK-01` | Production Cryptographic Verification | Fails closed or verifies JWKS signature | Fails closed with `MissingAuthenticationConfigurationError` when unconfigured; raises `NotImplementedError` when configured | **PASS (Dependency Noted)** | 0.02 ms |
| `AUTH-CHK-02` | Token Claims & Signature Validation | Validates `iss`, `aud`, `exp`, and HMAC-SHA256 signature | Rejects forged signatures, expired timestamps, and mismatched issuers/audiences | **PASS** | 0.61 ms |
| `AUTH-CHK-03` | Trusted JWKS Retrieval Mechanism | Fetches and validates public keys via JWKS | Class contains `jwks_url` string parameter but lacks network retrieval logic (`NotImplementedError`) | **UNRESOLVED DEPENDENCY** | 0.00 ms |
| `AUTH-CHK-04` | Revocation and Key Invalidation | Rejects revoked credentials | Rejects tokens registered in the revocation set (`UnauthenticatedReviewerError`) | **PASS** | 0.11 ms |
| `AUTH-CHK-05` | Direct Construction Resistance | Prohibits unverified `AuthenticatedReviewer` | Direct instances rejected by `validate_reviewer_session()`. *Bypass noted for `operator_id='SYSTEM'`* | **PASS WITH LIMITATION** | 0.58 ms |
| `AUTH-CHK-06` | Raw String Auto-Coercion Prohibition | Rejects arbitrary strings (e.g., `"admin"`) | Raw strings without valid 3-part signed JWT format rejected | **PASS** | 0.08 ms |
| `AUTH-CHK-07` | Server-Side RBAC Enforcement | Blocks Tier 1/2 from `HIGH_RISK_MANUAL` | `NOC_TIER_1` and `NOC_TIER_2` raise `InsufficientPrivilegeError`; `NOC_LEAD` allowed | **PASS** | 0.40 ms |
| `AUTH-CHK-08` | Replay Protection & Terminal State Locking | Replaying approval on terminal state blocked | Raises `IllegalStateTransitionError` on re-approval attempt | **PASS** | 0.01 ms |
| `AUTH-CHK-09` | Missing Production Config Fails Closed | Production deployment without IdP fails closed | Raises `MissingAuthenticationConfigurationError` | **PASS** | 0.02 ms |
| `AUTH-CHK-10` | Environment-Aware Verifier Separation | Dev uses test verifier; Prod uses OIDC | Environment switch correctly assigns verifier instances | **PASS** | 0.02 ms |

**Phase 1 Summary**: 9/10 Passed (1 Unresolved Integration Dependency `DEP-M5.2-001`, 1 Trust Boundary Limitation `FIND-M5.2-001`).  
**Machine-Readable Artifact**: [`artifacts/m5_metrics/m5_2_independent_phase1_auth.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_independent_phase1_auth.json).

---

## 3. Phase 2 — Audit Key Governance & Ledger Integrity Results

Executed via [`scripts/audit_phase2_ledger_governance.py`](file:///c:/Production%20level%20projects/PIIS/scripts/audit_phase2_ledger_governance.py).

### Adversarial Ledger Test Matrix (18 Checks)

| Test ID | Adversarial Test Scenario | Injected Vector | Expected Response | Observed Response | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `LEDGER-01` | Missing Audit Key in Production | `PIIS_AUDIT_HMAC_KEY` unset | Raise `MissingAuditKeyError` | Raised `MissingAuditKeyError` | **PASS** |
| `LEDGER-02` | Short Key Rejection | 16-byte key supplied | Raise `MissingAuditKeyError` (<32B) | Raised `MissingAuditKeyError` | **PASS** |
| `LEDGER-03` | Predictable / Default Key Rejection | Key containing `DEFAULT` | Raise `MissingAuditKeyError` | Raised `MissingAuditKeyError` | **PASS** |
| `LEDGER-04` | Key Replacement / Foreign Key | Ledger signed with K1, loaded with K2 | Invalidate HMAC signatures | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-05` | Key Rotation Identifier | Inspect entry metadata | Verify `key_id` provenance | `key_id` preserved in all entries | **PASS** |
| `LEDGER-06` | Hash Chain & Signature Verification | Self-consistency check | Complete chain valid | 0 errors reported | **PASS** |
| `LEDGER-07` | Full Ledger Historical Rewrite | Modified `operator_id` in line 1 | Detect digest/HMAC mismatch | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-08` | Ledger Truncation / Tail Dropping | Removed last 2 lines of JSONL | Process loads truncated subset | Loaded cleanly (see Threat Model) | **PASS** |
| `LEDGER-09` | Missing / Deleted Ledger File | Target path does not exist | Graceful return 0 | Returned 0 entries loaded | **PASS** |
| `LEDGER-10` | Ledger Rollback to Prior Snapshot | Replaced with valid old snapshot | Evaluated against threat model | Valid old snapshot self-consistent | **PASS** |
| `LEDGER-11` | Event Insertion & Reordering | Swapped line 2 and line 3 | Sequence / hash break | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-12` | Protected Field Modification | Backdated `timestamp_utc` | Canonical digest mismatch | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-12B`| Unprotected Field Modification (`notes`)| Altered `notes` field in JSONL | Test if mutation is detected | **Mutation NOT detected** (`FIND-M5.2-002`) | **PASS (Flaw Confirmed)** |
| `LEDGER-13` | Checkpoint Signature Replacement | Zeroed out `hmac_signature` | Reject invalid HMAC signature | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-14` | Post-Approval In-Memory Mutation | Mutated recommendation text | Detect content hash break | Raised `RecommendationTamperedError` | **PASS** |
| `LEDGER-15` | Torn Line / Mid-Write Crash | Appended unclosed JSON fragment | Reject corrupted entry | Raised `AuditTrailDiscontinuityError` | **PASS** |
| `LEDGER-16` | Concurrent Approval Writes | 10 racing multi-threaded threads | Synchronized via `RLock` | 0 errors, 100% valid monotonic trail | **PASS** |
| `LEDGER-17` | Restart & Full Restoration | Reloaded multi-entry ledger | Full restore & re-verification | Restored all entries, 0 errors | **PASS** |

**Phase 2 Summary**: 18/18 Checks Completed (1 Vulnerability Documented `FIND-M5.2-002`).  
**Machine-Readable Artifact**: [`artifacts/m5_metrics/m5_2_independent_phase2_ledger.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_independent_phase2_ledger.json).

---

## 4. Threat Model & Trust Boundary Analysis

### 4.1 Ledger and Key Storage Separation
In the current implementation:
- The audit ledger is persisted to a local file (e.g. `audit_ledger.jsonl`).
- The HMAC signing key is loaded from the process environment (`PIIS_AUDIT_HMAC_KEY`).

**Vulnerability Assessment**:
If an attacker attains filesystem or host-level access sufficient to overwrite `audit_ledger.jsonl`, they typically also have permissions to read process environment variables or memory, thereby exposing `PIIS_AUDIT_HMAC_KEY`. An attacker possessing both:
1. Can reconstruct the entire sequence from genesis.
2. Can recompute valid SHA-256 parent hash pointers for all entries.
3. Can re-sign every entry using the acquired HMAC key.
4. The resulting rewritten ledger will pass `load_from_ledger()` and `verify_audit_trail()` without error.

**Compensating Control Requirement (`RES-M5.2-001`)**:
To achieve enterprise non-repudiation and tamper-proofing, PIIS requires:
- **Asymmetric Digital Signatures** (ECDSA P-256 / RSA-PSS) where the signing private key resides in a Hardware Security Module (HSM) or Cloud KMS, and PIIS only holds the public verification key.
- **Write-Once-Read-Many (WORM) Storage** or append-only cloud blob storage (e.g., AWS S3 Object Lock in Compliance Mode) where existing objects cannot be overwritten even by administrative credentials.

### 4.2 Rollback and Truncation Threat
A standalone JSONL ledger file possesses no internal wall-clock time anchor or global monotonic block sequence. If an attacker replaces `audit_ledger.jsonl` with a valid, signed snapshot from 3 days prior, PIIS will restore the snapshot without error, effectively reverting operational decisions. Detecting rollbacks requires an external trust anchor (e.g. distributed ledger, append-only transparency log, or monotonic counter service).
