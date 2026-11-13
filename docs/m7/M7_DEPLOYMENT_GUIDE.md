# M7 Local Deployment and Reproducibility Guide

## Production Incident Intelligence System (PIIS — Telecom Edition)
**Milestone:** M7 Portfolio Edition (Release Candidate v1.0.0-rc2)  
**Deployment Target:** Local Reproducible Testbed (Windows / Linux / macOS)  
**Operational Scope:** Strictly Read-Only Decision Support

---

## 1. Quick Start (Single Command Demonstration)

To run the complete 18-stage end-to-end portfolio demonstration:

```bash
python scripts/demonstrate_m7_portfolio_flow.py
```

Expected execution time: **~15 seconds**.  
Expected exit code: **`0`**.

---

## 2. Local Environment Setup

### 2.1. Prerequisites
- **Python:** 3.11 or higher (Python 3.11.5 recommended).
- **Git:** Required for cloning and submodule management.
- **Operating System:** Windows 10/11, Ubuntu 22.04 LTS+, or macOS 13+ (Ventura).
- **RAM:** Minimum 4 GB (8 GB recommended).
- **Disk:** 500 MB free space.

### 2.2. Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url> PIIS
   cd PIIS
   ```

2. **Create and activate a virtual environment:**
   - **Linux / macOS:**
     ```bash
     python3.11 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify installation:**
   ```bash
   pytest -q
   ```
   **Expected result:** `388 passed` (Exit code 0).

---

## 3. Launching the Local NOC Operator Dashboard

To start the interactive local web server and operator workspace:

```bash
uvicorn piis.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Then open your browser to:
- **Operator Workspace SPA:** [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui)
- **Interactive OpenAPI Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **System Health Endpoint:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 4. Configuration & Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PIIS_ENVIRONMENT` | `development` | Deployment mode: `development` enables local simulated IdP and file keys; `production` enforces real KMS/OIDC. |
| `PIIS_PORT` | `8000` | Port for the FastAPI HTTP server. |
| `PIIS_HOST` | `127.0.0.1` | Network interface to bind. |
| `PIIS_AUDIT_LEDGER_PATH` | `./data/audit_ledger.jsonl` | Persistent file location for the append-only cryptographic audit trail. |
| `PIIS_CHECKPOINT_ANCHOR_PATH` | `./data/checkpoint_anchor.json` | Persistent location for monotonic sequence checkpoint anchor. |
| `PIIS_OIDC_ISSUER` | `https://idp.telecom-corp.local` | Expected OIDC token issuer URL. |
| `PIIS_OIDC_AUDIENCE` | `piis-telecom-api` | Expected JWT audience claim. |
| `PIIS_KMS_ENDPOINT` | `None` | Optional custom KMS endpoint for AWS LocalStack or on-prem HSM. |
| `PIIS_KMS_REGION` | `us-east-1` | Cloud region for KMS key provider. |

---

## 5. Docker & Containerization Status

> [!WARNING]
> **Container Runtime Disclosure:**  
> `DOCKER CONFIGURATION PROVIDED; CONTAINER RUNTIME NOT TESTED IN THIS ENVIRONMENT.`  
> The developer has provided Dockerfile and Compose templates for enterprise evaluation, but in accordance with honest release governance, the containerized runtime has not been verified on this development workstation due to local daemon unavailability. All automated tests and benchmarks run natively on bare-metal Python 3.11.

---

## 6. Troubleshooting Common Local Issues

1. **Port 8000 already in use:**
   - Run on an alternative port:
     ```bash
     uvicorn piis.api.app:app --host 127.0.0.1 --port 8080
     ```
2. **Missing Token Verification Error in UI:**
   - In the top-right header of `/ui`, click **Set Auth** after generating a token using `LocalTestOIDCProvider` or the demo script.
3. **PowerShell Execution Policy Error:**
   - If `.\.venv\Scripts\Activate.ps1` is blocked, run:
     ```powershell
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     ```
