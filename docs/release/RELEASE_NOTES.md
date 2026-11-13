# PIIS Release Notes — Version 1.0.0-rc1

**Release Identifier:** `PIIS-v1.0.0-rc1`  
**Milestone Scope:** M1 through M6 Consolidated Release Freeze  
**Release Date:** November 2026  
**Operational Status:** Strictly Read-Only Decision Support  
**Production Pilot Status:** BLOCKED Pending Enterprise Infrastructure  
**Historical M6 Closure Source / Test Digest:** `cfd9ce798195d727f3698d7c73008b6dd59c05ec2716294b8c1ccbcd0e03579d`  
**Final Release Candidate (`v1.0.0-rc1`) Clean Source / Test Digest (145 files):** `09a280bd04971a88c44627fd9145c8ed34aa3f765c5ecc216182656a81e26af9`  
**Complete Reconciled Release Manifest (405 files):** `docs/release/RELEASE_MANIFEST.sha256`

---

## 1. Overview & Milestone Scope

The Production Incident Intelligence System (PIIS) Telecom Edition has reached final engineering closure across all six planned development milestones:

- **Milestone M1 (Data Foundations):** Ingestion contracts, canonical schema definitions (3GPP/ETSI), and provenance tracking.
- **Milestone M2 (Classifier & Anomaly Detection):** Multi-class incident domain classification (RAN, Core, Transport, Facility) and streaming RF anomaly detection.
- **Milestone M3 (Multi-Modal Correlation):** Topological graph correlation, temporal windowing, and alarm clustering.
- **Milestone M4 (Evidence-Grounded RAG):** Hybrid retrieval (BM25 + dense embeddings) against certified vendor SOPs and epistemic sufficiency verification.
- **Milestone M5 (Governance & Cryptographic Ledger):** RFC 8785 canonical JSON formatting, HMAC-SHA256 tamper-evident audit ledger, rollback detection, and service-principal review lockout.
- **Milestone M6 (Enterprise Integration & Readiness):** File-based restart persistence, production OIDC discovery (RFC 8414), real OTLP gRPC distributed tracing, strict read-only adapter boundaries, server-side RBAC, and operator dashboard.

---

## 2. Major Engineering & Reliability Improvements in M6

1. **Restart-Persistent Deduplication & Dead-Letter Queue (DLQ):**
   - Transformed in-memory idempotency cache and DLQ into append-only, thread-safe JSONL persistence.
   - Preserves event suppression and uncommitted failure state across process restarts.
   - Resolved deduplication cache poisoning: uncommitted keys are pruned upon normalization failure, enabling idempotent replay.
2. **Production OIDC Implementation:**
   - Standard RFC 8414 discovery (`/.well-known/openid-configuration`) with dynamic JWKS caching and rate limiting.
   - Comprehensive SSRF protection blocking loopback (`127.0.0.1`), RFC 1918 private subnets, and cloud metadata endpoints (`169.254.169.254`).
   - Rejection of future not-before (`nbf`) tokens (`ImmatureSignatureError`) and enforced RS256/ES256 cryptographic algorithms.
3. **Real OpenTelemetry Distributed Tracing (OTLP gRPC):**
   - Standard OpenTelemetry SDK integration supporting W3C `TraceContext` header propagation.
   - `FailSafeSpanExporter` isolation: collector downtime or network timeouts fail safely without disrupting operational incident triage.
   - Verified end-to-end network export over real local gRPC sockets (`opentelemetry.proto.collector.trace.v1`).
4. **Strict Read-Only Integration Guardrails:**
   - Explicit operational boundaries enforced on all external adapters (`ALLOWED_OPERATIONS`).
   - Mutative attempts (`CREATE_TICKET`, `MODIFY_CONFIG`, `EXECUTE_COMMAND`) raise `ReadOnlyBoundaryViolationError`.
   - Verified zero mutative API routes exist in the web service.
5. **Operator Dashboard Server-Side Security:**
   - Direct API endpoints enforce server-side RBAC (401/403). Automated service principals and unauthorized roles cannot approve recommendations.
   - Eliminated embedded tokens, HMAC keys, or secrets from UI HTML/JS. Tokens are stored strictly in client-side session storage.

---

## 3. Security, Safety & Governance Controls

- **Strictly Read-Only Boundary:** Zero authority or capability to alter live network elements, dispatch commands, modify configurations, or close tickets.
- **Mandatory Human-in-the-Loop:** Consequential operational decisions require cryptographic approval by an authenticated human NOC engineer.
- **Tamper-Evident RFC 8785 JCS Ledger:** Monotonically numbered, cryptographically signed audit chain ensuring immutable operational accountability.
- **Air-Gap Capability:** Zero dependencies on external third-party cloud LLM APIs. Core algorithms run 100% locally.

---

## 4. Release Verification Results

- **Automated Test Fleet:** **349 / 349 tests passing (100.0%)**
  - 312 Frozen M1–M5 Baseline Tests (Zero regressions)
  - 20 M6 Integration Scenarios
  - 17 M6 Hardening Verification Tests
  - Warnings: 2 expected `UserWarning`s (intentional trust boundary controls); 0 deprecation warnings.
- **Operational Demonstrations:**
  - [`scripts/run_piis_demo.py`](file:///c:/Production%20level%20projects/PIIS/scripts/run_piis_demo.py) verified across all 12 operational stages with exit code 0.
  - [`scripts/demonstrate_m6_operational_flow.py`](file:///c:/Production%20level%20projects/PIIS/scripts/demonstrate_m6_operational_flow.py) verified across all 9 operational steps with exit code 0.
- **Static Analysis & Lint Hygiene:** `ruff check .` passes with **0 errors across the entire codebase** (Exit code 0).
  - Resolved `Optional` type import defect in `alarm_simulator.py`.
  - Upgraded deprecated Starlette constant `HTTP_422_UNPROCESSABLE_ENTITY` to RFC 9110 standard `HTTP_422_UNPROCESSABLE_CONTENT` in `src/piis/api/app.py` and `src/piis/api/routers/incidents.py`.
  - Pruned unused variable assignment in `prometheus.py`.
  - Cleaned safe unused imports across 22 modules under `src/`.
  - Pruned 5 unused test fixture variables in `test_m6_integration_and_reliability.py`.
  - Cleaned naming and imports across historical audit scripts in `scripts/`.
- **Secret & Licensing Audit:**
  - Automated scan confirmed 0 credentials, 0 private keys, and 0 production tokens leaked.
  - Licensing Governance: Root `LICENSE` file is currently absent from repository root; source code is intended for Apache-2.0 licensing, and a formal `LICENSE` file and third-party notices are prepared for maintainer review prior to initial commit. Core runtime dependencies use permissive licenses (MIT/Apache 2.0/BSD); copyleft raw datasets (`SRC-005` GPL-3.0) isolated via `.gitignore`.
- **Installation Smoke Test:** Clean venv creation verified; offline sandbox package download boundary documented; local runtime API health (`/api/v1/health`), readiness (`/api/v1/ready`), UI dashboard (`/ui`), and CLI entry points 100% verified.
- **Source Tree Digest Progression:**
  - Historical M6 Closure Baseline: `cfd9ce798195d727f3698d7c73008b6dd59c05ec2716294b8c1ccbcd0e03579d`
  - Post-Hygiene Intermediate Digest: `7706ff99f0816558ab2b9fad513c32ba0a0c215ccc132d8503eae1936c852452`
  - Post-Warning-Reconciliation Intermediate Digest: `fa05cbe631f2d567015d6b17b88ec9d406014849dfff046f4a2205c0d64df7de` (with unpruned setuptools `piis.egg-info`)
  - Final Release Candidate Clean Source / Test SHA-256 (`v1.0.0-rc1`): `09a280bd04971a88c44627fd9145c8ed34aa3f765c5ecc216182656a81e26af9` (exact 145 pure source and test files: `src/` 92 + `tests/` 53)
- **Complete Reconciled Release Manifest:**
  - Manifest file: `docs/release/RELEASE_MANIFEST.sha256` (405 files)
  - Scope: 92 in `src/`, 53 in `tests/`, 66 in `scripts/`, 153 in `docs/` (excluding manifest), 5 in `configs/`, 3 in `infra/`, 7 in `schemas/`, 3 in `.github/`, 10 in `data/evaluation/`, 6 root configuration files, and 7 directory anchors (`.gitkeep`).
  - Evaluation Protection: 4 `SEALED_HOLDOUT` evaluation datasets (`blind_holdout.json`, `blind_redteam.json`, `fresh_redteam_m5_5.json`, `sealed_holdout_m5_5.json`) strictly excluded via `.gitignore` to protect against model tuning and evaluation leakage; 10 governance manifests, regression benchmarks, and benign control sets are staged.
- **Dependency Reproducibility:**
  - Deterministic lockfile `requirements-lock.txt` pinning 23 core runtime packages with explicit direct vs transitive classification. Sandbox offline boundary truthfully disclosed.

---

## 5. Known Operational Limitations

- **Simulated Test Harnesses:** Ingestion adapters are validated against local simulation engines; live carrier network adapters require enterprise staging trials.
- **Static Topology Representation:** Correlation operates on static cell hierarchies; dynamic SDN pathing requires inventory integration.
- **Out-of-Distribution Runbooks:** Un-indexed vendor equipment codes default to conservative human escalation.
- **Docker Daemon Availability:** Static Dockerfile and Compose configurations were validated; live image builds require host Docker daemon activation.

---

## 6. External Enterprise Deployment Blockers (Open Prerequisites)

Live production deployment remains **BLOCKED** pending the provisioning of four external enterprise infrastructure dependencies:

| Prerequisite ID | Subsystem | Requirement Description |
| :--- | :--- | :--- |
| **`DEP-M5.3-001`** | Identity | Corporate OIDC identity provider discovery endpoint and client registration. |
| **`DEP-M5.3-002`** | Storage | Hardware WORM storage or S3 Object Lock bucket for audit ledger root anchoring. |
| **`DEP-M5.5.1-001a`** | KMS | Cloud KMS (AWS KMS / Azure Key Vault) HSM for asymmetric evaluation manifest signing. |
| **`DEP-M5.5.1-001b`** | Timestamp | Trusted RFC 3161 Timestamp Authority (TSA) HTTPS endpoint. |

---

## 7. Quickstart Commands

```bash
# 1. Install PIIS
pip install -e ".[api,observability,retrieval,dev]"

# 2. Run Complete Test Suite (349 tests)
pytest

# 3. Run Static Analysis Linter (0 errors)
ruff check .

# 4. Run Reproducible 12-Stage Operational Demo
python scripts/run_piis_demo.py

# 5. Start Application Server
python -m uvicorn piis.api.app:app --host 0.0.0.0 --port 8000
```
