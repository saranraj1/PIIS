# ADR-0013: Fail-Closed Checkpoint Integrity, RFC 8785 Canonicalization, and OIDC Concurrency Hardening

- **Status:** Accepted
- **Context:**
  Independent adversarial security revalidation of Milestone M5.3 revealed six implementation defects:
  1. `FIND-M5.3-001`: Direct revocation omission in `ProductionOIDCVerifier.verify_service_token`.
  2. `FIND-M5.3-002`: Nested `threading.Lock()` reentrancy deadlock during session validation and network I/O serialization.
  3. `FIND-M5.3-003`: Non-compliance of canonical JSON serialization with RFC 8785 (JCS) due to ASCII escaping (`ensure_ascii=True`).
  4. `FIND-M5.3-004` & `FIND-M5.3-005`: File-based checkpoint anchor failed open when anchor file was deleted or unreadable for non-empty ledgers, and local host compromise threat boundary required explicit boundary definitions (`DEP-M5.3-002`).
  5. `FIND-M5.3-006`: Transient operational glitches (<5s self-cleared spikes without alarms) were incorrectly supported with active SOPs rather than abstaining to `INCONCLUSIVE`.
- **Decision:**
  1. **OIDC Direct Revocation & Claim Enforcement:**
     - `verify_service_token()` enforces strict algorithm allowlisting (`RS256`, `ES256`), validates `kid`, mandates required claims (`exp`, `iss`, `aud`, `sub`), and actively checks `is_revoked(jti)` and derived `token_id`.
     - Fails closed upon expired, forged, missing, or revoked service credentials with `UnauthenticatedReviewerError`.
  2. **Concurrency & Reentrancy Architecture:**
     - Replace `threading.Lock()` with `threading.RLock()` in `ProductionOIDCVerifier` to allow reentrant calls (`validate_service_session` -> `is_revoked`).
     - Decouple remote HTTPS JWKS retrieval using a dedicated network lock (`_network_lock`), ensuring network socket delays never block in-memory token validations or state lookups.
  3. **Strict RFC 8785 JSON Canonicalization Scheme (JCS):**
     - Replace `json.dumps(..., ensure_ascii=True)` with a pure-Python RFC 8785 serializer.
     - Enforce lexicographical key sorting by UTF-16 code units (RFC 8785 Section 3.2.3).
     - Preserve native UTF-8 bytes for all code points $\ge$ U+0020 (except `"` and `\`).
     - Strictly escape control characters (U+0000..U+001F) to `\u00XX` lowercase hex or standard escapes (`\b`, `\f`, `\n`, `\r`, `\t`).
     - Normalize IEEE 754 numbers: negative zero (`-0.0` $\to$ `0`), integer floats without decimal point, shortest round-trip representation, and reject `NaN` and `Infinity`.
  4. **Fail-Closed Checkpoint Integrity & Host Compromise Boundary:**
     - In `FileBasedCheckpointAnchor.verify_ledger_head()`, fail closed (`False`) if the checkpoint anchor is missing/deleted while the ledger contains records. Only brand-new uninitialized deployments (empty ledger + absent anchor) return `(True, None)`.
     - Propagate corruption and I/O errors rather than silently swallowing them as `None`.
     - Enforce `0o600` owner-only file permissions.
     - Document clear trust boundaries: local file anchors provide tamper-evidence against accidental state loss or unprivileged user modification, whereas enterprise protection against host root compromise requires hardware WORM or cloud immutable blob storage (`DEP-M5.3-002`).
  5. **Transient Event Safety & Heuristic Abstention:**
     - Incident investigation engine evaluates self-cleared transient events (<5s duration, explicit self-healing descriptions) in the absence of active alarms (`len(alarm_codes) == 0`) and telemetry anomalies.
     - Safely marks evidence sufficiency as `is_sufficient=False` and `is_transient_event=True`, classifies top hypothesis as `HypothesisStatus.INCONCLUSIVE`, and routes recommendations strictly to `HUMAN_ESCALATION` (`READ_ONLY_SAFE`).
- **Consequences:**
  - 100% elimination of self-deadlocks and token revocation evasion paths.
  - Full cryptographic compliance with RFC 8785 without breaking historical ASCII v1.0 records.
  - Ledger rollback attacks via anchor file deletion or truncation are detected and blocked.
  - Safe abstention on transient non-fault events prevents disruptive automated runbook execution on self-healed nodes.
  - Milestone M6 remains **UNAUTHORIZED**. Production pilot remains **BLOCKED**. Strictly read-only boundary preserved.
