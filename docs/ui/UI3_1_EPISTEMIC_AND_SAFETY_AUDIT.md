# PIIS UI-3.1: Epistemic Integrity, Safety Boundaries & Cryptographic Provenance Audit

**Milestone:** UI-3.1 (Independent Verification & Hardening)  
**Subject:** Epistemic Calibration, Telemetry Freshness Policies, Operational Safety Boundaries & Cryptographic Provenance  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  
**Auditor / Implementer:** Antigravity Agentic Engineer  

---

## 1. Executive Summary

Milestone **UI-3.1** evaluates the epistemic claims and operational boundaries presented by the PIIS Investigation Workspace. In telecommunications network operations, overstating model certainty, misrepresenting heuristic rankings as calibrated probabilities, or presenting advisory recommendations as execution-ready authorizations introduces critical operational safety risks.

This audit establishes technical trust by aligning frontend representations strictly with backend algorithms, formalizing freshness policy disclosures, and enforcing non-disruptive operational boundaries.

---

## 2. Confidence Semantics Audit

### Underlying Generation Engine
An end-to-end trace through `IncidentInvestigationEngine` (`src/piis/investigation/engine.py`) confirms the exact origin of `confidence_proxy`:

1. **Algorithm Source:**
   ```python
   # Line 713 in engine.py:
   conf_proxy = round(min(1.0, 0.6 * primary_ev.confidence_proxy + 0.4 * pred_prob), 3)
   ```
   - `primary_ev.confidence_proxy`: Reciprocal Rank Fusion (RRF) score from M4 sparse (BM25) and dense bi-encoder semantic retrieval against Standard Operating Procedures (SOPs).
   - `pred_prob`: Softmax prediction probability from M2 classifier for the fault category.
2. **Epistemic Classification:**
   - It is an **empirical heuristic proxy score**, **NOT** a calibrated statistical probability.
   - The backend explicitly annotates the rationale: `(Empirical heuristic, not a probability)`.
   - Ranking of candidate hypotheses directly follows this score; ties are broken by retrieval document priority.
3. **Abstention Values:**
   - If evidence sufficiency fails: `confidence_proxy = 0.0`.
   - If retrieval confidence falls below the 0.35 safety floor: `confidence_proxy = 0.15` (marked `INCONCLUSIVE`).
   - If secondary candidate exists: `confidence_proxy = round(sec_ev.confidence_proxy * 0.75, 3)`.

### Frontend Presentation Hardening (UI-3.1):
- **Labeling:** The UI explicitly displays the metric as **`Heuristic Proxy`** with a subtitle **`Not a probability`**.
- **Tooltip Disclosure:** Hovering over the metric renders: `Heuristic rank score (0.00–1.00), not a calibrated probability of root cause.`
- **Missing Value Defense:** If `confidence_proxy` is null or undefined, the component renders `N/A` rather than `NaN%`.

---

## 3. Telemetry Freshness Policy Audit

### Backend vs. Frontend Freshness Architecture
Inspection of `src/piis/investigation/temporal.py` demonstrates that PIIS backend implements a **multi-tiered, source-specific freshness policy** (`DEFAULT_FRESHNESS_POLICIES`):

| Evidence Category | Backend Freshness Policy (`max_age_seconds`) | Clock Skew Tolerance | Context Role |
|---|---|---|---|
| **`TELEMETRY_ANOMALY`** | **3,600.0 s (1 hour)** | 60.0 s | Requires fresh confirmation for active fault |
| **`ALARM_CLUSTER`** | **7,200.0 s (2 hours)** | 60.0 s | Requires fresh confirmation for active fault |
| **`TICKET_METADATA`** | **14,400.0 s (4 hours)** | 60.0 s | Requires fresh confirmation for active fault |
| **`TOPOLOGY_IMPACT`** | **86,400.0 s (24 hours)** | 120.0 s | Permitted as contextual evidence |
| **`APPROVED_RUNBOOK`** | **31,536,000.0 s (1 year)** | 60.0 s | Policy reference |
| **`HISTORICAL_CASE`** | **31,536,000.0 s (1 year)** | 60.0 s | Comparative context |

### UI-3.1 Freshness Policy Labeling:
The UI-3 alert banner previously displayed `Stale Telemetry (>3600s)`. In UI-3.1:
- The alert is labeled: **`Stale Telemetry (Policy >3600s)`**
- A visible footnote clarifies: `* Evaluated per-source policy (3600s real-time probe baseline)`.
- Operators are transparently informed that the 3600s threshold applies to probe metrics, while alarms and tickets use longer policy horizons.
- The UI handles fresh signals, stale signals, missing timestamps (`N/A`), future-dated telemetry (clock skew warnings), and uninstrumented elements cleanly without throwing errors.

---

## 4. Human Approval & Operational Safety Boundaries

### Mandatory Invariant Verification
1. **Advisory Nature of Recommendations:**
   - The UI explicitly renders an immutable **Advisory Boundary Strip** in `RecommendationCard.tsx`:
     > *“Advisory Boundary: PIIS provides evidence-grounded recommendations. Existing authorized operational workflows remain responsible for execution. PIIS cannot execute commands or mutate network configurations.”*
2. **Zero Command Execution Capability:**
   - The frontend contains no terminal, SSH, Netconf, YANG, or REST client capable of dispatching execution commands to network elements.
   - Clicking `Inspect / Review` navigates to the human sign-off review form, never to an execution pipeline.
3. **No Independent Authorization:**
   - The frontend cannot unilaterally mark an action as approved. All approval transitions must be submitted to the backend `/review` endpoint, signed by an authenticated human operator with `Permission.APPROVE_RECOMMENDATIONS`.
4. **Reframing Review Records:**
   - Review records are accurately titled **`Human Reviewer Sign-Off Record`** with a clarifying note: `Decision support sign-off only. Does not constitute production execution authorization.`

---

## 5. Cryptographic Provenance & Envelope Integrity

### Granular Integrity Status Presentation
In UI-3.1, `IncidentContextHeader.tsx` integrates the canonical ingestion lineage and accurately differentiates five distinct cryptographic integrity states:

```
+----------------------------------------------------------------------------------------------------+
| 1. Checksum Available:    SHA-256 Checksum Available: e3b0c44298fc... (Calculated at ingestion)    |
| 2. Checksum Unavailable:  Ingested without raw payload digest from upstream legacy source           |
| 3. Verification Incomplete: Pending lineage trace synchronization from adapter                     |
| 4. Checksum Verified:     Cross-referenced and verified against RFC 8785 Merkle audit ledger root  |
| 5. Verification Failed:   Cryptographic mismatch detected during ledger traversal                  |
+----------------------------------------------------------------------------------------------------+
```

- **Safety Clarification:** The UI explicitly adds: `(Digest calculated at ingestion; audit root verification separate)`.
- A displayed SHA-256 hash is never presented as proof of total audit integrity or authentic hardware notarization without explicit confirmation from `/api/v1/audit/verify`.

---

## 6. Epistemic Audit Classification & Verdict

| Audit Item | Verification Scope | Finding & Evidence | Verdict |
|---|---|---|---|
| **EPIST-3.1-001** | Confidence Value | Derived from `0.6 * retrieval + 0.4 * classification`. Heuristic proxy disclosed with tooltip and "Not a probability" label. | **PASS** |
| **EPIST-3.1-002** | Contradictory Telemetry | Contradictory signals surfaced prominently; cannot be suppressed by high confidence scores. | **PASS** |
| **EPIST-3.1-003** | Freshness Policy | Clarified that 3600s threshold is the probe baseline within a multi-tiered backend freshness architecture. | **PASS** |
| **EPIST-3.1-004** | Operational Safety | Verified zero production execution capabilities; advisory role stated unambiguously. | **PASS** |
| **EPIST-3.1-005** | Cryptographic Provenance | Five distinct integrity states recognized; SHA-256 hash not conflated with Merkle notarization. | **PASS** |
