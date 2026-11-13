# PIIS Exploration and Verification Notebooks

This directory contains Jupyter notebooks demonstrating the core intelligence, anomaly detection, and cryptographic audit capabilities of the Production Incident Intelligence System (PIIS).

## Available Notebooks

1. **`01_incident_triage_and_investigation.ipynb`**
   - End-to-end incident ingestion using canonical ServiceNow envelopes.
   - Execution of the multi-stage investigation assistant.
   - Inspection of ranked hypotheses, confidence proxies, and runbook recommendations.

2. **`02_telemetry_anomaly_detection.ipynb`**
   - Simulation of 5G radio frequency VSWR degradation.
   - Causal sliding-window 3-sigma dynamic thresholding and Isolation Forest evaluation.
   - Detection of anomaly windows without lookahead data leakage.

3. **`03_cryptographic_audit_ledger_verification.ipynb`**
   - Demonstration of RFC 8785 JSON Canonicalization Scheme (JCS) determinism.
   - Simulation of human operator recommendation approval.
   - SHA-256 hash chaining, HMAC-SHA256 notarization, and monotonic checkpoint verification.

## Running the Notebooks

Ensure your virtual environment is active and dependencies are installed:

```bash
# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install Jupyter if not already present
pip install jupyterlab

# Launch Jupyter Lab
jupyter lab notebooks/
```
