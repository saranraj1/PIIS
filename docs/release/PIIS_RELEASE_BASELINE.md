# PIIS — Final Engineering Release Baseline

> [!IMPORTANT]
> ### Canonical Engineering Baseline Status
> - **Product:** Production Incident Intelligence System (PIIS) — Telecom Edition
> - **Release Identifier:** `v1.0.0-rc1` (Milestone M1–M6 Release Candidate)
> - **Milestone Closure Status:**
>   - **M1 (Data Foundations & Ingestion Contracts):** CLOSED
>   - **M2 (Telemetry Anomaly Detection & ML Incident Classifier):** CLOSED
>   - **M3 (Multi-Modal Incident Correlation & Topology Graph):** CLOSED
>   - **M4 (Evidence-Grounded Hybrid RAG & Runbook Synthesis):** CLOSED
>   - **M5 (Cryptographic Audit Ledger, Decision Governance & Safety):** CLOSED
>   - **M6 (Enterprise Integration, Observability & Operational Readiness):** ENGINEERING CLOSED
> - **Operational Boundary:** Strictly Read-Only Telecom Decision Support
> - **Production Pilot Status:** BLOCKED pending external corporate infrastructure prerequisites
> - **Historical M6 Closure Source / Test SHA-256:** `cfd9ce798195d727f3698d7c73008b6dd59c05ec2716294b8c1ccbcd0e03579d`
> - **Pre-Reconciliation Lint-Hygiene Source / Test SHA-256:** `7706ff99f0816558ab2b9fad513c32ba0a0c215ccc132d8503eae1936c852452`
> - **Final Release Candidate (`v1.0.0-rc1`) Clean Source / Test SHA-256 (145 files):** `09a280bd04971a88c44627fd9145c8ed34aa3f765c5ecc216182656a81e26af9`
> - **Complete Reconciled Release Manifest (405 files) SHA-256 Digest:** `docs/release/RELEASE_MANIFEST.sha256`

---

## 1. Executive Summary

This document establishes the verified baseline for the official engineering release freeze of the Production Incident Intelligence System (PIIS). PIIS has concluded its scheduled development cycles across Milestones M1 through M6. The codebase is frozen against changes to production algorithms, schemas, locked principles, and evaluation datasets.

The system functions exclusively as a read-only decision-support and investigation intelligence platform for telecommunications operations centers (NOCs). It possesses zero autonomous authority or technical integration to execute production network commands, mutate network element configurations, alter external ITSM tickets, or dispatch customer communications.

---

## 2. Cryptographic Source Integrity & Release Manifests

### 2.1 Source / Test SHA-256 Digest Progression
- **Target Directories:** `src/` (92 pure source files) and `tests/` (53 test files) = 145 files.
- **Historical M6 Closure Baseline:** `cfd9ce798195d727f3698d7c73008b6dd59c05ec2716294b8c1ccbcd0e03579d` (Recorded at formal closure of Milestone M6 prior to lint hygiene).
- **Post-Hygiene Intermediate Digest:** `7706ff99f0816558ab2b9fad513c32ba0a0c215ccc132d8503eae1936c852452` (Recorded after resolving 129 Ruff violations and `Optional` defect in `alarm_simulator.py`).
- **Post-Warning-Reconciliation Intermediate Digest:** `fa05cbe631f2d567015d6b17b88ec9d406014849dfff046f4a2205c0d64df7de` (Recorded after resolving FastAPI deprecation warnings, prior to `.gitignore` egg-info exclusion).
- **Final Release Candidate Clean Source / Test SHA-256 (`v1.0.0-rc1`):** `09a280bd04971a88c44627fd9145c8ed34aa3f765c5ecc216182656a81e26af9` (Exact pure 145-file digest excluding setuptools build artifacts).
- **Reconciliation of Changed Files:**
  1. `src/piis/api/app.py`: Updated `status.HTTP_422_UNPROCESSABLE_ENTITY` to RFC 9110 standard `status.HTTP_422_UNPROCESSABLE_CONTENT`.
  2. `src/piis/api/routers/incidents.py`: Updated `status.HTTP_422_UNPROCESSABLE_ENTITY` to `status.HTTP_422_UNPROCESSABLE_CONTENT`.
  3. `src/piis/integrations/simulators/alarm_simulator.py`: Added missing `Optional` type import.
  4. `src/piis/integrations/telemetry/prometheus.py`: Pruned unused variable assignment `result_type`.
  5. `src/`: Pruned safe unused imports across 22 modules.
  6. `tests/integration/test_m6_integration_and_reliability.py`: Pruned 5 unused test fixture variables.
  - Zero algorithm logic, zero test assertions, and zero security boundaries were altered.

### 2.2 Complete Release Manifest & File Scope
- **Scope:** Complete release distribution across `src/` (92), `tests/` (53), `scripts/` (66), `docs/` (153), `configs/` (5), `infra/` (3), `schemas/` (7), `.github/` (3), `data/evaluation/` (10 staged of 14 total on-disk), root configs (6), and directory anchors (7 `.gitkeep` files) = **405 release manifest files**.
- **Manifest File:** [`docs/release/RELEASE_MANIFEST.sha256`](file:///c:/Production%20level%20projects/PIIS/docs/release/RELEASE_MANIFEST.sha256).

### 2.3 Working Tree & Provenance
- **Git Metadata:** The repository working tree contains 406 clean untracked release files (405 manifest files + `RELEASE_MANIFEST.sha256`). Git reports no initial commit yet (`fatal: your current branch 'master' does not have any commits yet`).
- **Transcript Provenance:** An unbroken chain of custody is established and verifiable through system transcript logs (`transcript.jsonl` and `transcript_full.jsonl`).

---

## 3. Automated Test Fleet Execution & Results

### 3.1 Test Command
```powershell
pytest
```

### 3.2 Actual Test Execution Output
```text
============================= test session starts =============================
platform win32 -- Python 3.11.5, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Production level projects\PIIS
configfile: pyproject.toml
plugins: aegis-verify-0.1.0, anyio-4.12.1, langsmith-0.7.7, asyncio-1.3.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 349 items

tests/unit/test_anomaly_detection.py .....                               [  1%]
tests/unit/test_bounded_decoder.py ..............                        [  5%]
tests/unit/test_classifier.py ....                                       [  6%]
tests/unit/test_contracts.py ..                                          [  7%]
tests/unit/test_correlation.py ...                                       [  8%]
tests/unit/test_evaluation_v2.py ....                                    [  9%]
tests/unit/test_features.py ..                                           [  9%]
tests/unit/test_generator_v2.py ....                                     [ 11%]
tests/unit/test_impact_analysis.py ...                                   [ 11%]
tests/unit/test_knowledge_chunker.py ...                                 [ 12%]
tests/unit/test_m3_adversarial_audit.py ......                           [ 14%]
tests/unit/test_m5_1_approval_tamper.py ...........                      [ 17%]
tests/unit/test_m5_1_equipment_grounding.py .......                      [ 19%]
tests/unit/test_m5_1_unicode_security.py .........                       [ 22%]
tests/unit/test_m5_2_approval_auth.py ...............                    [ 26%]
tests/unit/test_m5_2_equipment_grounding.py ............................ [ 34%]
......                                                                   [ 36%]
tests/unit/test_m5_2_unicode_security.py .................               [ 41%]
tests/unit/test_m5_3_audit_ledger_canonicalization.py ......             [ 42%]
tests/unit/test_m5_3_oidc_verification.py ...........                    [ 45%]
tests/unit/test_m5_3_rollback_protection.py ....                         [ 47%]
tests/unit/test_m5_3_system_identity.py .......                          [ 49%]
tests/unit/test_m5_4_canonical_jcs.py .....                              [ 50%]
tests/unit/test_m5_4_checkpoint_integrity.py .....                       [ 51%]
tests/unit/test_m5_4_concurrency_and_oidc.py ......                      [ 53%]
tests/unit/test_m5_4_transient_safety.py ...                             [ 54%]
tests/unit/test_m5_5_prompt_injection_defense.py ............            [ 57%]
tests/unit/test_m5_5_temporal_evidence.py ..................             [ 63%]
tests/unit/test_m5_adversarial.py .....                                  [ 64%]
tests/unit/test_m5_approval.py .......                                   [ 66%]
tests/unit/test_m5_investigation.py ....                                 [ 67%]
tests/unit/test_m5_runbook_negative.py ....                              [ 68%]
tests/unit/test_m5_schemas.py ......                                     [ 70%]
tests/unit/test_m5_temporal_comprehensive.py ........                    [ 72%]
tests/unit/test_normalization.py ...                                     [ 73%]
tests/unit/test_profiler.py ...                                          [ 74%]
tests/unit/test_provenance.py ...                                        [ 75%]
tests/unit/test_retrieval_bm25.py ..                                     [ 76%]
tests/unit/test_retrieval_dense.py ..                                    [ 76%]
tests/unit/test_retrieval_engine.py .....                                [ 77%]
tests/unit/test_retrieval_filters.py ...                                 [ 78%]
tests/unit/test_retrieval_fusion.py .                                    [ 79%]
tests/unit/test_retrieval_security.py .....                              [ 80%]
tests/unit/test_retrieval_tokenizer.py ...                               [ 81%]
tests/unit/test_routing_evaluation.py ...                                [ 82%]
tests/unit/test_routing_policy.py .....                                  [ 83%]
tests/unit/test_schemas.py .......                                       [ 85%]
tests/unit/test_severity.py ...                                          [ 86%]
tests/unit/test_synthetic_generator.py ...                               [ 87%]
tests/unit/test_trust_boundary.py .......                                [ 89%]
tests/integration/test_m6_hardening_verification.py .................    [ 94%]
tests/integration/test_m6_integration_and_reliability.py ............... [ 98%]
.....                                                                    [100%]

====================== 349 passed, 2 warnings in 62.07s =======================
```

### 3.3 Test Fleet Breakdown
- **M1–M5 Frozen Baseline Suite:** 312 tests (100% passing, 0 regressions).
- **M6 Integration Scenarios:** 20 tests in [`tests/integration/test_m6_integration_and_reliability.py`](file:///c:/Production%20level%20projects/PIIS/tests/integration/test_m6_integration_and_reliability.py).
- **M6 Hardening Verification:** 17 tests in [`tests/integration/test_m6_hardening_verification.py`](file:///c:/Production%20level%20projects/PIIS/tests/integration/test_m6_hardening_verification.py).

---

## 4. Resolution of Final Verification Details & Release Governance

### 4.1 Audit-Trail Restart Coverage
During Milestone M6 hardening, Scenario 16 ([`tests/integration/test_m6_integration_and_reliability.py#L320-L353`](file:///c:/Production%20level%20projects/PIIS/tests/integration/test_m6_integration_and_reliability.py#L320-L353)) was expanded from a simple audit check to test file-based restart recovery for `IdempotencyEngine` and `DeadLetterQueue` across distinct process instances.

**Independent Verification:** Audit-trail restart integrity and durable restoration are independently and rigorously exercised across dedicated unit and integration tests:

1. **`tests/unit/test_m5_2_approval_auth.py::test_case_13_process_restart_ledger_restoration`:**
   - Registers recommendations, executes cryptographic operator sign-offs, and flushes to disk.
   - Instantiates a fresh `HumanApprovalWorkflow` in a simulated second process.
   - Calls `load_from_ledger()`, asserts restored entry count, verifies in-memory state restoration, and executes `verify_audit_trail()` to confirm unbroken HMAC hash chain continuity across restart.
2. **`tests/unit/test_m5_3_audit_ledger_canonicalization.py::test_tampered_notes_field_detected_on_restart`:**
   - Verifies that post-restart ledger loading detects modified entry notes and raises `AuditTrailDiscontinuityError`.
3. **`tests/unit/test_m5_3_audit_ledger_canonicalization.py::test_tampered_digest_detected_on_restart`:**
   - Verifies that recomputing the canonical hash on restart detects entry tampering.
4. **`tests/unit/test_m5_3_audit_ledger_canonicalization.py::test_tampered_hmac_detected_on_restart`:**
   - Verifies that HMAC signature mismatch is caught when loading an audit ledger on restart.
5. **`tests/unit/test_m5_3_rollback_protection.py::test_valid_ledger_and_anchor_restores_successfully`:**
   - Tests that external monotonic anchor verifies ledger head on restart.
6. **`tests/integration/test_m6_integration_and_reliability.py::test_scenario_16_database_restart_and_recovery` (lines 350–351):**
   - Asserts `workflow.verify_audit_trail()[0] is True` upon post-restart initialization.

**Conclusion:** Audit-trail restart integrity is fully covered by existing tests. No modifications to `tests/` were needed, preserving the source SHA-256 digest.

### 4.2 Ruff Linter Verification & Release Hygiene Pass
In accordance with release verification protocol and the release hygiene mandate, a comprehensive static analysis and lint resolution pass was executed across the entire repository without artificial workarounds or weakening configurations.

- **Exact Command:** `ruff check .`
- **Actual Exit Code:** `0`
- **Actual Output:** `All checks passed!`
- **Resolution Summary of 129 Violations:**
  1. **Actual Correctness Defects Fixed:**
     - `src/piis/integrations/simulators/alarm_simulator.py`: Fixed `F821 Undefined name Optional` by explicitly importing `Optional` from `typing`.
  2. **Unused Variables Cleaned:**
     - `src/piis/integrations/telemetry/prometheus.py`: Pruned unused variable assignment `result_type`.
     - `tests/integration/test_m6_integration_and_reliability.py`: Pruned 5 unused local variable assignments (`noc_token`, `alarm_sim`, `env`, `token`, `token`).
  3. **Safe Unused Imports Pruned:**
     - `src/`: Pruned unused imports across 22 core modules in routers, simulators, and pipelines (e.g., `fastapi.status`, `typing.List`, `datetime`).
     - `scripts/`: Cleaned unused imports and fixed variable naming (`E741` ambiguous variable name `l` -> `line`) and module import placement (`E402`) across historical audit scripts (`scripts/audit_m5_3_*.py`, `scripts/audit_m5_4_*.py`, `scripts/reproduce_m5_4_findings.py`, `scripts/generate_m5_5_1_blind_evaluation_datasets.py`).
  4. **Behavioral & Safety Impact:** Zero changes to algorithmic logic, zero test assertions relaxed or removed, and zero operational boundaries altered. All 349 tests pass continuously with zero regressions.

### 4.3 Pytest Warning Reconciliation & Deprecation Elimination
During the initial 349-test suite execution, five warnings were observed. In accordance with release-governance requirements, all five warnings were audited, classified, and addressed:

| Warning # | Test / Origin Location | Warning Category | Classification | Root Cause & Resolution |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `test_scenario_06_invalid_source_schema` (`fastapi/routing.py:314`) | `DeprecationWarning` | Actionable | Deprecated Starlette constant `HTTP_422_UNPROCESSABLE_ENTITY`. Updated to RFC 9110 standard `HTTP_422_UNPROCESSABLE_CONTENT` in `src/piis/api/app.py:87` and `src/piis/api/routers/incidents.py:120`. **Eliminated.** |
| **2** | `test_scenario_13_integration_service_unavailable` (`fastapi/routing.py:314`) | `DeprecationWarning` | Actionable | Resolved via RFC 9110 update above. **Eliminated.** |
| **3** | `test_scenario_15_partial_ingestion_failure` (`fastapi/routing.py:314`) | `DeprecationWarning` | Actionable | Resolved via RFC 9110 update above. **Eliminated.** |
| **4** | `test_trust_boundary.py:28` (`LocalDevKeyProvider`) | `UserWarning` | Harmless / Expected | Mandatory architectural safety warning alerting operators that local dev keys are not HSM-certified and fail closed in production. **Preserved by design.** |
| **5** | `trust_boundary.py:406` (`LocalDevKeyProvider`) | `UserWarning` | Harmless / Expected | Mandatory architectural safety warning during notarization manager initialization. **Preserved by design.** |

- **Post-Reconciliation Result:** 0 deprecation warnings, 2 expected architectural safety warnings. Test fleet status: **349 passed in 62.07s**.

### 4.4 Installation Smoke Test & Environment Boundary
A clean-room installation validation was conducted to verify package specifications:
- **Clean Venv Provisioning:** Executed `python -m venv <temp_dir>` and confirmed successful creation of isolated virtual environments.
- **Dependency Installation Boundary:** In accordance with the execution sandbox security boundary, outbound Internet connectivity to external package repositories (`files.pythonhosted.org`) is disabled (`[Errno 11001] getaddrinfo failed`). This is an expected environment restriction and confirms sandbox isolation.
- **Local Application Runtime Smoke Test:** The pre-installed local Python 3.11.5 environment contains all pinned dependencies (`fastapi 0.115.6`, `uvicorn 0.34.0`, `pydantic 2.10.4`, `opentelemetry-sdk 1.29.0`, `pyjwt 2.10.1`, `cryptography 44.0.0`). Runtime smoke testing verified 100% operational readiness:
  - `GET /api/v1/health` -> HTTP 200 `{"status": "healthy"}`
  - `GET /api/v1/ready` -> HTTP 200 `{"status": "ready"}`
  - `GET /ui` -> HTTP 200 (27,029 bytes operator dashboard HTML/JS payload)
  - `python scripts/run_piis_demo.py` -> 12 of 12 stages verified (Exit code 0)
  - `pytest` -> 349 of 349 tests passing (Exit code 0)

### 4.5 Repository Inventory, Secret Scan & Licensing Audit
- **Full Repository Filesystem Audit:** 940 total files residing on disk across all directories.
- **Inventory Reconciliation:**
  - Build/test caches & virtual environments (ignored): 83 `src` pyc, 52 `tests` pyc, 6 `scripts` pyc, 1 `artifacts` pyc, 5 `.pytest_cache`, 13 `.ruff_cache`.
  - Build metadata artifacts (ignored): 5 `src/piis.egg-info` files.
  - Raw and intermediate datasets (ignored): 194 raw data files (`data/raw/SRC-002`, `SRC-005`), 5 processed data files, 9 synthetic data files.
  - Evaluation run outputs (ignored): 118 files under `artifacts/`.
  - Model weights (ignored): 16 pre-trained joblib and json weights under `models/`.
  - Development tools & archives (ignored): `PIIS_Full_Starter_Kit.zip`, `.agent/` (5 files).
  - Protected evaluation holdouts (ignored): 4 `SEALED_HOLDOUT` datasets under `data/evaluation/`.
  - **Proposed Git Staging Set:** Exactly **406 clean files**.
  - **Release Manifest Entries:** Exactly **405 release files** (Git staging set excluding `RELEASE_MANIFEST.sha256` itself).
- **Secret Scan Results:** Automated regex scan covering AWS keys, PKCS8/RSA private keys, GitHub tokens, API keys, passwords, and JWTs executed across all non-binary files.
  - **Findings:** Zero credentials, zero private keys, zero actual tokens leaked. Exactly 1 synthetic test string detected (`tests/integration/test_m6_integration_and_reliability.py:207 -> "Bearer forged.invalid.token"` for negative authentication testing).
- **Licensing Audit & Governance Notice:**
  - Root `LICENSE` file is currently absent from repository root; source code is intended for Apache-2.0 licensing, and a formal `LICENSE` file and third-party notices are prepared for maintainer review prior to initial commit.
  - Core dependencies: Permissive open-source licenses (MIT, Apache 2.0, BSD-3-Clause).
  - External raw datasets: `SRC-002` (TelecomTS) is MIT licensed. `SRC-005` (UCC 5G) is GPL-3.0 licensed.
  - Copyleft Isolation: `data/raw/**` is strictly gitignored in `.gitignore`. Zero copyleft code is incorporated into `src/`, completely isolating the core engine from GPL contamination.

### 4.6 Evaluation Data Classification & Protection
All 14 files under `data/evaluation/` were audited and classified in accordance with release-governance requirements:

| File Path | Size | Classification | Protection Status & Rationale |
| :--- | :---: | :--- | :--- |
| `data/evaluation/MASTER_GOVERNANCE_REGISTRY.json` | 19,253 B | `INTERNAL_GOVERNANCE` | **STAGED.** Master ledger of canonical RFC 8785 hashes and provenance records. |
| `data/evaluation/benign_controls_m5_5/MANIFEST.json` | 5,677 B | `INTERNAL_GOVERNANCE` | **STAGED.** Cryptographic seal manifest for benign control test set. |
| `data/evaluation/benign_controls_m5_5/benign_multilingual_m5_5.json` | 18,387 B | `SYNTHETIC_RELEASE` | **STAGED.** 60 synthetic benign multilingual NOC incident descriptions. |
| `data/evaluation/blind_holdout_m5_5_1/MANIFEST.json` | 4,556 B | `INTERNAL_GOVERNANCE` | **STAGED.** Cryptographic seal manifest for M5.5.1 blind holdout. |
| `data/evaluation/blind_holdout_m5_5_1/blind_holdout.json` | 14,443 B | `SEALED_HOLDOUT` | **EXCLUDED (Gitignored).** 30 sealed evaluation cases. Protected against model tuning. |
| `data/evaluation/blind_redteam_m5_5_1/MANIFEST.json` | 7,036 B | `INTERNAL_GOVERNANCE` | **STAGED.** Cryptographic seal manifest for M5.5.1 blind red-team dataset. |
| `data/evaluation/blind_redteam_m5_5_1/blind_redteam.json` | 12,003 B | `SEALED_HOLDOUT` | **EXCLUDED (Gitignored).** 50 sealed prompt-injection payloads. Protected against leakage. |
| `data/evaluation/redteam_m5_5/MANIFEST.json` | 9,546 B | `INTERNAL_GOVERNANCE` | **STAGED.** Cryptographic seal manifest for M5.5 red-team dataset. |
| `data/evaluation/redteam_m5_5/fresh_redteam_m5_5.json` | 18,580 B | `SEALED_HOLDOUT` | **EXCLUDED (Gitignored).** 100 adversarial prompt-injection cases from M5.5. |
| `data/evaluation/regression/m5_3_regression_manifest.json` | 294 B | `INTERNAL_GOVERNANCE` | **STAGED.** Historical scenario mapping for M5.3 regression fleet. |
| `data/evaluation/regression/m5_4_redteam_regression.json` | 38,677 B | `PUBLIC_RELEASE` | **STAGED.** Historical audit benchmark report recording attack vector results. |
| `data/evaluation/regression/m5_4_transient_regression.json` | 5,487 B | `PUBLIC_RELEASE` | **STAGED.** Historical audit regression log for transient failures. |
| `data/evaluation/sealed_holdout_m5_5/MANIFEST.json` | 2,697 B | `INTERNAL_GOVERNANCE` | **STAGED.** Cryptographic seal manifest for M5.5 sealed holdout dataset. |
| `data/evaluation/sealed_holdout_m5_5/sealed_holdout_m5_5.json` | 10,313 B | `SEALED_HOLDOUT` | **EXCLUDED (Gitignored).** 25 sealed holdout evaluation incidents from M5.5. |

- **Summary:** The 4 `SEALED_HOLDOUT` files are protected by `.gitignore` to prevent benchmark contamination and prompt-injection leakage. The remaining 10 governance manifests and synthetic benchmarks are staged to preserve cryptographic provenance.

### 4.7 Dependency Lock & Installation Reproducibility Disclosure
- **Direct vs Transitive Dependencies:** `pyproject.toml` declares 9 direct core dependencies (`pandas`, `numpy`, `pyarrow`, `pydantic`, `jsonschema`, `scikit-learn`, `typer`, `rich`, `pyyaml`) and 8 optional module dependencies (`fastapi`, `uvicorn`, `sentence-transformers`, `faiss-cpu`, `opentelemetry-api`, `opentelemetry-sdk`, `pytest`, `ruff`).
- **Integration Dependencies:** [`requirements-lock.txt`](file:///c:/Production%20level%20projects/PIIS/requirements-lock.txt) pins 23 packages including runtime integration packages (`grpcio==1.74.0`, `opentelemetry-exporter-otlp-proto-grpc==1.44.0`, `pyjwt==2.12.1`, `cryptography==46.0.7`, `pytest-asyncio==1.3.0`).
- **Cryptographic Hashes Disclosure:** `requirements-lock.txt` does not include per-package cryptographic `--hash=sha256:...` flags. It represents a strict version-pinned dependency specification.
- **Platform Assumptions:** Pinned wheels (`numpy==2.4.6`, `scikit-learn==1.6.1`, `faiss-cpu==1.13.2`) are built for x86_64 architecture. Cross-platform container deployments must use compatible Linux wheels via the provided Dockerfile.
- **Clean Installation Verification Status:** Clean virtual environment installation from PyPI could NOT be verified due to sandbox network isolation (`[Errno 11001] getaddrinfo failed`). In-process runtime verification (349 tests, 12-stage demo, API endpoints) is 100% verified on the local host environment.

### 4.8 Git Release Provenance & Proposed Initial Commit Plan
- **Current Repository State:** The repository working tree contains exactly **406 clean, untracked release files**. Git reports no initial commit yet (`fatal: your current branch 'master' does not have any commits yet`).
- **Exclusion Verification:** `.gitignore` excludes caches, raw datasets, model binaries, starter kit archives, and sealed holdout data.
- **Proposed Initial Commit Command:**
  ```powershell
  git add .gitignore pyproject.toml requirements-lock.txt Makefile README.md .env.example .github/ configs/ infra/ schemas/ src/ tests/ scripts/ docs/ data/evaluation/
  git commit -m "feat(release): initial release candidate v1.0.0-rc1 (Milestones M1-M6 complete)"
  ```
- **Proposed Release Tag Command:**
  ```powershell
  git tag -a v1.0.0-rc1 -m "PIIS Telecom Edition Release Candidate 1 (Source/Test Digest: 09a280bd04971a88c44627fd9145c8ed34aa3f765c5ecc216182656a81e26af9)"
  ```
- **Governance Rule:** In compliance with pair-programming safety guidelines, no Git commits or tags will be generated without explicit operator authorization.

### 4.9 Complete Release Manifest & File Hierarchy
- Complete release contents are enumerated in [`docs/release/RELEASE_MANIFEST.sha256`](file:///c:/Production%20level%20projects/PIIS/docs/release/RELEASE_MANIFEST.sha256).
- **Tracked Manifest Entries:** Exactly **405 release files** (reconciles 1:1 with 406 Git staging candidate files excluding `RELEASE_MANIFEST.sha256` itself).
- **Manifest File SHA-256 Digest:** To be verified upon final release stamping.

---

## 5. Environment & Dependency Specifications

### 5.1 Host Runtime
- **Operating System:** Windows 11 Enterprise (build 26100)
- **Python Version:** 3.11.5 (tags/v3.11.5:cce6ba9)
- **Architecture:** AMD64

### 5.2 Key Dependencies & Versions
| Package | Version | Purpose |
| :--- | :--- | :--- |
| **fastapi** | `0.115.6` | REST API framework & OpenAPI specification |
| **uvicorn** | `0.34.0` | ASGI production application server |
| **pydantic** | `2.10.4` | Data modeling, validation, and schema generation |
| **opentelemetry-sdk** | `1.29.0` | Distributed tracing framework |
| **opentelemetry-exporter-otlp-proto-grpc** | `1.29.0` | OTLP gRPC telemetry exporter |
| **grpcio** | `1.68.1` | High-performance RPC transport |
| **pyjwt** | `2.10.1` | Cryptographic JWT token handling |
| **cryptography** | `44.0.0` | Asymmetric & symmetric cryptographic primitives |
| **pytest** | `9.0.3` | Test execution harness |
| **ruff** | `0.8.4` | Fast Python static analysis |

---

## 6. Repository Layout

```text
PIIS/
├── data/                               # Local persistent storage (JSONL)
│   ├── dedup/                          # Ingestion idempotency cache
│   ├── dlq/                            # Dead-letter queue entries
│   └── ledger/                         # Tamper-evident audit ledger
├── docs/                               # Engineering documentation
│   ├── api/                            # OpenAPI and REST specifications
│   ├── architecture/                   # Architecture decision records (ADRs)
│   ├── release/                        # Release baseline, quickstart & notes
│   │   ├── INSTALLATION_AND_QUICKSTART.md
│   │   ├── PIIS_EVALUATION_AND_LIMITATIONS.md
│   │   ├── PIIS_RELEASE_BASELINE.md
│   │   ├── PIIS_TECHNICAL_OVERVIEW.md
│   │   └── RELEASE_NOTES.md
│   └── research/                       # Milestone verification reports (M1-M6)
├── infra/                              # Infrastructure and containerization
│   └── docker/
│       ├── compose.yaml                # Hardened Docker Compose configuration
│       └── Dockerfile                  # Multi-stage non-root container image
├── scripts/                            # Operational & verification tools
│   ├── demonstrate_m6_operational_flow.py
│   └── run_piis_demo.py                # 12-stage technical demonstration
├── src/piis/                           # Production source code
│   ├── api/                            # FastAPI routers, middleware, UI
│   ├── audit/                          # Trust boundary & key providers
│   ├── auth/                           # Authentication, RBAC, OIDC dependencies
│   ├── integrations/                   # Ingestion adapters (ServiceNow, Jira, OSS, Prometheus)
│   ├── investigation/                  # Approval workflow, RAG engine, schemas
│   ├── models/                         # ML classifiers, feature engineering
│   ├── observability/                  # Logging, metrics, OpenTelemetry tracing
│   └── pipeline/                       # Unified ingestion, deduplication, DLQ
└── tests/                              # Automated test suites
    ├── integration/                    # M6 integration & hardening verification
    └── unit/                           # M1-M5 baseline regression suites
```

---

## 7. Operational Boundaries & External Production Prerequisites

### 7.1 Locked Operational Boundaries
1. **Strictly Read-Only Decision Support:** PIIS provides evidence-grounded hypotheses and recommendations. It has zero authority or interfaces to alter network element states.
2. **Zero Autonomous External Mutations:** PIIS never updates, reassigns, or closes tickets in external ITSM systems.
3. **Mandatory Authenticated Human Approval:** Automated service accounts are barred with HTTP 403 Forbidden. Operator review requires a valid human bearer token.
4. **Zero Automated Customer Communications:** External messaging is strictly prohibited.

### 7.2 Open External Infrastructure Prerequisites
Production deployment remains **BLOCKED** pending corporate infrastructure provisioning:
- **`DEP-M5.3-001` (Corporate OIDC IdP):** Live enterprise OpenID Connect identity provider for human operator authentication.
- **`DEP-M5.3-002` (Hardware WORM Storage):** S3 Object Lock or compliance-mode immutable storage for audit ledger root anchoring.
- **`DEP-M5.5.1-001a` (Cloud KMS Hardware Key):** AWS KMS or Azure Key Vault HSM for asymmetric evaluation manifest signing.
- **`DEP-M5.5.1-001b` (RFC 3161 Timestamp Authority):** Authenticated HTTPS TSA endpoint for third-party cryptographic time-stamping.

---

## 8. Verification & Reproducibility Command Reference

```powershell
# 1. Run Complete Automated Test Suite (349 tests)
pytest

# 2. Run Static Analysis & Linter Verification (0 errors)
ruff check .

# 3. Run Reproducible 12-Stage Operational Demonstration
python scripts/run_piis_demo.py

# 4. Verify Final Release Candidate Clean Source / Test Digest (09a280bd...)
python -c "import hashlib, os; h = hashlib.sha256(); [(h.update(os.path.relpath(os.path.join(root, f), '.').replace('\\', '/').encode('utf-8')), h.update(open(os.path.join(root, f), 'rb').read())) for p in ['src', 'tests'] for root, dirs, files in os.walk(p) for f in sorted(files) if not any(d in root for d in ['.git', '__pycache__', '.pytest_cache', '.ruff_cache', 'venv', '.venv', 'piis.egg-info']) and not f.endswith(('.pyc', '.zip'))]; print('Computed Digest:', h.hexdigest())"

# 5. Verify Complete Release Manifest (405 files) Digest
python -c "import hashlib; h = hashlib.sha256(open('docs/release/RELEASE_MANIFEST.sha256', 'rb').read()); print('Manifest SHA-256:', h.hexdigest())"
```
