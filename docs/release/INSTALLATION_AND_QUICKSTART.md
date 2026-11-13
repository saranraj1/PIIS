# PIIS — Installation & Quickstart Guide

This guide walks an engineer through installing, configuring, running, and testing the Production Incident Intelligence System (PIIS) on a local workstation.

---

## 1. Prerequisites & Environment Compatibility

### Mandatory Prerequisites
- **Python:** Python `>= 3.11` (`3.11.5` recommended)
- **Git:** Git `>= 2.40`
- **Operating System:**
  - Windows 10/11 (PowerShell 5.1 or PowerShell Core 7+)
  - Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9)
  - macOS (Ventura 13+ / Sonoma 14+)

### Optional Prerequisites (Enterprise Integrations)
- **OpenTelemetry Collector:** Local or remote OTLP collector listening on gRPC port `4317` (e.g. Jaeger, OpenTelemetry Collector). If unavailable, PIIS fails safely in-process.
- **Docker & Docker Compose:** Docker Engine `>= 24.0` for containerized execution.

---

## 2. Installation Steps

### Step 2.1: Clone the Repository

**Windows PowerShell:**
```powershell
git clone https://github.com/telecom-intelligence/piis.git
cd piis
```

**Linux / macOS Bash:**
```bash
git clone https://github.com/telecom-intelligence/piis.git
cd piis
```

---

### Step 2.2: Create and Activate a Python Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If script execution is disabled in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

**Linux / macOS Bash:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 2.3: Install Dependencies

PIIS defines optional dependency groups for modular installation:
- `api`: FastAPI & Uvicorn application server
- `observability`: OpenTelemetry SDK & OTLP gRPC export
- `retrieval`: Hybrid RAG and sentence embeddings
- `dev`: Pytest test harness and Ruff linter

Install all components in editable mode:

**Windows PowerShell & Linux/macOS:**
```bash
pip install --upgrade pip
pip install -e ".[api,observability,retrieval,dev]"
```

---

## 3. Configuration & Environment Variables

Configure required application settings. For local development, secure defaults are provided:

**Windows PowerShell:**
```powershell
$env:PIIS_ENV = "development"
$env:PIIS_PORT = "8000"
$env:PIIS_LOG_LEVEL = "INFO"
$env:PIIS_AUDIT_SIGNING_KEY = "local-dev-audit-key-32bytes-minimum!"
# Optional: Remote OpenTelemetry Collector Endpoint
# $env:OTEL_EXPORTER_OTLP_ENDPOINT = "127.0.0.1:4317"
```

**Linux / macOS Bash:**
```bash
export PIIS_ENV="development"
export PIIS_PORT="8000"
export PIIS_LOG_LEVEL="INFO"
export PIIS_AUDIT_SIGNING_KEY="local-dev-audit-key-32bytes-minimum!"
# Optional: Remote OpenTelemetry Collector Endpoint
# export OTEL_EXPORTER_OTLP_ENDPOINT="127.0.0.1:4317"
```

| Variable Name | Required? | Default | Description |
| :--- | :---: | :---: | :--- |
| `PIIS_ENV` | Optional | `development` | Environment mode (`development` or `production`). |
| `PIIS_PORT` | Optional | `8000` | Port for the Uvicorn web server. |
| `PIIS_LOG_LEVEL` | Optional | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `PIIS_AUDIT_SIGNING_KEY` | Recommended | Built-in Dev Key | HMAC-SHA256 key ($\ge 32$ bytes) for audit ledger signing. |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| Optional | None | Remote OTLP gRPC collector target (e.g., `127.0.0.1:4317`). |

---

## 4. Local Storage Initialization

PIIS operates without external relational database dependencies for development and standalone operation. Ingestion state, deduplication keys, dead-letter items, and the RFC 8785 audit ledger are persisted in append-only JSONL files under `data/`:

Directories are initialized automatically on startup:
- `data/dedup/`: Ingestion deduplication keys
- `data/dlq/`: Dead-letter queue envelopes
- `data/ledger/`: Tamper-evident cryptographic audit ledger

---

## 5. Starting the FastAPI Application

Launch the ASGI application using Uvicorn:

**Windows PowerShell:**
```powershell
python -m uvicorn piis.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Linux / macOS Bash:**
```bash
uvicorn piis.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Output:
```text
INFO:     Started server process [7890]
INFO:     Waiting for application startup.
INFO:     PIIS Decision Support Service initialized (Env: development)
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 6. Accessing the Operator Dashboard & API Docs

Open a web browser and navigate to:

- **Interactive Operator UI:** [http://localhost:8000/ui](http://localhost:8000/ui)
- **Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health Status:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Operator UI Authentication
In development mode, generate an operator token to access the dashboard:

```powershell
python -c "from piis.auth import AuthManager, ApplicationRole; print('Bearer ' + AuthManager().mint_dev_token('operator_sarah', role=ApplicationRole.NOC_L2))"
```
Paste this bearer token into the Operator UI authentication modal.

---

## 7. Running the 12-Stage Technical Demonstration

Run the reproducible end-to-end simulated telecom workflow:

**Windows PowerShell & Linux/macOS:**
```bash
python scripts/run_piis_demo.py
```

This script exercises the entire incident lifecycle in under 2 seconds:
1. Ingests a simulated ServiceNow incident (`INC0089201`).
2. Ingests an active Nokia 5G RAN alarm (`ALM-RAN-VSWR-HIGH`).
3. Ingests real-time Prometheus RF telemetry (`vswr_ratio=1.96`).
4. Normalizes payloads and records cryptographic provenance.
5. Verifies duplicate event suppression.
6. Runs streaming anomaly detection and topological graph correlation.
7. Retrieves historical evidence via hybrid BM25 + dense RAG.
8. Synthesizes an evidence-grounded investigation.
9. Produces a read-only recommendation (SOP antenna inspection dispatch).
10. Verifies service-principal lockout (HTTP 403) and authenticates human NOC review.
11. Appends the approval to the RFC 8785 JCS audit ledger.
12. Verifies cryptographic ledger continuity and monotonic hash chain integrity.

---

## 8. Executing the Automated Test Fleet

Execute the complete 349-test regression and hardening fleet:

**Windows PowerShell & Linux/macOS:**
```bash
pytest
```

Run specific test suites:
```bash
# Run M6 integration scenarios
pytest tests/integration/test_m6_integration_and_reliability.py -v

# Run M6 hardening verification (persistence, OIDC, OTLP gRPC export)
pytest tests/integration/test_m6_hardening_verification.py -v

# Run with test coverage report
pytest --cov=piis
```
