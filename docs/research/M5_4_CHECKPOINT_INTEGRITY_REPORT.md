# PIIS Milestone M5.4 Checkpoint Integrity & Fail-Closed Behavior Report

**Status:** VERIFIED & CLOSED  
**Milestone:** M5.4 (Workstream D)  
**Date:** 2026-11-01  
**Author:** Principal Security Engineer & Infrastructure Trust Architect  
**Classification:** Internal Engineering Audit Report  
**Relevant Machine-Readable Artifact:** [`artifacts/m5_metrics/m5_3_ledger_and_rollback_audit.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_3_ledger_and_rollback_audit.json)  
**Unit Test Suite:** [`tests/unit/test_m5_4_checkpoint_integrity.py`](file:///c:/Production%20level%20projects/PIIS/tests/unit/test_m5_4_checkpoint_integrity.py)

---

## 1. Executive Summary

During Milestone M5.3 revalidation, two critical issues were identified regarding monotonic checkpoint anchoring:
1. **`FIND-M5.3-005` (Missing Checkpoint Anchor Fails Open Against Ledger Rollback):**
   `FileBasedCheckpointAnchor.verify_ledger_head()` evaluated `checkpoint = self.get_latest_checkpoint(); if checkpoint is None: return True, None`. When an adversary or operational incident deleted or truncated the external anchor file, a non-empty ledger with hundreds of records returned `(True, None)`, failing open and permitting silent ledger rollback. In addition, `get_latest_checkpoint()` silently swallowed exceptions.
2. **`FIND-M5.3-004` (Local File-Based Anchor Host Compromise Boundary):**
   The threat model for `FileBasedCheckpointAnchor` lacked explicit documentation of trust boundaries: a local file on the same filesystem can be rewritten simultaneously with the ledger by a host root attacker.

In Milestone M5.4, fail-closed semantics and explicit trust boundaries were implemented and verified.

---

## 2. Technical Remediation & Implementation

### 2.1 Fail-Closed Verification Logic (`FIND-M5.3-005`)
In [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py) (`FileBasedCheckpointAnchor.verify_ledger_head`):
- **Brand-New Deployment Disambiguation:**
  - If `checkpoint is None` AND `latest_entry is None`: The system is a brand-new, uninitialized deployment $\to$ returns `(True, None)`.
  - If `checkpoint is None` AND `latest_entry is not None`: The ledger contains records, but the anchor file is missing, deleted, or unreadable $\to$ **FAILS CLOSED** by returning `(False, "CRITICAL ROLLBACK / ANCHOR DELETION: Ledger contains sequence N ... but external checkpoint anchor is missing or deleted!")`.
- **Exception Propagation in Checkpoint Loading:**
  - `get_latest_checkpoint()` now catches `(json.JSONDecodeError, OSError)` and explicitly raises `LedgerRollbackDetectedError(f"External checkpoint anchor at '{self.anchor_path}' is corrupted or unreadable: {e}")`.
  - Swallowing corruption as `None` is completely prohibited.
- **Rollback and Fork Detection:**
  - Monotonic regression (`latest_entry.sequence_number < checkpoint["sequence_number"]`) returns `(False, "CRITICAL ROLLBACK: Ledger sequence is older than external anchor")`.
  - State fork / hash mismatch (`latest_entry.sequence_number == checkpoint["sequence_number"]` and `entry_sha256 != checkpoint["entry_sha256"]`) returns `(False, "CRITICAL TAMPERING / FORK: Ledger sequence matches anchor, but entry hash differs")`.

### 2.2 Host Compromise Trust Boundary & Hardened File Modes (`FIND-M5.3-004`)
- **Restricted Filesystem Permissions:**
  When `FileBasedCheckpointAnchor.record_checkpoint()` writes the anchor file, it specifies `0o600` (read/write only by the process owner).
- **Formalized Trust Boundary:**
  Documented in code docstrings and ADR 0013: Local file anchors detect unprivileged user tampering, partial disk truncation, accidental state reversion, and process crashes. However, because both ledger and anchor reside on the local host filesystem, an adversary with OS root privileges can overwrite both files simultaneously. True defense-in-depth against root compromise requires binding to hardware WORM or cloud immutable blob storage (`DEP-M5.3-002`).

---

## 3. Empirical Verification Results

The test suite in [`tests/unit/test_m5_4_checkpoint_integrity.py`](file:///c:/Production%20level%20projects/PIIS/tests/unit/test_m5_4_checkpoint_integrity.py) verified:
1. `test_missing_checkpoint_fails_closed_when_ledger_non_empty`: Successfully confirmed that a missing anchor file returns `(False, "CRITICAL ROLLBACK / ANCHOR DELETION")` when ledger has records.
2. `test_brand_new_system_empty_ledger_and_missing_anchor_succeeds`: Confirmed that a brand-new empty system correctly returns `(True, None)`.
3. `test_corrupted_checkpoint_anchor_fails_closed`: Confirmed that unparseable JSON in the anchor file fails closed with an integrity error.
4. `test_monotonic_checkpoint_recording_and_advancement`: Confirmed that sequence numbers advance monotonically and backward recording attempts raise `LedgerRollbackDetectedError`.
5. `test_ledger_head_hash_mismatch_detected`: Confirmed detection of ledger fork attacks.

*End of Checkpoint Integrity Report.*
