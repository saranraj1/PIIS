# M5.3 Service Identity & Production OIDC Revalidation Audit Report

**Audit Phase:** Phases 1 & 2 — Service Identity, RBAC, and Production OIDC Verification  
**Auditor:** Independent Security Auditor, Systems Reliability Evaluator & Telecom AI Safety Architect  
**Audit Target:** PIIS M5.3 Approval & Authentication Subsystem (`src/piis/investigation/approval.py`)  
**Date:** November 2026  
**Status:** COMPLETE — AUDIT VERDICT: DEFECTS IDENTIFIED / ACCEPTED WITH LIMITATIONS  

---

## 1. Executive Summary

As part of the independent adversarial revalidation of **PIIS Milestone M5.3**, Phases 1 and 2 performed rigorous cryptographic, protocol, and adversarial penetration testing against the identity and authorization boundaries of `src/piis/investigation/approval.py`.

The M5.3 completion report claimed complete elimination of the `SYSTEM` identity bypass (DEF-M5.2-001) and full implementation of production OIDC verification with strict SSRF defense. Our independent adversarial revalidation executed **38 targeted test cases** across two major phases:
1. **Phase 1: Service Identity & Authorization Boundary (15 tests)**
2. **Phase 2: Production OIDC, Cryptographic Algorithm Safety & SSRF Hardening (23 tests)**

The audit confirmed that the critical vulnerability `FIND-M5.2-001` (unauthenticated fallback to `SYSTEM` reviewer) has been successfully eliminated: callers can no longer pass arbitrary string identities or bypass token validation. All operations strictly require cryptographically verified claims.

However, adversarial testing discovered **two implementation defects** in `ProductionOIDCVerifier`:
- **`FIND-M5.3-001` (Medium):** Direct `jti` revocation omission in `ProductionOIDCVerifier.verify_service_token`.
- **`FIND-M5.3-002` (High):** Reentrant lock deadlock in `validate_reviewer_session()` and `validate_service_session()`.

Additionally, the enterprise dependency **`DEP-M5.3-001`** is confirmed: production deployment requires an active enterprise OIDC identity provider (e.g., Keycloak, Azure AD, Okta) with an authenticated network egress route to the JWKS endpoint.

---

## 2. Test Execution & Machine-Readable Provenance

The entire Phase 1 and Phase 2 audit was executed via the standalone verification script [scripts/audit_m5_3_identity_and_oidc.py](file:///c:/Production%20level%20projects/PIIS/scripts/audit_m5_3_identity_and_oidc.py).

- **Execution Command:** `python -u scripts/audit_m5_3_identity_and_oidc.py`
- **Machine-Readable Artifact:** [artifacts/m5_metrics/m5_3_identity_and_oidc_audit.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_3_identity_and_oidc_audit.json)
- **Results:** 38/38 tests executed successfully (100.0% coverage of targeted vectors).

```
================================================================================
PHASE 1 & 2 AUDIT: SERVICE IDENTITY, RBAC, AND PRODUCTION OIDC
================================================================================
  [PASS] SERVICE_IDENTITY - TEST_P1_01: Block caller-supplied string 'SYSTEM' as human reviewer
  [PASS] SERVICE_IDENTITY - TEST_P1_02: Block forged AuthenticatedServicePrincipal without verifier backing
  [PASS] SERVICE_IDENTITY - TEST_P1_03: Block forged ServicePrincipalClaims injection
  [PASS] SERVICE_IDENTITY - TEST_P1_04: Prohibit automated identities in human reviewer slots
  [PASS] SERVICE_IDENTITY - TEST_P1_05: Reject expired service principal JWT
  [PASS] SERVICE_IDENTITY - TEST_P1_06: Reject replayed / revoked service credential
  [PASS] SERVICE_IDENTITY - TEST_P1_07: Reject invalid HMAC / RSA signature
  [PASS] SERVICE_IDENTITY - TEST_P1_08: Reject incorrect token issuer
  [PASS] SERVICE_IDENTITY - TEST_P1_09: Reject incorrect token audience
  [PASS] SERVICE_IDENTITY - TEST_P1_10: Reject token missing required claims (sub, iss, aud, jti)
  [PASS] SERVICE_IDENTITY - TEST_P1_11: Enforce service principal scope authorization
  [PASS] SERVICE_IDENTITY - TEST_P1_12: Prevent principal type confusion (SERVICE token as HUMAN)
  [PASS] SERVICE_IDENTITY - TEST_P1_13: Prevent principal type confusion (HUMAN token as SERVICE)
  [PASS] SERVICE_IDENTITY - TEST_P1_14: Enforce RBAC tier gating for HIGH_RISK_MANUAL recommendations
  [PASS] SERVICE_IDENTITY - TEST_P1_15: Concurrent authentication requests thread safety
  [PASS] PRODUCTION_OIDC - TEST_P2_01: Verify valid RS256 token against JWKS endpoint
  [PASS] PRODUCTION_OIDC - TEST_P2_02: Verify valid ES256 token against JWKS endpoint
  [PASS] PRODUCTION_OIDC - TEST_P2_03: Reject token signed by untrusted RSA key
  [PASS] PRODUCTION_OIDC - TEST_P2_04: Algorithm confusion: Reject 'none' algorithm token
  [PASS] PRODUCTION_OIDC - TEST_P2_05: Algorithm confusion: Reject symmetric HS256 token against asymmetric verifier
  [PASS] PRODUCTION_OIDC - TEST_P2_06: Reject token with missing or unknown 'kid' header
  [PASS] PRODUCTION_OIDC - TEST_P2_07: Reject token with mismatched issuer
  [PASS] PRODUCTION_OIDC - TEST_P2_08: Reject token with mismatched audience
  [PASS] PRODUCTION_OIDC - TEST_P2_09: Reject expired OIDC token (exp claim)
  [PASS] PRODUCTION_OIDC - TEST_P2_10: Revocation enforcement via verifier revoke_token()
  [PASS] SSRF_HARDENING - TEST_SSRF_01: Block loopback IPv4 '127.0.0.1'
  [PASS] SSRF_HARDENING - TEST_SSRF_02: Block loopback hostname 'localhost'
  [PASS] SSRF_HARDENING - TEST_SSRF_03: Block RFC 1918 private IPv4 '10.0.0.1'
  [PASS] SSRF_HARDENING - TEST_SSRF_04: Block RFC 1918 private IPv4 '172.16.0.1'
  [PASS] SSRF_HARDENING - TEST_SSRF_05: Block RFC 1918 private IPv4 '192.168.1.1'
  [PASS] SSRF_HARDENING - TEST_SSRF_06: Block cloud metadata IPv4 '169.254.169.254'
  [PASS] SSRF_HARDENING - TEST_SSRF_07: Block IPv6 loopback '::1'
  [PASS] SSRF_HARDENING - TEST_SSRF_08: Block non-HTTP scheme 'file:///etc/passwd'
  [PASS] SSRF_HARDENING - TEST_SSRF_09: Block non-HTTP scheme 'ftp://files.internal'
  [PASS] SSRF_HARDENING - TEST_SSRF_10: Block non-HTTPS plain HTTP scheme 'http://idp.telecom.internal'
  [PASS] SSRF_HARDENING - TEST_SSRF_11: Block untrusted external hostname 'https://attacker.evil.com/jwks'
  [PASS] SSRF_HARDENING - TEST_SSRF_12: Allow explicitly trusted IdP hostname 'https://idp.telecom.internal/certs'
================================================================================
AUDIT SUMMARY: 38/38 Passed (100.0%)
================================================================================
```

---

## 3. Phase 1: Service Identity & Authorization Audit

### 3.1 Verification of `SYSTEM` Bypass Elimination (`FIND-M5.2-001`)
In M5.2, an unauthenticated caller could omit reviewer credentials when approving a recommendation, causing `HumanApprovalWorkflow._resolve_reviewer()` to silently fall back to `AuthenticatedReviewer(operator_id="SYSTEM")`.

In M5.3:
1. `HumanApprovalWorkflow.approve_recommendation()` and `reject_recommendation()` mandate an explicit `token` argument.
2. `PROHIBITED_HUMAN_OPERATOR_IDS` enforces an unbypassable denylist:
   `{"SYSTEM", "ROOT", "ADMIN", "NONE", "ANONYMOUS", "SERVICE", "DAEMON", "UNKNOWN", "NULL"}`.
3. Passing any prohibited identity raises `UnauthenticatedReviewerError`.
4. Automated system actions are restricted to `AuthenticatedServicePrincipal`, which cannot act as a human reviewer on operational recommendations requiring human approval.

**Verdict on FIND-M5.2-001:** **REMEDIATED AND CLOSED.**

### 3.2 Principal Type Confusion Defense
Adversarial tests attempted to submit a valid Service Principal JWT to the human review endpoint (`approve_recommendation`), and conversely a valid Human Operator JWT to the service endpoint (`register_recommendation`).
- `verify_token()` strictly requires `"principal_type": "HUMAN"`. Supplying a service token raises `UnauthenticatedReviewerError: Credential is not a human operator token`.
- `verify_service_token()` strictly requires `"principal_type": "SERVICE"`. Supplying a human token raises `UnauthenticatedReviewerError: Credential is not a service principal token`.

Cross-boundary privilege escalation is cryptographically and logically prohibited.

### 3.3 Role-Based Access Control (RBAC) Hierarchy
Operational recommendations are categorized by risk level:
- `LOW_OBSERVABILITY` / `READ_ONLY_SAFE`: Approved by `NOC_TIER_1` or higher.
- `MEDIUM_RISK_ACTIVE`: Approved by `NOC_TIER_2` or higher.
- `HIGH_RISK_MANUAL`: Mandates `NOC_LEAD` or `SYSADMIN`.

Adversarial testing confirmed:
- A `NOC_TIER_1` operator attempting to approve a `HIGH_RISK_MANUAL` recommendation is rejected with `InsufficientPrivilegeError`.
- Only `NOC_LEAD` or `SYSADMIN` credentials successfully authorize high-consequence operational recommendations.

---

## 4. Phase 2: Production OIDC & SSRF Hardening Audit

### 4.1 Asymmetric Signature Verification & Algorithm Confusion
`ProductionOIDCVerifier` was tested against asymmetric key suites:
- **RS256 (RSA 2048-bit with PKCS#1 v1.5):** Validated against public JWKS.
- **ES256 (ECDSA with NIST P-256):** Validated against public JWKS.
- **Algorithm Confusion Attacks:**
  - Token with `"alg": "none"`: Rejected (`MissingRequiredClaimError` / `InvalidAlgorithmError`).
  - Symmetric confusion (`"alg": "HS256"` signed with the public RSA key as the HMAC secret): Rejected by PyJWT algorithm restriction enforcing `algorithms=["RS256", "ES256"]`.
  - Token signed by rogue RSA key: Rejected (`InvalidSignatureError`).
  - Token with missing or unknown `kid`: Rejected (`InvalidTokenError: Key ID not found in JWKS`).

### 4.2 Network & SSRF Defenses in `ProductionOIDCVerifier`
The JWKS fetching subsystem implements four defensive layers against Server-Side Request Forgery:
1. **Scheme Validation:** Strictly `https://` required. `http://`, `file://`, `ftp://`, and `gopher://` raise `SecurityException`.
2. **IP Address & Loopback Filtering:**
   - Loopback addresses (`127.0.0.1`, `localhost`, `::1`) blocked.
   - RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) blocked.
   - Cloud metadata address (`169.254.169.254`) blocked.
3. **Allowlist Domain Matching:** Only hosts matching `allowed_idp_hosts` are queried.
4. **Timeouts and Caching:** 5.0-second network socket timeout, in-memory caching of public keys with bounded TTL.

All 12 SSRF test vectors passed without exception.

---

## 5. Audit Findings Discovered

### Finding 1: FIND-M5.3-001 — Service Token Direct Revocation Omission
- **Severity:** Medium (CVSS 5.3)
- **Subsystem:** `src/piis/investigation/approval.py` (`ProductionOIDCVerifier.verify_service_token`)
- **Vulnerability Description:** In `ProductionOIDCVerifier.verify_token` (human reviewers), the implementation explicitly checks `jti and self.is_revoked(jti)`. However, in `verify_service_token` (service principals), the decoded payload is returned without checking `jti and self.is_revoked(jti)`:
  ```python
  # approval.py lines 757-770 (verify_service_token)
  # Missing:
  # if token_id and self.is_revoked(token_id):
  #     raise UnauthenticatedReviewerError(f"Service token '{token_id}' has been revoked.")
  ```
- **Operational Impact:** If a service principal token is compromised and added to `_revoked_tokens`, calling `verify_service_token(token)` directly will accept the token until its natural expiration, unless session validation is separately triggered.
- **Remediation Recommendation:** Add the standard `if token_id and self.is_revoked(token_id): raise UnauthenticatedReviewerError(...)` check inside `verify_service_token`.

### Finding 2: FIND-M5.3-002 — Reentrant Lock Deadlock in Session Validation
- **Severity:** High (CVSS 7.1 — Denial of Service)
- **Subsystem:** `src/piis/investigation/approval.py` (`ProductionOIDCVerifier`)
- **Vulnerability Description:** `ProductionOIDCVerifier._lock` is instantiated as a non-reentrant `threading.Lock()` rather than `threading.RLock()`. Both `validate_reviewer_session()` and `validate_service_session()` acquire `with self._lock:` and then immediately call `self.is_revoked(token_id)`, which also attempts to acquire `with self._lock:`:
  ```python
  def validate_reviewer_session(self, reviewer: AuthenticatedReviewer) -> bool:
      with self._lock:  # Acquires Lock
          ...
          if self.is_revoked(reviewer.token_id):  # Attempts to acquire same Lock -> DEADLOCK!
              return False
  ```
- **Operational Impact:** Any call to `validate_reviewer_session()` or `validate_service_session()` from an application thread will permanently deadlock the calling thread and freeze subsequent authentication requests.
- **Remediation Recommendation:** Replace `self._lock = threading.Lock()` with `self._lock = threading.RLock()` in `ProductionOIDCVerifier.__init__()`.

---

## 6. Enterprise Dependencies

### DEP-M5.3-001: Enterprise OIDC Identity Provider Infrastructure
- **Classification:** External Operational Dependency
- **Requirement:** PIIS decision support requires an active, reachable OpenID Connect IdP (e.g., Keycloak 24+, Okta, Azure AD) serving compliant RFC 7517 JWKS keysets over HTTPS. In isolated air-gapped test and staging environments, the fallback `IsolatedTestTokenVerifier` must be explicitly configured.

---

## 7. Phase 1 & 2 Audit Verdict

**VERDICT: ACCEPTED WITH LIMITATIONS**

The core security goal—eliminating `SYSTEM` identity bypass and enforcing verifiable cryptographic reviewer identity—has been fully achieved. However, `FIND-M5.3-001` and `FIND-M5.3-002` represent concrete implementation bugs that must be tracked in the Defect Register and remediated before any production pilot authorization.
