# ADR-018: Portfolio Simulation Harness & Local Enterprise Reproducibility

## Status
Approved (Milestone M7)

## Context
PIIS is designed to integrate into telecom Network Operations Centers (NOCs) alongside commercial ITSM platforms (ServiceNow, Jira Service Management), OSS/NMS alarm managers, and Prometheus/OpenTelemetry monitoring systems.

Live enterprise telecom production environments cannot be connected to external portfolio demonstrations or open-source evaluation sandboxes. Attempting to mock enterprise systems with shallow unit test mocks fails to validate end-to-end network behaviors, rate-limiting, retries, deduplication, and schema validation.

## Decision
1. **Deterministic Local Simulation Suite:**
   - Maintain dedicated, stateful simulator engines under `src/piis/integrations/simulators/`:
     - `SimulatedITSMPlatform`: Models ServiceNow Table API and Jira Service Management REST API with realistic carrier schema payloads, pagination, and simulated rate limiting (HTTP 429).
     - `SimulatedAlarmSystem`: Generates 3GPP/ETSI-compliant alarm events (loss of signal, high VSWR, BGP session flap) with configurable burst frequencies and out-of-order delivery.
     - `SimulatedPrometheusServer`: Serves Prometheus PromQL instant and range query vectors with synthetic RF anomaly metrics (SINR drop, PRB saturation).
2. **Local Test OIDC Provider:**
   - Provide a deterministic, in-process or local OIDC identity server (`LocalTestOIDCProvider`) generating real cryptographic RSA (RS256) and Elliptic Curve (ES256) key pairs.
   - Serve dynamic `/.well-known/openid-configuration` and `/.well-known/jwks.json`.
   - Support on-demand token minting, claim manipulation, key rotation, and token revocation for automated end-to-end security test suites.
3. **Transparent Operational Labeling:**
   - Every integration endpoint, UI dashboard component, and demonstration log must carry an explicit status tag:
     - `[LOCALLY VERIFIED]`: Fully exercised with real local cryptographic engines or disk persistence.
     - `[SIMULATED]`: Exercised against realistic local simulation harnesses.
     - `[CONTRACT TESTED]`: Pydantic schemas validated against vendor API specifications.
     - `[EXTERNALLY UNVERIFIED]`: Pending live carrier staging deployment.

## Consequences
- **Positive:** Reviewers, recruiters, and engineering auditors can clone the repository, run one script, and observe realistic telecom incident intelligence workflows end-to-end without needing external carrier credentials.
- **Negative:** Simulated platforms cannot replicate subtle undocumented vendor bugs or carrier-specific CMDB customizations; enterprise staging trials remain mandatory before production rollout.
