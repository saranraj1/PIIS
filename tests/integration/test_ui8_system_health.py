"""Integration tests for PIIS UI-8 System Health & Operations Workspace endpoints.

Comprehensive test suite verifying:
1. Aggregate health calculation (all healthy -> HEALTHY).
2. Critical component unavailable -> aggregate UNAVAILABLE.
3. Non-critical component degraded -> aggregate DEGRADED.
4. Missing health information does not become healthy (returns UNKNOWN/DEGRADED).
5. Stale health information correctly flagged (FRESH vs STALE vs EXPIRED).
6. Unknown health state handling.
7. Unconfigured AI provider / fallback mode handling.
8. Failed retrieval dependency isolation.
9. Ingestion pipeline health counters accuracy.
10. DLQ depth and status reflection.
11. Audit ledger unavailable reflection.
12. Missing checkpoint anchor handling.
13. Health endpoint authorization (requires VIEW_INCIDENTS, 401 unauthenticated).
14. Secret redaction (zero credentials exposed).
15. GET endpoint non-mutation (calling endpoints multiple times causes zero state mutations).
16. No hidden AI inference.
17. No subprocess execution.
18. No external network access.
19. No audit ledger modification.
20. Timestamp and freshness correctness.
21. Concurrent health requests safety.
22. Dependency graph accuracy.
23. Failure isolation when one health check encounters an unexpected error.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from piis.api.app import app
from piis.api.routers.incidents import get_pipeline, get_workflow
from piis.api.routers.system import (
    compute_aggregate_health,
    compute_freshness,
    evaluate_system_components,
)
from piis.api.schemas import ComponentHealthItem
from piis.auth import ApplicationRole, AuthManager


@pytest.fixture
def auth_manager():
    return AuthManager()


@pytest.fixture
def auth_headers_operator(auth_manager):
    """Network operator with VIEW_INCIDENTS permission."""
    token = auth_manager.mint_dev_token(
        principal_id="noc-operator-01",
        role=ApplicationRole.NOC_L1,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(auth_manager):
    """PIIS admin with full administration permissions."""
    token = auth_manager.mint_dev_token(
        principal_id="piis-admin-01",
        role=ApplicationRole.PIIS_ADMIN,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Aggregate Health Calculation (All Healthy -> HEALTHY)
# ---------------------------------------------------------------------------

def test_aggregate_health_all_healthy():
    components = [
        ComponentHealthItem(
            component_id="api-gateway",
            name="API Gateway",
            category="API",
            health_state="HEALTHY",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="ingestion-pipeline",
            name="Ingestion",
            category="INGESTION",
            health_state="HEALTHY",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="telemetry-anomaly",
            name="Telemetry",
            category="TELEMETRY",
            health_state="HEALTHY",
            criticality="STANDARD",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="background-worker",
            name="Worker",
            category="BACKGROUND",
            health_state="UNKNOWN",
            criticality="INFORMATIONAL",
            check_source="boundary",
            implementation_nature="NOT_INSTRUMENTED",
        ),
    ]
    assert compute_aggregate_health(components) == "HEALTHY"


# ---------------------------------------------------------------------------
# 2. Critical Component Unavailable -> Aggregate UNAVAILABLE
# ---------------------------------------------------------------------------

def test_critical_component_unavailable_forces_aggregate_unavailable():
    components = [
        ComponentHealthItem(
            component_id="api-gateway",
            name="API Gateway",
            category="API",
            health_state="UNAVAILABLE",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="telemetry-anomaly",
            name="Telemetry",
            category="TELEMETRY",
            health_state="HEALTHY",
            criticality="STANDARD",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
    ]
    assert compute_aggregate_health(components) == "UNAVAILABLE"


# ---------------------------------------------------------------------------
# 3. Non-Critical Component Degraded -> Aggregate DEGRADED
# ---------------------------------------------------------------------------

def test_non_critical_component_degraded_forces_aggregate_degraded():
    components = [
        ComponentHealthItem(
            component_id="api-gateway",
            name="API Gateway",
            category="API",
            health_state="HEALTHY",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="telemetry-anomaly",
            name="Telemetry",
            category="TELEMETRY",
            health_state="DEGRADED",
            criticality="STANDARD",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
    ]
    assert compute_aggregate_health(components) == "DEGRADED"


# ---------------------------------------------------------------------------
# 4. Missing Health Information Does Not Become Healthy
# ---------------------------------------------------------------------------

def test_missing_health_information_does_not_become_healthy():
    now_dt = datetime.now(timezone.utc)
    # Missing timestamp returns UNKNOWN, never FRESH or HEALTHY
    assert compute_freshness(None, now_dt) == "UNKNOWN"
    assert compute_freshness("", now_dt) == "UNKNOWN"

    # Informational components with no instrumentation must be UNKNOWN
    pipeline = get_pipeline()
    workflow = get_workflow()
    now_iso = now_dt.isoformat()
    components = evaluate_system_components(pipeline, workflow, now_iso, now_dt)

    worker = next(c for c in components if c.component_id == "background-worker")
    assert worker.health_state == "UNKNOWN"
    assert worker.implementation_nature == "NOT_INSTRUMENTED"
    assert worker.health_state != "HEALTHY"


# ---------------------------------------------------------------------------
# 5. Stale Health Information Correctly Flagged (FRESH vs STALE vs EXPIRED)
# ---------------------------------------------------------------------------

def test_stale_health_information_correctly_flagged():
    now_dt = datetime.now(timezone.utc)

    fresh_ts = (now_dt - timedelta(seconds=60)).isoformat()
    assert compute_freshness(fresh_ts, now_dt) == "FRESH"

    stale_ts = (now_dt - timedelta(minutes=15)).isoformat()
    assert compute_freshness(stale_ts, now_dt) == "STALE"

    expired_ts = (now_dt - timedelta(hours=3)).isoformat()
    assert compute_freshness(expired_ts, now_dt) == "EXPIRED"

    # Future timestamps within clock skew tolerance remain FRESH
    skew_ts = (now_dt + timedelta(seconds=10)).isoformat()
    assert compute_freshness(skew_ts, now_dt) == "FRESH"


# ---------------------------------------------------------------------------
# 6. Unknown Health State Handling
# ---------------------------------------------------------------------------

def test_unknown_health_state_handling():
    # Critical UNKNOWN forces aggregate UNKNOWN
    comp_crit_unknown = [
        ComponentHealthItem(
            component_id="auth-manager",
            name="Auth",
            category="AUTH",
            health_state="UNKNOWN",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
    ]
    assert compute_aggregate_health(comp_crit_unknown) == "UNKNOWN"

    # Standard UNKNOWN causes aggregate DEGRADED
    comp_std_unknown = [
        ComponentHealthItem(
            component_id="api-gateway",
            name="API",
            category="API",
            health_state="HEALTHY",
            criticality="CRITICAL",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
        ComponentHealthItem(
            component_id="dead-letter-quarantine",
            name="DLQ",
            category="DLQ",
            health_state="UNKNOWN",
            criticality="STANDARD",
            check_source="probe",
            implementation_nature="REAL_LOCAL",
        ),
    ]
    assert compute_aggregate_health(comp_std_unknown) == "DEGRADED"


# ---------------------------------------------------------------------------
# 7. Unconfigured AI Provider / Fallback Mode Handling
# ---------------------------------------------------------------------------

def test_unconfigured_ai_provider_fallback_mode_handling(test_client, auth_headers_operator):
    resp = test_client.get("/api/v1/system-health/intelligence", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    assert data["engine_version"] == "1.0.0"
    assert data["investigation_status"] == "OPERATIONAL"
    assert data["bm25_index_status"] == "OPERATIONAL"
    assert isinstance(data["dense_is_fallback_mode"], bool)
    assert data["dense_index_status"] in {"OPERATIONAL", "LOCAL_FALLBACK"}
    assert data["sop_rules_count"] == 15
    assert "RECIPROCAL_RANK_FUSION" in data["fusion_algorithm"]


# ---------------------------------------------------------------------------
# 8. Failed Retrieval Dependency Isolation
# ---------------------------------------------------------------------------

def test_failed_retrieval_dependency_isolation():
    now_dt = datetime.now(timezone.utc)
    pipeline = get_pipeline()
    workflow = get_workflow()

    # Simulate retrieval exception
    with patch.object(pipeline, "_engine", None):
        components = evaluate_system_components(pipeline, workflow, now_dt.isoformat(), now_dt)
        # Check that BM25 and Dense are handled cleanly without crashing
        bm25_comp = next(c for c in components if c.component_id == "knowledge-retrieval-bm25")
        dense_comp = next(c for c in components if c.component_id == "knowledge-retrieval-dense")
        assert bm25_comp is not None
        assert dense_comp is not None
        # Other critical components remain healthy
        gateway_comp = next(c for c in components if c.component_id == "api-gateway")
        assert gateway_comp.health_state == "HEALTHY"


# ---------------------------------------------------------------------------
# 9. Ingestion Pipeline Health Counters Accuracy
# ---------------------------------------------------------------------------

def test_ingestion_pipeline_health_counters_accuracy(test_client, auth_headers_operator):
    resp = test_client.get("/api/v1/system-health/ingestion", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    assert data["pipeline_status"] == "OPERATIONAL"
    assert data["rate_limit_policy"] == "TOKEN_BUCKET_BURST_PROTECTED"
    assert data["data_direction"] == "INBOUND_ONLY"
    assert isinstance(data["cumulative_ingested_events"], int)
    assert isinstance(data["cumulative_stored_incidents"], int)
    assert isinstance(data["current_dlq_depth"], int)
    assert isinstance(data["registered_adapters_count"], int)
    assert data["registered_adapters_count"] >= 6


# ---------------------------------------------------------------------------
# 10. DLQ Depth and Status Reflection
# ---------------------------------------------------------------------------

def test_dlq_depth_and_status_reflection(test_client, auth_headers_operator):
    pipeline = get_pipeline()
    initial_dlq = pipeline.dlq.count()

    resp = test_client.get("/api/v1/system-health/components/dead-letter-quarantine", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    if initial_dlq == 0:
        assert data["health_state"] == "HEALTHY"
        assert data["failure_reason"] is None
    else:
        assert data["health_state"] == "DEGRADED"
        assert "quarantined payload" in data["failure_reason"]


# ---------------------------------------------------------------------------
# 11. Audit Ledger Unavailable Reflection
# ---------------------------------------------------------------------------

def test_audit_ledger_unavailable_reflection(test_client, auth_headers_operator):
    workflow = get_workflow()
    now_dt = datetime.now(timezone.utc)

    # When ledger file does not exist
    non_existent_path = Path("non_existent_ledger_test.jsonl")
    with patch.object(workflow, "_ledger_path", non_existent_path):
        components = evaluate_system_components(get_pipeline(), workflow, now_dt.isoformat(), now_dt)
        ledger_comp = next(c for c in components if c.component_id == "audit-ledger-jcs")
        assert ledger_comp.health_state == "UNAVAILABLE"
        assert "not found on disk" in ledger_comp.failure_reason


# ---------------------------------------------------------------------------
# 12. Missing Checkpoint Anchor Handling
# ---------------------------------------------------------------------------

def test_missing_checkpoint_anchor_handling(test_client, auth_headers_operator):
    workflow = get_workflow()
    now_dt = datetime.now(timezone.utc)

    with patch.object(workflow, "_checkpoint_anchor", None):
        components = evaluate_system_components(get_pipeline(), workflow, now_dt.isoformat(), now_dt)
        anchor_comp = next(c for c in components if c.component_id == "checkpoint-anchor")
        assert anchor_comp.health_state == "DEGRADED"
        assert "Checkpoint anchor not configured" in anchor_comp.failure_reason

    # Test persistence endpoint reflects MISSING anchor
    with patch.object(workflow, "_checkpoint_anchor", None):
        resp = test_client.get("/api/v1/system-health/persistence", headers=auth_headers_operator)
        assert resp.status_code == 200
        assert resp.json()["checkpoint_anchor_status"] == "MISSING"


# ---------------------------------------------------------------------------
# 13. Health Endpoint Authorization (Requires VIEW_INCIDENTS, 401 Unauthenticated)
# ---------------------------------------------------------------------------

def test_health_endpoint_authorization(test_client):
    protected_endpoints = [
        "/api/v1/system-health/overview",
        "/api/v1/system-health/components",
        "/api/v1/system-health/components/api-gateway",
        "/api/v1/system-health/ingestion",
        "/api/v1/system-health/intelligence",
        "/api/v1/system-health/persistence",
        "/api/v1/system-health/events",
        "/api/v1/system-health/dependencies",
    ]

    for ep in protected_endpoints:
        res = test_client.get(ep)
        assert res.status_code == 401, f"Endpoint {ep} must require authentication"

    # Public runtime probes & Prometheus exporter do not require auth
    assert test_client.get("/api/v1/health").status_code == 200
    assert test_client.get("/api/v1/ready").status_code in {200, 200}
    assert test_client.get("/metrics").status_code == 200


# ---------------------------------------------------------------------------
# 14. Secret Redaction (Zero Credentials Exposed)
# ---------------------------------------------------------------------------

def test_secret_redaction(test_client, auth_headers_operator):
    endpoints = [
        "/api/v1/system-health/overview",
        "/api/v1/system-health/components",
        "/api/v1/system-health/persistence",
        "/api/v1/system-health/dependencies",
    ]

    forbidden_patterns = [
        "piis-dev-audit-key-32bytes-long!",
        "secret",
        "private_key",
        "api_key",
        "password",
        "Bearer ey",
    ]

    for ep in endpoints:
        resp = test_client.get(ep, headers=auth_headers_operator)
        assert resp.status_code == 200
        raw_text = resp.text
        for forbidden in forbidden_patterns:
            assert forbidden not in raw_text, f"Secret pattern '{forbidden}' leaked in {ep}"


# ---------------------------------------------------------------------------
# 15. GET Endpoint Non-Mutation
# ---------------------------------------------------------------------------

def test_get_endpoint_non_mutation(test_client, auth_headers_operator):
    pipeline = get_pipeline()
    workflow = get_workflow()

    initial_incidents = pipeline.count_incidents()
    initial_dlq = pipeline.dlq.count()
    initial_audit_count = len(workflow.get_audit_trail())

    endpoints = [
        "/api/v1/system-health/overview",
        "/api/v1/system-health/components",
        "/api/v1/system-health/ingestion",
        "/api/v1/system-health/intelligence",
        "/api/v1/system-health/persistence",
        "/api/v1/system-health/events",
        "/api/v1/system-health/dependencies",
    ]

    for ep in endpoints:
        for _ in range(3):
            resp = test_client.get(ep, headers=auth_headers_operator)
            assert resp.status_code == 200

    assert pipeline.count_incidents() == initial_incidents
    assert pipeline.dlq.count() == initial_dlq
    assert len(workflow.get_audit_trail()) == initial_audit_count


# ---------------------------------------------------------------------------
# 16. No Hidden AI Inference
# ---------------------------------------------------------------------------

def test_no_hidden_ai_inference(test_client, auth_headers_operator):
    with patch("piis.retrieval.dense.DenseBiEncoderIndex.encode") as mock_encode:
        resp = test_client.get("/api/v1/system-health/overview", headers=auth_headers_operator)
        assert resp.status_code == 200
        mock_encode.assert_not_called()

        resp = test_client.get("/api/v1/system-health/intelligence", headers=auth_headers_operator)
        assert resp.status_code == 200
        mock_encode.assert_not_called()


# ---------------------------------------------------------------------------
# 17. No Subprocess Execution
# ---------------------------------------------------------------------------

def test_no_subprocess_execution(test_client, auth_headers_operator):
    with patch.object(subprocess, "Popen") as mock_popen, \
         patch.object(os, "system") as mock_system:
        resp = test_client.get("/api/v1/system-health/overview", headers=auth_headers_operator)
        assert resp.status_code == 200
        mock_popen.assert_not_called()
        mock_system.assert_not_called()


# ---------------------------------------------------------------------------
# 18. No External Network Access
# ---------------------------------------------------------------------------

def test_no_external_network_access(test_client, auth_headers_operator):
    real_connect = socket.socket.connect

    def patched_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if str(host) not in {"127.0.0.1", "localhost", "::1", "testclient"}:
            raise RuntimeError(f"Unauthorized external socket connection attempted: {address}")
        return real_connect(self, address)

    with patch.object(socket.socket, "connect", patched_connect):
        resp = test_client.get("/api/v1/system-health/overview", headers=auth_headers_operator)
        assert resp.status_code == 200
        resp = test_client.get("/api/v1/system-health/dependencies", headers=auth_headers_operator)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 19. No Audit Ledger Modification
# ---------------------------------------------------------------------------

def test_no_audit_ledger_modification(test_client, auth_headers_operator):
    workflow = get_workflow()
    trail_before = len(workflow.get_audit_trail())

    for _ in range(5):
        resp = test_client.get("/api/v1/system-health/persistence", headers=auth_headers_operator)
        assert resp.status_code == 200

    trail_after = len(workflow.get_audit_trail())
    assert trail_after == trail_before


# ---------------------------------------------------------------------------
# 20. Timestamp and Freshness Correctness
# ---------------------------------------------------------------------------

def test_timestamp_and_freshness_correctness(test_client, auth_headers_operator):
    resp = test_client.get("/api/v1/system-health/overview", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    eval_ts = data["last_evaluated_at"]
    # Ensure parseable as valid ISO-8601 UTC timestamp
    dt = datetime.fromisoformat(eval_ts.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff = abs((now - dt).total_seconds())
    assert diff < 60.0  # Must be freshly generated


# ---------------------------------------------------------------------------
# 21. Concurrent Health Requests Safety
# ---------------------------------------------------------------------------

def test_concurrent_health_requests_safety(test_client, auth_headers_operator):
    def fetch_health():
        res = test_client.get("/api/v1/system-health/overview", headers=auth_headers_operator)
        return res.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_health) for _ in range(16)]
        results = [f.result() for f in futures]

    assert all(code == 200 for code in results)


# ---------------------------------------------------------------------------
# 22. Dependency Graph Accuracy
# ---------------------------------------------------------------------------

def test_dependency_graph_accuracy(test_client, auth_headers_operator):
    resp = test_client.get("/api/v1/system-health/dependencies", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    assert data["graph_type"] == "STATIC_CODEBASE_GROUNDED"
    assert data["epistemic_classification"] == "VERIFIED_ARCHITECTURE"

    nodes = data["nodes"]
    edges = data["edges"]

    assert len(nodes) == 17
    node_ids = {n["id"] for n in nodes}
    expected_nodes = {
        "api-gateway", "auth-manager", "ingestion-pipeline", "idempotency-engine",
        "dead-letter-quarantine", "investigation-engine", "knowledge-retrieval-bm25",
        "knowledge-retrieval-dense", "telemetry-anomaly", "human-review-hub",
        "audit-ledger-jcs", "checkpoint-anchor", "trust-boundary-hmac",
        "integration-adapters", "enterprise-oidc", "external-worm-storage",
        "background-worker",
    }
    assert node_ids == expected_nodes

    assert len(edges) >= 12
    edge_pairs = {(e["source"], e["target"]) for e in edges}
    assert ("api-gateway", "auth-manager") in edge_pairs
    assert ("ingestion-pipeline", "dead-letter-quarantine") in edge_pairs
    assert ("human-review-hub", "audit-ledger-jcs") in edge_pairs


# ---------------------------------------------------------------------------
# 23. Failure Isolation When One Health Check Encounters An Unexpected Error
# ---------------------------------------------------------------------------

def test_failure_isolation_per_component():
    now_dt = datetime.now(timezone.utc)
    pipeline = get_pipeline()
    workflow = get_workflow()

    # Mock pipeline.list_adapters to raise an unexpected runtime error
    with patch.object(pipeline, "list_adapters", side_effect=RuntimeError("Simulated unexpected adapters crash")):
        components = evaluate_system_components(pipeline, workflow, now_dt.isoformat(), now_dt)

        # The failing component is safely caught and marked DEGRADED
        adapter_comp = next(c for c in components if c.component_id == "integration-adapters")
        assert adapter_comp.health_state == "DEGRADED"
        assert "Simulated unexpected adapters crash" in adapter_comp.failure_reason

        # Other components are NOT impacted
        gateway_comp = next(c for c in components if c.component_id == "api-gateway")
        assert gateway_comp.health_state == "HEALTHY"
        assert gateway_comp.failure_reason is None

        auth_comp = next(c for c in components if c.component_id == "auth-manager")
        assert auth_comp.health_state == "HEALTHY"
