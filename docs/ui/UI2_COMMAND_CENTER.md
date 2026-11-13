# PIIS UI-2: Command Center Operational Overview Specification

**Milestone:** UI-2  
**Component:** Command Center (`CommandCenterPage.tsx`)  
**Route:** `/`  
**Operational Mode:** READ-ONLY SUPERVISORY DECISION SUPPORT  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  

---

## 1. Purpose & Mission

The **Command Center** serves as the primary operational landing interface for the Production Incident Intelligence System (PIIS — Telecom Edition). Built for Network Operations Center (NOC) shift managers and telecom incident engineers, it delivers an evidence-grounded, real-time supervisory overview of network incidents, subsystem readiness, adapter health, and cryptographic audit integrity.

In strict alignment with the PIIS core tenets:
- **Zero Hallucinated Metrics:** Every metric card, chart bar, and status pill is derived directly from actual FastAPI backend responses (`/api/v1/health`, `/api/v1/ready`, `/api/v1/incidents`, `/api/v1/integrations/health`, `/api/v1/audit/verify`).
- **Read-Only Operational Boundary:** The interface is strictly supervisory. Autonomous infrastructure mutations and destructive actions are prevented at the protocol and UI boundary.
- **Epistemic Transparency:** Every summary card and subsystem status explicitly declares its epistemic category (`OBSERVED_FACT`, `CORROBORATED_FINDING`, or `UNCONFIRMED_HYPOTHESIS`) and backend provenance source.

---

## 2. Metric Provenance & Calculation Matrix

The Command Center aggregates operational state across five verified backend endpoints. Below is the exact provenance mapping for all displayed indicators:

| UI Indicator | Displayed Value | Backend Origin / Calculation | Epistemic Classification | Fallback / Unavailable State |
|---|---|---|---|---|
| **Total Incidents** | Canonical ticket count | `GET /api/v1/ready` (`incidents_count`) fallback to `GET /api/v1/incidents` (`total_count`) | `OBSERVED_FACT` | "0" / Skeleton pulse |
| **Critical / Major Severity** | Ratio (e.g. `1 / 1 Major`) | Filtered count over `GET /api/v1/incidents` items where `severity == 'CRITICAL'` and `severity == 'MAJOR'` | `OBSERVED_FACT` | "0 / 0" |
| **Registered Adapters** | Healthy count vs total | `GET /api/v1/ready` (`registered_adapters_count` vs `degraded_adapters`) | `OBSERVED_FACT` | "0 / 0 Degraded" |
| **Audit Integrity** | Record count & tamper status | `GET /api/v1/ready` (`audit_ledger_records`) & `GET /api/v1/audit/verify` (`verified`, `tamper_detected`) | `OBSERVED_FACT` | "Unverified" |
| **Severity Distribution** | Stacked bar with Critical, Major, Minor, Warning segments | Computed client-side distribution from fetched incident records | `OBSERVED_FACT` | "No incident data recorded" |
| **Domain Breakdown** | Stacked bar across RAN, 5G_CORE, TRANSPORT, SERVICE | Computed client-side breakdown from `network_domain` field | `OBSERVED_FACT` | "No domain data recorded" |
| **FastAPI Core** | Service status pill | `GET /api/v1/health` (`status == 'ok'`) | `OBSERVED_FACT` | "DEGRADED" / "UNAVAILABLE" |
| **Isolation Forest Engine** | Anomaly pipeline status | `GET /api/v1/ready` readiness probe | `SIMULATED` (Local Scikit-learn) | "SIMULATED (LOCAL)" |
| **Dense Hybrid Retriever** | RAG retrieval status | `GET /api/v1/ready` readiness probe | `SIMULATED` (Local BM25/Dense) | "SIMULATED (LOCAL)" |
| **ITSM Adapters (SNOW/Jira)** | Adapter heartbeat & state | `GET /api/v1/integrations/health` items | `READ-ONLY (MOCK)` | "READ-ONLY (MOCK)" |

---

## 3. Subsystem Transparency & Operational Status

PIIS enforces total honesty regarding execution environments. The Command Center distinguishes local/verified components from simulated enterprise dependencies:

1. **FastAPI Core (`piis-core`):**
   - Verified local runtime.
   - Probed via `/api/v1/health`.
   - Displayed as `HEALTHY` (`OBSERVED_FACT`).

2. **ML Models (Isolation Forest & Random Forest Classifiers):**
   - Verified local scikit-learn pipeline operating on synthetic/public holdout datasets.
   - Displayed as `SIMULATED (LOCAL)` to prevent users from mistaking local models for production telco cloud deployments.

3. **Hybrid RAG Retriever (Dense Vector + BM25):**
   - In-memory deterministic retrieval engine over synthetic telecom runbooks.
   - Displayed as `SIMULATED (LOCAL)`.

4. **Telemetry & ITSM Adapters (ServiceNow, Jira, Prometheus, OSS/NMS):**
   - Validated integration adapters running in mock/fixture mode without live WAN telecom credentials.
   - Displayed as `READ-ONLY (MOCK)`.

5. **Cryptographic Audit Ledger:**
   - Real SHA-256 Merkle-tree verification executed locally.
   - Probed via `/api/v1/audit/verify`.
   - Displays real cryptographic root hash prefix (e.g. `a1b2c3d4...`) and record count.

---

## 4. Visual Components & Layout Architecture

The Command Center is structured into four primary sections:

1. **Supervisory Header Banner:**
   - High-visibility safety notice affirming read-only supervisory posture.
   - Quick **"Refresh All"** button triggering simultaneous refetch across all queries with animated loading state.
   - Linked to Epistemic Classification definitions.

2. **Key Performance Indicator (KPI) Grid:**
   - 4 responsive cards (`Total Incidents`, `Critical / High Severity`, `Registered Adapters`, `Audit Integrity`).
   - Each card features:
     - Clear metric counter.
     - Descriptive subtext explaining impact.
     - Provenance tag indicating the exact backend endpoint.
     - Interactive click navigation directly into the relevant sub-view (e.g., clicking severity card filters Incident Explorer to Critical/Major).

3. **Telemetry & Fault Distribution Analytics:**
   - **Severity Distribution Bar:** Accessible stacked progress bar with color-coded segments (Critical = Rose-500, Major = Amber-500, Minor = Sky-500, Warning = Yellow-500) and interactive legend counts.
   - **Network Domain Breakdown Bar:** Stacked progress bar visualizing fault allocation across telecom network tiers (`RAN (gNodeB)`, `5G Core`, `Transport (DWDM)`, `Service (DNS/IMS)`).

4. **Recent Ingestion Activity Queue:**
   - Real-time feed showing the 5 most recent incidents ingested into PIIS.
   - Displays Canonical Incident ID, Fault Category badge, Network Domain badge, Severity badge, and creation timestamp.
   - Direct action button to launch deep-dive analysis in the **Investigation Workspace** (`/investigation?id=...`).

---

## 5. Error Handling & Resilience

The Command Center handles degraded backend states gracefully:
- **Network Outage / Gateway Timeout:** Displays the high-contrast `ErrorState` component with a direct "Retry Request" trigger.
- **Unauthorized / Expired Token:** Prompts user with 401 error explanation and direct link to enter bearer credentials in the security modal.
- **Empty Dataset:** If no incidents have been ingested, renders an honest `EmptyState` explaining that the ingestion pipeline is listening for upstream ITSM/telemetry envelopes.
