# ADR-0010: Service Principal Scopes, Elimination of SYSTEM Bypass, and Cryptographic OIDC Trust Boundaries

- **Status:** Accepted
- **Decision:** 
  1. Completely eliminate the unconditional `operator_id == "SYSTEM"` string bypass in `HumanApprovalWorkflow._resolve_reviewer()`.
  2. Prohibit human reviewers from claiming reserved identity strings (`SYSTEM`, `ANONYMOUS`, `ROOT`, `DAEMON`, `ADMIN`, `SUPERUSER`), raising `UnauthenticatedReviewerError` at both validation and verification time.
  3. Formalize internal workload identity through `ServicePrincipalClaims` and `AuthenticatedServicePrincipal`. Workload entities must present cryptographically verified tokens carrying authorized service scopes (`piis.internal.register_incident`, `piis.internal.observe`, `piis.internal.query_diagnostic`).
  4. Enforce strict least-privilege boundary rules: Service principals are permitted solely to register incidents and observe system metrics; they are strictly prohibited from approving, rejecting, or modifying human-in-the-loop diagnostic recommendations, raising `InsufficientPrivilegeError`.
  5. Implement `ProductionOIDCVerifier` for corporate IdP integration supporting asymmetric key verification (`RS256`, `ES256`) via JSON Web Key Sets (JWKS), in-memory key caching with TTL (3600s), throttled cache refresh (60s minimum interval) upon unknown `kid` detection, and explicit token revocation tracking (`jti`).
  6. Harden JWKS endpoints against SSRF attacks: enforce HTTPS, require hostname allowlisting (`allowed_jwks_domains`), and proactively block RFC 1918 private ranges, loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), and AWS/GCP cloud metadata IP endpoints (`169.254.169.254`).
  7. Formally track live enterprise IdP URL configuration and credential deployment as external prerequisite dependency `DEP-M5.3-001`.
- **Context:** The M5.2 independent adversarial revalidation identified `FIND-M5.2-001` (SYSTEM identity bypass in approval workflow) and `DEP-M5.2-001` (incomplete production OIDC verifier). Any unauthenticated client could pass `operator_id="SYSTEM"` without an auth token to bypass cryptographic verification, creating an unverified lateral movement vector.
- **Consequences:** Eliminates all unauthenticated paths in the human approval subsystem. Prevents autonomous or programmatic agents from bypassing human operational authority. Protects token verification infrastructure against SSRF and JWKS cache poisoning. Provides full cryptographic assurance that every human action is backed by an authenticated operator identity.
