# PIIS UI-2: API Integration & Data Contract Audit Report

**Milestone:** UI-2  
**Subject:** Frontend-to-Backend Integration Audit  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  

---

## 1. Executive Summary

Milestone **UI-2** established full data integration between the PIIS React frontend and the existing FastAPI backend (`src/piis/api/`). Rather than mocking arbitrary data in the UI layer, every component in the **Command Center** and **Incident Explorer** was mapped directly to verified FastAPI backend routes.

This document details:
1. The backend endpoints consumed.
2. The exact request query parameters and response schemas.
3. Client-side handling of unsupported backend features (e.g. text search).
4. The strict separation between verified local execution and simulated external systems.

---

## 2. Consumed Backend Endpoints & Query Mappings

| Endpoint | Method | Consumed By | Query / Body Parameters | Response Model |
|---|---|---|---|---|
| `/api/v1/health` | GET | `CommandCenterPage.tsx` | None | `{ status: string, service: string, mode: string }` |
| `/api/v1/ready` | GET | `CommandCenterPage.tsx` | None | `{ status: string, registered_adapters_count: number, degraded_adapters: string[], incidents_count: number, dead_letter_count: number, audit_ledger_records: number }` |
| `/api/v1/incidents` | GET | `CommandCenterPage.tsx`, `IncidentExplorerPage.tsx` | `limit` (int, default 20), `offset` (int, default 0), `domain` (str, optional), `severity` (str, optional) | `PaginatedResponse<CanonicalIncidentItem>` |
| `/api/v1/incidents/{incident_id}` | GET | `IncidentExplorerPage.tsx` (Detail Drawer) | Path parameter: `incident_id` | `{ incident: CanonicalIncidentItem, lineage: LineageRecord }` |
| `/api/v1/integrations/health` | GET | `CommandCenterPage.tsx` | None | `Array<AdapterHealthItem>` |
| `/api/v1/audit/verify` | GET | `CommandCenterPage.tsx` | None | `{ verified: boolean, record_count: number, tamper_detected: boolean, root_hash: string }` |

---

## 3. Query Parameter Analysis & Unsupported Filter Handling

### Backend Query Capabilities in `src/piis/api/routers/incidents.py`:
- **`limit` & `offset`**: Fully supported by backend.
- **`domain`**: Fully supported (filters by `network_domain == domain.upper()`).
- **`severity`**: Fully supported (filters by `severity == severity.upper()`).

### Unsupported Parameters in Backend API:
- **Text Search (`search`)**:
  - *Backend behavior:* Does not support arbitrary text search on `GET /api/v1/incidents`.
  - *UI Solution:* The frontend queries an ample page batch (`limit: 200`) and executes instant, client-side substring matching across `incident_id`, `title`, `description`, `fault_category`, and `network_element_ids`.
- **Status Filter (`status`)**:
  - *Backend behavior:* The backend does not expose an explicit status query param; canonical incidents track lifecycle through the presence or absence of `resolved_at`.
  - *UI Solution:* The UI provides an intuitive `ACTIVE` (`resolved_at === null`) vs `RESOLVED` (`resolved_at !== null`) dropdown filter, computed reactively over the incident list.
- **Sorting (`sort_by`, `sort_order`)**:
  - *Backend behavior:* Incidents are stored and returned in pipeline insertion order.
  - *UI Solution:* Interactive table sorting (by Created Date, Severity weight, or Incident ID) is performed client-side using deterministic comparison algorithms.

---

## 4. Contract Schema Alignment with `schemas/incident.schema.json`

The TypeScript interface `CanonicalIncidentItem` in `frontend/src/api/types.ts` was rigorously validated against the canonical JSON schema in `schemas/incident.schema.json`:

```typescript
export interface CanonicalIncidentItem {
  incident_id: string
  title?: string | null
  description: string
  network_domain: string
  fault_category: string
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'WARNING'
  support_level_label?: 'L1' | 'L2' | 'L3' | null
  support_level_rationale?: string | null
  affected_region?: string | null
  affected_subscribers?: number | null
  network_element_ids?: string[]
  created_at: string
  resolved_at?: string | null
  resolution_summary?: string | null
  root_cause_confirmed?: boolean
  source_type?: 'PUBLIC_REAL' | 'SYNTHETIC' | 'HUMAN_ANNOTATED'
  source_dataset?: string | null
  source_record_id?: string | null
}
```

Every property accessed in `IncidentExplorerPage.tsx` and `CommandCenterPage.tsx` conforms to this definition. Nullable properties are defended with safe fallback expressions.

---

## 5. Security & Authentication Boundary

1. **Bearer Token Injection:**
   - All API calls through `apiClient` (`frontend/src/api/client.ts`) inject volatile Bearer tokens if available from `AuthContext`.
2. **Read-Only Enclosure:**
   - None of the UI-2 screens make `POST`, `PUT`, `PATCH`, or `DELETE` requests to `/api/v1/incidents` or `/api/v1/investigation`.
   - The UI strictly consumes read-only data, adhering to the safety posture of PIIS.
3. **No Persistent Token Leaks:**
   - Security tokens remain solely in React memory (`AuthContext.tsx`). No tokens are saved to `localStorage` or `sessionStorage`.

---

## 6. Verification Status

- **Contract Tests:** `IncidentExplorer.test.tsx` and `CommandCenter.test.tsx` verify successful deserialization and rendering of all canonical fields.
- **Error Handling:** Tested against 401 Unauthorized, 403 Forbidden, 500 Internal Error, and network timeouts.
- **Backend Regression:** All 388 Python tests pass without change.
