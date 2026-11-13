# M5.3 Research Report: Service Principal Identity, SYSTEM Bypass Elimination, and OIDC Trust Boundaries

- **Milestone:** M5.3 — Trust Boundary & Audit Integrity Remediation
- **Date:** 2026-11-01
- **Status:** COMPLETED & VERIFIED
- **Related Defect IDs:** `FIND-M5.2-001`, `DEP-M5.2-001`
- **Related ADR:** [ADR-0010](file:///c:/Production%20level%20projects/PIIS/docs/architecture/adr/0010-service-principal-and-oidc-trust-boundaries.md)

---

## 1. Executive Summary & Problem Formulation

In the M5.2 independent revalidation, audit finding `FIND-M5.2-001` identified an unauthenticated identity bypass in `HumanApprovalWorkflow._resolve_reviewer()`:
```python
# DEFECTIVE CODE (M5.2):
if operator_id == "SYSTEM":
    return AuthenticatedReviewer(
        operator_id="SYSTEM",
        role="AUTOMATION",
        auth_token="system_internal",
        claims={"scope": "system"},
    )
```
Any caller supplying `operator_id="SYSTEM"` without an `auth_token` completely bypassed server-side cryptographic token verification. This allowed arbitrary processes or attackers with API access to inject automated decisions masquerading as the core system. Furthermore, `DEP-M5.2-001` noted that `ProductionOIDCVerifier` was a skeleton without complete cryptographic asymmetric verification, JWKS rotation, or network SSRF protections.

---

## 2. Technical Implementation

### 2.1 Complete Elimination of SYSTEM String Bypass
In `src/piis/investigation/approval.py`:
1. The unconditional `operator_id == "SYSTEM"` bypass was completely excised from `_resolve_reviewer()`.
2. A strict blacklist of prohibited operator identities was introduced:
   ```python
   PROHIBITED_HUMAN_OPERATOR_IDS: Set[str] = {
       "SYSTEM",
       "ANONYMOUS",
       "ROOT",
       "DAEMON",
       "ADMIN",
       "SUPERUSER",
       "INTERNAL",
   }
   ```
   Direct instantiation or presentation of an `AuthenticatedReviewer` using any prohibited identity raises `UnauthenticatedReviewerError`.

### 2.2 Formal Workload Identity & Least-Privilege Scoping
Internal automated services and asynchronous ingestion pipelines require a legitimate mechanism to register incidents and submit observational telemetry without masquerading as human operators. To accomplish this cleanly:
1. `ServicePrincipalClaims` and `AuthenticatedServicePrincipal` classes were created with Pydantic validation.
2. Standardized service principal scopes were defined:
   - `SCOPE_INTERNAL_REGISTRATION = "piis.internal.register_incident"`
   - `SCOPE_READ_ONLY_OBSERVATION = "piis.internal.observe"`
   - `SCOPE_DIAGNOSTIC_QUERY = "piis.internal.query_diagnostic"`
3. Role enforcement was implemented: Service principals are strictly barred from invoking `approve_recommendation()`, `reject_recommendation()`, or `modify_recommendation()`. Any attempt to execute a human decision using a service principal immediately raises `InsufficientPrivilegeError`.

### 2.3 Production OIDC Cryptographic Verifier (`ProductionOIDCVerifier`)
Implemented using `PyJWT` (2.12.1) and `cryptography` (46.0.7):
- **Asymmetric Signature Verification:** Parses public keys from JSON Web Key Sets (`JWKS`) supporting `RS256` and `ES256`.
- **SSRF Defenses:** Validates JWKS URLs:
  - Enforces `https://` protocol.
  - Requires domain matching against `allowed_jwks_domains`.
  - Proactively blocks private and internal IP ranges: RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), and cloud instance metadata service (`169.254.169.254`).
- **Key Caching & Dynamic Rotation:**
  - In-memory key caching with configurable TTL (default 3600 seconds).
  - Throttled cache refresh on encountering an unknown `kid` (minimum 60-second cooldown) to eliminate cache-stampede / Denial-of-Service attacks against the IdP.
- **Fail-Closed Semantics:** Token verification fails closed if the IdP is unreachable and keys are not cached.
- **Revocation Tracking:** In-memory revoked token ID (`jti`) registry.

---

## 3. Verification & Empirical Results

The implementation was validated against a dedicated test suite (`tests/unit/test_m5_3_system_identity.py` and `tests/unit/test_m5_3_oidc_verification.py`):

| Test ID | Test Objective | Result |
| :--- | :--- | :--- |
| `test_system_operator_id_bypass_eliminated` | Passing `operator_id="SYSTEM"` without token is rejected | **PASS** |
| `test_prohibited_human_identities_rejected` | `ANONYMOUS`, `ROOT`, `DAEMON` rejected | **PASS** |
| `test_service_principal_cannot_approve` | Service principal attempting recommendation approval raises `InsufficientPrivilegeError` | **PASS** |
| `test_service_principal_can_register_incident` | Internal registration with `SCOPE_INTERNAL_REGISTRATION` succeeds | **PASS** |
| `test_successful_rs256_oidc_verification` | Valid RS256 token verified against mock JWKS | **PASS** |
| `test_key_rotation_and_cache_refresh` | Dynamic key rollover with cached public keys | **PASS** |
| `test_unknown_key_id_rejected` | Unregistered `kid` rejected | **PASS** |
| `test_disallowed_algorithm_rejected` | Algorithm confusion (`HS256` or `none`) rejected | **PASS** |
| `test_expired_token_rejected` | Expired tokens rejected with `UnauthenticatedReviewerError` | **PASS** |
| `test_ssrf_protection_blocks_internal_ips` | Private IPs and metadata endpoint (`169.254.169.254`) blocked | **PASS** |

**Summary:** 18/18 targeted identity and authentication tests passing (100.0%).

---

## 4. Enterprise Integration Dependency

`DEP-M5.3-001` is formally logged in `docs/DEFECT_REGISTER.md`:
- **Requirement:** Live enterprise OIDC Identity Provider (e.g., Azure AD / Entra ID, Okta, Keycloak) endpoint configuration and client credentials must be provisioned before staging or production deployment.
- **Decision:** The cryptographic verification engine is fully implemented and tested. Production readiness is constrained by external enterprise infrastructure provisioning, adhering to strict zero-trust principles without mocking in production.
