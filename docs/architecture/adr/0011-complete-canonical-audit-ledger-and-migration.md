# ADR-0011: Complete Canonical Audit Ledger, Schema Versioning, and Legacy Migration

- **Status:** Accepted
- **Decision:**
  1. Upgrade the audit trail ledger to Schema Version 2.0 (`v2.0`).
  2. Require full cryptographic coverage: Include `notes`, `key_id`, `schema_version`, `principal_type`, and `authorization_scope` in the canonical payload, SHA-256 payload hash, and HMAC-SHA256 signature computation.
  3. Enforce RFC 8785 (JSON Canonicalization Scheme) serialization: deterministic key sorting by UTF-16 code units, no whitespace between tokens (`separators=(',', ':')`), native UTF-8 encoding (`ensure_ascii=False`), and strict float normalization via `canonical_json_dumps()`.
  4. Preserve backward compatibility for historical audit ledgers: When parsing legacy `v1.0` records, re-compute integrity using the legacy 7-field canonical representation, verify signatures, and set `notes_cryptographically_covered = False`.
  5. Prevent retroactive claims: When upgrading a `v1.0` ledger via `migrate_ledger_v1_to_v2()`, append an authenticated `MIGRATION_CHECKPOINT` entry carrying the final v1 hash anchor, timestamp, and migrating principal signature, while preserving original v1 entries byte-for-byte.
- **Context:** The M5.2 independent adversarial revalidation identified `FIND-M5.2-002`, discovering that `notes` was omitted from the canonical hash dictionary. This allowed a malicious actor with write access to the JSONL log file to rewrite operator notes, comments, or justification text without failing hash-chain verification or invalidating HMAC signatures.
- **Consequences:** Completely eliminates audit note tampering and attribute injection vectors. Ensures end-to-end non-repudiation for all human reviewer commentary. Preserves historical audit logs without breaking tamper-evident validation across version boundaries.
