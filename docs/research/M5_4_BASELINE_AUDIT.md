# PIIS Milestone M5.4 Baseline Audit & Defect Reproduction Report

**Status:** COMPLETE & INDEPENDENTLY REPRODUCED  
**Milestone:** M5.4 (Targeted Security, Integrity & Reliability Remediation)  
**Date:** 2026-11-01  
**Authors:** Principal Security Engineer, Systems Reliability Architect & Telecom AI Safety Lead  
**Classification:** Internal Engineering Audit  
**Authoritative Machine-Readable Artifact:** [`artifacts/m5_metrics/m5_4_baseline_reproduction.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_4_baseline_reproduction.json)

---

## 1. Executive Summary & Baseline State

Before applying any code modifications to the production tree (`src/`), an independent baseline audit and empirical reproduction of all findings from the Milestone M5.3 Independent Security & Reliability Revalidation was performed.

### 1.1 Non-Negotiable Operational Constraints
* **Strictly Read-Only Boundary:** Zero production command execution, zero network mutations, zero autonomous ticket closures, zero customer-facing communications.
* **Milestone Boundaries:** Milestone M6 remains **UNAUTHORIZED**. Production pilot remains **BLOCKED**.
* **Integrity of History:** Historical ledger records and ADRs must not be retroactively authenticated or modified.
* **Test Suite Integrity:** Existing unit tests must not be weakened or deleted to obtain passing status.

### 1.2 Baseline Verification Metrics
* **Unit Test Suite:** 244 passed, 0 failed in `pytest tests/unit/` (Execution time: 63.67 seconds).
* **Static Linter & Type Compliance:** `ruff check src/ tests/` clean (0 warnings, 0 errors).
* **Empirical Reproduction Score:** 6/6 findings reproduced (100% confirmation).

---

## 2. Empirical Finding Reproductions & Root Cause Analyses

All reproduction experiments were executed via [`scripts/reproduce_m5_4_findings.py`](file:///c:/Production%20level%20projects/PIIS/scripts/reproduce_m5_4_findings.py).

### 2.1 FIND-M5.3-001: Service Token Direct Revocation Omission
* **Severity:** High
* **Source Location:** [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L730-L767) (`ProductionOIDCVerifier.verify_service_token`)
* **Reproduction Steps:**
  1. Instantiate `ProductionOIDCVerifier` with RS256 signing keys and allowlisted issuer.
  2. Issue a valid service token containing payload `"principal_type": "SERVICE"`, `"scopes": ["read_evidence"]`, and `"jti": "service-jti-revoked-001"`.
  3. Register `"service-jti-revoked-001"` in the verifier's revocation set via `verifier.revoke_token(jti)`.
  4. Invoke `verifier.verify_service_token(token)`.
* **Expected Behavior:** `verify_service_token()` must verify revocation status against `self._revoked_tokens` and raise `UnauthenticatedReviewerError("Service token has been revoked.")`.
* **Actual Observed Behavior:** `verify_service_token()` decoded the JWT, bypassed revocation checking entirely, and returned valid `ServicePrincipalClaims` for service `network-slice-sync`. Additionally, missing required claims (`exp`, `sub`, `iss`, `aud`) are silently defaulted rather than rejected.
* **Root Cause:** Asymmetry between `verify_token` (human reviewers) and `verify_service_token` (service workloads). While `verify_token` performs `if jti and self.is_revoked(jti): raise UnauthenticatedReviewerError(...)`, `verify_service_token` omitted both `jti` extraction and revocation validation.
* **Proposed Minimal Remediation:**
  1. Extract `jti` from payload; enforce presence of `jti`, `exp`, `iss`, `aud`, and `sub` claims.
  2. Query `self.is_revoked(jti)`; raise `UnauthenticatedReviewerError` if revoked.
  3. Fail closed if `jti` is missing or empty for privileged service principal tokens.
* **Regression Risks:** Existing unit tests issuing mock service tokens without `jti` might fail if `jti` is strictly required; remediation will ensure standard fallback/test tokens supply valid `jti` identifiers.

---

### 2.2 FIND-M5.3-002: Reentrant Lock Deadlock in Session Validation
* **Severity:** High
* **Source Location:** [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L580-L586) and [`L776-L797`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L776-L797) (`ProductionOIDCVerifier`)
* **Reproduction Steps:**
  1. Instantiate `ProductionOIDCVerifier`.
  2. Register an active session for `AuthenticatedServicePrincipal(service_id="sp-test", token_id="jti-session-test")`.
  3. Invoke `verifier.validate_service_session(service_principal)` in a worker thread with a 1.0s timeout.
* **Expected Behavior:** Session validation completes synchronously within sub-millisecond latency.
* **Actual Observed Behavior:** The worker thread deadlocked and timed out after 1.0 second.
* **Root Cause:**
  `self._lock` is instantiated as `threading.Lock()` (non-reentrant). Both `validate_service_session` and `validate_reviewer_session` acquire `with self._lock:` and subsequently invoke `self.is_revoked(token_id)` inside that block. Because `self.is_revoked()` also acquires `with self._lock:`, the thread attempts to re-acquire its own exclusive lock, causing an immediate, deterministic self-deadlock. Furthermore, `_get_signing_key()` invokes network I/O (`_fetch_jwks`) while holding `self._lock`.
* **Proposed Minimal Remediation:**
  1. Change `self._lock = threading.Lock()` to `self._lock = threading.RLock()` across `ProductionOIDCVerifier`.
  2. Refactor network I/O in `_fetch_jwks()` to avoid holding `self._lock` during remote HTTP socket transactions (double-checked locking or isolated lock for cache updates).
* **Regression Risks:** None. `RLock` is strictly backwards-compatible with `Lock` and eliminates the reentrant deadlock while preserving thread safety.

---

### 2.3 FIND-M5.3-003: Canonical Serialization Unicode RFC 8785 Divergence
* **Severity:** Medium
* **Source Location:** [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L799-L801) (`canonical_json_dumps`)
* **Reproduction Steps:**
  1. Pass non-ASCII Unicode strings (e.g. telecom station `"München_Core_01"`, Chinese station `"北京"`, math symbol `"≥"`, and float `-0.0`) to `canonical_json_dumps()`.
  2. Inspect output string.
* **Expected Behavior:** Per RFC 8785 (JSON Canonicalization Scheme / JCS) Section 3.2.2:
  - Non-ASCII characters (U+0080 through U+10FFFF) must NOT be escaped and must be preserved as raw UTF-8 characters.
  - Escaping is strictly restricted to quotation mark (`"`), reverse solidus (`\`), and control characters (U+0000 through U+001F).
  - Negative zero (`-0.0`) must serialize as integer `0`.
* **Actual Observed Behavior:**
  `canonical_json_dumps` utilized `json.dumps(..., ensure_ascii=True)`, producing:
  `{"alert":"5G NR High VSWR \u2265 1.5","city":"\u5317\u4eac","station_id":"M\u00fcnchen_Core_01","value":-0.0}`
  This contains `\u00fc`, `\u5317\u4eac`, `\u2265`, and `-0.0`, violating RFC 8785.
* **Root Cause:** Standard library `json.dumps` defaults `ensure_ascii=True`, and does not implement RFC 8785 float shortest-round-trip / zero-normalization semantics out-of-the-box.
* **Proposed Minimal Remediation:**
  Implement a pure-Python, zero-dependency RFC 8785 JCS canonical serializer function:
  1. Lexicographical sorting of object member keys by UTF-16 code units.
  2. Native UTF-8 string encoding (`ensure_ascii=False`) with strict RFC 8785 escaping rules.
  3. IEEE 754 float representation: normalize `-0.0` to `0`, reject `NaN` and `Infinity`.
  4. Maintain backwards compatibility with legacy v1.0 entries while migrating v2.0 entries to genuine RFC 8785 canonical hashes.
* **Regression Risks:** Historical ledger entries hashed under v2.0 in M5.2/M5.3 used the older ASCII-escaped serializer. A canonicalization versioning or transparent dual-verification mechanism is required to avoid breaking valid historical records.

---

### 2.4 FIND-M5.3-004: Local File-Based Anchor Host Compromise Boundary
* **Severity:** Medium
* **Source Location:** [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L927-L1002) (`FileBasedCheckpointAnchor`)
* **Reproduction Steps:**
  1. Record an audit entry in a local file-based checkpoint anchor.
  2. Simulate a root compromise on the local host by rewriting both the ledger JSONL file and the anchor JSON file simultaneously.
* **Expected Behavior:** Threat model must explicitly clarify trust boundaries: local file anchors protect against accidental state corruption or unprivileged process tampering, but cannot defend against host root-compromise without external append-only / WORM attestation (`DEP-M5.3-002`).
* **Actual Observed Behavior:** The class docstring and architectural documentation lacked explicit trust boundary statements regarding co-located filesystem compromise.
* **Proposed Minimal Remediation:**
  1. Document explicit trust boundary in code and architecture documentation (ADR 0013): local file anchor is an operational tamper-evident sentinel, while production deployments require `CloudWORMCheckpointAnchor` or remote HSM/S3 Object Lock attestation.
  2. Harden file permissions on local anchor files (`0o600` on POSIX / explicit restricted ACLs on Windows).
* **Regression Risks:** None. Clarifies threat model and tightens file modes.

---

### 2.5 FIND-M5.3-005: Missing Checkpoint Anchor Fails Open Against Ledger Rollback
* **Severity:** High
* **Source Location:** [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py#L960-L977) (`FileBasedCheckpointAnchor.verify_ledger_head` & `get_latest_checkpoint`)
* **Reproduction Steps:**
  1. Initialize `FileBasedCheckpointAnchor` pointing to a missing or deleted path.
  2. Construct a non-empty ledger head (`AuditLogEntry` sequence 5).
  3. Call `anchor.verify_ledger_head(entry)`.
* **Expected Behavior:** If the ledger contains entries but the checkpoint anchor file is missing, deleted, or unreadable, the verifier must FAIL CLOSED (return `False` or raise `LedgerRollbackDetectedError`) because an attacker may have deleted the anchor to hide rollback/truncation.
* **Actual Observed Behavior:** `verify_ledger_head()` executed `checkpoint = self.get_latest_checkpoint(); if checkpoint is None: return True, None`. It returned `(True, None)`, failing completely open! Furthermore, `get_latest_checkpoint()` silently caught `except Exception: return None`.
* **Root Cause:** Permissive initialization logic conflated a newly created, uninitialized system (empty ledger AND missing anchor) with an established ledger whose anchor was maliciously deleted or unreadable.
* **Proposed Minimal Remediation:**
  1. In `verify_ledger_head(latest_entry)`:
     - If `latest_entry is None` and `checkpoint is None`: Valid brand-new system -> `(True, None)`.
     - If `latest_entry is not None` and `checkpoint is None`: Tampering / anchor deletion detected -> `(False, "CRITICAL ROLLBACK: Anchor missing for non-empty ledger")`.
  2. In `get_latest_checkpoint()`: Raise or propagate corrupt JSON and I/O errors rather than silently swallowing them as `None`.
* **Regression Risks:** Test cases that test ledger creation without creating an initial checkpoint must either initialize the anchor with sequence 0 or test both empty.

---

### 2.6 FIND-M5.3-006: Transient Operational Glitch Misclassification
* **Severity:** Medium
* **Source Location:** [`src/piis/investigation/engine.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/engine.py#L416-L450) (`IncidentInvestigationEngine._evaluate_sufficiency_and_contradictions`)
* **Reproduction Steps:**
  1. Pass scenario `ABS-08`: Incident describing a self-cleared 200ms CPU spike during routing reload, with zero active alarm codes (`active_alarm_codes=[]`), nominal subsequent polling, and network element `SMF-CORE-01`.
  2. Invoke `engine.investigate(incident, m2={}, m3={})`.
* **Expected Behavior:** Because the glitch self-cleared, telemetry returned to nominal, and no active alarms are present, the investigation engine must classify evidence as insufficient/transient, assign hypothesis status `HypothesisStatus.INCONCLUSIVE`, and recommend safe abstention / human review (`HUMAN_ESCALATION`), rather than prescribing an active disruptive runbook.
* **Actual Observed Behavior:** Engine evaluated description length $\ge 4$ words and element IDs present, treated evidence as sufficient, ranked runbook `SOP-5GC-AMF-001`, and marked hypothesis as `HypothesisStatus.SUPPORTED`.
* **Root Cause:** Sufficiency evaluation lacked transient/self-cleared anomaly heuristics. In the absence of active alarms, a transient spike with self-clearing text description was matched purely against semantic keywords.
* **Proposed Minimal Remediation:**
  1. Add transient event detection in `IncidentInvestigationEngine`: check for explicit self-cleared indicators (e.g. "self-cleared", "returned to nominal", duration $< 5$s) combined with empty active alarms (`len(alarm_codes) == 0`).
  2. Flag `EvidenceSufficiencyReport` with `is_transient_event = True` and `is_sufficient = False`.
  3. Mark hypotheses for transient self-clearing events as `HypothesisStatus.INCONCLUSIVE` and route recommendations to `HUMAN_ESCALATION` / `OBSERVE_AND_MONITOR`.
* **Regression Risks:** Sustained incidents that mention transient recovery in their historical context must still be recognized if active alarms persist. The heuristic must strictly require `len(alarm_codes) == 0` and absence of ongoing metric degradation.

---

## 3. Baseline Audit Sign-Off

All 6 findings have been reproduced and verified against the actual running codebase. Source code edits will now proceed in strict accordance with the planned workstreams:

* **Workstream A:** OIDC Token Revocation (`FIND-M5.3-001`)
* **Workstream B:** Session Validation Concurrency & RLock (`FIND-M5.3-002`)
* **Workstream C:** RFC 8785 Canonical JSON Compliance (`FIND-M5.3-003`)
* **Workstream D:** Checkpoint Integrity & Fail-Closed Monotonic Anchoring (`FIND-M5.3-004`, `FIND-M5.3-005`)
* **Workstream E:** Transient Telemetry & Recommendation Safety (`FIND-M5.3-006`)
* **Workstream F:** Full Regression & Quality Audit

*End of Baseline Audit Report.*
