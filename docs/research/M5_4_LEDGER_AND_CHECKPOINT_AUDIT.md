# PIIS M5.4 Audit Ledger & Checkpoint Threat Model Independent Audit Report

**Milestone:** PIIS M5.4 — Targeted Security, Integrity & Reliability Remediation  
**Auditor Role:** Independent Security Auditor & Cryptographic Evaluator  
**Audit Purpose:** Comprehensive adversarial evaluation of audit ledger tamper-resistance, schema migration non-retroactivity, external checkpoint anchor integrity, and rollback threat boundaries  
**Target Codebase:** `src/piis/investigation/approval.py` (`AuditLogEntry`, `HumanApprovalWorkflow`, `FileBasedCheckpointAnchor`)  
**Date of Audit:** November 2026  
**Artifact Link:** [artifacts/m5_metrics/m5_4_independent_ledger.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_4_independent_ledger.json)  

---

## 1. Executive Summary & Verdict

```
================================================================================
          PIIS M5.4 AUDIT LEDGER & CHECKPOINT INDEPENDENT GATE
================================================================================
  OVERALL EVALUATION RATE:     25 / 25 TESTS PASSED (100.0%)
  SINGLE-FIELD TAMPERING:      14 / 14 DETECTED (100.0% Detection Rate)
  STRUCTURAL ATTACKS:          3 / 3 DETECTED (Deletion, Reordering, Insertion)
  MIGRATION INTEGRITY:         VERIFIED (Digest preserved; no retroactive claims)
  CHECKPOINT ANCHOR TESTS:     5 / 5 VERIFIED (Fail-closed missing/corrupt anchor)
  THREAT BOUNDARY STATUS:      DEMONSTRATED & DOCUMENTED (DEP-M5.3-002 Remains Open)
  FIND-M5.3-004 & 005 STATUS:  CLOSED & VERIFIED
================================================================================
```

---

## 2. Phase 1: Single-Field Mutation Attacks (14 Fields Tested)

The audit ledger Schema v2.0 was subjected to single-field adversarial tampering across every field in the authenticated payload. Across all 14 fields, modifying a single byte resulted in immediate cryptographic signature and hash mismatch:

| Test ID | Tampered Field Name | Adversarial Payload Value | Tamper Detection Mechanism | Result |
|---|---|---|---|:---:|
| **MUT-NOTES** | `notes` | `"Tampered notes: bypassed review"` | Canonical RFC 8785 payload digest mismatch | **DETECTED (100%)** |
| **MUT-OPERATOR_ID** | `operator_id` | `"malicious_operator"` | HMAC-SHA256 signature mismatch | **DETECTED (100%)** |
| **MUT-REVIEWER_ROLE** | `reviewer_role` | `"SYSADMIN"` | Canonical hash mismatch | **DETECTED (100%)** |
| **MUT-AUTHORIZATION_SCOPE**| `authorization_scope` | `"FULL_SYSTEM_ROOT"` | HMAC-SHA256 signature mismatch | **DETECTED (100%)** |
| **MUT-PRINCIPAL_TYPE** | `principal_type` | `"SERVICE"` | HMAC-SHA256 signature mismatch | **DETECTED (100%)** |
| **MUT-KEY_ID** | `key_id` | `"rogue-compromised-key-v1"` | HMAC-SHA256 signature mismatch | **DETECTED (100%)** |
| **MUT-SCHEMA_VERSION** | `schema_version` | `"1.0"` | Canonical payload divergence | **DETECTED (100%)** |
| **MUT-ACTION** | `action` | `"REJECTED"` (on approved entry) | Canonical payload divergence | **DETECTED (100%)** |
| **MUT-INCIDENT_ID** | `incident_id` | `"INC-FORGED-999"` | Canonical payload divergence | **DETECTED (100%)** |
| **MUT-RECOMMENDATION_ID** | `recommendation_id` | `"REC-FORGED-999"` | Canonical payload divergence | **DETECTED (100%)** |
| **MUT-PREVIOUS_STATUS** | `previous_status` | `APPROVED` | State machine hash mismatch | **DETECTED (100%)** |
| **MUT-NEW_STATUS** | `new_status` | `REJECTED` | State machine hash mismatch | **DETECTED (100%)** |
| **MUT-CONTENT_HASH** | `recommendation_content_hash` | `"0" * 64` | Canonical hash mismatch | **DETECTED (100%)** |
| **MUT-PREVIOUS_ENTRY_SHA256**| `previous_entry_sha256` | `"f" * 64` | Broken cryptographic hash pointer | **DETECTED (100%)** |

---

## 3. Phase 2: Structural Sequence Tampering

Adversarial operations altering the sequence of the audit log were executed:
1. **Intermediate Record Deletion (`STRUCT-01`):** Deleting sequence 2 from a 3-record ledger causes record 3's `previous_entry_sha256` to point to the deleted record rather than record 1, and causes sequence number 3 to skip sequence 2. Detected immediately.
2. **Record Reordering Swap (`STRUCT-02`):** Swapping records 2 and 3 breaks the cryptographic hash pointer in record 2 and produces sequence numbers [1, 3, 2]. Detected immediately.
3. **Rogue Record Injection (`STRUCT-03`):** Inserting a forged record into the chain produces sequence numbers [1, 2, 2, 3] and breaks hash continuity. Detected immediately.

---

## 4. Phase 3: Schema v1.0 to v2.0 Migration Integrity

To verify historical immutability:
1. **No Retroactive Authenticity Claims (`MIG-01`):** In Schema v1.0, operator notes were not covered by the canonical payload. When migrated to v2.0, the system sets `notes_cryptographically_covered: false` on historical entries. The audit engine does NOT retroactively re-sign or claim cryptographic coverage for unauthenticated legacy notes.
2. **Digest Preservation (`MIG-02`):** Historical `entry_sha256` digests are preserved byte-for-byte. Verification of historical entries uses the legacy v1 canonical payload constructor, ensuring historical audit trails remain valid without retroactive mutation.

---

## 5. Phase 4: Checkpoint Anchor & Rollback Threat Model

### 5.1 Verification of Remediations
1. **Missing Anchor Fails Closed (`CHK-01`):** Remediating `FIND-M5.3-005`, when the ledger contains records (e.g. sequence 3) and the anchor file is missing or unlinked, `verify_ledger_head()` returns `False` (`CRITICAL ROLLBACK / ANCHOR DELETION: Ledger contains sequence 3 ... but anchor is missing or deleted`).
2. **Uninitialized Deployment Disambiguation (`CHK-02`):** Brand-new systems where both the ledger and anchor are empty cleanly return `(True, None)`, resolving false alarms during cold initial startup.
3. **Corrupted Anchor Fails Closed (`CHK-03`):** Truncated or corrupted JSON in the anchor file causes `get_latest_checkpoint()` to raise `LedgerRollbackDetectedError`, and `verify_ledger_head()` returns `False` (`CRITICAL ANCHOR INTEGRITY ERROR`).
4. **Monotonic Advancement Enforcement (`CHK-04`):** If an attacker truncates the ledger or restores an older snapshot (sequence 2) while the anchor is at sequence 3, `verify_ledger_head()` flags `CRITICAL ROLLBACK: Ledger sequence 2 is older than external anchor sequence 3`.
5. **File Permissions (`CHK-05`):** Anchor files are written with restricted permissions `0o600` (readable and writable by the service owner only).

### 5.2 Four-Tier Rollback Threat Boundary Distinction

```
+----------------------------------------------------------------------------------------------------+
|                                    ROLLBACK THREAT BOUNDARY MATRIX                                 |
+-----------------------------------------+----------------------+-----------------------------------+
| Attack Level / Scenario                 | Defense Mechanism    | Verified Threat Boundary Status   |
+-----------------------------------------+----------------------+-----------------------------------+
| 1. Local Ledger File Tampering          | HMAC & SHA-256 chain | PROTECTED: 100% detection rate    |
| 2. Ledger Truncation / Snapshot Rollback| File-based Anchor    | PROTECTED: Anchor detects rollback|
| 3. Unlinking / Deletion of Anchor       | Fail-Closed Check    | PROTECTED: verify_ledger_head=Fail|
| 4. Host-Level Dual Replacement          | Cloud/Hardware WORM  | BOUNDARY DEMONSTRATED (DEP-M5.3-2)|
+-----------------------------------------+----------------------+-----------------------------------+
```

#### Detailed Threat Boundary Demonstration (`CHK-06`):
In test `CHK-06`, a simulated host-level compromise where the attacker controls the local block device replaced *both* `audit_trail.jsonl` and `checkpoint_anchor.json` with an older consistent snapshot (sequence 1).
Because both files were restored consistently on the local filesystem, local checks inside the container/host pass.
This test empirically proves that **local filesystem controls cannot defend against a root-level host compromise that rolls back the entire block device**.
Therefore:
- **`FIND-M5.3-004` & `FIND-M5.3-005`** are **CLOSED** as software-level implementations.
- **`DEP-M5.3-002`** (External Immutable WORM Storage / AWS S3 Object Lock / Cloud KMS Notary) must remain **OPEN** as an operational enterprise dependency prior to live carrier deployment.
