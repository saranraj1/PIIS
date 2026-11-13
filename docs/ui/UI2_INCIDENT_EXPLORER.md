# PIIS UI-2: Incident Explorer Specification & Operations Guide

**Milestone:** UI-2  
**Component:** Incident Explorer (`IncidentExplorerPage.tsx`)  
**Route:** `/incidents`  
**Operational Mode:** READ-ONLY SUPERVISORY CATALOG & DEEP-DIVE INSPECTION  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  

---

## 1. Overview & Operational Purpose

The **Incident Explorer** provides NOC operators, root-cause investigators, and telecom engineering teams with a high-density, searchable catalog of all canonical incident records ingested into PIIS.

It bridges broad supervisory awareness with granular diagnostic workflows, adhering strictly to:
- **Canonical Schema Adherence:** Every incident row and detail panel reflects the standardized fields defined in `schemas/incident.schema.json`.
- **Epistemic Labeling:** Observational facts (network element IDs, raw timestamps, subscriber counts) are distinguished from diagnostic inferences or synthetic classifications.
- **Workflow Continuity:** Full integration with the **Investigation Workspace** (`/investigation`) via cross-screen state management in Zustand (`incidentContextStore`).

---

## 2. Canonical Data Model Mapping

The Incident Explorer displays canonical attributes ingested from diverse upstream telecom systems (ServiceNow ITSM, Jira Service Management, OSS/NMS alarm managers, OTLP metric pipelines):

| Canonical Field | Schema Type | Table Representation | Detail Drawer Representation |
|---|---|---|---|
| `incident_id` | String (`INC-...`) | Monospace bold text with sky-500 accent | Header identifier with copy-to-clipboard |
| `title` / `description` | String | Truncated bold header and descriptive secondary line | Full un-truncated description block |
| `network_domain` | Enum | `DomainBadge` (`RAN`, `5G_CORE`, `TRANSPORT`, `SERVICE`) | Network Domain badge with tier classification |
| `fault_category` | String | Monospace inline tag (e.g. `HARDWARE_RF`, `CORE_USER_PLANE`) | Dedicated fault category metadata badge |
| `severity` | Enum | `SeverityBadge` (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`) | Severity badge with WCAG-compliant color contrast |
| `support_level_label` | String (`L1`, `L2`, `L3`) | L-tier pill badge with rationale tooltip | Support tier allocation and routing rationale |
| `affected_region` | String | Truncated regional identifier (e.g. `US-EAST-1`) | Geographical region with blast-radius context |
| `affected_subscribers` | Integer | Formatted subscriber count | High-visibility impact indicator |
| `network_element_ids` | Array[String] | Embedded in detail drawer | Interactive monospace tags of affected gNodeB / UPF / DWDM nodes |
| `created_at` | ISO-8601 Timestamp | Localized tabular date/time string | Full UTC and localized observation timestamp |
| `resolved_at` | ISO-8601 / Null | Status pill (`ACTIVE` vs `RESOLVED`) | Resolution lifecycle timestamp and duration |
| `resolution_summary` | String / Null | Embedded in detail drawer | Final resolution text and root-cause confirmation tag |
| `source_type` | Enum | `PUBLIC_REAL`, `SYNTHETIC`, `HUMAN_ANNOTATED` | Data provenance badge indicating dataset origin |
| `source_dataset` | String | Originating system name (e.g. `ServiceNow`, `Jira-JSM`) | Ingestion source system |
| `source_record_id` | String | External ticket ID (e.g. `INC0089201`) | Upstream ITSM ticket link |

---

## 3. Search, Filtering, and Sorting Architecture

### A. Multi-Criterion Filtering
The Explorer controls bar allows instant multi-dimensional slicing of operational records:
1. **Full-Text Search:**
   - Real-time client-side filter matching across:
     - `incident_id` (case-insensitive substring)
     - `title`
     - `description`
     - `fault_category`
     - `network_element_ids`
2. **Network Domain Filter:**
   - Dropdown with options: `ALL DOMAINS`, `RAN`, `5G_CORE`, `TRANSPORT`, `SERVICE`.
   - Propagates to backend `GET /api/v1/incidents?domain=...` and refines locally.
3. **Severity Filter:**
   - Dropdown with options: `ALL SEVERITIES`, `CRITICAL`, `MAJOR`, `MINOR`, `WARNING`.
   - Propagates to backend `GET /api/v1/incidents?severity=...` and refines locally.
4. **Resolution Lifecycle Status:**
   - Dropdown with options: `ALL STATUS`, `ACTIVE` (`resolved_at === null`), `RESOLVED` (`resolved_at !== null`).
5. **Clear / Reset Mechanism:**
   - Dedicated "Clear Filters" button restores all controls to default state (`ALL`, empty search, page 1).

### B. Column Sorting
- Interactive column headers for **Incident ID**, **Severity** (hierarchically ordered: CRITICAL > MAJOR > MINOR > WARNING), and **Created Date**.
- Toggles between descending (`desc`) and ascending (`asc`) with visual directional chevron icons.

### C. Responsive Pagination
- Configurable page size selector (`10`, `20`, `50`, `100` rows per page).
- Accessible page navigation buttons with current page count and total records indicator.
- Automatically resets to Page 1 upon query or filter mutation to prevent index overflow.

---

## 4. Lateral Detail Inspection Drawer

Clicking any row or the "Inspect" eye button opens a slide-out detail drawer on the right side of the screen:
- **Zero Ingestion Modification:** Operates in pure read mode.
- **Lineage Verification:** Queries `GET /api/v1/incidents/{incident_id}` to retrieve envelope-level cryptographic provenance, including:
  - Envelope ID (`ENV-...`).
  - Raw payload SHA-256 checksum.
  - Ingestion timestamp and latency.
- **Affected Topologies:** Displays granular network elements (e.g., `gnb-cluster-tx-09`, `upf-edge-core-01`).
- **Direct Workspace Transition:**
  - Includes a prominent **"Open Investigation Workspace"** CTA button.
  - Saves the active `incident_id` to `incidentContextStore` and navigates immediately to `/investigation`, pre-populating all diagnostic tabs with the selected incident.

---

## 5. UI States & Fallbacks

- **Loading State:** Monospace pulsing spinner indicating communication with `/api/v1/incidents`.
- **Empty Filter State:** If a search query yields zero matches, renders the `EmptyState` component with a single-click "Reset All Filters" action.
- **API Error State:** Renders the `ErrorState` component detailing the exact HTTP error code (e.g., 500 Internal Error or 401 Unauthorized) and an immediate "Retry Request" trigger.
