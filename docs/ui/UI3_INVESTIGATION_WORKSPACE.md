# PIIS UI-3: Investigation Workspace Architecture & Specification

**Milestone:** UI-3  
**Screen:** Investigation Workspace (`InvestigationPage.tsx`)  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  
**Auditor / Implementer:** Antigravity Agentic Engineer  

---

## 1. Executive Overview

The **Investigation Workspace** is the analytical epicenter of the Production Incident Intelligence System (PIIS — Telecom Edition). In modern telecommunications operations, when critical network disruptions occur—such as radio return loss spikes, IMS call dropping, IP core BGP session flappings, or 5G user plane function (UPF) disconnections—NOC engineers and domain specialists require an evidence-grounded, epistemically disciplined workspace to diagnose root causes and evaluate remediation runbooks.

The workspace strictly adheres to the core PIIS design principle:
> **EXISTING TELECOM WORKFLOW + PIIS = ADDITIVE INVESTIGATION ENGINE**  
> PIIS operates purely as a read-only, evidence-grounded decision support companion. It synthesizes telemetry, ranks diagnostic hypotheses with transparent mathematical proxies, highlights contradictory and stale signals, and maps approved standard operating procedures (SOPs). It strictly forbids autonomous production mutations or unverified diagnostic assertions.

---

## 2. Information Architecture & Workspace Topology

The Investigation Workspace layout is structured into five logical, high-density analytical zones:

```
+----------------------------------------------------------------------------------------------------+
| Zone 1: Incident Context Header (Ticket Switcher, Severity, Domain, Impact, Lineage Checksum)      |
+----------------------------------------------------------------------------------------------------+
| Zone 2: Evidence Sufficiency & Stale Signals Alert Banner (Freshness, Contradictions, Missing)     |
+----------------------------------------------------------------------------------------------------+
| Zone 3: Analytical Tabs Navigation [ Hypotheses (Ranked) | Evidence Register | Recommendations ]   |
|                                                                                                    |
| +-----------------------------------------------+ +----------------------------------------------+ |
| | Tab 1: Hypothesis Analysis                    | | Tab 2: Evidence Register                     | |
| | - Ranked Hypotheses with Confidence Proxies   | | - Structured Signals by Category             | |
| | - Mathematical Rationale & Heuristic Basis    | | - Trust Levels (M1 Hash, Synthetic, ML)      | |
| | - Supporting vs Contradictory Evidence Links  | | - Stale Flag (>3600s), Raw JSON Metadata     | |
| | - Safe Abstention & Alternative Explanations  | |                                              | |
| +-----------------------------------------------+ +----------------------------------------------+ |
| | Tab 3: Diagnostic Recommendations & Approvals                                                  | |
| | - SOP / Runbook Mapping (Section-Level Provenance)                                             | |
| | - Risk Classification (READ_ONLY_SAFE vs DISRUPTIVE_AUDIT)                                      | |
| | - Mandatory Human Review Declaration & Historical Sign-Off Ledger                              | |
| +------------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
| Zone 4: Chronological Lifecycle Investigation Timeline (Observation -> Ingestion -> Review)        |
+----------------------------------------------------------------------------------------------------+
| Zone 5: Epistemic Taxonomy & System Boundary Ledger (Non-Disruptive Safety Boundary Guarantee)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Architecture

### Zone 1: Incident Context Header (`IncidentContextHeader.tsx`)
- **Navigation & Ticket Switcher:** Back button returning directly to the Incident Explorer (`/incidents`), accompanied by a live ticket dropdown allowing quick switching between active and historical telecom incidents.
- **Canonical Telemetry Summary:** Renders canonical backend fields conforming to `schemas/incident.schema.json`:
  - `incident_id`: Unique identifier (e.g., `INC-2026-0001`).
  - `title`: Telecommunications fault title (e.g., `High VSWR on 5G NR Sector 4B`).
  - `severity`: Visual `SeverityBadge` (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`).
  - `network_domain`: Telecom tier badge (`RAN`, `5G_CORE`, `TRANSPORT`, `SERVICE`).
  - `status`: Active vs Resolved lifecycle badge.
  - `source`: Source system and event origin (e.g., `ServiceNow` / `PUBLIC_REAL`).
  - `affected_subscribers`: Quantified customer impact count.
  - `network_element_ids`: Affected physical/virtual nodes (e.g., `gNodeB-7821`, `RRU-4B`).
- **Cryptographic Provenance:** Direct display of raw ingestion envelope SHA-256 checksums to guarantee data integrity across boundaries.

### Zone 2: Evidence Sufficiency Banner (`SufficiencyAlertBanner.tsx`)
- **Mathematical Evaluation:** Directly consumes boolean `is_sufficient` and diagnostic telemetry from the backend investigation engine.
- **Freshness & Stale Signals:** Explicitly checks timestamps of all ingested evidence. If any signal exceeds the 3600s threshold, a prominent stale signal warning is triggered.
- **Contradictory Signal Alert:** Highlights conflicting telemetry (e.g., cell availability reported normal while radio return loss is severe).
- **Missing Telemetry Checklist:** Declares uncollected network probes needed for high-confidence isolation (e.g., missing optical power levels or fiber OTDR traces).

### Zone 3A: Hypothesis Analysis (`HypothesisAnalysisCard.tsx`)
- **Ranked Hypothesis Cards:** Evaluates candidate root causes generated by the hybrid reasoning engine (IsolationForest, GNN anomaly detector, and deterministic rule engine).
- **Confidence Calibration:** Confidences are explicitly labeled as **Heuristic Confidence Proxies** (ranging from `0.00` to `1.00`), never presented as certified facts.
- **Transparent Rationale:** Full mathematical rationale detailing the heuristic weight, signal correlation coefficient, and anomaly deviation z-scores.
- **Bi-Directional Evidence Cross-Linking:** Clicking a supporting (green) or contradicting (rose) evidence chip instantly switches to the Evidence Register tab and smoothly scrolls to the exact evidence card, highlighting it in amber.
- **Safe Abstention & Alternative Hypotheses:** Transparently lists rejected or low-confidence alternative explanations (e.g., transient thermal expansion, substation power drops) and recommended operator verification steps.

### Zone 3B: Evidence Register (`EvidenceRegisterCard.tsx`)
- **Multifaceted Telemetry Filter:** Operators can filter evidence items by category (`ALL`, `METRIC`, `ALARM`, `TOPOLOGY`, `LOG`, `CONFIG`).
- **Cryptographic Verification:** Distinguishes verified real evidence from synthetic traces and ML inference outputs via `EpistemicBadge`.
- **Signal Age Indicators:** Dynamically calculates relative and absolute timestamps with explicit warning badges for stale telemetry.
- **Deep Metadata Drawer:** Collapsible inspection drawer displaying full raw JSON metadata payloads (e.g., return loss in dB, VSWR ratios, alarm codes) for deep forensic auditing.

### Zone 3C: Recommendations & Approvals (`RecommendationCard.tsx`)
- **Runbook Provenance:** Every recommendation cites its source standard operating procedure and specific section (e.g., `SOP-RAN-VSWR-001`, Section 3.2).
- **Risk Classification:**
  - `READ_ONLY_SAFE`: Non-intrusive diagnostic probes and passive spectrum sweeps.
  - `DISRUPTIVE_AUDIT`: Traffic-affecting diagnostic routines (e.g., carrier cell barring, RF loopback).
- **Mandatory Human-in-the-Loop Review:** Declares that PIIS cannot execute remediation commands. A prominent warning banner reminds the operator that manual approval through the enterprise telecom ITSM workflow is required.
- **Approval Audit Ledger:** Displays current approval status (`PENDING_REVIEW`, `APPROVED`, `REJECTED`), reviewer identity, review timestamp, and operator rationale notes.

### Zone 4: Chronological Investigation Timeline (`InvestigationTimeline.tsx`)
- **Temporal Alignment:** Plots every lifecycle milestone strictly from genuine backend timestamps:
  1. *Observed at Tower/Node:* `lineage.observation_timestamp`
  2. *Ingested into PIIS Gateway:* `lineage.ingested_at`
  3. *Telemetry Evidentiary Traces:* `evidence.observed_at`
  4. *Hybrid Investigation Execution:* `investigation.created_at`
  5. *Diagnostic Review & Sign-Off:* `recommendation.review_timestamp`
  6. *Network Fault Resolution:* `incident.resolved_at`
- **Zero Hallucinated Dates:** If a timestamp was not recorded by the upstream system, the timeline explicitly renders an "Unrecorded / Pending" marker.

---

## 4. Epistemic Taxonomy & Guardrails

The workspace enforces the six PIIS epistemic categories across all rendered data:
1. `DETERMINISTIC_VERIFIED`: Cryptographic hashes, raw alarm payloads, Merkle audit roots.
2. `HEURISTIC_PREDICTION`: Machine learning anomaly scores, IsolationForest rank outputs.
3. `RAG_RETRIEVAL`: Telecom standard operating procedures and technical documentation snippets.
4. `UNVERIFIED_SOURCE`: Telemetry from external legacy probes without cryptographic seals.
5. `SYNTHETIC_EVALUATION`: Benchmarking scenarios generated for stress and regression testing.
6. `OPERATOR_ASSERTION`: Manual sign-off notes and human supervisor approvals.

The UI visually enforces these distinctions with colored border styling, warning badges, and explicit explanatory tooltips.
