# PIIS Data Quality Assessment Report

- **Document Version:** 1.0
- **Milestone:** M1 — Data Foundation (Deliverable M1.4)
- **Status:** Complete / Verified
- **Assessed By:** Principal AI/ML Engineer & Telecom Data Architect
- **Date:** 2026-10-31

---

## 1. Executive Summary

This report presents the empirical data quality findings from profiling the acquired public-real telecommunications datasets:
1. **TelecomTS (`SRC-002`)**: High-frequency (10 Hz) 5G testbed time series covering RF jamming interference, congestion, and normal mobile baselines, accompanied by multi-modal diagnostic reasoning traces.
2. **UCC 5G Production Dataset (`SRC-005`)**: 1 Hz client-side production telemetry collected from a major commercial Irish mobile network across driving and stationary mobility profiles.

All findings are directly supported by machine-readable profiling artifacts generated in `artifacts/data_profiles/`.

---

## 2. Profiling Artifacts Provenance

The following machine-readable profiles were generated and validated:

| Dataset Profile Directory | Source File Path | Rows Profiled | Columns | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| `artifacts/data_profiles/SRC-002-jammer_metrics/` | `data/raw/SRC-002/jammer_metrics.csv` | 9,999 | 20 | `59d489b49b5206cdedfdce924a7ab1891189858ea1a33fd373eb8449e4e4f554` |
| `artifacts/data_profiles/SRC-002-congestion_metrics/` | `data/raw/SRC-002/congestion_metrics.csv` | 9,999 | 19 | `fe95b3f89c3364de03c98ffb816172f84e9f3759ff996109907d9afbb5c30b04` |
| `artifacts/data_profiles/SRC-002-normal_mobile_metrics/` | `data/raw/SRC-002/normal_mobile_metrics.csv` | 9,999 | 19 | `22fed40d9bdf2e2af062d80455842b9876677a51709d475c1f91066d2356f9a8` |
| `artifacts/data_profiles/SRC-002-jammer_chunked/` | `data/raw/SRC-002/jammer_chunked.jsonl` | 93 | 9 | `bfe1e686b0b24d24cd7fc7be472be36109b8a37ffd8e8691ee9ed2c8730d3b82` |
| `artifacts/data_profiles/SRC-005-ucc_5g_drive/` | `data/raw/SRC-005/unpacked/.../B_2019.11.28_07.27.57.csv` | 1,898 | 26 | `59e3c9e16b19d6ac7cffd857b542224032dfd08b3a152f41172087e9007b6160` |
| `artifacts/data_profiles/SRC-005-ucc_5g_static/` | `data/raw/SRC-005/unpacked/.../B_2019.11.23_14.30.10.csv` | 1,098 | 26 | `e9e55dd1ecbf3aa175f10be64f42ebb5592a9d3789660e5ff69b8f1d1375b318` |

---

## 3. Detailed Data Quality Assessment

### 3.1 Missingness Patterns

1. **TelecomTS (`SRC-002`)**:
   - The majority of PHY/MAC/Transport KPIs (`RSRP`, `DL_BLER`, `DL_MCS`, `UL_BLER`, `UL_MCS`, `PRBs_DL_Current`, etc.) exhibit **0.0% missingness**.
   - Protocol classification columns contain structural missing values:
     - `DL_Protocol`: 7.04% missing (704 / 9,999 rows) in `jammer_metrics.csv`; 18.99% missing (1,899 / 9,999 rows) in `congestion_metrics.csv`; 11.48% missing (1,148 / 9,999 rows) in `normal_mobile_metrics.csv`.
     - `UL_Protocol`: 0.30% missing in jammer metrics, 0.05% in congestion metrics, and 3.16% in normal mobile metrics.
   - **Root Cause & Mechanism:** Missing protocol values correspond to idle telemetry windows where no downlink or uplink IP packets were scheduled across the radio bearer. This is **Missing Completely at Random (MCAR)** with respect to the measurement equipment, but **Missing Not at Random (MNAR)** with respect to user traffic activity.
   - **Handling Strategy:** Impute with categorical token `"NONE"` or `"IDLE"`; do not drop rows.

2. **UCC 5G (`SRC-005`)**:
   - Standard Pandas `isna()` reported 0% missingness because unrecorded measurements are encoded as sentinel character strings: `"-"`.
   - Sentinel prevalence:
     - `PINGAVG`, `PINGMIN`, `PINGMAX`, `PINGSTDEV`, `PINGLOSS`: **100.0% encoded as `"-"`** in video streaming and file download traces (ICMP active pinging was disabled during HTTP application benchmarking).
     - `CQI`: 13.70% encoded as `"-"` in drive tests, 4.19% in static tests (indicating out-of-coverage or asynchronous channel state report).
     - `NRxRSRQ`: 20.23% in drive tests and 10.29% in static tests encoded as `"-"` (reflecting periods where 5G secondary cell component was deactivated or unattached).
   - **Handling Strategy:** Normalization parser must map sentinel string `"-"` to IEEE NaN / `null` and flag indicator column `has_active_ping=False`.

---

### 3.2 Duplicate Records

- **Full-Row Duplication:**
  - Both `SRC-002` (all telemetry and reasoning records) and `SRC-005` (drive and static traces) have **0 duplicate rows (0.0%)**.
- **Timestamp Key Collisions:**
  - `SRC-002`: Timestamps are millisecond-resolved with 0 duplicate timestamps across all 9,999 records.
  - `SRC-005`: In `B_2019.11.28_07.27.57.csv`, there are **75 timestamp collisions (3.95%)**.
  - **Investigation:** G-NetTrack logs timestamps at 1-second integer resolution (`YYYY.MM.DD_HH.MM.SS`). When rapid GPS or radio state changes trigger back-to-back writes within the same second, multiple rows share identical integer seconds.
  - **Handling Strategy:** De-duplicate only using compound primary key: `(Timestamp, CellID, State, DL_bitrate)` or add monotonic microsecond sequence offset. Never discard records based on timestamp alone.

---

### 3.3 Temporal Characteristics & Sampling Cadence

1. **TelecomTS Sampling:**
   - Cadence: Exactly **10.0 Hz** (median interval = `0.1000` seconds; mean = `0.1000` seconds; std dev = `0.0000`).
   - Time span: 999.8 seconds (~16.66 minutes continuous uninterrupted observation per file).
   - Quality: Zero sampling jitter, zero timestamp gaps. Highly suitable for high-resolution anomaly detection and sequence modeling.

2. **UCC 5G Production Sampling:**
   - Cadence: **1.0 Hz nominal** (median interval = `1.000` seconds), with occasional duplicate seconds (0s delta) and minor GPS acquisition latency gaps.
   - Time span: Drive trace span = 31.6 minutes (1,898 records); Static trace span = 18.3 minutes (1,098 records).
   - Quality: Realistic field telemetry reflecting vehicular mobility and multi-path radio propagation.

---

### 3.4 Outlier Analysis & Extreme Value Regimes

1. **TelecomTS Physical Layer Outliers:**
   - In `jammer_metrics.csv`, **6,684 outlier observations** were flagged by IQR bounds.
   - DL Block Error Rate (`DL_BLER`) surges from a baseline of `0.0` to `1.0` (100% packet loss) during jamming events.
   - `UL_MCS` (Modulation and Coding Scheme) drops from modulation index 28 (256-QAM) down to index 0 (QPSK or link loss).
   - `RSRP` drops from nominal -78 dBm down to -115 dBm.
   - **Verdict:** These are not measurement errors or corrupted data; they represent the **genuine physical symptoms of radio frequency interference**. They must be preserved to train anomaly detection and RCA models.

2. **UCC 5G Physical Layer Outliers:**
   - `NRxRSRQ` contains values of `-204.0 dB` and `-225.0 dB`.
   - **Investigation:** Standard 3GPP RSRQ ranges from -3 dB to -19.5 dB. Values below -100 dB represent modem unattached / out-of-sync error codes in Qualcomm baseband diagnostic logs.
   - **Handling Strategy:** Clip unphysical values below -30 dB or map to separate out-of-sync indicator.

---

### 3.5 Class Imbalance & Target Label Distribution

1. **TelecomTS Jammer Anomaly Labels:**
   - `Jamming = 0` (Normal): 8,103 samples (**81.04%**).
   - `Jamming = 1` (Anomalous): 1,896 samples (**18.96%**).
   - **Imbalance Ratio:** ~4.27 : 1.
   - **Evaluation Impact:** Accuracy is an invalid metric. Baseline models must report Precision-Recall AUC (PR-AUC), balanced accuracy, and Macro-F1.

2. **UCC 5G Radio Access Technology (RAT) Distribution:**
   - Drive trace `NetworkMode`:
     - `5G`: 1,054 records (**55.53%**)
     - `LTE`: 584 records (**30.77%**)
     - `HSPA+`: 253 records (**13.33%**)
     - `UMTS`: 6 records (**0.32%**)
     - `HSUPA`: 1 record (**0.05%**)
   - Static trace `NetworkMode`:
     - `5G`: 974 records (**88.71%**)
     - `LTE`: 78 records (**7.10%**)
     - `HSPA+`: 31 records (**2.82%**)
     - `UMTS`: 8 records (**0.73%**)
   - **Significance:** Illustrates real-world Non-Standalone (NSA) 5G mobility where coverage gaps cause seamless handover/fallback down to 4G LTE and 3G HSPA.

---

### 3.6 Data Leakage & Feature Contract Hazards

> [!WARNING]
> **Severe Target Leakage Risk in `SRC-002/jammer_chunked.jsonl`:**
> Each record in `jammer_chunked.jsonl` contains post-incident diagnostic reasoning:
> `troubleshooting_tickets`: `"**Diagnose Summary:** **Issue:** Severe communication degradation... **Root Cause:** Active jammer generating continuous radio interference... **Resolution:** Identify, locate, and isolate the jammer..."`
> - If these fields are accessible during ticket-time triage, classification models will trivially predict root causes with 100% artificial accuracy.
> - **Mandatory Guardrail:** Ingestion pipelines for classification and routing must enforce a strict **Ticket-Time Feature Contract**: only initial symptoms, raw telemetry windows prior to prediction timestamp, and customer report text are permitted as model inputs.

---

### 3.7 Cross-Source Incompatibilities

| Characteristic | TelecomTS (`SRC-002`) | UCC 5G (`SRC-005`) | PIIS Canonical Model |
| :--- | :--- | :--- | :--- |
| **Perspective** | Network / gNB Base Station | Client / UE (Handset) | Multi-perspective Observation |
| **Timestamp Format** | Elapsed seconds (numeric float) | Calendar date-time (`YYYY.MM.DD_HH.MM.SS`) | ISO 8601 UTC string (`YYYY-MM-DDTHH:MM:SS.sssZ`) |
| **Sampling Cadence** | 10 Hz (0.1s delta) | 1 Hz (1.0s delta) | Normalized resampled observation window |
| **Radio Metrics** | DL/UL BLER, MCS, PRBs, RSRP | RSRP, RSRQ, SNR, CQI, Bitrate | Canonical Telemetry schema |
| **Entity Identifiers** | Generic testbed node IDs | `CellID`, `NodeHex` (eNB/gNB hex), `LACHEX` | Canonical `network_element_ids` |
| **Missing Representation**| Standard null / NaN | String sentinel `"-"` | JSON null / IEEE NaN |

---

## 4. Conclusion & Actionable Pipeline Directives

1. **Preserve Raw Immutability:** Never modify `data/raw/` files.
2. **Sentinel Transformation:** Normalize string sentinel `"-"` to standard nulls during normalization.
3. **Timezone Normalization:** Convert all timestamps to UTC ISO 8601 strings while preserving `original_timezone` in canonical metadata.
4. **Feature Quarantine:** Enforce strict feature contracts separating ticket-time features from post-resolution diagnostic text.
5. **Evaluation Splitting:** Ensure samples from the same drive trace or testbed run are kept strictly in the same split group (GroupKFold by trace ID / session ID) to prevent temporal data leakage.
