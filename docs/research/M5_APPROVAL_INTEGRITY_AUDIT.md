# PIIS Milestone 5: Human Approval & Audit Trail Integrity Audit

- **Document Version:** 1.0.0
- **Auditor:** Independent AI Safety & Cryptographic Systems Auditor
- **Status:** COMPLETED — CRITICAL AUDIT FINDINGS RECORDED
- **Date:** 2026-11-01
- **Target Component:** `src/piis/investigation/approval.py` (`HumanApprovalWorkflow`, `AuditLogEntry`)
- **Evaluation Suite:** `scripts/audit_approval_integrity.py` (9 Tamper Tests)
- **Artifact Exported:** `artifacts/m5_metrics/m5_approval_integrity_audit_results.json`

---

## 1. Executive Summary & Audit Mandate

The Milestone 5 Completion Report asserted that the human approval workflow implements:
> *"Cryptographically signed human approval workflow... SHA-256 state signatures... immutable decision audit trail guaranteeing non-repudiation."*

An independent cryptographic systems audit was conducted to verify whether `HumanApprovalWorkflow` fulfills these assertions. The audit executed **9 distinct adversarial tamper and integrity tests** covering record modification, deletion, reordering, identity spoofing, timestamp alteration, in-place modification, replay, illegal state transitions, and identity authentication.

### Core Finding (FIND-M5-001):
The implementation provides **unkeyed hash-based integrity only**. It does **NOT** provide cryptographic digital signatures, Merkle/blockchain event chaining, reviewer identity authentication, or non-repudiation. Describing a plain SHA-256 digest as a *"cryptographic approval signature providing non-repudiation"* is a **high-severity nomenclature and cryptographic mischaracterization**.

---

## 2. Adversarial Tamper Test Results (9 Tests)

| Test ID | Adversarial Test Target | Action Executed | Observed System Behavior | Security Assessment |
| :--- | :--- | :--- | :--- | :---: |
| **APPR-01** | Modify earlier approval event | Changed `operator_id` from `OP-ALICE` to `OP-MALLORY` on an existing in-memory log entry. | Modification succeeds in-place. The stored digest retains the original value, but the class has no built-in `.verify()` method to detect the tampering. | **VULNERABLE** |
| **APPR-02** | Delete an event from audit log | Deleted intermediate approval record from `self._audit_trail`. | Intermediate entry deleted. Total count drops from 4 to 3. Zero subsequent entries fail validation because each entry's hash is completely independent. | **NO CHAIN INTEGRITY** |
| **APPR-03** | Reorder events | Reversed audit trail sequence in memory. | Events reordered without cryptographic failure. Reordering is only detectable by inspecting string prefix `AUD-0001` vs `AUD-0004`. | **NO MERKLE CHAIN** |
| **APPR-04** | Change reviewer identity | Spoofed `operator_id` string on recommendation object. | `operator_id` is an arbitrary unauthenticated string. No asymmetric key, X.509 cert, HMAC, or JWT signature is verified. | **UNAUTHENTICATED IDENTITY** |
| **APPR-05** | Change timestamp | Backdated timestamp to `2020-01-01T00:00:00Z`. | System accepts arbitrary timestamp string. No RFC 3161 Timestamp Authority (TSA) or consensus time source. | **HOST-CLOCK DEPENDENT** |
| **APPR-06** | Change recommendation content after approval | Injected `"format c:"` into approved recommendation description. | Python dataclass is mutable in place. While manual external recomputation of `_compute_state_hash` reveals the mismatch, the class lacks automatic change detection. | **MUTABLE OBJECT** |
| **APPR-07** | Replay an earlier approval | Called `approve_recommendation` twice on the same recommendation. | System permitted the second approval without error, creating a duplicate audit entry and overwriting reviewer metadata. | **NO DOUBLE-APPROVAL GUARD** |
| **APPR-08** | Submit invalid state transition | Attempted `REJECTED -> APPROVED` transition. | System permitted the approval! An operator-rejected recommendation was overwritten to `APPROVED` without an explicit override flow. | **DEFECTIVE STATE MACHINE** |
| **APPR-09** | Submit approval without reviewer identity | Tested empty string `""` and whitespace `"   "`. | System raised `ValueError("Human approval requires a non-empty operator_id.")`. Input sanitization works. | **PASS (INPUT SANITIZED)** |

---

## 3. Cryptographic Capabilities Assessment

The table below contrasts the claimed capabilities versus what is actually implemented in `approval.py`:

| Capability | Claimed in M5 Report | Actual Implementation in Code | Gap Severity | Technical Remediation |
| :--- | :--- | :--- | :---: | :--- |
| **Digest Integrity** | Cryptographic state signature | `hashlib.sha256(json.dumps(...))` | **HIGH** | Clarify as *"SHA-256 State Hash Digest"*; never call it a digital signature. |
| **Chain Integrity** | Immutable decision audit trail | Independent digests per entry; zero linkage | **HIGH** | Add `prev_entry_sha256` pointer to link entry $i$ to entry $i-1$ (hash chain). |
| **Append-Only History** | Append-only audit trail | Standard mutable Python list `self._audit_trail` | **MEDIUM** | Persist to append-only file (WORM/ledger) or use frozen tuples with verifier. |
| **Reviewer Authentication** | Authorized operator identity | Arbitrary string `operator_id` | **HIGH** | Integrate HMAC token, asymmetric public key lookup, or SSO JWT claim. |
| **Non-Repudiation** | Guaranteed non-repudiation | **None**. Any entity can generate matching SHA-256 | **HIGH** | True non-repudiation strictly requires asymmetric digital signatures (Ed25519/RSA). |
| **State Machine Guard** | Strict transition enforcement | Missing checks for double-approval and `REJECTED -> APPROVED` | **HIGH** | Enforce: only `PENDING_REVIEW` can transition to `APPROVED` or `REJECTED`. |

---

## 4. Detailed Reproduction Procedure

To reproduce these 9 findings independently:
```bash
python scripts/audit_approval_integrity.py
```
Output artifact generated at `artifacts/m5_metrics/m5_approval_integrity_audit_results.json`.

### Specific Code Defect in `approve_recommendation`:
In lines 63–75 of `src/piis/investigation/approval.py`:
```python
def approve_recommendation(
    self, recommendation_id: str, operator_id: str, incident_id: str, notes: Optional[str] = None
) -> DiagnosticRecommendation:
    rec = self._get_pending_recommendation(recommendation_id)
    # DEFECT: Does not verify that rec.approval_status == ApprovalStatus.PENDING_REVIEW!
    # If rec was already APPROVED or REJECTED, it overwrites it silently!
    ...
```

---

## 5. Auditor Recommendations

1. **Terminology Downgrade (Mandatory):** Retract claims of *"cryptographic digital signatures"* and *"non-repudiation"*. Accurately describe the subsystem as providing **hash-based record integrity verification**.
2. **State Machine Hardening:** Enforce strict preconditions:
   ```python
   if rec.approval_status != ApprovalStatus.PENDING_REVIEW:
       raise IllegalStateTransitionError(f"Cannot approve recommendation in status {rec.approval_status}")
   ```
3. **Audit Trail Verification Method:** Implement `HumanApprovalWorkflow.verify_audit_trail()` to iterate through entries, verify internal hashes, and check chain continuity.
4. **Hash Chain Linkage:** Include `previous_hash: Optional[str]` in `AuditLogEntry`, binding each entry to the preceding entry digest.
