# ADR-0012: External Monotonic Checkpoint Anchoring and Rollback Protection

- **Status:** Accepted
- **Decision:**
  1. Introduce the `ExternalCheckpointAnchor` abstract base class to decouple ledger persistence from external monotonic state verification.
  2. Implement `FileBasedCheckpointAnchor` with strict atomic file updates and thread-safe `threading.RLock()` synchronization as the reference local anchor.
  3. Validate ledger monotonicity on all append and recovery operations: Whenever a new audit entry is written or the ledger is loaded from disk, the current sequence index and cumulative SHA-256 entry hash are compared against the anchor.
  4. If the loaded sequence index is lower than the anchored index or the entry hash does not match, raise `LedgerRollbackDetectedError` immediately and fail-closed.
  5. Define the enterprise threat model: While local filesystem anchors mitigate accidental rollback and local file swapping, true defense-in-depth against host-level root compromise requires external WORM (Write-Once-Read-Many) storage or a cloud KMS ledger notary. Formally record this production infrastructure integration requirement as `DEP-M5.3-002`.
- **Context:** Residual risk finding `RES-M5.2-001` noted that while hash-chaining detects intra-file tampering, a privileged host actor could truncate the JSONL file or replace it with a valid snapshot from earlier in time, silently wiping recent approval records without violating hash continuity.
- **Consequences:** Eliminates silent ledger rollback and truncation vulnerabilities. Enforces monotonic progression across restarts and state reloads. Provides a clean pluggable interface for enterprise immutable storage backends (e.g. AWS S3 Object Lock, GCP Cloud Storage Bucket Lock, or Azure Immutable Storage).
