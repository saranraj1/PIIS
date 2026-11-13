# PIIS UI-9 — Settings & Configuration Workspace Reconnaissance Report

**Milestone:** UI-9 Settings & Configuration Workspace  
**Subsystem:** Production Incident Intelligence System (PIIS — Telecom Edition)  
**Author:** Senior Full-Stack Engineer, Backend Architect, Security Engineer & UI/UX Engineer  
**Date:** November 4, 2026  
**Status:** COMPLETE & AUTHORITATIVE RECONNAISSANCE  
**Operational Scope:** STRICTLY READ-ONLY DECISION SUPPORT — PORTFOLIO EDITION  

---

## 1. Executive Summary & Objective

In accordance with the UI-9 milestone directive, this reconnaissance report conducts an exhaustive, pre-implementation audit of the Production Incident Intelligence System (PIIS — Telecom Edition). The mission is to design and implement a professional, evidence-grounded Settings & Configuration workspace at `/settings`.

Core design principles:
> **EVIDENCE BEFORE INTELLIGENCE.**  
> **INTELLIGENCE BEFORE AUTOMATION.**  
> **CONFIGURATION WITHOUT UNAUTHORIZED OPERATIONAL CONTROL.**

The Settings workspace must provide complete visibility into legitimate application-level preferences, session context, and system configuration while maintaining inviolate read-only security boundaries: zero production mutations, zero telecom command execution, zero ticket closures, zero credential exposure, and zero unauthenticated administrative controls.

---

## 2. Existing Configuration Inventory

### 2.1 Frontend Configuration & State Management
| Item | Source / Location | Scope | Mutability | Persistence Mechanism |
|---|---|---|---|---|
| **Color Theme** | `frontend/src/theme/ThemeContext.tsx` | UI Shell | User-Configurable (`dark` / `light`) | `localStorage.getItem('piis_theme_preference')` |
| **Active Bearer Token** | `frontend/src/auth/AuthContext.tsx` | Session | User-Entered in React State | **Volatile In-Memory Only** (Zero storage in `localStorage`/`sessionStorage`) |
| **Decoded JWT Claims** | `frontend/src/auth/AuthContext.tsx` | Session | Read-Only (Derived from JWT) | Volatile In-Memory Only |
| **Display Density** | Proposed in UI-9 | UI Shell | User-Configurable (`comfortable` / `compact`) | `localStorage.getItem('piis_display_density')` |
| **Timezone Preference** | Proposed in UI-9 | Display | User-Configurable (`UTC` / `LOCAL`) | `localStorage.getItem('piis_timezone_preference')` |
| **Datetime Format** | Proposed in UI-9 | Display | User-Configurable (`24H` / `12H`) | `localStorage.getItem('piis_time_format')` |
| **Default Page Size** | Proposed in UI-9 | Tables | User-Configurable (`10` / `25` / `50`) | `localStorage.getItem('piis_page_size')` |
| **Auto-Refresh Rate** | Proposed in UI-9 | Polling | User-Configurable (`OFF` / `15s` / `30s` / `60s`) | `localStorage.getItem('piis_refresh_interval')` |

### 2.2 Backend Configuration & Environment Variables
| Variable / Setting | Default Value | Physical File Grounding | Mutability | Security Classification |
|---|---|---|---|---|
| `PIIS_ENVIRONMENT` / `PIIS_ENV` | `"development"` | `src/piis/auth/manager.py`, `src/piis/audit/trust_boundary.py` | Environment-Locked | Public Architectural Mode |
| `PIIS_LOG_LEVEL` | `"INFO"` | `src/piis/observability/logging.py` | Environment-Locked | Operational Telemetry |
| `PIIS_AUDIT_HMAC_KEY` | Development Key | `src/piis/audit/trust_boundary.py:89` | Environment-Locked | **SECRET** (Redacted: Never exposed) |
| `PIIS_OIDC_JWKS_URL` | None (Local IdP) | `src/piis/auth/manager.py:55` | Environment-Locked | Configuration Endpoint |
| `PIIS_OIDC_ISSUER` | None (Local IdP) | `src/piis/auth/manager.py:56` | Environment-Locked | Identity Trust Domain |
| `PIIS_OIDC_AUDIENCE` | None (Local IdP) | `src/piis/auth/manager.py:57` | Environment-Locked | Client Audience |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| None (Disabled) | `src/piis/observability/tracing.py:112` | Environment-Locked | Telemetry Egress |
| `DETERMINISTIC_SOP_MAP` | 15 Rules | `src/piis/retrieval/engine.py:28` | Code-Locked | Deterministic SOP Knowledge |
| `IDEMPOTENCY_TTL` | 86400s (24h) | `src/piis/ingestion/idempotency.py` | Code-Locked | Ingestion Deduplication |
| `DLQ_MAX_RETRIES` | 3 attempts | `src/piis/ingestion/dlq.py` | Code-Locked | Quarantine Policy |

---

## 3. Frontend & Backend Integration Points

### 3.1 Frontend Routing & Navigation
- **Route:** `/settings` is already registered in `frontend/src/routes/router.tsx:55-57`.
- **Navigation:** `AppSidebar.tsx:36` contains `{ name: 'Settings & Profile', path: '/settings', icon: Settings }`.
- **Header:** `AppHeader.tsx` provides in-memory token trigger and theme toggle button.
- **Current Page:** `frontend/src/pages/SettingsPage.tsx` currently contains an initial placeholder handling only the bearer token form and theme switch. It will be completely evolved into the comprehensive 6-tab workspace.

### 3.2 Backend API Integration
The backend currently exposes authoritative, read-only system metadata across several endpoints:
- `GET /api/v1/health` & `GET /api/v1/ready` — Runtime liveness and readiness status.
- `GET /api/v1/system-health/overview` — Aggregate status, component counts, operational modes.
- `GET /api/v1/system-health/persistence` — Audit ledger path, HMAC signing key availability, checkpoint sequence.
- `GET /api/v1/system-health/intelligence` — BM25 index status, dense bi-encoder fallback mode, 15 SOP rules.
- `GET /api/v1/integrations` — 6 registered telecom protocol adapters, health states, configuration flags.
- `GET /api/v1/audit/summary` — Total ledger entries, first/last sequence, tamper status.

**New Dedicated Read-Only Endpoint:**
To consolidate application-level metadata and operational boundary guarantees without requiring multiple cross-endpoint joins, a dedicated read-only endpoint will be added:
- `GET /api/v1/settings/system-info`
  - Returns structured application version, edition, environment, active milestone, operational boundaries, and documentation catalog.
  - Protected by `require_permissions(Permission.VIEW_INCIDENTS)`.
  - Zero side-effects; strictly read-only.

---

## 4. Settings Classification: Safe vs Immutable

### 4.1 Safe User-Configurable Preferences (Browser-Local)
These preferences modify only the local client's presentation of data and carry zero operational risk:
1. **Theme Mode:** `dark` (NOC default) vs `light` vs `system`.
2. **Interface Density:** `comfortable` (standard padding) vs `compact` (data-dense NOC mode).
3. **Timezone Mode:** `UTC` (standard telecom operations) vs `LOCAL` (station local time).
4. **Time Notation:** `24H` (military / 3GPP timestamp) vs `12H` (AM/PM).
5. **Table Page Size:** `10`, `25` (default), or `50` records per page.
6. **Auto-Refresh Rate:** `OFF`, `15s`, `30s` (default), or `60s`.
7. **Session Token:** In-memory bearer token loaded into volatile React state; purge session on demand.

### 4.2 Strictly Immutable System Configuration
These settings must remain completely non-editable from the frontend interface:
1. **User Roles and Permissions:** Derived exclusively from server-side cryptographic validation of the JWT. Never editable by user.
2. **Operational Boundaries:** `read_only_decision_support` locked. Zero production commands or telecom mutations.
3. **Environment & Secrets:** `PIIS_ENVIRONMENT`, HMAC secret keys, and JWT verification keys are completely immutable and redacted.
4. **Audit Ledger & Checkpoint State:** Monotonic sequence numbers and cryptographic hashes cannot be altered or cleared.
5. **Adapter Operational Modes:** `READ_ONLY=True`, `MUTATION_ALLOWED=False` locked on all 6 adapters.

---

## 5. Persistence & Authorization Architecture

### 5.1 Storage Matrix
```
+--------------------------------+----------------------------+-----------------------------+
| Category                       | Storage Location           | Lifecycle                   |
+--------------------------------+----------------------------+-----------------------------+
| User Display Preferences       | Browser `localStorage`     | Persistent across reloads   |
| Authenticated Bearer Token     | Volatile React State       | Purged on tab reload/close  |
| Decoded Identity & Claims      | Volatile React State       | Purged on tab reload/close  |
| System & Security Config       | Backend Runtime State      | Immutable / Read-Only       |
| Cryptographic Audit Ledger     | Append-Only JSONL on Disk  | Permanent & Monotonic       |
+--------------------------------+----------------------------+-----------------------------+
```

### 5.2 Authorization Model
- Reading system settings: Requires authenticated JWT bearer token with `Permission.VIEW_INCIDENTS`.
- Unauthenticated requests to `/api/v1/settings/*`: Return HTTP 401 Unauthorized.
- Editing system settings: Prohibited. No `PUT`, `POST`, `PATCH`, or `DELETE` endpoints exist for system configuration.
- Local preference changes: Purely client-side; no network calls or server persistence.

---

## 6. Proposed Settings Workspace Structure (6 Sections)

The workspace at `/settings` will feature a responsive tabbed layout conforming to the NOC visual design system:

```
+---------------------------------------------------------------------------------------+
|  Settings & Configuration Workspace                  [OPERATOR: OP-TIER2-01] [RESET] |
|  Evidence-grounded application preferences and read-only operational telemetry        |
+---------------------------------------------------------------------------------------+
| [Appearance] [User & Session] [Application] [Security & Trust] [Integrations] [About] |
+---------------------------------------------------------------------------------------+
| TAB CONTENT AREA                                                                      |
| - Section A: Appearance & Display (Theme, Density, Timezone, Time Format, Page Size)   |
| - Section B: User & Session Information (Profile, Roles, Permissions, Token Form)    |
| - Section C: Application Configuration (Read-only environment, SOP rules, DLQ limit)  |
| - Section D: Security & Trust Configuration (HMAC provider, Ledger status, WORM stub) |
| - Section E: Integration Configuration (6 adapters, read-only flags, connection stats)|
| - Section F: About & System Information (Version 1.0.0-rc2, Milestone UI-9, Docs)    |
+---------------------------------------------------------------------------------------+
```

---

## 7. Security Risks & Mitigations

| Identified Threat / Risk | Likelihood | Impact | Built-in Mitigation |
|---|---|---|---|
| **Credential Leakage in UI** | Low | Critical | Regex redaction in serializers; zero secret keys or raw token hashes exposed in configuration tabs. |
| **Privilege Escalation** | Low | Critical | Roles and permissions rendered as read-only badges. No role-editing form controls exist. |
| **Token Persistence Risk** | Low | High | Enforced zero-storage rule: token stored only in volatile React memory; never in `localStorage`/`sessionStorage`. |
| **Phantom Mutation Endpoints** | Low | High | All settings API endpoints are strictly `GET` methods. Zero mutation routes. |
| **Insecure Defaults** | Low | Medium | Factory defaults are secure-by-default: dark theme, UTC timezone, 24H military notation, read-only mode. |
| **Misleading Health Status** | Low | Medium | Disconnected components (`enterprise-oidc`, `external-worm-storage`) display `UNKNOWN` / `REFERENCE_ONLY`, never false `HEALTHY`. |

---

## 8. Implementation & Verification Plan

1. **Step 1 — Backend Schema & Router (`src/piis/api/routers/settings.py`):**
   - Implement `SettingsSystemInfoResponse` schema in `schemas.py`.
   - Implement `GET /api/v1/settings/system-info` with `require_permissions(Permission.VIEW_INCIDENTS)`.
   - Register router in `src/piis/api/app.py`.
2. **Step 2 — Frontend Types & API Endpoints:**
   - Add `API_ENDPOINTS.SETTINGS.SYSTEM_INFO` in `frontend/src/api/endpoints.ts`.
   - Add `SettingsSystemInfoResponse` and `DisplayPreferences` types in `frontend/src/api/types.ts`.
3. **Step 3 — Frontend Preferences Context / Hook:**
   - Create a typed `useDisplayPreferences` hook managing `density`, `timezone`, `timeFormat`, `pageSize`, and `refreshInterval` with `localStorage` persistence and factory reset capability.
4. **Step 4 — Implement Full `SettingsPage.tsx`:**
   - Build 6 rich sections (A through F) with genuine data grounding, responsive cards, and zero fake toggles.
5. **Step 5 — Automated Test Suites:**
   - Backend integration tests in `tests/integration/test_ui9_settings.py` (authentication, secret redaction, read-only semantics, schema validation).
   - Frontend Vitest tests in `frontend/src/test/SettingsWorkspace.test.tsx` (tab switching, theme toggle, preference persistence, role read-only protection, reset action).
6. **Step 6 — Browser Verification & Screenshots:**
   - Playwright visual capture script `scripts/capture_ui9_screenshots.py` capturing all 6 tabs in dark and light modes.
7. **Step 7 — Regression Suite & Documentation:**
   - Verify full pytest fleet (592 baseline + UI-9 additions).
   - Verify full Vitest fleet (92 baseline + UI-9 additions).
   - Verify Ruff and ESLint (0 errors).
   - Verify M7 demonstration flow (18/18 stages).
   - Produce `docs/ui/UI9_SETTINGS_WORKSPACE.md` and update `README.md`.
