# PIIS Repository Audit & Architectural Health Assessment

- **Date:** 2026-10-31
- **Status:** Complete (Stage A Execution)
- **Assessed By:** Principal AI/ML Engineer & Telecom Systems Architect

---

## 1. Executive Summary

This audit establishes the baseline technical state of the **Production Incident Intelligence System (PIIS)** repository prior to Milestone 1 execution. 
The repository currently represents an initial engineering starter kit and structural scaffold. Core governance rules, architectural principles, schema specifications, and evaluation guidelines are thoroughly drafted. However, the operational implementation is currently minimal: core ingestion, normalization, and profiling pipelines are either skeletal or absent, only 4 unit tests exist, and no raw or processed datasets have yet been acquired or registered.

---

## 2. Inventory of Existing Components

The repository comprises the following structural components:

| Component Area | Directory / Path | Current State | Notes |
| :--- | :--- | :--- | :--- |
| **Agent Configuration** | `.agent/` | Complete specifications | Contains `rules/` (`data-and-ml.md`, `engineering.md`) and `workflows/` (`milestone-1-data-foundation.md`, `model-development.md`). |
| **GitHub Scaffolding** | `.github/` | Scaffolding | Issue templates (`bug_report.md`, `data_issue.md`) and basic CI workflow (`ci.yml`). |
| **Specifications & Governance** | `docs/` | Comprehensive initial draft | Complete PRD, TRD, architecture documentation, 3 ADRs, data governance, annotation handbook, and evaluation plan. |
| **JSON Schemas** | `schemas/` | Complete v1.0 specifications | 6 draft-2020-12 schemas: `incident`, `alarm`, `telemetry`, `resolution`, `evidence`, `recommendation`. |
| **Configuration** | `configs/` | Scaffolding | `app.yaml` (runtime flags) and `routing_policy.example.yaml` (routing rules). |
| **Core Application Code** | `src/piis/` | Skeletal scaffold | Minimal stubs for `provenance.py` and `policies/routing.py`. Submodules (`audit`, `classification`, `correlation`, `ingestion`, `normalization`, `recommendations`, `retrieval`, `routing`) contain only `README.md` and `__init__.py`. |
| **Data Directory Tree** | `data/` | Empty structure | Subdirectories (`raw/`, `interim/`, `processed/`, `synthetic/`) contain only `.gitkeep`. |
| **Developer Utilities** | `scripts/` | Partial prototype | `validate_record.py` (CLI JSON Schema validator) and `profile_dataset.py` (basic single-file profiling script). |
| **Test Suite** | `tests/` | Minimal | `conftest.py`, `fixtures/incident.example.json`, and `unit/test_routing_policy.py` (4 unit tests). |
| **Infrastructure** | `infra/docker/` | Scaffolding | `Dockerfile` and `compose.yaml` for local containerization. |
| **Packaging & Build** | `pyproject.toml`, `Makefile` | Configured | Configured for Python 3.11+ editable build; installed cleanly in local environment. |

---

## 3. Implemented vs. Missing Functionality

### 3.1 Implemented Functionality
- **Packaging and build system:** `pyproject.toml` correctly sets up the `piis` package with tool configs for `ruff`, `mypy`, and `pytest`.
- **Policy stub & conservative decision rules:** `piis.policies.routing.recommend_support_level` provides a pure Python function implementing 4 conservative routing decisions (`L1`, `L2`, `L3`, `HUMAN_REVIEW`).
- **Initial schema validation CLI:** `scripts/validate_record.py` successfully validates records against Draft 2020-12 JSON schemas using `jsonschema`.
- **Basic DataFrame Profiler:** `scripts/profile_dataset.py` reads CSV/JSON/JSONL and extracts file SHA-256, shape, data types, missing counts/percentages, duplicate row counts, and numeric summaries.
- **Unit testing:** 4 baseline tests verifying routing policy behavior against synthetic evidence.

### 3.2 Missing Functionality (Gap Analysis)
- **Multi-format dataset ingestion pipeline:** No reusable Python module under `src/piis/ingestion` to stream, read, or batch-load heterogeneous sources (Parquet, compressed CSVs, chunked JSON/JSONL) with provenance metadata attachments.
- **Robust comprehensive profiling pipeline (M1.3 requirement):** `scripts/profile_dataset.py` does not output the required artifacts:
  - `profile.json` (comprehensive structure)
  - `column_summary.csv`
  - `missingness_report.csv`
  - `duplicate_report.json`
  - `label_distribution.csv`
  - `temporal_profile.json`
  - `data_quality_report.md`
  - Parquet and compressed formats are not supported.
  - Outliers, timestamp cadence/sampling intervals, categorical cardinality, and identifier uniqueness checks are not implemented.
- **Source-to-canonical normalization:** `src/piis/normalization` has no transformation functions for timestamp timezone alignment to UTC, metric unit standardizations, or canonical identifier mapping.
- **Provenance management library:** `src/piis/provenance.py` only contains a basic `SourceType` enum without classes for tracking dataset lineage, checksums, license attributes, or ingestion batches.
- **Configuration loading & policy engine:** `configs/routing_policy.example.yaml` exists, but there is no parser or engine in `src/piis` that dynamically loads YAML rules into the routing policy evaluator.
- **Target leakage guards & feature contracts:** No contract definitions or pipeline guards to enforce Rule 1 (preventing resolution summaries and post-prediction telemetry from entering feature sets).
- **Public dataset acquisition & verification:** No raw public dataset files currently exist under `data/raw/`.

---

## 4. Architecture and Schema Inconsistencies

During the audit, the following inconsistencies and divergences across documentation, schemas, and code were identified:

1. **`SourceType` / Provenance Enum Divergence:**
   - In `schemas/incident.schema.json` & `schemas/resolution.schema.json`: `source_type` enum allows:
     `["PUBLIC_REAL", "SYNTHETIC", "DERIVED", "HUMAN_ANNOTATED"]`
   - In `schemas/alarm.schema.json` & `schemas/telemetry.schema.json`: `source_type` enum allows:
     `["PUBLIC_REAL", "SYNTHETIC", "DERIVED"]` (omits `HUMAN_ANNOTATED`)
   - In `schemas/evidence.schema.json`: `source_type` enum allows:
     `["PUBLIC_REAL", "SYNTHETIC", "DERIVED", "HUMAN_ANNOTATED", "OPERATOR_INTERNAL"]`
   - In `docs/data/DATA_GOVERNANCE.md`: Provenance classes are defined as `PUBLIC_REAL`, `SYNTHETIC`, `DERIVED`, `HUMAN_ANNOTATED` (`OPERATOR_INTERNAL` is omitted).
   - In `src/piis/provenance.py`: Only `PUBLIC_REAL`, `SYNTHETIC`, `DERIVED`, `HUMAN_ANNOTATED` are defined.
   - *Impact:* Validating an evidence record with `source_type="OPERATOR_INTERNAL"` would fail if processed against Python enum or incident schemas.
   - *Resolution:* Align provenance definitions across code, schemas, and governance documentation.

2. **Support Level Field Naming Mismatch:**
   - In `schemas/incident.schema.json`: Property is named `support_level_label` with enum `["L1", "L2", "L3", "HUMAN_REVIEW", "UNLABELED"]`.
   - In `schemas/resolution.schema.json`: Property is named `support_level` with enum `["L1", "L2", "L3", "HUMAN_REVIEW", "UNLABELED"]`.
   - In `schemas/recommendation.schema.json`: Property is named `decision` with enum `["L1", "L2", "L3", "HUMAN_REVIEW"]`.
   - *Impact:* Mapping resolution records to incident records requires explicit key renaming rather than uniform attribute naming.

3. **Date-Time Format Constraints:**
   - In `schemas/incident.schema.json`: `created_at` enforces `"format": "date-time"`, but `resolved_at` only specifies `{"type": ["string", "null"]}` without `"format": "date-time"`.
   - *Impact:* Malformed timestamp strings in `resolved_at` could pass schema validation.

4. **Policy Configuration vs Implementation:**
   - `configs/routing_policy.example.yaml` specifies rule predicates: `known_issue_match`, `approved_runbook`, `required_permissions_available`, `advanced_diagnostics_required`, `specialist_dependency`, `insufficient_evidence`.
   - `src/piis/policies/routing.py` hardcodes these in a `@dataclass(frozen=True) class RoutingEvidence`, but uses `approved_runbook_available` (with `_available` suffix) and `evidence_sufficient` (inverted logic compared to `insufficient_evidence`).
   - *Impact:* The code cannot directly bind to the YAML configuration without translation.

---

## 5. Dependency Analysis & Environment Verification

- **Python Version:** Local environment runs `Python 3.11.5` on Windows.
- **Dependencies Installed & Verified:**
  - `pandas` (2.2.3)
  - `numpy` (2.4.6)
  - `pyarrow` (21.0.0)
  - `pydantic` (2.12.5)
  - `jsonschema` (4.26.0)
  - `scikit-learn` (1.6.1)
  - `typer` (0.26.2)
  - `rich` (14.3.2)
  - `pytest` (8.4.1)
  - `pyyaml` (6.0.3)
- **Dependency Discrepancy:**
  - `pyproject.toml` lacks `pyyaml` in its primary dependencies, despite `configs/*.yaml` being central to the configuration model.
  - *Recommendation:* Add `pyyaml>=6.0` to `dependencies` in `pyproject.toml`.

---

## 6. Test Suite & Coverage Assessment

- **Existing Tests:** Only 1 test file (`tests/unit/test_routing_policy.py`) containing 4 unit tests.
- **Test Execution Status:** 4 passed in 0.07s.
- **Missing Test Coverage:**
  - Schema validation test suite (validating all 6 schemas with valid fixtures and testing rejection of invalid records, missing fields, out-of-range values, invalid enum literals).
  - Dataset profiler tests (testing profile generation across CSV, JSON, JSONL, Parquet, handling nulls, empty files, duplicates, skewed distributions).
  - Ingestion adapter tests (testing line parsing, format detection, chunking, malformed row quarantine).
  - Provenance tracking tests (testing SHA-256 calculation, source metadata integrity, immutable metadata validation).
  - Timezone and timestamp normalization tests (converting offset timestamps to UTC, detecting missing tz, parsing ISO 8601).
  - Policy parser and evaluator tests (testing loading YAML policies, rule evaluation order, default fallback to `HUMAN_REVIEW`).

---

## 7. Security & Operational Safety Audit

PIIS is designed as a telecom operations decision-support system with safety-critical boundaries:
- **Operational Safety Boundary:** Verified present in code and configuration. `configs/app.yaml` sets `read_only_mode: true`, `production_commands_enabled: false`, `autonomous_ticket_updates: false`. ADR-0002 prohibits autonomous actions.
- **Untrusted Input Risk:** Incident descriptions and resolution notes originate from external ITSM or public datasets. They must be treated as untrusted text to prevent prompt-injection attacks when feeding downstream LLM components.
- **Subscriber PII Minimization:** Telemetry and ticket records must strictly exclude subscriber MSISDN, IMSI, IMEI, and personal identifiers.
- **Secret Management:** No API keys, credentials, or production tokens are committed. `.env.example` provides clean variable stubs.

---

## 8. Milestone 1 Execution Plan

To fulfill the requirements of Milestone 1 (Data Foundation), the following phased engineering steps are structured:

### Stage B: Public Dataset Acquisition Research & Registration
1. Investigate the 4 candidate sources listed in `DATASET_MANIFEST.md`:
   - ITU/Zindi AI Telco Troubleshooting Challenge
   - TelecomTS (Hugging Face)
   - LCORE-D (Zenodo)
   - Kaggle Cellular Network Anomaly Detection
2. Verify access, licenses, format, network domain, and schemas.
3. Download permitted accessible datasets into `data/raw/<source_id>/` without modification.
4. Record exact SHA-256 hashes, file sizes, versions, and licensing in `docs/data/SOURCE_REGISTER.csv`.
5. Compile comprehensive findings into `docs/data/DATASET_ACQUISITION_REPORT.md`.

### Stage C: Robust Automated Profiling Pipeline
1. Upgrade `scripts/profile_dataset.py` and implement modular profiling utilities in `src/piis/ingestion/profiling.py`.
2. Support CSV, JSON, JSONL, and Parquet.
3. Compute all required statistical, missingness, duplicate, cardinality, outlier, and temporal metrics.
4. Generate structured profile outputs in `artifacts/data_profiles/<source_id>/`:
   - `profile.json`, `column_summary.csv`, `missingness_report.csv`, `duplicate_report.json`, `label_distribution.csv`, `temporal_profile.json`, `data_quality_report.md`.

### Stage D: Data Quality & Provenance Assessment
1. Profile acquired datasets.
2. Conduct deep data quality investigation (missingness mechanisms, sampling jitter, class imbalances, label noise, duplicate records).
3. Produce `docs/data/DATA_QUALITY_REPORT.md` backed by actual profiling artifacts.

### Stage E: Canonical Schema Mapping & Ingestion Module
1. Create `docs/data/SOURCE_TO_CANONICAL_MAPPING.md` mapping source fields to canonical schemas.
2. Resolve identified schema inconsistencies and update schema files if needed.
3. Build normalization and validation functions in `src/piis/normalization/` and `src/piis/ingestion/`.

### Stage F: Annotation Guidelines & Synthetic Scenario Specifications
1. Review and refine `ANNOTATION_HANDBOOK.md` into `docs/data/L1_L2_ANNOTATION_GUIDELINES.md` with explicit decision matrices, ambiguous case handling, and inter-annotator agreement protocol.
2. Review and elaborate `SYNTHETIC_DATA_SPEC.md` covering initial scenario families (S01 to S10) with explicit causal parameterizations and negative controls.

### Stage G: Validation & Test Suite
1. Build comprehensive unit and integration tests across schemas, profiling, normalization, and provenance.
2. Verify 100% test pass rate and verify reproducibility.

### Stage H: Milestone 1 Completion Review
1. Compile `docs/MILESTONE_1_COMPLETION_REPORT.md` with verifiable evidence, statistics, and audit verification.
