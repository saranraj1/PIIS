# Dataset Source Manifest & Verified Register

- **Document Version:** 1.1 (Updated Post Milestone 1 Investigation)
- **Status:** Verified & Active
- **Last Updated:** 2026-10-31

This manifest records candidate and acquired telecommunications datasets, their verified canonical URLs, licensing status, acquisition reality, and storage paths.

| Source ID | Source Name | Primary Publisher | Verified Canonical URL | Permitted Use & License | Local Acquisition Status | Storage Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SRC-001** | ITU/Zindi AI Telco Troubleshooting Challenge | ITU / Zindi Africa | `https://zindi.world/competitions/ai-telco-troubleshooting-challenge` | Competition Terms (Non-commercial, non-redistributable) | **BLOCKED (Auth Required)** | `BLOCKED_AUTH_REQUIRED` |
| **SRC-002** | TelecomTS (5G Testbed Multimodal Time-Series) | Ali Maatouk et al. (ICML 2026) | `https://huggingface.co/datasets/AliMaatouk/TelecomTS` | **MIT License** | **ACQUIRED (Verified)** | `data/raw/SRC-002/` |
| **SRC-003** | LCORE-D (ISP Core Network Fault Dataset) | Akanksha Singh & Ratneshwer Gupta (JNU) | `https://data.mendeley.com/datasets/77sztrg5ks/1` (DOI: `10.17632/77sztrg5ks.1`) | CC BY 4.0 | **BLOCKED (Embargoed)** | `BLOCKED_EMBARGOED` |
| **SRC-004** | Anomaly Detection in Cellular Networks | Josep Vidal (UPC / Kaggle) | `https://www.kaggle.com/competitions/anomaly-detection-in-cellular-networks` | Kaggle InClass Terms | **BLOCKED (Auth Required)** | `BLOCKED_AUTH_REQUIRED` |
| **SRC-005** | UCC 5G Production Network Dataset | Mobile & Internet Systems Lab (UCC) | `https://github.com/uccmisl/5Gdataset` | **GPL-3.0 License** | **ACQUIRED (Verified)** | `data/raw/SRC-005/` |

---

## Source Verification Details & Corrections

1. **SRC-001 (ITU / Zindi):**
   - Redirected from `zindi.africa` to `https://zindi.world/competitions/ai-telco-troubleshooting-challenge`.
   - Requires active user account and authenticated browser session to download. Automated unauthenticated HTTP requests are blocked.
2. **SRC-002 (TelecomTS):**
   - Successfully acquired via Hugging Face. Contains 5G PHY/MAC/network metrics at 10 Hz with ground-truth RF jamming and synthetic congestion scenarios, plus multi-modal diagnostic reasoning JSONL.
3. **SRC-003 (LCORE-D):**
   - **Correction:** The original URL `https://zenodo.org/records/10693296` in the initial scaffold draft was determined to be invalid (it pointed to an unrelated zoology paper figure).
   - The verified canonical DOI is `10.17632/77sztrg5ks.1` hosted on Mendeley Data.
   - Active repository embargo (`embargo_date: 2026-06-14T23:59:59.000Z`) currently disables web downloads on Mendeley Data.
4. **SRC-004 (Kaggle Anomaly Detection):**
   - Archived competition. Requires `kaggle.json` API token or manual session login.
5. **SRC-005 (UCC 5G Production Dataset):**
   - Acquired from University College Cork. Real commercial 5G Non-Standalone drive tests and stationary traces from an Irish mobile operator. Contains client KPIs, channel conditions, throughput, and multi-RAT handovers.

---

## Acquisition Checklist & Verification Rules
- [x] Confirm exact canonical URL and publisher.
- [x] Read license, terms, and competition restrictions.
- [x] Record release/version and access date.
- [x] Download permitted files to `data/raw/<source_id>/`.
- [x] Compute SHA-256 and exact file sizes.
- [x] Inspect archive contents safely.
- [x] Record row counts, schema, units, timezone, and labels in `docs/data/SOURCE_REGISTER.csv`.
- [x] Record limitations and known leakage risks in `docs/data/DATASET_ACQUISITION_REPORT.md`.
- [x] Map source fields to canonical schemas in `docs/data/SOURCE_TO_CANONICAL_MAPPING.md`.
- [x] Keep raw data immutable.
