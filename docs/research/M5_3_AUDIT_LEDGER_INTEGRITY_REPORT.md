# M5.3 Research Report: Complete Canonical Audit Ledger, Schema Migration, and Monotonic Rollback Protection

- **Milestone:** M5.3 — Trust Boundary & Audit Integrity Remediation
- **Date:** 2026-11-01
- **Status:** COMPLETED & VERIFIED
- **Related Defect IDs:** `FIND-M5.2-002`, `RES-M5.2-001`
- **Related ADRs:** [ADR-0011](file:///c:/Production%20level%20projects/PIIS/docs/architecture/adr/0011-complete-canonical-audit-ledger-and-migration.md), [ADR-0012](file:///c:/Production%20level%20projects/PIIS/docs/architecture/adr/0012-external-monotonic-rollback-protection.md)

---

## 1. Executive Summary & Problem Formulation

Audit findings in the M5.2 independent revalidation revealed two ledger vulnerabilities:
1. **`FIND-M5.2-002` (Ledger Canonicalization Defect):** `AuditLogEntry.notes` was excluded from the canonical serialization payload used to compute the SHA-256 entry hash and HMAC signature. An attacker with filesystem access could alter operator notes, justification records, or operational instructions without breaking hash chains or triggering signature verification errors.
2. **`RES-M5.2-001` (Ledger Rollback & Truncation Vulnerability):** In-place file verification only checked intra-file chain continuity. If a rogue administrator truncated the JSONL file or restored an earlier valid backup, the system accepted the truncated state without detecting that newer approval records had been erased.

---

## 2. Technical Implementation

### 2.1 Schema Version 2.0 & RFC 8785 Canonicalization
In `src/piis/investigation/approval.py`:
1. Updated `AuditLogEntry` to include schema versioning (`schema_version: str = "v2.0"`), key identifier (`key_id`), principal classification (`principal_type`), authorization scopes (`authorization_scope`), and cryptographic coverage tracking (`notes_cryptographically_covered: bool = True`).
2. Implemented strict RFC 8785 canonical JSON serialization via `canonical_json_dumps()`:
   - Keys sorted by Unicode codepoints (UTF-16 code unit order).
   - Zero whitespace delimiters (`separators=(',', ':')`).
   - Native unescaped UTF-8 encoding (`ensure_ascii=False`).
   - Deterministic IEEE-754 float formatting.
3. In Schema 2.0, the canonical payload dictionary explicitly incorporates `notes`:
   ```python
   canonical_payload = {
       "action": self.action,
       "authorization_scope": self.authorization_scope,
       "incident_id": self.incident_id,
       "key_id": self.key_id,
       "notes": self.notes,
       "operator_id": self.operator_id,
       "prev_entry_hash": self.prev_entry_hash,
       "principal_type": self.principal_type,
       "recommendation_id": self.recommendation_id,
       "schema_version": self.schema_version,
       "sequence_index": self.sequence_index,
       "timestamp": self.timestamp,
   }
   ```
4. Tampering with any byte of `notes` alters `entry_hash` and invalidates the HMAC signature.

### 2.2 Backward Compatibility & Safe Ledger Migration
1. When reading existing logs, `AuditLogEntry.from_dict()` inspects `schema_version`:
   - If `v1.0` (or absent), it evaluates integrity using the legacy 7-field format and sets `notes_cryptographically_covered = False`.
   - If `v2.0`, it evaluates integrity using the full 12-field schema and validates `notes_cryptographically_covered = True`.
2. Created `migrate_ledger_v1_to_v2()`:
   - Validates all legacy v1 entries against legacy hash-chain rules.
   - Appends an authenticated `MIGRATION_CHECKPOINT` entry signed with the current key.
   - Preserves all historical bytes without making retroactive authenticity claims for legacy notes.

### 2.3 External Monotonic Checkpoint Anchoring (`ExternalCheckpointAnchor`)
1. Defined `ExternalCheckpointAnchor` abstract base class with methods `record_checkpoint(sequence_index, entry_hash)` and `get_latest_checkpoint()`.
2. Implemented `FileBasedCheckpointAnchor` with thread-safe `threading.RLock()` and atomic file swap semantics (`tempfile` + `os.replace`).
3. Integrated anchor verification into `HumanApprovalWorkflow.load_from_ledger()` and append methods:
   - If loaded sequence count or latest entry hash lags behind or diverges from the external anchor, the system immediately raises `LedgerRollbackDetectedError`.
   - Halts further operations to prevent state replay.

---

## 3. Verification & Empirical Results

The implementation was validated against unit tests in `tests/unit/test_m5_3_audit_ledger_canonicalization.py` and `tests/unit/test_m5_3_rollback_protection.py`:

| Test ID | Objective | Result |
| :--- | :--- | :--- |
| `test_v2_canonical_payload_includes_notes` | Verify `notes` is present in canonical representation | **PASS** |
| `test_v2_notes_tampering_detected` | Mutating notes breaks HMAC and hash chain | **PASS** |
| `test_rfc8785_canonical_json_dumps_determinism` | Deterministic ordering, zero whitespace, unicode preserving | **PASS** |
| `test_v1_legacy_loading_backward_compatibility` | Legacy v1.0 entries load and verify with `notes_cryptographically_covered = False` | **PASS** |
| `test_ledger_v1_to_v2_migration_checkpoint` | Migration checkpoint appended cleanly without breaking chain | **PASS** |
| `test_file_checkpoint_anchor_recording_and_monotonicity` | Anchor records and verifies sequence monotonically | **PASS** |
| `test_ledger_truncation_detected_by_anchor` | Truncating entries raises `LedgerRollbackDetectedError` | **PASS** |
| `test_ledger_substitution_detected_by_anchor` | Swapping with divergent ledger raises `LedgerRollbackDetectedError` | **PASS** |

**Summary:** 10/10 targeted ledger canonicalization and rollback protection tests passing (100.0%).

---

## 4. Enterprise Threat Model & Production Dependency

`DEP-M5.3-002` is formally logged in `docs/DEFECT_REGISTER.md`:
- **Threat Boundary:** `FileBasedCheckpointAnchor` protects against accidental operator rollback and application-layer tampering. However, an attacker with local OS root permissions can simultaneously modify both the JSONL ledger and the local anchor file.
- **Enterprise Requirement:** Production deployments must bind `ExternalCheckpointAnchor` to a hardware WORM storage service (e.g. AWS S3 Object Lock, Azure Immutable Blob Storage) or an enterprise KMS notary.
