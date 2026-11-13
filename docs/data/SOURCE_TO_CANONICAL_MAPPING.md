# Source-to-Canonical Schema Mapping Specification

- **Document Version:** 1.0
- **Milestone:** M1 — Data Foundation (Deliverable M1.5)
- **Status:** Complete / Approved
- **Assessed By:** Principal AI/ML Engineer & Telecom Data Architect
- **Date:** 2026-10-31

---

## 1. Executive Summary

This document establishes the official semantic and technical mapping between raw external telecommunications datasets and the PIIS Canonical Schemas (`schemas/telemetry.schema.json`, `schemas/incident.schema.json`, `schemas/alarm.schema.json`, `schemas/evidence.schema.json`).

Every source field is mapped with explicit transformations, unit conversions, missingness policies, and limitation disclosures.
**Immutable Rule:** Missing source information is never fabricated; original source identifiers and raw payloads are strictly preserved.

---

## 2. Canonical Target Schemas Overview

The primary canonical schemas used for public-real data intake in Milestone 1 are:
1. **`telemetry.schema.json`**: Standardized individual time-series metric observations across physical, MAC, transport, and network layers.
2. **`incident.schema.json`**: Standardized incident ticket records encompassing network domain, fault category, initial symptoms, and ticket metadata.
3. **`evidence.schema.json`**: Normalized evidence items linking observations and artifacts to specific incidents.

---

## 3. Mapping: TelecomTS (`SRC-002`) to Canonical `telemetry.schema.json`

### 3.1 Field-by-Field Specification

| Original Source Field | Canonical Field (`telemetry.schema.json`) | Target Type | Canonical Unit | Transformation / Logic | Missing-Value Handling | Mapping Limitations / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| *(Generated)* | `observation_id` | string | - | `f"TELTS-OBS-{file_stem}-{row_idx:07d}"` | Generated deterministically | Unique record primary key. |
| *(Associated)* | `incident_id` | string \| null | - | `f"INC-TELTS-{file_stem}"` for anomalous scenarios; `null` for normal runs | Set to null for normal controls | Explicitly groups telemetry to scenario run. |
| `timestamp` | `timestamp` | string (ISO-8601) | UTC | Convert relative float seconds to base epoch UTC: `BASE_EPOCH + pd.to_timedelta(timestamp, unit='s')` formatted as `YYYY-MM-DDTHH:MM:SS.sssZ` | Mandatory; reject row if unparseable | Original relative second value preserved in `metadata.relative_timestamp_sec`. |
| *(Fixed context)* | `network_element_id` | string | - | `"GNB-TESTBED-5G-01"` | Constant | Testbed gNB base station identifier. |
| *(Fixed context)* | `network_domain` | string | - | `"RAN"` (or `"CROSS_DOMAIN"` for transport metrics) | Constant | Radio Access Network domain. |
| `RSRP` | `metric_name` / `metric_value` | string / number | `dBm` | Exploded into canonical telemetry record where `metric_name="RSRP"` and `metric_value=float(RSRP)` | If null, `metric_value=null` | Reference Signal Received Power. |
| `DL_BLER` | `metric_name` / `metric_value` | string / number | `ratio (0-1)` | Exploded: `metric_name="DL_BLER"`, `metric_value=float(DL_BLER)` | If null, `metric_value=null` | Downlink Block Error Rate. |
| `DL_MCS` | `metric_name` / `metric_value` | string / number | `index (0-28)` | Exploded: `metric_name="DL_MCS"`, `metric_value=float(DL_MCS)` | If null, `metric_value=null` | Modulation and Coding Scheme index. |
| `UL_BLER` | `metric_name` / `metric_value` | string / number | `ratio (0-1)` | Exploded: `metric_name="UL_BLER"`, `metric_value=float(UL_BLER)` | If null, `metric_value=null` | Uplink Block Error Rate. |
| `UL_MCS` | `metric_name` / `metric_value` | string / number | `index (0-28)` | Exploded: `metric_name="UL_MCS"`, `metric_value=float(UL_MCS)` | If null, `metric_value=null` | Uplink Modulation index. |
| `UL_SNR` | `metric_name` / `metric_value` | string / number | `dB` | Exploded: `metric_name="UL_SNR"`, `metric_value=float(UL_SNR)` | If null, `metric_value=null` | Uplink Signal-to-Noise Ratio. |
| `PRB_Utilization_DL` | `metric_name` / `metric_value` | string / number | `ratio (0-1)` | Exploded: `metric_name="PRB_UTIL_DL"`, `metric_value=float(PRB_Utilization_DL)` | If null, `metric_value=null` | Downlink Physical Resource Block load. |
| `PRB_Utilization_UL` | `metric_name` / `metric_value` | string / number | `ratio (0-1)` | Exploded: `metric_name="PRB_UTIL_UL"`, `metric_value=float(PRB_Utilization_UL)` | If null, `metric_value=null` | Uplink Physical Resource Block load. |
| `TX_Bytes` | `metric_name` / `metric_value` | string / number | `bytes/sec` | Exploded: `metric_name="TX_THROUGHPUT"`, `metric_value=float(TX_Bytes * 10)` (since 10Hz sampling) | If null, `metric_value=null` | Converted from 100ms sample to 1-sec equivalent rate. |
| `RX_Bytes` | `metric_name` / `metric_value` | string / number | `bytes/sec` | Exploded: `metric_name="RX_THROUGHPUT"`, `metric_value=float(RX_Bytes * 10)` | If null, `metric_value=null` | Converted from 100ms sample to 1-sec equivalent rate. |
| `DL_Protocol` | `metadata.dl_protocol` | string \| null | - | Stored in record metadata as protocol tag | Mapped to `"NONE"` when missing | Captures packet traffic type (TCP, UDP, NONE). |
| `Jamming` | `metadata.ground_truth_anomaly` | boolean | - | `bool(Jamming == 1)` stored in metadata | Default `false` if missing | Ground-truth RF anomaly flag (for evaluation only). |
| *(Constant)* | `source_type` | string (enum) | - | `"PUBLIC_REAL"` | Mandatory | Strictly marked as public-real observation. |
| *(Constant)* | `source_dataset` | string | - | `"AliMaatouk/TelecomTS"` | Mandatory | Canonical source dataset identifier. |
| *(Row index)* | `source_record_id` | string | - | `f"row_{row_idx}"` | Mandatory | Exact row index in original CSV file. |
| *(Constant)* | `original_timezone` | string | - | `"UTC"` | Mandatory | Base reference timezone. |

---

## 4. Mapping: UCC 5G Production Traces (`SRC-005`) to Canonical `telemetry.schema.json`

### 4.1 Field-by-Field Specification

| Original Source Field | Canonical Field (`telemetry.schema.json`) | Target Type | Canonical Unit | Transformation / Logic | Missing-Value Handling | Mapping Limitations / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| *(Generated)* | `observation_id` | string | - | `f"UCC5G-OBS-{trace_id}-{row_idx:06d}"` | Generated deterministically | Unique observation primary key. |
| *(Generated)* | `incident_id` | string \| null | - | `f"INC-UCC5G-{trace_id}"` for degraded segments, else `null` | Defaults to `null` | Linked when anomaly detection triggers. |
| `Timestamp` | `timestamp` | string (ISO-8601) | UTC | Parse `YYYY.MM.DD_HH.MM.SS` and format as `YYYY-MM-DDTHH:MM:SSZ` | Mandatory; reject row if invalid | Original handset time was local Ireland (UTC / IST). |
| `NODEHEX` / `CellID` | `network_element_id` | string | - | `f"CELL-{NODEHEX}-{CELLHEX}"` if available, else `f"CELL-{CellID}"` | If missing, `"UNKNOWN_CELL"` | Base station eNodeB/gNB cell identifier. |
| `NetworkMode` | `network_domain` | string | - | If `NetworkMode == "5G"` -> `"RAN"`; else `"RAN_LEGACY"` | Preserved in metadata | Captures 5G New Radio vs LTE fallback. |
| `RSRP` | `metric_name` / `metric_value` | string / number | `dBm` | Exploded: `metric_name="RSRP"`, `metric_value=float(RSRP)` | Sentinel `"-"` -> `null` | Reference Signal Received Power. |
| `RSRQ` | `metric_name` / `metric_value` | string / number | `dB` | Exploded: `metric_name="RSRQ"`, `metric_value=float(RSRQ)` | Sentinel `"-"` -> `null` | Reference Signal Received Quality. |
| `SNR` | `metric_name` / `metric_value` | string / number | `dB` | Exploded: `metric_name="SNR"`, `metric_value=float(SNR)` | Sentinel `"-"` -> `null` | Signal to Noise Ratio. |
| `CQI` | `metric_name` / `metric_value` | string / number | `index (1-15)` | Exploded: `metric_name="CQI"`, `metric_value=float(CQI)` | Sentinel `"-"` -> `null` | Channel Quality Indicator. |
| `DL_bitrate` | `metric_name` / `metric_value` | string / number | `kbps` | Exploded: `metric_name="DL_BITRATE"`, `metric_value=float(DL_bitrate)` | Sentinel `"-"` -> `null` | Downlink data throughput. |
| `UL_bitrate` | `metric_name` / `metric_value` | string / number | `kbps` | Exploded: `metric_name="UL_BITRATE"`, `metric_value=float(UL_bitrate)` | Sentinel `"-"` -> `null` | Uplink data throughput. |
| `Speed` | `metadata.speed_kmh` | number | `km/h` | `float(Speed)` in metadata | Sentinel `"-"` -> `0.0` | Handset vehicular velocity. |
| `Latitude` / `Longitude`| `metadata.geo_coordinates`| object | degrees | `{"lat": float(Latitude), "lon": float(Longitude)}` in metadata | If missing or invalid -> `null` | Geospatial cell coordinates. |
| `State` | `metadata.handset_state` | string | - | Stored in metadata (`"D"` = data active, `"I"` = idle) | Sentinel `"-"` -> `null` | Application activity state. |
| *(Constant)* | `source_type` | string (enum) | - | `"PUBLIC_REAL"` | Mandatory | Validated against schema enum. |
| *(Constant)* | `source_dataset` | string | - | `"uccmisl/5Gdataset"` | Mandatory | Explicit attribution. |
| `RAWCELLID` | `source_record_id` | string | - | `f"trace_{trace_id}_row_{row_idx}_cell_{RAWCELLID}"` | Mandatory | Traceable link back to original raw record. |
| *(Constant)* | `original_timezone` | string | - | `"Europe/Dublin"` | Mandatory | Handset local logging timezone. |

---

## 5. Mapping: TelecomTS Diagnostic Reasoning (`SRC-002`) to Canonical `incident.schema.json`

TelecomTS `chunked.jsonl` contains 93 structured diagnostic records. These map directly into canonical incident records for retrieval and historical case matching:

| JSONL Field | Canonical Field (`incident.schema.json`) | Target Type | Transformation / Policy | Leakage Guardrail |
| :--- | :--- | :--- | :--- | :--- |
| *(Generated)* | `incident_id` | string | `f"INC-TELTS-JAMMER-{idx:04d}"` | Unique incident identifier. |
| `troubleshooting_tickets` (parsed) | `title` | string | Extracted `"Issue"` text: e.g., `"Severe wireless communication degradation from external RF interference"` | Safe for ticket triage. |
| `context.environment_description` | `description` | string | Testbed operational description and observed symptoms | Safe for ticket triage. |
| *(Fixed)* | `network_domain` | string (enum) | `"RAN"` | Canonical enum literal. |
| `anomalies.type` | `fault_category` | string | `"rf_jamming_interference"` | Target label (predictand). |
| *(Policy mapped)* | `severity` | string (enum) | `"MAJOR"` (high packet loss and rate degradation) | Validated against severity rubric. |
| *(Ground truth policy)* | `support_level_label` | string (enum) | `"L2"` (RF interference requires field engineering & spectrum analyzer) | Formally annotated under PIIS policy. |
| *(Generated)* | `created_at` | string (ISO-8601) | Normalized UTC timestamp of anomaly onset | Ticket creation time. |
| `anomalies.troubleshooting_tickets` | `resolution_summary` | string \| null | Complete diagnostic resolution text | **QUARANTINED:** Excluded from ticket-time routing features! |
| *(Fixed)* | `root_cause_confirmed` | boolean | `true` | Verified ground-truth scenario. |
| *(Constant)* | `source_type` | string (enum) | `"PUBLIC_REAL"` | Preserves public dataset provenance. |
| *(Constant)* | `source_dataset` | string | `"AliMaatouk/TelecomTS"` | Provenance reference. |
| *(Row index)* | `source_record_id` | string | `f"chunked_record_{idx}"` | Original line reference. |
| *(Constant)* | `annotation_status` | string (enum) | `"REVIEWED"` | Verified against ground truth. |

---

## 6. Schema Consistency Alignment

To maintain zero schema friction across all canonical models, the schemas are aligned as follows:
1. `source_type` in `telemetry.schema.json` and `alarm.schema.json` is updated to include `HUMAN_ANNOTATED` and `OPERATOR_INTERNAL` so that all schemas share the identical 5-value provenance domain:
   `["PUBLIC_REAL", "SYNTHETIC", "DERIVED", "HUMAN_ANNOTATED", "OPERATOR_INTERNAL"]`.
2. `resolved_at` in `incident.schema.json` is strengthened with `"format": "date-time"` when non-null.
3. `src/piis/provenance.py` is updated to define all 5 standard `SourceType` enum values.
