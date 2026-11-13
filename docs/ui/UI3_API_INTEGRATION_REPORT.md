# PIIS UI-3: API Integration & Data Contract Audit Report

**Milestone:** UI-3  
**Subject:** Investigation Workspace API Integration & Backend Contract Justification  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  
**Auditor / Implementer:** Antigravity Agentic Engineer  

---

## 1. Executive Summary

Milestone **UI-3** integrates the React frontend with the deep analytical pipeline of the PIIS backend (`src/piis/api/`). The Investigation Workspace requires multi-faceted evidentiary telemetry, ranked hypotheses with mathematical proxies, runbook-backed diagnostic recommendations, and chronological lifecycle traces.

Rather than resorting to simulated client-side mocks or ungrounded data generation, the frontend communicates with verified FastAPI backend routes. To support complete read-only investigation inspection without modifying pipeline business logic, a **minimal, strictly justified backend contract extension** was implemented and audited.

---

## 2. Consumed Backend Endpoints & Schemas

| Endpoint | Method | Consumed By | Query / Body Parameters | Response Schema |
|---|---|---|---|---|
| `/api/v1/incidents` | GET | `InvestigationPage.tsx` | `limit: 50`, `offset: 0` | `PaginatedResponse<CanonicalIncidentItem>` |
| `/api/v1/incidents/{incident_id}` | GET | `InvestigationPage.tsx` | Path: `incident_id` | `{ incident: CanonicalIncidentItem, lineage: LineageRecord }` |
| `/api/v1/incidents/{incident_id}/evidence` | GET | `EvidenceRegisterCard.tsx` | Path: `incident_id` | `List[InvestigationEvidenceItem]` |
| `/api/v1/incidents/{incident_id}/investigate` | POST | `InvestigationPage.tsx` | Path: `incident_id` | `InvestigationResponse` (with ranked hypotheses) |
| `/api/v1/incidents/{incident_id}/investigation` | GET | `InvestigationPage.tsx` | Path: `incident_id` | `InvestigationResponse` (read-only cached investigation) |
| `/api/v1/incidents/{incident_id}/hypotheses` | GET | `HypothesisAnalysisCard.tsx` | Path: `incident_id` | `List[IncidentHypothesisItem]` |
| `/api/v1/incidents/{incident_id}/recommendations` | GET | `RecommendationCard.tsx` | Path: `incident_id` | `List[DiagnosticRecommendationItem]` |

---

## 3. Justification for Minimal Backend Contract Additions

### Context & Gap Analysis
During the UI-3 readiness audit, the backend investigation engine (`IncidentInvestigationEngine` in `src/piis/investigation/engine.py`) was verified to generate rich, mathematically grounded hypothesis objects (`ctx.hypotheses: List[IncidentHypothesis]`) including confidence proxies, supporting and contradicting evidence IDs, and diagnostic rationales.

However, the existing public API had two limitations:
1. `InvestigationResponse` in `src/piis/api/schemas.py` only returned an integer count (`hypotheses_count: int`), discarding the rich `ctx.hypotheses` array during serialization.
2. The router in `src/piis/api/routers/incidents.py` provided `GET /evidence` and `GET /recommendations`, but lacked a corresponding read-only `GET /hypotheses` endpoint and a pure `GET /investigation` inspection route (forcing clients to trigger a mutating `POST /investigate` calculation even when merely reviewing existing data).

### Implemented Additions (Smallest Justified Surface)
To adhere strictly to project invariants while delivering an evidence-grounded operator experience, the following surgical additions were made:

1. **`src/piis/api/schemas.py`:**
   ```python
   class InvestigationResponse(BaseModel):
       ...
       hypotheses_count: int
       hypotheses: List[Dict[str, Any]] = Field(
           default_factory=list,
           description="Ranked candidate hypotheses with confidence proxies and evidence mappings",
       )
   ```
2. **`src/piis/api/routers/incidents.py`:**
   - Updated `POST /api/v1/incidents/{incident_id}/investigate` to populate `hypotheses=[h.model_dump() for h in ctx.hypotheses]`.
   - Added `GET /api/v1/incidents/{incident_id}/hypotheses` returning `[h.model_dump() for h in ctx.hypotheses]`.
   - Added `GET /api/v1/incidents/{incident_id}/investigation` returning an idempotent read-only `InvestigationResponse` without mutating system state.

### Independent Verification
These additions were validated through 4 dedicated integration tests in `tests/integration/test_ui3_investigation_endpoints.py`:
- `test_get_hypotheses_endpoint`: Verifies ranked hypotheses array schema and status 200.
- `test_get_hypotheses_not_found`: Verifies 404 behavior for unknown incidents.
- `test_get_investigation_read_endpoint`: Verifies read-only idempotent investigation retrieval.
- `test_post_investigate_returns_hypotheses`: Verifies `POST /investigate` returns populated hypotheses.

**Full Python Test Suite Result:** 392 / 392 passed (100% pass rate, 0 regressions).

---

## 4. Frontend Data Contracts & Types (`types.ts`)

The TypeScript definitions in `frontend/src/api/types.ts` strictly mirror the backend Pydantic models:

```typescript
export interface IncidentHypothesisItem {
  hypothesis_id: string
  description: string
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  evidence_source: string
  evidence_timestamp: string
  confidence_proxy: number
  confidence_rationale: string
  alternative_explanations?: string[]
  recommended_verification_steps?: string[]
  status?: string
}

export interface InvestigationEvidenceItem {
  evidence_id: string
  category: string
  description: string
  source: string
  observed_at: string
  trust_level: 'VERIFIED' | 'UNVERIFIED' | 'SYNTHETIC' | 'DERIVED'
  raw_payload?: Record<string, unknown>
  is_stale?: boolean
}

export interface DiagnosticRecommendationItem {
  recommendation_id: string
  description: string
  reason: string
  supporting_evidence_ids: string[]
  source_runbook_id: string
  source_section: string
  risk_classification: 'READ_ONLY_SAFE' | 'DISRUPTIVE_AUDIT'
  human_approval_required: boolean
  approval_status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED'
  reviewed_by?: string | null
  review_timestamp?: string | null
  review_notes?: string | null
}
```

---

## 5. Client-Side Query Optimization & Error Resilience

- **Stale-While-Revalidate Caching:** TanStack Query caches investigation responses for 30 seconds (`staleTime: 30000`) with window refocus refetching disabled to avoid redundant computational load on the backend.
- **Bi-Directional Query Coordination:** The `useInvestigationQuery` hook orchestrates concurrent fetching of incident details, evidence records, hypotheses, and recommendations.
- **Graceful Error Handling:** If any upstream subsystem encounters a 504 Gateway Timeout or 500 Internal Error, `InvestigationPage.tsx` traps the failure and renders an accessible `ErrorState` card with clear diagnostic details and a manual "Retry" trigger.
