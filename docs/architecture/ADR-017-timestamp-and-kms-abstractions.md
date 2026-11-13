# ADR-017: Cryptographic Timestamp Authority & KMS Key Provider Abstractions

## Status
Approved (Milestone M7)

## Context
In Milestone M5 and M6, PIIS established cryptographic trust boundaries, including HMAC-SHA256 audit ledgers, RFC 8785 canonical JSON formatting, and signing key provider abstractions. However, full enterprise certification requires integration with hardware-backed Key Management Systems (KMS/HSM) and RFC 3161 compliant Timestamp Authorities (TSA).

In a portfolio or pre-production research setting, direct network access to enterprise hardware security modules (e.g., AWS KMS HSMs, Azure Key Vault Managed HSM) and commercial RFC 3161 TSAs (e.g., DigiCert, Sectigo) is unavailable. Blocking development or release on these unavailable enterprise dependencies halts verification of the surrounding cryptographic protocols.

Conversely, silently falling back to unauthenticated local clocks or ephemeral in-memory keys without strict architectural boundaries creates a false sense of security.

## Decision
1. **Explicit Interface Boundaries:**
   - Formalize `SigningKeyProvider` as the single abstraction for audit ledger cryptographic signing keys.
   - Maintain `LocalDevKeyProvider` strictly for development, testing, and portfolio demonstration, with explicit `UserWarning` telemetry and fail-closed checks in `production` environments.
   - Formalize `ExternalKMSProvider` with pluggable hooks for AWS KMS (`GenerateDataKey`/`Sign`) and Azure Key Vault.
2. **Cryptographic Timestamp Abstraction:**
   - Formalize `TimestampAuthorityProvider` interface requiring `generate_timestamp_token(data_hash)` and `verify_timestamp_token(token, data_hash)`.
   - Provide `LocalUtcTimestampProvider` for standard UTC ISO 8601 timestamps without cryptographic claims.
   - Provide `RFC3161TimestampProvider` modeling real RFC 3161 `TimeStampResp` structures with ASN.1 token simulation, SHA-256 digest binding, and TSA policy identification.
   - Enforce fail-closed verification: production mode strictly requires HTTPS endpoints for RFC 3161 TSAs and rejects simulated providers.

## Consequences
- **Positive:** Enables 100% reproducible local testing and demonstration of ledger signing and timestamp verification without external cloud fees or hardware dependencies.
- **Negative:** Local runs do not carry legally binding non-repudiation in a court of law; this distinction must be visibly documented on all evaluation reports and the UI dashboard.
