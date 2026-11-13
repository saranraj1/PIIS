# PIIS: Production Incident Intelligence System (Telecom Edition)

> [!IMPORTANT]
> **Project Release Status: Production Ready (v1.0.0-rc2)**
> - Backend Test Suite: 602 / 602 passing (pytest, 100 percent pass rate)
> - Frontend Test Suite: 102 / 102 passing (vitest, 15 test files, 100 percent pass rate)
> - Total Automated Verification: 704 passing tests
> - Code Quality Gates: Zero Ruff findings (Python), zero ESLint warnings or errors (TypeScript)
> - Operational Mode: Strict read-only decision support for Network Operations Centers (NOC)

---

## 1. Executive Summary and Operational Boundaries

PIIS (Production Incident Intelligence System) is an evidence-grounded decision support platform built specifically for Tier 1 and Tier 2 Network Operations Center (NOC) engineers managing telecommunications infrastructure. The system correlates multi-vendor incident tickets, alarm streams, and high-frequency telemetry to surface probable root causes, rank historical runbooks, and formulate human-verifiable diagnostic recommendations.

### Hardened Architectural Safeguards

- **Strictly Read-Only Operations:** PIIS operates exclusively as an analytical decision-support tool. It has no execution authority, credentials, or network paths to alter network configurations, dispatch commands to network elements, or modify routing tables.
- **Zero Autonomous Ticket Mutation:** Incident tickets in upstream ITSM platforms (ServiceNow, Jira Service Management) are never autonomously closed, resolved, or reassigned by automated routines.
- **Automated Communication Lockout:** PIIS does not emit external or customer-facing notifications.
- **Mandatory Authenticated Human Approval:** Every diagnostic recommendation requires explicit review and cryptographic authorization by an authenticated human operator. Automated service principals are hard-blocked from approving operational recommendations.
- **Cryptographic Auditability:** Human review decisions are canonicalized under RFC 8785 (JSON Canonicalization Scheme) and chained with SHA-256 and HMAC-SHA256 digests into an append-only ledger.

---

## 2. Core Architecture and Intelligence Capabilities

```
+-----------------------------------------------------------------------------------+
|                        Telecom Data Ingestion Layer                               |
|   ServiceNow ITSM  |  Jira SM  |  OSS/NMS Alarms (3GPP)  |  Prometheus / OTLP     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     Unified Ingestion and Normalization                           |
|   SHA-256 Deduplication  |  Dead-Letter Quarantine (DLQ)  |  Canonical Envelopes  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       Multi-Stage Intelligence Engine                             |
|   - Multi-Domain Classifier: RAN, Transport, 5G Core, IMS, and Cloud              |
|   - Telemetry Anomaly Detection: 3-Sigma Z-Score and Isolation Forest             |
|   - Topological Blast Radius: Directed Acyclic Graph (DAG) Traversal              |
|   - Hybrid Retrieval: Okapi BM25 + Dense Bi-Encoder (all-MiniLM-L6-v2)            |
|   - Temporal Grounding: Freshness evaluation and contradictory signal detection   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                      Human Review and Cryptographic Audit                         |
|   - Dual-Operator Review Hub with Mandatory Rationale Verification               |
|   - RFC 8785 JCS Canonicalization and SHA-256 Hash Chaining                       |
|   - Local Checkpoint Monotonic Anchor and Tamper Detection                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    Operations Console (React 19 Single Page App)                  |
|   Command Center | Incident Explorer | Investigation | Network Intelligence       |
|   Human Review Hub | Audit Ledger | Integrations & DLQ | System Health | Settings |
+-----------------------------------------------------------------------------------+
```

### Intelligence Subsystems

1. **Multi-Domain Triage Classifier:** Classifies incidents across five telecom domains (RAN, Transport, 5G Core, IMS, Cloud Infrastructure) and predicts severity levels using class-imbalance-mitigated estimators.
2. **Causal Telemetry Anomaly Detection:** Applies sliding-window statistical evaluators with strict causal indexing to eliminate lookahead leakage.
3. **Alarm Correlation and Blast Radius Mapping:** Correlates 3GPP alarm payloads against topological dependency graphs to calculate blast radius and impacted subscriber counts.
4. **Hybrid Sparse and Dense Evidence Retrieval:** Combines Okapi BM25 lexical indexing with dense semantic embeddings (`all-MiniLM-L6-v2`) filtered by vendor equipment compatibility and software release versions.
5. **Epistemic Classification System:** Every display token, hypothesis, and recommendation is explicitly labeled with one of six epistemic classifications to prevent confirmation bias:
   - `OBSERVED_FACT`: Grounded telemetry, raw alarms, and observed metrics.
   - `MODEL_PREDICTION`: Inferred fault classes and predicted impact scores.
   - `HYPOTHESIS`: Ranked candidate root causes with confidence proxies.
   - `RECOMMENDATION`: Suggested procedural runbook actions.
   - `HUMAN_APPROVED_DECISION`: Explicitly signed human operator actions.
   - `CONFIRMED_ROOT_CAUSE`: Cryptographically finalized root cause findings.

---

## 3. Frontend Workspaces and User Experience

The frontend is a single-page console built with React 19, TypeScript strict mode, Vite, and Tailwind CSS v4. The interface features custom scrollbar styling, sticky headers, high-contrast status tokens, and keyboard-accessible workflows across nine dedicated workspaces:

1. **Command Center (`/`):** High-level operational overview displaying active incidents, domain distribution, healthy subsystem counters, and recent alerts.
2. **Incident Explorer (`/incidents`):** Filterable incident catalog with multi-field search, severity filters, domain grouping, and a slide-over incident detail drawer.
3. **Investigation Workspace (`/investigation`):** Deep investigation workspace showing ranked hypotheses, supporting and contradicting evidence registers, temporal freshness badges, and runbook recommendations.
4. **Network Intelligence (`/network`):** Interactive SVG topology explorer with tiered domain layouts, blast radius calculation, alarm correlation clusters, and time-series anomaly charts.
5. **Human Review Hub (`/human-review`):** Secure approval queue enforcing mandatory reviewer rationale, dual-role separation, and cryptographic receipt generation.
6. **Audit and Provenance Ledger (`/audit`):** Append-only audit record explorer with on-demand SHA-256 verification, RFC 8785 canonical hash checking, and sequence gap detection.
7. **Integrations and DLQ (`/integrations`):** Protocol adapter registry (ServiceNow, Jira, Prometheus, OSS/NMS), 8-stage data flow topology, live event stream, and Dead-Letter Quarantine inspection.
8. **System Health and Operations (`/health`):** Component health registry monitoring 17 internal subsystems with criticality-aware evaluation and uninstrumented component disclosures.
9. **Settings and Configuration (`/settings`):** Operator preferences (theme, density, timezone, page size, telemetry refresh interval), in-memory zero-persistence JWT token management, operational boundary monitors, and documentation catalog.

---

## 4. Repository Structure

```
PIIS/
├── configs/                   # System and adapter configuration profiles
├── data/                      # Canonical data definitions, schemas, and fixtures
│   ├── canonical/             # Standardized telecom event schemas
│   └── evaluation/            # Benchmark datasets and evaluation ground truth
├── docs/                      # Technical documentation, architecture ADRs, and audits
│   ├── api/                   # REST API documentation
│   ├── architecture/          # Architecture Decision Records (ADR 0001 to ADR 0018)
│   ├── m7/                    # Portfolio release notes and deployment guides
│   └── ui/                    # Workspace specifications and independent verification audits
├── frontend/                  # React 19 + TypeScript + Vite + Tailwind CSS v4 application
│   ├── src/
│   │   ├── api/               # Typed API clients, endpoints, and TanStack queries
│   │   ├── components/        # UI components, layout shell, drawers, and modal dialogs
│   │   ├── context/           # In-memory authentication, theme, and shared UI state
│   │   ├── pages/             # 9 primary workspace page components
│   │   └── test/              # 15 Vitest component and workspace test suites (102 tests)
│   ├── package.json           # Frontend dependency manifest
│   └── vite.config.ts         # Vite build configuration with API reverse proxy
├── models/                    # Trained model weights and metadata cards
├── schemas/                   # Authoritative JSON Schemas for telecom entities
├── scripts/                   # Operations, bootstrapping, and demonstration scripts
├── src/piis/                  # Core Python backend package
│   ├── anomaly/               # Statistical anomaly detection routines
│   ├── api/                   # FastAPI application, routers, schemas, and middleware
│   ├── audit/                 # RFC 8785 canonicalization, hash chaining, and checkpoint anchors
│   ├── auth/                  # RBAC, JWT verification, and test OIDC providers
│   ├── correlation/           # Topological graph correlation and blast radius algorithms
│   ├── data/                  # Schema validators, entity normalizers, and profiling tools
│   ├── features/              # Feature extractors and sliding-window aggregators
│   ├── integrations/          # ServiceNow, Jira, Prometheus, and OSS/NMS adapters
│   ├── investigation/         # Multi-stage investigation engine and human review workflow
│   ├── knowledge/             # Telecom SOP catalog and runbook embeddings
│   ├── models/                # Domain classification and severity estimators
│   ├── observability/         # Prometheus metrics, OpenTelemetry tracing, and JSON logging
│   ├── pipeline/              # Ingestion pipeline, deduplication cache, and DLQ quarantine
│   ├── retrieval/             # BM25 and dense bi-encoder retrieval engines
│   └── security/              # 4-ring input sanitization and execution guards
└── tests/                     # Backend test suites (602 pytest tests)
    ├── unit/                  # Unit tests for individual algorithms and components
    ├── integration/           # Subsystem integration and API endpoint tests
    └── adversarial/           # Security, tamper detection, and injection resistance tests
```

---

## 5. Getting Started and Local Setup

### Prerequisites

- Python 3.11 or later
- Node.js 20 or later with npm
- Git

### Backend Setup

```bash
# 1. Clone repository
git clone https://github.com/saranraj1/PIIS.git
cd PIIS

# 2. Create and activate a Python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements-lock.txt

# 4. Set required environment variables
copy .env.example .env
# Set audit signing key for local execution:
set PIIS_AUDIT_HMAC_KEY=4a8f9c0e2b1d3f5a7e6c8b0d2e4f6a8c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9d1f

# 5. Start the FastAPI backend server
python -m uvicorn piis.api.app:app --host 127.0.0.1 --port 8000
```

The backend server initializes on `http://127.0.0.1:8000` and automatically bootstraps canonical telecom demonstration data (incidents, alarms, telemetry samples, and pending human review items).

### Frontend Setup

```bash
# In a separate terminal window:
cd frontend

# 1. Install frontend dependencies
npm install

# 2. Run TypeScript strict typecheck
npm run typecheck

# 3. Start the Vite development server
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` in your browser. All API requests to `/api` are automatically proxied to the backend at `http://127.0.0.1:8000`.

---

## 6. Authentication and Operator Access

PIIS enforces in-memory JWT authentication. Tokens are stored exclusively in React component memory and are never persisted to `localStorage` or `sessionStorage` to mitigate cross-site script theft.

### Minting a Development Token

To access protected endpoints or use the UI, generate a local token with administrative or operator privileges:

```bash
python -c "from piis.auth import AuthManager, ApplicationRole; token = AuthManager().mint_dev_token('noc-operator-01', ApplicationRole.PIIS_ADMIN); print(token)"
```

In the web interface:
1. Click the **Set Bearer Token** button in the top navigation bar.
2. Paste the generated token.
3. The session state updates to authenticated status, unlocking the full workspace.

---

## 7. Quality and Verification Verification Suite

### Frontend Verification

```bash
cd frontend

# Run all 102 unit, component, and workspace tests
npm test

# Run ESLint (must return zero errors and zero warnings)
npm run lint

# Compile production bundle
npm run build
```

### Backend Verification

```bash
# Run complete test suite (602 tests)
pytest

# Verify code formatting and linting
ruff check .

# Run self-contained demonstration flow
python scripts/demonstrate_m7_portfolio_flow.py
```

### Verification Results Summary

| Test Domain | Runner | Test Files | Total Tests | Pass Rate | Code Quality |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Backend Suite** | `pytest` | 56 | 602 | 100 percent | 0 Ruff violations |
| **Frontend Suite** | `vitest` | 15 | 102 | 100 percent | 0 ESLint warnings |
| **Complete System** | Consolidated | 71 | 704 | 100 percent | Strict type checking clean |

---

## 8. REST API Reference Overview

Base path: `/api/v1`

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Settings** | `GET` | `/api/v1/settings/system-info` | System metadata, operational boundaries, and documentation catalog. |
| **Settings** | `GET` | `/api/v1/settings/preferences-defaults` | NOC standard default display preferences. |
| **Incidents** | `GET` | `/api/v1/incidents` | List incidents with filtering by domain, severity, and resolution status. |
| **Incidents** | `GET` | `/api/v1/incidents/{incident_id}` | Retrieve comprehensive incident record. |
| **Investigation** | `GET` | `/api/v1/incidents/{incident_id}/investigation` | Fetch synthesized evidence, ranked hypotheses, and recommendations. |
| **Investigation** | `POST` | `/api/v1/incidents/{incident_id}/investigate` | Trigger investigation execution engine on an unanalyzed incident. |
| **Human Review** | `GET` | `/api/v1/review/queue` | List pending recommendations requiring human operator validation. |
| **Human Review** | `POST` | `/api/v1/review/approve` | Authenticated human approval with mandatory review rationale notes. |
| **Human Review** | `POST` | `/api/v1/review/reject` | Authenticated human rejection with required rationale notes. |
| **Audit Ledger** | `GET` | `/api/v1/audit/records` | Paginated append-only audit records with filtering and cursor pagination. |
| **Audit Ledger** | `POST` | `/api/v1/audit/verify` | Execute full cryptographic verification across ledger chain. |
| **Network Intel** | `GET` | `/api/v1/network/topology` | Topology graph with nodes, directional edges, and domain metadata. |
| **Network Intel** | `GET` | `/api/v1/network/elements/{element_id}/impact` | Directed graph blast radius and affected subscriber metrics. |
| **System Health** | `GET` | `/api/v1/system-health/overview` | Subsystem counts, aggregate health status, and readiness indicators. |
| **System Health** | `GET` | `/api/v1/system-health/components` | Detailed health states and diagnostic probes for all 17 subsystems. |
| **Integrations** | `GET` | `/api/v1/integrations/adapters` | List registered protocol adapters and configurations. |
| **Integrations** | `GET` | `/api/v1/integrations/activity` | Paginated integration event stream. |
| **Integrations** | `GET` | `/api/v1/integrations/dlq` | Dead-Letter Quarantine inspection and replay management. |

Full OpenAPI documentation is interactively accessible at `http://127.0.0.1:8000/docs` when the backend is running.

---

## 9. License and Governance

PIIS is provided for research, evaluation, and operational decision support under the Apache 2.0 License. It is strictly configured as read-only decision support and must not be connected to autonomous network mutation tooling without authorized human oversight.
