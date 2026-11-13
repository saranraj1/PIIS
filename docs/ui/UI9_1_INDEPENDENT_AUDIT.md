# PIIS UI-9.1 — Independent Settings, Security & Regression Integrity Audit Report

**Auditor:** Independent Principal Full-Stack Engineer, Security Engineer, Backend Architect & Verification Auditor  
**Subsystem:** Production Incident Intelligence System (PIIS — Telecom Edition)  
**Target Milestone:** UI-9 Settings & Configuration Workspace  
**Audit Milestone:** UI-9.1 Independent Adversarial Audit & Final Milestone Freeze  
**Execution Type:** Documentation-Only Correction & Final Project Closure  
**Audit Date:** November 5, 2026  
**Final Audit Verdict:** **ACCEPTED WITH LIMITATIONS**  
**Operational Security Level:** STRICTLY READ-ONLY DECISION SUPPORT — PORTFOLIO EDITION  
**Final Phase Status:** UI-9 IS THE FINAL PROJECT PHASE. ALL MILESTONES FROZEN. NO UI-10 AUTHORIZED.  

---

## 1. Executive Summary & Final Verdict

### 1.1 Formal Verdict: ACCEPTED WITH LIMITATIONS

Following an independent verification across the codebase, runtime execution paths, failure-injection tests, frontend interface, and architectural claims of UI-9, the Settings & Configuration Workspace is formally graded **ACCEPTED WITH LIMITATIONS**.

The verdict is governed by the core PIIS principles:
> **EVIDENCE BEFORE INTELLIGENCE. INTELLIGENCE BEFORE AUTOMATION.**  
> **OPERATIONAL VISIBILITY WITHOUT OPERATIONAL EXECUTION AUTHORITY.**  
> **CONFIGURATION WITHOUT UNVERIFIED STATE MUTATION.**  
> **EXISTING TELECOM WORKFLOW + PIIS = ADDITIONAL OBSERVABILITY, INTEGRITY AND PROVENANCE.**

UI-9 delivers an operator-grade, six-tabbed settings console (`/settings`) that provides centralized visibility into application metadata, in-memory operator sessions, locked operational boundaries, security postures, adapter configurations, and documentation catalog items. All backend settings endpoints enforce authentication, rejection of mutative HTTP methods (HTTP 405), zero credential leakage in tested responses, zero subprocess execution in tested scenarios, and zero outbound socket connections in tested scenarios.

### 1.2 Summary of Limitations
The workspace is accepted for portfolio demonstration and decision-support environments subject to four explicit, documented operational limitations:

1. **Client-Side Display Preference Scope:**
   Display preferences (`density`, `timezone`, `time_format`, `page_size`, `refresh_interval`) are managed via Zustand (`displayPreferencesStore`) and persisted locally in the browser's `localStorage`. While `theme` mode, interface `density`, and catalog `page_size` are fully propagated to active UI styling and query initialization, `timezone`, `time_format`, and `refresh_interval` are stored in state but are not currently consumed by all legacy views (such as Investigation timeline events and Audit Ledger records, which continue to render standard UTC ISO-8601 strings).
2. **Volatile In-Memory Token Lifecycle:**
   Operator authentication tokens reside exclusively in React volatile state (`AuthContext.tsx`). There is zero persistence to `localStorage`, `sessionStorage`, `IndexedDB`, or cookies. Refreshing the browser or opening a new tab completely clears the active session and reverts the operator to unauthenticated or dev-fallback state.
3. **Authoritative Static Configuration Boundary:**
   The six operational boundary flags (`network_mutations_allowed: false`, `production_commands_allowed: false`, etc.) returned by `GET /api/v1/settings/system-info` are backed by code-level architectural controls (absence of mutative endpoints, read-only adapter contracts, prohibition of subprocess calls in tested paths), but are returned from an authoritative static configuration dictionary rather than dynamic hardware attestation or live kernel probes.
4. **Simulated Enterprise Integration Registry:**
   Adapter configurations displayed in the Settings workspace reflect locally simulated and verified telecom adapters (`SNOW-ITSM-01`, `JIRA-ITSM-01`, `PROM-TELEM-01`, `OTLP-TELEM-01`, `OSS-ALARM-01`, `REST-ITSM-01`) with zero live enterprise cloud access or production mutations.

---

## 2. Scope and Audit Methodology

### 2.1 Scope of Audit
The audit inspected the actual physical implementation of the UI-9 milestone, encompassing:
- **Backend Settings API:** [`src/piis/api/routers/settings.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/api/routers/settings.py), [`src/piis/api/schemas.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/api/schemas.py), and [`src/piis/api/app.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/api/app.py).
- **Frontend Workspace & State:** [`frontend/src/pages/SettingsPage.tsx`](file:///c:/Production%20level%20projects/PIIS/frontend/src/pages/SettingsPage.tsx), [`frontend/src/store/displayPreferencesStore.ts`](file:///c:/Production%20level%20projects/PIIS/frontend/src/store/displayPreferencesStore.ts), [`frontend/src/store/incidentContextStore.ts`](file:///c:/Production%20level%20projects/PIIS/frontend/src/store/incidentContextStore.ts), [`frontend/src/theme/ThemeContext.tsx`](file:///c:/Production%20level%20projects/PIIS/frontend/src/theme/ThemeContext.tsx), and [`frontend/src/index.css`](file:///c:/Production%20level%20projects/PIIS/frontend/src/index.css).
- **Integration & Unit Tests:** [`tests/integration/test_ui9_settings.py`](file:///c:/Production%20level%20projects/PIIS/tests/integration/test_ui9_settings.py) and [`frontend/src/test/SettingsWorkspace.test.tsx`](file:///c:/Production%20level%20projects/PIIS/frontend/src/test/SettingsWorkspace.test.tsx).
- **Visual Artifacts:** 8 high-resolution Playwright screenshot captures in [`docs/ui/screenshots/`](file:///c:/Production%20level%20projects/PIIS/docs/ui/screenshots/).

### 2.2 Audit Methodology & Epistemic Boundaries
Every conclusion in this audit distinguishes between:
1. **Inspected repository code paths:** Direct static review of physical Python and TypeScript sources.
2. **Directly tested execution scenarios:** Scenarios asserted and verified by automated integration test cases.
3. **Identified architectural controls:** Design constraints enforced by code structure (e.g. read-only abstract base classes, absence of mutation routes).
4. **Capabilities not independently established:** Scenarios where limited test instrumentation (such as mocking a single function) does not constitute universal proof.

---

## 3. Six-Preference Propagation Matrix

The audit evaluated how each of the six client-side preferences is declared, persisted, and propagated across the application. The audit explicitly distinguishes between preferences that are **fully propagated** versus those that are **persisted but not globally consumed**:

| Preference | Storage Key | Allowed Values | NOC Factory Default | Storage Target | Runtime Propagation Status | Verified Scope & Evidence |
|---|---|---|---|---|---|---|
| **Theme Mode** | `piis_theme_preference` | `dark`, `light`, `system` | `dark` | `localStorage` | **Fully Propagated** | Handled in `ThemeContext.tsx`. Toggles `.dark` class and `data-theme` attribute on `<html>`. Toggles CSS design tokens application-wide. Verified across all views. |
| **Interface Density** | `piis_display_density` | `comfortable`, `compact` | `comfortable` | `localStorage` | **Fully Propagated** | Stored in `displayPreferencesStore.ts`. Sets `data-density` attribute on `<html>`. Applies table cell padding overrides via `[data-density="compact"]` in `index.css`. Verified. |
| **Incident Page Size** | `piis_page_size` | `10`, `25`, `50` | `25` | `localStorage` | **Fully Propagated** | Stored in `localStorage`. Consumed by `useIncidentContextStore.getInitialPageLimit()` to initialize the Incident Explorer pagination query limit. Verified. |
| **Timezone Mode** | `piis_timezone_preference` | `UTC`, `LOCAL` | `UTC` | `localStorage` | **Persisted but Not Globally Consumed** | Stored in Zustand state and persisted to `localStorage`. Consumed within the Settings workspace. Legacy views (Investigation timeline, Audit records) render authoritative UTC ISO-8601 strings and do not parse this preference. |
| **Time Format** | `piis_time_format` | `24H`, `12H` | `24H` | `localStorage` | **Persisted but Not Globally Consumed** | Stored in Zustand state and persisted to `localStorage`. Consumed within the Settings workspace. Legacy views use standard 24-hour ISO strings and do not dynamically reformat. |
| **Auto-Refresh Interval** | `piis_refresh_interval` | `OFF`, `15s`, `30s`, `60s` | `30s` | `localStorage` | **Persisted but Not Globally Consumed** | Stored in Zustand state and persisted to `localStorage`. Consumed within the Settings workspace. Legacy telemetry views utilize component-level polling queries and do not bind to this setting. |

> [!NOTE]
> Preferences classified as **Persisted but Not Globally Consumed** are safely stored and persisted, but do not currently control legacy components. In accordance with strict audit boundaries, no runtime consumer was claimed where none exists, and no new consumers were implemented during this audit.

---

## 4. Authentication and Token Lifecycle Findings

### 4.1 In-Memory Volatile Security Boundary
- The operator token is managed exclusively through React state inside `frontend/src/auth/AuthContext.tsx`.
- Adversarial code inspection confirmed **ZERO** calls to `localStorage.setItem('token', ...)`, `sessionStorage.setItem('token', ...)`, `document.cookie`, or IndexedDB.
- When an operator clicks **"Purge Memory Session"** or clears the token input, `clearToken()` is invoked, immediately destroying the Bearer JWT in memory and resetting `principal` to `null`.
- On browser reload, memory state is discarded, enforcing a secure fail-closed posture suitable for shared NOC workstations.

### 4.2 Non-Human Lockout Enforcement
- The backend metadata endpoint explicitly returns `service_principals_barred: true`.
- Tokens minted with `is_service=True` (e.g. `SVC-SNOW-POLLER`) are barred from human approvals in `src/piis/investigation/approval.py:approve_recommendation`, returning HTTP 403 Forbidden:
  > *"Token subject belongs to a service principal workload identity, not a human operator. Automated service accounts and bots are strictly prohibited from approving diagnostic recommendations."*

### 4.3 Bearer Token Visibility & Security-Hardening Recommendation
- The token input in `SettingsPage.tsx` currently renders an unmasked `<textarea>` displaying the active Bearer JWT in plaintext.
- Because operator tokens in the portfolio edition are ephemeral, locally minted test JWTs without embedded passwords or private keys, displaying the encoded JWT allows operators to inspect token headers and claims.
- **Security-Hardening Recommendation (Recorded as DEF-UI9-003, Severity P3):**
  For enterprise hardening beyond the portfolio edition, the recommended future security posture is:
  1. Mask the token by default (e.g. display bullet mask `••••••••`).
  2. Provide an explicit, temporary "reveal" toggle.
  3. Preserve the existing in-memory purge operation.
  4. Never persist tokens in browser storage (`localStorage`, `sessionStorage`, cookies).
  5. Never log tokens or expose them through URLs.
- In accordance with documentation-only execution rules, this change is recorded as a recommendation and was not implemented in application code during this audit.

---

## 5. Operational Boundary Verification Matrix

The six operational boundary flags exposed by `GET /api/v1/settings/system-info` were inspected against physical repository paths, tested execution scenarios, and architectural controls:

| Boundary Claim | Reported Value | Inspected Repository Paths | Directly Tested Execution Scenarios | Architectural Controls Identified | Capabilities Not Independently Established |
|---|---|---|---|---|---|
| `network_mutations_allowed` | `false` | `src/piis/integrations/base.py`, `src/piis/api/routers/` | Verified that API route inventory contains zero network configuration or write endpoints. | Adapter base class `TelecomAdapterBase` enforces `MUTATION_ALLOWED=False` and restricts HTTP methods to `GET` and `HEAD`. | Does not prove external carrier systems in a production deployment are incapable of mutation if external credentials were supplied. Verified within inspected repository paths. |
| `production_commands_allowed` | `false` | `src/piis/security/guard.py`, `tests/integration/test_ui9_settings.py` | `test_settings_zero_subprocess_execution` verifies `subprocess.Popen` is not invoked during settings requests. | No SSH, Telnet, NETCONF, or shell execution modules exist in `src/piis/`. `ToolExecutionGuard` enforces read-only tool gating. | Patching `subprocess.Popen` verifies tested execution paths do not call `Popen`, but does not prove every low-level OS process creation mechanism is unavailable. Verified within tested scenarios. |
| `ticket_closures_allowed` | `false` | `src/piis/integrations/itsm/` | Verified that ITSM adapters implement only `read_incidents()` and `get_incident()`. | Absence of ticket update, transition, resolution, or closure methods in ITSM adapter contracts. | Does not establish behavior of external live ServiceNow/Jira instances if configured outside portfolio simulation. Verified within inspected repository code. |
| `external_egress_allowed` | `false` | `tests/integration/test_ui9_settings.py` | `test_settings_zero_external_network_egress` verifies `socket.create_connection` is not invoked during settings requests. | All settings endpoints resolve locally from memory and static metadata without external HTTP client calls. | Patching `socket.create_connection` verifies tested settings requests do not open standard sockets, but does not prove every possible networking call is impossible. Verified within tested scenarios. |
| `autonomous_remediation_allowed` | `false` | `src/piis/investigation/approval.py`, `src/piis/investigation/engine.py` | Verified in M7 flow stages 13–15: recommendations remain in `PENDING_REVIEW` until authenticated human sign-off. | Automated daemons are barred (HTTP 403); approvals require HMAC-SHA256 signature from human operator. | Does not prove that external downstream automation systems could not act on read-only recommendations independently. Verified within system boundary. |
| `secret_exposure_allowed` | `false` | `src/piis/api/routers/settings.py`, `tests/integration/test_ui9_settings.py` | `test_settings_secret_redaction` scans responses with regex patterns for RSA private keys, PEM headers, and API keys. | HMAC signing keys are sanitized to `"[HMAC-SHA256 REDACTED]"`; sensitive credentials excluded from schemas. | Regex scanning of tested payloads confirms absence of detected key patterns, but does not constitute formal mathematical information-theoretic leakage proof. Verified within tested execution payloads. |

> [!IMPORTANT]
> All six operational boundaries are **verified within the inspected repository paths and tested execution scenarios**. They represent architectural and contractual guarantees of the PIIS codebase, not dynamic kernel or hardware attestation proofs.

---

## 6. Backend API Immutability Findings

Adversarial testing in [`tests/integration/test_ui9_settings.py`](file:///c:/Production%20level%20projects/PIIS/tests/integration/test_ui9_settings.py) verified the following immutability and security invariants:

1. **Authentication Enforcement:**
   - Both `/api/v1/settings/system-info` and `/api/v1/settings/preferences-defaults` reject unauthenticated requests lacking Bearer authorization with **HTTP 401 Unauthorized**.
2. **Immutability & Method Protection:**
   - All mutative HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) against settings endpoints return **HTTP 405 Method Not Allowed**. Settings cannot be mutated via API.
3. **Secret Redaction:**
   - Responses were scanned with regex patterns for RSA private keys, PEM headers, live JWT signatures, and API key tokens. Zero credentials leaked in tested payloads.
4. **Idempotency & Zero Side-Effects:**
   - Repeated GET requests to settings endpoints produced identical responses with zero state changes or cache corruption.
5. **Subprocess & Egress Isolation:**
   - Settings requests triggered zero calls to `subprocess.Popen` and zero calls to `socket.create_connection` in tested scenarios.

---

## 7. Service-Principal Restrictions

The audit verified non-human identity restrictions enforced by the authentication subsystem:

1. **Metadata Disclosure:**
   - The `/api/v1/settings/system-info` endpoint explicitly discloses `service_principals_barred: true`.
2. **Workload Identity Detection:**
   - The JWT verifier in `AuthManager` extracts `principal_type` and `is_service` claims from the token payload.
3. **Enforcement Gate:**
   - When a service account (such as `SVC-SNOW-POLLER` or `snow_poller_daemon`) attempts to call `POST /api/v1/incidents/{id}/reviews`, the operation fails closed with **HTTP 403 Forbidden**.
4. **Epistemic Justification:**
   - Telecom incident diagnosis requires human accountability. AI systems propose candidate hypotheses and read-only runbook actions; deterministic systems constrain them; only certified human operators possess legal sign-off authority.

---

## 8. Historical Regression Reconciliation

The test fleet was reconciled against the baseline frozen at UI-8.1:

| Subsystem | UI-8.1 Baseline | UI-9 / UI-9.1 Current | Net Delta | Reconciliation Finding |
|---|---:|---:|---:|---|
| **Backend Test Files** | 71 files | 72 files | +1 file | Added `tests/integration/test_ui9_settings.py` |
| **Backend Tests** | 592 tests | 602 tests | +10 tests | 10 integration tests in `test_ui9_settings.py` |
| **Frontend Test Files** | 14 files | 15 files | +1 file | Added `frontend/src/test/SettingsWorkspace.test.tsx` |
| **Frontend Tests** | 92 tests | 102 tests | +10 tests | 10 Vitest tests in `SettingsWorkspace.test.tsx` |
| **Total Test Fleet** | **684 tests** | **704 tests** | **+20 tests** | **All current test suites passed** |

### Regression & Assertion-Preservation Distinction:
- **Current test-suite execution success:** Confirmed. All 704 automated tests (602 backend + 102 frontend) currently execute and pass with zero failures.
- **Historical test-file comparison:** Confirmed. Exactly one backend test file and one frontend test file were added, matching the 20 new tests.
- **Assertion-preservation verification:**  
  *All current test suites passed. Historical assertion preservation was not independently established through complete file-level baseline reconciliation.*

---

## 9. Defect Register

| Defect ID | Severity | Description | Status | Classification & Mitigation |
|---|---|---|---|---|
| **DEF-UI9-001** | P2 | Legacy table views (Investigation timeline, Audit records) render UTC ISO strings rather than consuming client timezone preference. | DOCUMENTED LIMITATION | Preserved for audit precision; core audit logs require unambiguous UTC timestamps. |
| **DEF-UI9-002** | P2 | Telemetry polling queries in legacy views use hardcoded intervals rather than consuming `piis_refresh_interval`. | DOCUMENTED LIMITATION | Preference is safely persisted in Zustand store for future telemetry consumer components. |
| **DEF-UI9-003** | P3 | Token textarea displays plaintext Bearer JWT without default masking. | SECURITY-HARDENING RECOMMENDATION | Recommended future posture: mask by default with temporary reveal toggle. Documented as P3 UX recommendation. |

*Total Defects: 0 P0, 0 P1, 2 P2 (Documented Limitations), 1 P3 (Security-Hardening Recommendation).*

---

## 10. Test Execution Evidence

Recorded automated verification results from the execution environment:

```text
================================================================================
1. Python Code Quality (Ruff)
Command: ruff check src tests scripts
Output:  All checks passed! (0 errors across entire repository)

2. Backend Test Fleet (Pytest)
Command: pytest
Output:  602 passed, 2 warnings in 106.76s (72 test files)

3. Frontend Code Quality (ESLint)
Command: npm --prefix frontend run lint
Output:  0 errors, 0 warnings

4. Frontend Test Fleet (Vitest)
Command: npm --prefix frontend test -- --run
Output:  15 test files passed (15/15)
         102 tests passed (102/102) in 25.85s

5. TypeScript & Vite Production Build
Command: npm --prefix frontend run build
Output:  tsc --noEmit && vite build -> built in 2.00s (0 errors)

6. M7 Portfolio Demonstration Flow
Command: python scripts/demonstrate_m7_portfolio_flow.py
Output:  ALL 18 DEMO STAGES PASSED [OK] in 17.72s (<60s target)
================================================================================
```

*Note: In compliance with documentation-only execution boundaries, tests were not rerun unnecessarily during this documentation correction, as application code and tests remained completely untouched.*

---

## 11. Explicit Limitations and Unverified Claims

1. **Portfolio Boundary:** PIIS does not connect to live external ServiceNow, Jira, or cloud monitoring instances; all adapters use local simulators or reference data.
2. **Volatile Session:** All authentication is in-memory; browser refreshes require re-entering the operator token or using the dev fallback.
3. **Static Configuration Declarations:** Operational boundary flags reflect authoritative static configuration and code constraints, not dynamic hardware or kernel attestation proofs.
4. **Local Trust Boundary:** HMAC verification uses `LocalDevKeyProvider` with documented warning disclaimers.
5. **No Universal Egress/Subprocess Proof:** Mock-based test passes verify absence of calls in tested scenarios, but do not prove impossibility under every conceivable OS-level mechanism.
6. **Production Pilot Blocked:** Production deployment remains blocked pending live enterprise prerequisites (`DEP-M5.3-001`, `DEP-M5.3-002`, `DEP-M5.5.1-001a`, `DEP-M5.5.1-001b`).

---

## 12. Final Project Closure Declaration

### Milestone Acceptance & Final Status:
- **UI-9 Implementation:** COMPLETED.
- **UI-9.1 Independent Audit:** COMPLETED.
- **UI-9 Final Verdict:** ACCEPTED WITH LIMITATIONS.
- **UI-9.1 Final Verdict:** ACCEPTED WITH LIMITATIONS.
- **UI-9 is the final project phase.**
- **All previous milestones remain frozen.**
- **No additional UI milestone is planned or authorized.**
- **No production deployment or production pilot is authorized.**

---

### Verbatim Final Project Declaration

> **PIIS — Telecom Edition has completed its authorized development scope through UI-9. UI-9 is the final project phase. All milestones are frozen, the final audit limitations are documented, and no further development phase is authorized. The system remains a read-only portfolio demonstration and is not approved for production deployment.**
