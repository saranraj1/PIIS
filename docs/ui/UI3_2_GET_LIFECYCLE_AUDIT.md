# PIIS UI-3.2 — Investigation GET Lifecycle & Side-Effect Audit

**Milestone:** UI-3.2  
**Status:** Complete & Verified  
**Date:** November 2026  
**Audited Routers:** `src/piis/api/routers/incidents.py`, `src/piis/pipeline/unified.py`, `src/piis/api/schemas.py`  
**Frontend Modules:** `frontend/src/pages/InvestigationPage.tsx`, `frontend/src/api/queries.ts`

---

## 1. Executive Summary

In Milestone UI-3.1, architectural analysis revealed an anti-pattern in the Investigation REST API: four `GET` endpoints (`/{id}/investigation`, `/{id}/hypotheses`, `/{id}/evidence`, `/{id}/recommendations`) exhibited **lazy execution side-effects**. Specifically, if an incident had not yet been investigated, calling any of these `GET` endpoints would transparently invoke `pipeline.investigate_incident(incident_id)` and register recommendations into the `HumanApprovalWorkflow` state machine.

This lazy computation violated core architectural invariants:
1. **HTTP/1.1 RFC 9110 Safe & Idempotent Semantics:** `GET` operations must be free of state-mutating side-effects.
2. **Read-Only Operational Posture:** Autonomous backend execution must not be surreptitiously triggered by read-only dashboard navigation, link crawling, or speculative prefetching.
3. **Explicit Operator Attribution:** In a telecommunications NOC, investigative AI and recommendation registration must occur only upon deliberate operator action or scheduled event processing, not as an unlogged byproduct of UI rendering.

Under **Milestone UI-3.2**, all four `GET` endpoints have been refactored to enforce **pure read-only semantics**. Lazy computation has been completely eliminated. `POST /api/v1/incidents/{incident_id}/investigate` remains the single, audited trigger for investigation generation.

---

## 2. Endpoint Side-Effect Matrix

| Endpoint | Method | Safe / Idempotent | Reads Data | Computes / Mutates State | Registers Recommendations | Status Codes |
|---|---|---|---|---|---|---|
| `/api/v1/incidents/{id}/investigate` | `POST` | No / No | Yes (reads incident & element telemetry) | **Yes** (executes M2–M5 pipeline, updates metrics) | **Yes** (registers items into `HumanApprovalWorkflow`) | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |
| `/api/v1/incidents/{id}/investigation` | `GET` | **Yes / Yes** | Yes (in-memory pipeline lookup) | **No** (pure lookup) | **No** (zero registration) | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |
| `/api/v1/incidents/{id}/hypotheses` | `GET` | **Yes / Yes** | Yes (in-memory pipeline lookup) | **No** (pure lookup) | **No** (zero registration) | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |
| `/api/v1/incidents/{id}/evidence` | `GET` | **Yes / Yes** | Yes (in-memory pipeline lookup) | **No** (pure lookup) | **No** (zero registration) | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |
| `/api/v1/incidents/{id}/recommendations` | `GET` | **Yes / Yes** | Yes (in-memory pipeline lookup) | **No** (pure lookup) | **No** (zero registration) | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |

---

## 3. Detailed Call Paths & Audit Analysis

### 3.1 `POST /api/v1/incidents/{incident_id}/investigate`
- **RBAC Guard:** `require_permissions(Permission.TRIGGER_INVESTIGATION)`
- **Behavior:**
  1. Retrieves correlation ID from tracing context.
  2. Executes `ctx = pipeline.investigate_incident(incident_id)`.
  3. If incident does not exist in pipeline, raises `HTTPException(404, "Incident '{incident_id}' not found")`.
  4. Records latency and telemetry metrics via `record_investigation()`.
  5. Registers candidate recommendations into `HumanApprovalWorkflow`:
     ```python
     for rec in ctx.recommendations:
         try:
             workflow.register_recommendation(rec, incident_id=incident_id)
         except Exception:
             pass
     ```
  6. Returns typed `InvestigationResponse` (HTTP 200).
- **Audit Logging:** Traces span `investigate_incident` with tags `incident_id`, telemetry counters, and latency histogram.

### 3.2 Refactored `GET` Call Paths
All four `GET` endpoints now implement the identical strict two-tier resolution pattern:

```python
# Step 1: Check canonical incident existence
incident = pipeline.get_incident(incident_id)
if not incident:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Incident '{incident_id}' not found",
    )

# Step 2: Check cached investigation existence
ctx = pipeline.get_investigation(incident_id)
if not ctx:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Investigation not yet generated for incident '{incident_id}'. "
               f"Trigger investigation via POST /api/v1/incidents/{incident_id}/investigate.",
    )
```

#### Verification Invariants:
1. **Zero Pipeline Execution:** `pipeline.investigate_incident` is never called.
2. **Zero Workflow Registration:** `workflow.register_recommendation` is never called; the `HumanApprovalWorkflow` dependency was removed from `get_investigation_context`.
3. **Deterministic Error Differentiation:**
   - If incident `INC-X` does not exist: HTTP 404 with body `{"detail": "Incident 'INC-X' not found"}`.
   - If incident `INC-X` exists but investigation is not generated: HTTP 404 with body `{"detail": "Investigation not yet generated for incident 'INC-X'. Trigger investigation via POST /api/v1/incidents/INC-X/investigate."}`.

---

## 4. Frontend Lifecycle Handling & Operator Control

In `frontend/src/pages/InvestigationPage.tsx`:

1. **Pure Read-Only On Load:**  
   Navigating to `/investigation?id=INC-X` triggers only `GET` queries (`useIncidentDetailQuery` and `useInvestigationQuery`). It will **never** automatically execute a `POST` mutation.

2. **Domain Lifecycle Detection:**  
   When `useInvestigationQuery` returns an HTTP 404 with `"not yet generated"`, the UI distinguishes this from unexpected network/server errors:
   ```typescript
   const isUngeneratedState = Boolean(
     invError &&
     invErr &&
     (invErr.message.toLowerCase().includes('not yet generated') ||
      invErr.message.toLowerCase().includes('trigger investigation'))
   )
   ```

3. **Explicit Operator Invocation CTA:**  
   Rather than displaying a generic error message, the workspace presents an intentional "Status: Not Initiated" domain banner with an explicit **"Trigger Investigation"** action button.

4. **Audited Trigger Execution:**  
   Clicking the button calls `useTriggerInvestigationMutation`, executing `POST /api/v1/incidents/{id}/investigate`. Upon success, TanStack Query invalidates the query keys, triggering fresh `GET` requests that populate the hypotheses, evidence register, sufficiency alerts, and recommendations.

---

## 5. Automated Verification Evidence

The behavior is verified in `tests/integration/test_ui3_investigation_endpoints.py`:
- `test_get_investigation_not_yet_generated_returns_404_without_side_effects`:
  - Verifies HTTP 404 on all 4 `GET` routes before investigation.
  - Verifies `pipeline.get_investigation(seeded_incident)` remains `None`.
  - Verifies `workflow._recommendations` has 0 items registered for this incident.
- `test_get_investigation_nonexistent_incident_returns_404`:
  - Verifies HTTP 404 `"Incident 'INC-NONEXISTENT-9999' not found"` on all 4 `GET` routes.
- `test_investigate_post_populates_cache_and_enables_get`:
  - Verifies `POST /investigate` populates cache and enables subsequent `GET` calls to succeed with HTTP 200.
- `test_get_investigation_idempotency`:
  - Verifies that multiple sequential `GET` requests return identical payloads without mutations.

Frontend behavior is verified in `frontend/src/test/InvestigationWorkspace.test.tsx`:
- `renders ungenerated state and allows deliberate trigger when investigation is not yet generated`:
  - Simulates 404 "not yet generated" response.
  - Asserts that "Investigation Not Yet Generated" banner renders.
  - Clicks "Trigger Investigation" button and verifies `apiClient.post` was called with `/api/v1/incidents/INC-2026-0001/investigate`.
