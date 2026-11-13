# PIIS Dataset Acquisition & Candidate Source Investigation Report

- **Document Version:** 1.0
- **Milestone:** M1 — Data Foundation (Deliverable M1.1)
- **Status:** Complete / Verified
- **Assessed By:** Principal AI/ML Engineer & Telecom Data Architect
- **Date:** 2026-10-31

---

## 1. Executive Summary

This report delivers a rigorous technical evaluation of candidate telecommunications datasets for the **Production Incident Intelligence System (PIIS)**.
In accordance with Milestone 1 requirements, all sources were evaluated against strict criteria: canonical URL verification, licensing and redistribution rights, downloadable file formats, target labels, network domain coverage, temporal characteristics, and potential data leakage risks.

### Source Evaluation Summary Matrix

| Source ID | Candidate Dataset Name | Publisher / Authors | Canonical URL | License | Acquisition Status | Primary Modality & Telecom Domain |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SRC-001** | ITU/Zindi AI Telco Troubleshooting Challenge | ITU / Zindi | `https://zindi.world/competitions/ai-telco-troubleshooting-challenge` | Competition Specific (Restricted, Non-Commercial) | **BLOCKED (Auth Required)** | 5G RAN User-Plane & Cell Configs; C1–C8 Root-Cause Categories |
| **SRC-002** | TelecomTS | Ali Maatouk et al. (ICML / arXiv 2510.06063) | `https://huggingface.co/datasets/AliMaatouk/TelecomTS` | **MIT License** | **ACQUIRED (Verified)** | 5G PHY/MAC/Network KPIs (10 Hz), RF Jamming, Synthetic Faults, Multi-modal JSONL |
| **SRC-003** | LCORE-D (Mendeley Data) | Akanksha Singh & Ratneshwer Gupta (JNU) | `https://data.mendeley.com/datasets/77sztrg5ks/1` (DOI: 10.17632/77sztrg5ks.1) | CC BY 4.0 (Under Embargo until 2026-06-14) | **BLOCKED (Embargoed)** | ISP Core Network (GNS3), 407h ICMP/SNMP, Hard Failures & Transient Dynamics |
| **SRC-004** | Anomaly Detection in Cellular Networks | Josep Vidal (UPC Barcelona / Kaggle) | `https://www.kaggle.com/competitions/anomaly-detection-in-cellular-networks` | Kaggle Competition Terms | **BLOCKED (Auth Required)** | 4G LTE Base Station (eNodeB) Hourly KPI Matrix, Binary Anomaly Labels |
| **SRC-005** | UCC 5G Production Network Traces | Mobile & Internet Systems Lab (UCC) | `https://github.com/uccmisl/5Gdataset` | **GPL-3.0** | **ACQUIRED (Verified)** | Real 5G Production Network (Irish Operator) Client KPIs (G-NetTrack Pro), Channel/Throughput/Cell |

---

## 2. In-Depth Source Evaluation

---

### 2.1 SRC-001: ITU/Zindi AI Telco Troubleshooting Challenge

- **Canonical URL:** `https://zindi.world/competitions/ai-telco-troubleshooting-challenge` (Redirected from `https://zindi.africa/competitions/ai-telco-troubleshooting-challenge`)
- **Publisher & Authors:** International Telecommunication Union (ITU) and Zindi Africa.
- **Dataset Version / Release:** Challenge Competition Release (November 2025 – Early 2026).
- **License & Permitted Usage:**
  - Governed by Zindi Competition Terms and Conditions.
  - Participants may only use competition data for model development within the competition scope.
  - Public redistribution is strictly prohibited without explicit authorization. Commercial use is disallowed.
- **Available Files & Formats:**
  - Compressed archives containing tabular CSV files (`telelogs`, `drive_test_metrics.csv`, `cell_engineering_parameters.csv`) and challenge split metadata.
- **Available Labels:**
  - Ground-truth root-cause classification labels grouped into 8 operational categories (`C1` through `C8`), covering radio misconfiguration, optical fiber link faults, cell handover failure, and baseband hardware degradation.
- **Network Domain Coverage:** 5G RAN and backhaul transport interfaces.
- **Temporal Characteristics:** Time-stamped drive tests and alarm windows collected over active mobile cluster environments.
- **Known Limitations & Leakage Risks:**
  - Requires user account login, acceptance of competition rules, and session-authenticated download tokens.
  - **Leakage Risk:** Several engineering parameter files contain static fault identifiers that directly index the target root-cause class if not carefully quarantined before feature construction.
- **Acquisition Verdict & Instructions:**
  - **Status: BLOCKED (Authentication Required).**
  - Unauthenticated automated retrieval returned HTTP redirects to authentication gateways.
  - *Manual Retrieval Instructions:* Register at `zindi.world`, join the competition, agree to the terms, and download the dataset archive to `data/raw/SRC-001/` for local evaluation.

---

### 2.2 SRC-002: TelecomTS

- **Canonical URL:** `https://huggingface.co/datasets/AliMaatouk/TelecomTS` (Code: `https://github.com/Ali-maatouk/TelecomTS`, Paper: `arXiv:2510.06063`)
- **Publisher & Authors:** Ali Maatouk et al. (Accepted at ICML 2026).
- **Dataset Version / Release:** 1.0 (Public release via Hugging Face Datasets).
- **License & Permitted Usage:**
  - **MIT License**. Fully open for research, modification, and commercial application without gating or redistribution restrictions.
- **Available Files & Formats:**
  - Direct HTTP/Parquet/JSONL/CSV endpoints:
    - `metrics.csv`: High-resolution (10 Hz) time series containing over 30 distinct telecom KPIs.
    - `chunked.jsonl`: Multi-modal reasoning traces, step-by-step diagnostic question-answer pairs, and structured root-cause explanations.
    - `description.txt`: Physical testbed deployment metadata and environmental conditions.
- **Available Labels:**
  - Anomaly binary indicators, anomaly temporal duration bounding intervals, fault taxonomy categories (RF jamming, synthetic congestion, buffer starvation, signal loss), and explicit reasoning traces.
- **Network Domain Coverage:**
  - End-to-end 5G testbed: Radio Access (PHY/MAC), Transport, and Core User-Plane interfaces.
- **Temporal Characteristics:**
  - 10 Hz continuous telemetry windows preserving unnormalized absolute physical units (dBm, bytes/sec, latency in ms).
- **Known Limitations & Leakage Risks:**
  - Physical testbed conditions may exhibit lower background traffic entropy than large macro-cell commercial networks.
  - **Leakage Risk:** `chunked.jsonl` contains post-incident diagnostic reasoning. Fields containing `"reasoning"` and `"root_cause"` must be strictly excluded from ticket-time routing models and used exclusively for retrieval and recommendation evaluation.
- **Acquisition Verdict:**
  - **Status: ACQUIRED (Direct Download & Verified).**
  - Downloaded to `data/raw/SRC-002/`.

---

### 2.3 SRC-003: LCORE-D (ISP Core Network Fault Dataset)

- **Canonical URL:** `https://data.mendeley.com/datasets/77sztrg5ks/1` (DOI: `10.17632/77sztrg5ks.1`)
- **Correction of Manifest Error:** The initial manifest referenced `https://zenodo.org/records/10693296`. Technical verification revealed that Zenodo record 10693296 is an unrelated biological taxonomy figure in *Zootaxa*. The authentic canonical LCORE-D repository is hosted on Mendeley Data.
- **Publisher & Authors:** Akanksha Singh and Ratneshwer Gupta (Jawaharlal Nehru University).
- **Dataset Version / Release:** Version 1 (Published December 2025).
- **License & Permitted Usage:**
  - Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Available Files & Formats:**
  - `LCORE-D R1.csv` through `LCORE-D R7.csv`, topology definitions, and fault injection logs.
- **Available Labels:**
  - Intentional hard failure logs (single link failure, multi-link failure, node outage, routing misconfiguration, line card failure) and natural transient protocol dynamics (OSPF reconvergence, BGP flapping).
- **Network Domain Coverage:** IP Core / ISP Transport network (GNS3 emulated topology over 407 monitoring hours).
- **Temporal Characteristics:** SNMP/ICMP metric sampling at 30-second and 60-second intervals.
- **Known Limitations & Access Blocker:**
  - **Status: BLOCKED (Embargoed by Repository).**
  - Mendeley Data API and web inspection confirmed the dataset is under an active embargo:
    `"embargo_date": "2026-06-14T23:59:59.000Z"`.
  - The download interface is disabled by the publisher until the embargo expires.
- **Action Plan:**
  - Document authentic DOI and contact authors for early academic sharing if necessary; proceed with accessible sources.

---

### 2.4 SRC-004: Kaggle Anomaly Detection in Cellular Networks

- **Canonical URL:** `https://www.kaggle.com/competitions/anomaly-detection-in-cellular-networks`
- **Publisher & Authors:** Prof. Josep Vidal, Universitat Politècnica de Catalunya (UPC Barcelona).
- **Dataset Version / Release:** Archived Kaggle InClass Competition.
- **License & Permitted Usage:**
  - Kaggle InClass competition rules (restricted to educational/research use, no public unauthenticated API).
- **Available Files & Formats:**
  - `train.csv` (hourly eNodeB KPI matrix with anomaly labels), `test.csv`, and baseline submission scripts.
- **Available Labels:**
  - Binary anomaly flag (`0` = normal operation, `1` = degraded/anomalous cell hour).
- **Network Domain Coverage:** 4G LTE Radio Access Network (eNodeB cells).
- **Temporal Characteristics:** Hourly aggregated counters spanning multiple months.
- **Known Limitations & Leakage Risks:**
  - Requires Kaggle API authentication (`kaggle.json`) or browser-based download.
  - Aggregated hourly counters mask sub-second burst anomalies.
- **Acquisition Verdict:**
  - **Status: BLOCKED (Authentication Required).**
  - *Manual Retrieval Instructions:* Place valid `kaggle.json` into `~/.kaggle/` and run `kaggle competitions download -c anomaly-detection-in-cellular-networks` into `data/raw/SRC-004/`.

---

### 2.5 SRC-005: UCC 5G Production Network Traces

- **Canonical URL:** `https://github.com/uccmisl/5Gdataset`
- **Publisher & Authors:** Mobile & Internet Systems Laboratory (MISL), University College Cork (UCC), Ireland.
- **Dataset Version / Release:** Production Release 1.0 (Master branch).
- **License & Permitted Usage:**
  - **GNU General Public License v3.0 (GPL-3.0)**. Publicly accessible and downloadable.
- **Available Files & Formats:**
  - `5G-production-dataset.zip` (2,177,094 bytes): Raw CSV traces recorded via G-NetTrack Pro on non-rooted Android commercial handsets connected to a major Irish 5G operator.
- **Available Labels / Observables:**
  - Channel metrics: RSRP (Reference Signal Received Power), RSRQ (Reference Signal Received Quality), SNR, CQI.
  - Contextual & cell metrics: Cell ID, eNodeB/gNB ID, TAC, PCI, Speed, Mobility class (`static`, `car`), and Application workload (`video_streaming`, `file_download`).
- **Network Domain Coverage:** Commercial 5G Non-Standalone (NSA) / Sub-6 GHz and LTE anchor layer.
- **Temporal Characteristics:** 1 Hz continuous client-side telemetry across hundreds of kilometers of drive tests and stationary sessions.
- **Known Limitations & Leakage Risks:**
  - Client-side observation; does not expose internal core network control-plane signaling logs (e.g., AMF/SMF traces).
  - Must not be joined with proprietary operator IMSI or subscriber credentials.
- **Acquisition Verdict:**
  - **Status: ACQUIRED (Direct Download & Verified).**
  - Downloaded to `data/raw/SRC-005/5G-production-dataset.zip`.

---

## 3. Provenance & Integrity Register

All acquired raw files are placed in immutable storage under `data/raw/<source_id>/`.
Checksums, byte sizes, and timestamps are cataloged in `docs/data/SOURCE_REGISTER.csv`.
No raw files have been or will be modified in place.
