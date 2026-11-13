# Milestone 1 Completion Report — Data Foundation

- **System:** Production Incident Intelligence System (PIIS)
- **Milestone:** Milestone 1 — Data Foundation
- **Status:** **COMPLETE** (All Exit Criteria Satisfied with Empirical Verification)
- **Lead Architect / Engineer:** Principal AI/ML Engineer & Telecom Network Intelligence Architect
- **Completion Date:** 2026-10-31

---

## 1. Executive Summary

Milestone 1 establishes the empirical, reproducible, and governance-grounded data foundation for the Production Incident Intelligence System (PIIS).
In strict compliance with the **Master Execution Prompt**, no premature ML training or unconstrained synthetic data generation was undertaken. Instead, the entire repository was systematically audited, candidate public telecom datasets were researched and acquired, automated profiling and quality pipelines were engineered, schema discrepancies were resolved, an L1/L2 annotation framework was established, and deterministic scenario generation specifications were designed and verified.

---

## 2. Milestone 1 Exit Criteria Verification

| Exit Criterion | Status | Evidence & Artifact Reference |
| :--- | :--- | :--- |
| **Complete Repository Audit** | **COMPLETE** | `docs/REPOSITORY_AUDIT.md` (gap analysis, schema audit, dependency review). |
| **Public Dataset Acquisition** | **COMPLETE** | 2 permitted datasets acquired locally: TelecomTS (`SRC-002`, MIT) and UCC 5G (`SRC-005`, GPL-3.0). Detailed investigation of blocked sources (`SRC-001`, `SRC-003`, `SRC-004`) documented in `docs/data/DATASET_ACQUISITION_REPORT.md`. |
| **Source Register Catalog** | **COMPLETE** | `docs/data/SOURCE_REGISTER.csv` with SHA-256 hashes, file sizes, row counts, and licenses. |
| **Automated Profiling Engine** | **COMPLETE** | `src/piis/ingestion/profiling.py` and `scripts/profile_dataset.py` generating all 7 machine-readable reports per dataset in `artifacts/data_profiles/`. |
| **Data Quality Assessment** | **COMPLETE** | `docs/data/DATA_QUALITY_REPORT.md` backed by empirical profiling metrics (missingness, duplicates, outliers, temporal cadence). |
| **Canonical Schema Mapping** | **COMPLETE** | `docs/data/SOURCE_TO_CANONICAL_MAPPING.md` documenting field-by-field transforms and unit normalizations. |
| **Schema Inconsistency Resolution** | **COMPLETE** | Harmonized `source_type` enum across all 6 schemas; added date-time validation to `resolved_at`; added `pyyaml` to `pyproject.toml`. |
| **Provenance-First Pipeline** | **COMPLETE** | Implemented `src/piis/provenance.py` (`SourceType` and `ProvenanceRecord`), enforcing zero mixing of public-real, synthetic, and derived data. |
| **Normalization Pipeline** | **COMPLETE** | Built `src/piis/normalization/telemetry.py` and `src/piis/normalization/incidents.py`, validated by `scripts/normalize_dataset.py`. |
| **L1/L2 Annotation Framework** | **COMPLETE** | `docs/data/L1_L2_ANNOTATION_GUIDELINES.md` separating technical fault labels from support policy, detailing decision logic and $\kappa$ agreement metrics. |
| **Synthetic Scenario Specs** | **COMPLETE** | `docs/data/SYNTHETIC_DATA_SPEC.md` covering S01–S10 + S00; generator implemented in `src/piis/synthetic/generator.py` and CLI `scripts/generate_synthetic.py`. |
| **Automated Test Suite** | **COMPLETE** | **24 unit tests passing 100%** (`tests/unit/test_schemas.py`, `test_profiler.py`, `test_normalization.py`, `test_provenance.py`, `test_routing_policy.py`, `test_synthetic_generator.py`). |
| **Reproducibility Guide** | **COMPLETE** | `docs/REPRODUCIBILITY.md` detailing step-by-step commands from setup to validation. |

---

## 3. What Was Downloaded & Inspected

### 3.1 Acquired Raw Datasets (in `data/raw/`)

1. **TelecomTS (`SRC-002`)**:
   - `jammer_metrics.csv` (1,459,526 bytes | SHA-256: `59d489b49b5206cdedfdce924a7ab1891189858ea1a33fd373eb8449e4e4f554`)
     - Rows: 9,999 | Columns: 20
     - Cadence: Exactly 10.0 Hz (0.1s delta)
     - Content: Physical/MAC layer telemetry (RSRP, DL/UL BLER, MCS, PRB utilization) under active over-the-air RF jamming.
   - `congestion_metrics.csv` (1,437,934 bytes | SHA-256: `fe95b3f89c3364de03c98ffb816172f84e9f3759ff996109907d9afbb5c30b04`)
     - Rows: 9,999 | Columns: 19
   - `normal_mobile_metrics.csv` (1,559,941 bytes | SHA-256: `22fed40d9bdf2e2af062d80455842b9876677a51709d475c1f91066d2356f9a8`)
     - Rows: 9,999 | Columns: 19
   - `jammer_chunked.jsonl` (3,560,362 bytes | SHA-256: `bfe1e686b0b24d24cd7fc7be472be36109b8a37ffd8e8691ee9ed2c8730d3b82`)
     - Records: 93 multi-modal Q&A pairs with diagnostic reasoning and root-cause summaries.

2. **UCC 5G Production Dataset (`SRC-005`)**:
   - `5G-production-dataset.zip` (2,177,094 bytes | SHA-256: `abc729d696b5e0ba34a9c6ed35a851f2868d2b5071be5efb8a49691c23bb1a9b`)
   - Unpacked: 166 production drive-test and stationary trace files across Amazon Prime, Netflix, and file download workloads.
   - Content: Real commercial 5G Non-Standalone / LTE client KPIs (RSRP, RSRQ, SNR, CQI, Bitrate, Handover states).

### 3.2 Blocked Sources Inspected & Documented

- **SRC-001 (ITU / Zindi):** Requires account registration, terms agreement, and session token. Documented manual instructions.
- **SRC-003 (LCORE-D):** Discovered manifest error (Zenodo 10693296 was an unrelated zoology figure). Identified authentic Mendeley DOI `10.17632/77sztrg5ks.1`; verified active repository embargo until `2026-06-14`.
- **SRC-004 (Kaggle Anomaly Detection):** Requires Kaggle API authentication (`kaggle.json`).

---

## 4. What Was Implemented

1. **`src/piis/ingestion/profiling.py`**:
   - Production-grade dataset profiler supporting CSV, compressed CSV (gzip, bz2, zip), JSON, JSONL, and Parquet.
   - Robust against nested dictionaries and unhashable structures.
   - Computes statistical summaries, missingness tiers, duplicate rates, label frequencies, IQR outliers, and temporal metrics.
2. **`scripts/profile_dataset.py`**:
   - CLI utility exporting the 7 required machine-readable profile artifacts.
3. **`src/piis/provenance.py`**:
   - `SourceType` enum (`PUBLIC_REAL`, `SYNTHETIC`, `DERIVED`, `HUMAN_ANNOTATED`, `OPERATOR_INTERNAL`).
   - Immutable frozen dataclass `ProvenanceRecord` with audit serialization.
4. **`src/piis/normalization/telemetry.py`**:
   - Normalization functions for TelecomTS and UCC 5G datasets with schema validation.
5. **`src/piis/normalization/incidents.py`**:
   - Normalization function converting diagnostic records into canonical incidents with post-resolution feature quarantine.
6. **`scripts/normalize_dataset.py`**:
   - Ingestion CLI writing normalized JSONL streams to `data/processed/`.
7. **`src/piis/policies/routing.py`**:
   - Upgraded routing policy engine with YAML configuration loader (`PolicyEngine.from_yaml`) and backward-compatible evaluation functions.
8. **`src/piis/synthetic/generator.py` & `scripts/generate_synthetic.py`**:
   - Seeded scenario generator supporting S01 through S10 + S00 (negative controls), outputting schema-validated incidents, alarms, and telemetry.
9. **Harmonized JSON Schemas**:
   - Updated `telemetry.schema.json`, `alarm.schema.json`, `incident.schema.json`, and `resolution.schema.json`.

---

## 5. Automated Test Results

Executed with `pytest -v`:

```
tests/unit/test_normalization.py::test_telecomts_telemetry_normalization PASSED [  4%]
tests/unit/test_normalization.py::test_ucc5g_telemetry_normalization PASSED     [  8%]
tests/unit/test_normalization.py::test_telecomts_incident_normalization PASSED  [ 12%]
tests/unit/test_profiler.py::test_compute_sha256 PASSED                         [ 16%]
tests/unit/test_profiler.py::test_load_dataset_file PASSED                     [ 20%]
tests/unit/test_profiler.py::test_profiler_reports_and_artifacts PASSED        [ 25%]
tests/unit/test_provenance.py::test_source_type_enum PASSED                     [ 29%]
tests/unit/test_provenance.py::test_provenance_record_immutability PASSED      [ 33%]
tests/unit/test_provenance.py::test_provenance_serialization PASSED             [ 37%]
tests/unit/test_routing_policy.py::test_insufficient_evidence_abstains PASSED  [ 41%]
tests/unit/test_routing_policy.py::test_known_runbook_case_can_be_l1 PASSED     [ 45%]
tests/unit/test_routing_policy.py::test_advanced_diagnostics_routes_l2 PASSED   [ 50%]
tests/unit/test_routing_policy.py::test_specialist_dependency_routes_l3 PASSED  [ 54%]
tests/unit/test_routing_policy.py::test_policy_engine_yaml_loading PASSED       [ 58%]
tests/unit/test_schemas.py::test_valid_incident_record PASSED                   [ 62%]
tests/unit/test_schemas.py::test_invalid_incident_missing_required_fields PASSED[ 66%]
tests/unit/test_schemas.py::test_invalid_incident_illegal_enum PASSED          [ 70%]
tests/unit/test_schemas.py::test_valid_telemetry_record PASSED                  [ 75%]
tests/unit/test_schemas.py::test_valid_alarm_record PASSED                      [ 79%]
tests/unit/test_schemas.py::test_valid_evidence_record PASSED                   [ 83%]
tests/unit/test_schemas.py::test_valid_recommendation_record PASSED             [ 87%]
tests/unit/test_synthetic_generator.py::test_generator_deterministic_reproducibility PASSED [ 91%]
tests/unit/test_synthetic_generator.py::test_generator_all_scenario_families PASSED [ 95%]
tests/unit/test_synthetic_generator.py::test_generator_negative_control PASSED [100%]

============================== 24 passed in 1.03s ==============================
```

- **Ruff Linter:** `ruff check src tests scripts` -> **All checks passed (0 errors)**.

---

## 6. Key Empirical Findings & Known Limitations

1. **Class Imbalance in TelecomTS:**
   - Active RF jamming represents 18.96% of time steps; normal baseline represents 81.04%. Future anomaly detection models must use PR-AUC rather than accuracy.
2. **Missing Protocols During Idle Radio States:**
   - Uplink/downlink protocol columns exhibit 7–19% missing values corresponding to idle periods where no IP frames were scheduled. Normalization handles this by mapping to `"NONE"`.
3. **UCC 5G String Sentinels:**
   - Unrecorded measurements in commercial handsets are logged as `"-"` rather than NaN. The normalization pipeline maps these to standard nulls.
4. **Target Leakage Hazard:**
   - Diagnostic summaries and root causes in `chunked.jsonl` must remain strictly segregated from ticket-time routing features.
5. **No Production Claims from Synthetic Data:**
   - Synthetic data generation in `PIIS-TelcoBench` is calibrated for architectural testing and pipeline verification; it is never represented as live operator evidence.

---

## 7. Outstanding Tasks & Transition to Milestone 2

Milestone 1 is complete. The repository data foundation is verified and reproducible.
The project is now ready to proceed to **Milestone 2 — Baselines**:
- Task M2.1: Feature extraction pipeline (ticket-time text and telemetry-window features).
- Task M2.2: Deterministic routing policy baseline evaluation.
- Task M2.3: Telecom fault classification baseline (Logistic Regression / XGBoost / LightGBM).
- Task M2.4: Incident severity estimation baseline.
- Task M2.5: Baseline evaluation report and model cards.
