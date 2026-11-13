# PIIS M5.4 OIDC & Concurrency Independent Security Audit Report

**Milestone:** PIIS M5.4 — Targeted Security, Integrity & Reliability Remediation  
**Auditor Role:** Independent Security Auditor & Systems Reliability Architect  
**Audit Purpose:** Comprehensive adversarial verification of OIDC token authentication, direct revocation enforcement, principal segregation, and concurrent thread safety  
**Target Codebase:** `src/piis/investigation/approval.py` (`ProductionOIDCVerifier`, `HumanApprovalWorkflow`)  
**Date of Audit:** November 2026  
**Artifact Link:** [artifacts/m5_metrics/m5_4_independent_oidc_concurrency.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_4_independent_oidc_concurrency.json)  

---

## 1. Executive Summary & Audit Statement

```
================================================================================
            PIIS M5.4 OIDC & CONCURRENCY INDEPENDENT AUDIT GATE
================================================================================
  OIDC ADVERSARIAL ATTACKS:    30 / 30 NEUTRALIZED (100.0% Pass Rate)
  CONCURRENT OPERATIONS:       8,000 / 8,000 COMPLETED (5 trials x 16 threads)
  DEADLOCKS DETECTED:          0
  TIMEOUTS DETECTED:           0
  INCONSISTENCIES DETECTED:    0
  LOCK ORDERING VERIFICATION:  VERIFIED (RLock reentrancy + decoupled network lock)
  M5.3 FINDINGS REMEDIATED:    FIND-M5.3-001 (Revocation) & FIND-M5.3-002 (RLock)
================================================================================
```

---

## 2. Phase 1: 30 Adversarial OIDC Attack Vectors

An independent test battery of 30 distinct adversarial attack vectors was executed against `ProductionOIDCVerifier` and `HumanApprovalWorkflow` in [scripts/audit_m5_4_independent_oidc_concurrency.py](file:///c:/Production%20level%20projects/PIIS/scripts/audit_m5_4_independent_oidc_concurrency.py):

| Test ID | Adversarial Test Scenario | Expected Outcome | Observed Result | Status |
|---|---|---|---|:---:|
| **OIDC-01** | Direct `jti` revocation in `verify_service_token()` | Immediate rejection upon presentation | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-02** | Token ID derived from token hash revoked | Derived token ID rejected | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-03** | Service session invalidation post-cache revocation | `validate_service_session()` returns `False` | Session invalidated | **PASS** |
| **OIDC-04** | Human reviewer session invalidation post-cache revocation | `validate_reviewer_session()` returns `False` | Session invalidated | **PASS** |
| **OIDC-05** | Revocation store backend connection failure | Fails closed; token rejected | Rejected safely | **PASS** |
| **OIDC-06** | Token missing mandatory `exp` claim | Rejected by PyJWT claim requirements | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-07** | Expired service token (`exp` in past) | Rejected on signature expiration | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-08** | Token missing mandatory `iss` claim | Rejected by PyJWT claim requirements | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-09** | Token from untrusted issuer URI | Rejected on issuer mismatch | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-10** | Token missing mandatory `aud` claim | Rejected by PyJWT claim requirements | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-11** | Token with mismatched audience | Rejected on audience mismatch | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-12** | Token missing mandatory `sub` claim | Rejected by PyJWT claim requirements | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-13** | Token with future `nbf` (not-before) timestamp | Rejected before validity window opens | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-14** | Unsigned `none` algorithm confusion attack | Rejected by algorithm allowlist | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-15** | Symmetric `HS256` token presented to RS256 verifier | Rejected by algorithm allowlist | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-16** | RS256 token signed by rogue private key | Rejected on signature verification failure | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-17** | Token with unknown `kid` header | Rejected when key not found in JWKS | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-18** | Token completely lacking `kid` header | Rejected during header inspection | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-19** | JWKS key rotation handling | Rotated key accepted cleanly | Handled seamlessly | **PASS** |
| **OIDC-20** | Replay attack: replaying token after revocation | Replayed token blocked | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-21** | Human token presented to `verify_service_token()` | Rejected: missing `principal_type: "SERVICE"` | Segregated cleanly | **PASS** |
| **OIDC-22** | Service token presented to `verify_token()` | Rejected: `sub: "SERVICE"` is prohibited | Segregated cleanly | **PASS** |
| **OIDC-23** | Service principal attempt to approve recommendation | Blocked in `approve_recommendation()` | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-24** | Prohibited operator ID (`ROOT`) in human token | Rejected in `verify_token()` | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-25** | Privilege escalation: `admin: true` in service token | Ignored; strictly scoped to `allowed_scopes` | Least privilege preserved | **PASS** |
| **OIDC-26** | SQL/XSS payload embedded in `sub` claim | Handled strictly as plaintext literal | Zero code execution | **PASS** |
| **OIDC-27** | Blank `jti: ""` handling | Falls back to deterministic SHA-256 ID | Revocation ID populated | **PASS** |
| **OIDC-28** | Mutated signature bytes in JWT | Cryptographic signature failure | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-29** | Truncated two-segment token | Format error caught cleanly | `UnauthenticatedReviewerError` | **PASS** |
| **OIDC-30** | Unconfigured verifier presentation | Fails closed on missing IdP | `UnauthenticatedReviewerError` | **PASS** |

### Verdict on OIDC Verification:
The implementation in `ProductionOIDCVerifier.verify_service_token()` and `verify_token()` fulfills all security criteria. Revocation checks are directly enforced against both explicit `jti` and derived token identifiers. Claim requirements (`exp`, `iss`, `aud`, `sub`) are strictly mandatory. Algorithm allowlists prohibit `none` and `HS256` symmetric confusion attacks.

---

## 3. Phase 2: Concurrency, Deadlock & Stress Testing

### 3.1 Concurrency Stress Architecture
To rigorously evaluate `FIND-M5.3-002` (which previously produced a self-deadlock due to non-reentrant locking), the verifier was subjected to **5 repeated randomized trials**:
- **Concurrency Level:** 16 concurrent worker threads per trial.
- **Operations per Worker:** 100 randomized operations (session validations, active token verifications, revocation checks, cache reads, and invalid token floods).
- **Total Concurrent Operations Executed:** **8,000 operations**.
- **Bounded Timeout:** 10.0 seconds per trial batch.

### 3.2 Trial-by-Trial Empirical Results

```
+-------+-------------------+----------------------+--------------------+--------------------+
| Trial | Duration (s)      | Ops Completed        | Throughput (ops/s) | Errors / Deadlocks |
+-------+-------------------+----------------------+--------------------+--------------------+
| 1     | 0.050 s           | 1,600                | 31,971.4 ops/sec   | 0 errors, 0 hangs  |
| 2     | 0.041 s           | 1,600                | 39,090.5 ops/sec   | 0 errors, 0 hangs  |
| 3     | 0.034 s           | 1,600                | 46,752.0 ops/sec   | 0 errors, 0 hangs  |
| 4     | 0.039 s           | 1,600                | 41,164.5 ops/sec   | 0 errors, 0 hangs  |
| 5     | 0.038 s           | 1,600                | 42,192.1 ops/sec   | 0 errors, 0 hangs  |
+-------+-------------------+----------------------+--------------------+--------------------+
| TOTAL | 0.202 s           | 8,000 ops            | ~39,600 ops/sec avg| 0 DEADLOCKS        |
+-------+-------------------+----------------------+--------------------+--------------------+
```

### 3.3 Latency Percentiles Under Concurrent Stress
Across all 8,000 concurrent operations:
- **Latency P50:** **0.001 ms**
- **Latency P95:** **0.114 ms**
- **Latency P99:** **0.151 ms**
- **Maximum Observed Latency:** < 1.2 ms
- **Deadlocks Detected:** **0**
- **Timeouts Detected:** **0**
- **State Inconsistencies:** **0**

### 3.4 Lock Ordering & Network Decoupling Inspection
Static and dynamic inspection of `ProductionOIDCVerifier` confirms:
1. `self._lock` is instantiated as `threading.RLock()`. Reentrant acquisitions (e.g. `validate_reviewer_session()` $\to$ `is_revoked()`) succeed without blocking.
2. `self._network_lock` is instantiated as `threading.Lock()`.
3. In `_get_signing_key(kid)`:
   - Cache inspection occurs under `self._lock`.
   - If cache is stale or missing, `self._lock` is **released**.
   - `self._network_lock` is acquired for remote HTTPS retrieval.
   - HTTP socket I/O executes completely outside `self._lock`.
   - After fetch, `self._lock` is re-acquired only to update the in-memory `_jwks_cache` dictionary.
4. This lock ordering eliminates the vulnerability where slow or hung IdP network connections block local memory validations.

---

## 4. Final Security Findings & Status

- **FIND-M5.3-001 (Service Token Direct Revocation):** **CLOSED (VERIFIED)**.
- **FIND-M5.3-002 (Reentrant Lock Concurrency & Deadlocks):** **CLOSED (VERIFIED)**.
- **DEP-M5.3-001 (Live Enterprise IdP Provisioning):** **OPEN**. Must remain open until production deployment connects to an authentic corporate IdP.
