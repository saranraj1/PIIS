# PIIS UI-1 Authentication & Security Architecture Decision Record

**Milestone:** UI-1  
**Status:** ACCEPTED & ENFORCED  
**Security Boundary:** Volatile In-Memory Client Session + Server-Side RBAC Enforcement  

---

## 1. Context & Threat Model

The Production Incident Intelligence System (PIIS) operates in high-criticality telecom environments (NOC tier 1-3 operations). The frontend user interface provides incident discovery, root-cause reasoning, and human-in-the-loop review capabilities.

### Identified Client-Side Risks:
1. **Persistent Token Exfiltration:** Tokens stored in `localStorage` or `sessionStorage` persist across sessions and are vulnerable to malicious browser extensions, script injection (XSS), or physical device compromise.
2. **Client-Side Authorization Spoofing:** Naive SPAs often treat client-side role checks as security boundaries, allowing attackers to manipulate local state to gain administrative capabilities.
3. **Session Hijacking in Shared NOC Terminals:** Operators frequently share workstation terminals during shift handoffs. Stored credentials risk unintended session persistence.

---

## 2. Core Security Decisions

### Decision 1: Zero-Persistence In-Memory Bearer Token Management
- **Rule:** The JWT Bearer token is stored **exclusively in volatile React component state** (`AuthContext.tsx`).
- **Enforcement:**
  - `localStorage.setItem('token', ...)` is strictly prohibited.
  - `sessionStorage.setItem('token', ...)` is strictly prohibited.
  - Closing, navigating away from, or refreshing the browser tab immediately purges credentials from memory.
  - Automated unit test `src/test/AuthContext.test.tsx` explicitly asserts that neither `localStorage` nor `sessionStorage` contain token keys after login.

### Decision 2: The Frontend is Never an Authorization Boundary
- **Rule:** Client-side role and permission checks exist purely for UI affordance (e.g., disabling a button, hiding irrelevant controls).
- **Enforcement:**
  - The FastAPI backend is the sole authority for identity authentication, token cryptographic signature verification, role-based access control (RBAC), and dual-operator signing workflows.
  - An unauthorized user tampering with client state will receive `401 Unauthorized` or `403 Forbidden` from the backend API, properly handled by `ApiClientError`.

### Decision 3: Safe Client-Side Claims Inspection
- **Rule:** The frontend decodes the base64 URL-safe payload of the JWT solely to render informational UI elements (e.g., operator ID pill, assigned roles).
- **Enforcement:**
  - Payload parsing is defensive and wrapped in a try/catch block.
  - If a token is malformed, the client immediately treats the session as anonymous and reports an error.

### Decision 4: Non-Sensitive Theme Preference Persistence
- **Rule:** Only non-sensitive visual configuration (specifically `piis_theme_preference` with values `'dark'` or `'light'`) may be saved to `localStorage`.
- **Enforcement:**
  - Stored preferences contain zero user identifiers, tokens, or operational telemetry.

---

## 3. Communication & Proxy Architecture

During development, the React frontend runs on Vite (`http://localhost:5173`) while the FastAPI backend runs on `http://127.0.0.1:8000`.
To eliminate cross-origin configuration friction and avoid opening CORS headers indiscriminately:
- Vite's development server proxies all `/api` and `/metrics` requests to `http://127.0.0.1:8000`.
- The Bearer token header (`Authorization: Bearer <token>`) is transparently forwarded to FastAPI.
- In production, the built static SPA assets (`dist/`) are served directly behind a reverse proxy (e.g. NGINX) or static file mount alongside the API routes.

---

## 4. Verification Evidence

- `frontend/src/test/AuthContext.test.tsx`:
  - `initializes in anonymous read-only unauthenticated state` -> PASS
  - `decodes JWT claims in memory without writing to localStorage or sessionStorage` -> PASS
  - `purges memory token and claims completely on logout` -> PASS
- `frontend/src/test/ApiClient.test.tsx`:
  - `injects Bearer token when tokenProvider is configured` -> PASS
  - `throws ApiClientError with status code and details on non-ok response` -> PASS
