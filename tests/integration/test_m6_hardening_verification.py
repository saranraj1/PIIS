"""PIIS M6 Final Hardening & Verification Test Suite.

Rigorous automated verification covering:
- Workstream 2: Ingestion Reliability & Persistence
- Workstream 3: Identity Integration & OIDC Verification
- Workstream 4: OpenTelemetry Export & Fail-Safe Tracing
- Workstream 5: Strict Read-Only Integration Boundary
- Workstream 6: Operator Dashboard Server-Side Security
"""

from __future__ import annotations

import concurrent.futures
import json
import time
import pytest
from fastapi.testclient import TestClient

from piis.api.app import create_app
from piis.auth import ApplicationRole, AuthManager
from piis.integrations import (
    IngestionEnvelope,
    IngestionStatus,
    JiraServiceManagementAdapter,
    OSSAlarmAdapter,
    PrometheusAdapter,
    ReadOnlyBoundaryViolationError,
    ServiceNowAdapter,
)
from piis.investigation.approval import (
    ProductionOIDCVerifier,
    SSRFBlockedError,
    UnauthenticatedReviewerError,
)
from piis.observability.tracing import (
    InMemorySimulatedCollector,
    configure_tracing,
    extract_trace_context,
    flush_tracing,
    inject_trace_context,
    trace_span,
)
from piis.pipeline.dead_letter import DeadLetterQueue
from piis.pipeline.deduplication import IdempotencyEngine
from piis.pipeline.unified import UnifiedIngestionPipeline


# ===========================================================================
# WORKSTREAM 2: Ingestion Reliability & Persistence
# ===========================================================================

def test_dedup_single_process_and_restart_persistence(tmp_path):
    storage = tmp_path / "dedup.jsonl"
    engine1 = IdempotencyEngine(storage_path=storage)

    # First check: not a duplicate
    is_dup1, cid1 = engine1.check_and_record("SNOW::INC1001", "CANON-1001")
    assert is_dup1 is False
    assert cid1 == "CANON-1001"

    # Within same process: duplicate detected
    is_dup2, cid2 = engine1.check_and_record("SNOW::INC1001")
    assert is_dup2 is True
    assert cid2 == "CANON-1001"

    # Simulate process restart (engine2 reads from storage)
    engine2 = IdempotencyEngine(storage_path=storage)
    is_dup3, cid3 = engine2.check_and_record("SNOW::INC1001")
    assert is_dup3 is True
    assert cid3 == "CANON-1001"

    # New key is not duplicate
    is_dup4, _ = engine2.check_and_record("SNOW::INC1002", "CANON-1002")
    assert is_dup4 is False


def test_dedup_concurrent_submissions():
    """Verify thread-safety when 10 threads concurrently submit the exact same key."""
    engine = IdempotencyEngine()
    results = []

    def submit_duplicate(thread_idx: int):
        is_dup, cid = engine.check_and_record("SNOW::CONCURRENT_001", f"CANON-CONC-{thread_idx}")
        return is_dup, cid

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(submit_duplicate, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Exactly 1 request must succeed (is_dup == False); 9 must be flagged as duplicates
    non_duplicates = [r for r in results if r[0] is False]
    duplicates = [r for r in results if r[0] is True]
    assert len(non_duplicates) == 1
    assert len(duplicates) == 9


def test_dlq_persistence_and_replay_lifecycle(tmp_path):
    storage = tmp_path / "dlq_records.jsonl"
    dlq1 = DeadLetterQueue(storage_path=storage)

    env = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="OPERATOR_INTERNAL",
        raw_payload={"corrupted": True},
        external_event_id="INC_BAD_99",
    )
    item = dlq1.push(env, "SCHEMA_VALIDATION_ERROR", "Missing required field 'short_description'")
    assert dlq1.count() == 1
    assert item.attempt_count == 1
    assert item.replay_status == "PENDING"

    # Simulate restart
    dlq2 = DeadLetterQueue(storage_path=storage)
    assert dlq2.count() == 1
    restored = dlq2.get(item.item_id)
    assert restored is not None
    assert restored.envelope.external_event_id == "INC_BAD_99"
    assert restored.failure_reason == "SCHEMA_VALIDATION_ERROR"

    # Failed replay increment
    dlq2.push(env, "SCHEMA_VALIDATION_ERROR", "Still missing fields")
    assert dlq2.get(item.item_id).attempt_count == 2
    assert dlq2.get(item.item_id).replay_status == "FAILED"

    # Exhaust retries up to cap
    dlq2.push(env, "SCHEMA_VALIDATION_ERROR", "Retry 3")
    dlq2.push(env, "SCHEMA_VALIDATION_ERROR", "Retry 4")
    assert dlq2.get(item.item_id).attempt_count == 4
    assert dlq2.get(item.item_id).replay_status == "PERMANENTLY_FAILED"


def test_unified_pipeline_replay_and_no_downstream_duplicate():
    pipeline = UnifiedIngestionPipeline()
    adapter = ServiceNowAdapter()
    pipeline.register_adapter(adapter)

    # 1. Ingest invalid ticket that fails schema validation
    bad_payload = {"category": "RAN", "invalid": 123}  # missing number and sys_id
    env = IngestionEnvelope.create("ServiceNow", "OPERATOR_INTERNAL", bad_payload)
    res = pipeline.ingest_envelope(env)
    assert res.status == IngestionStatus.FAILED
    assert pipeline.dlq.count() == 1

    dlq_item = pipeline.dlq.list_items()[0]
    assert dlq_item.attempt_count == 1

    # 2. Fix the payload in the dead letter item's envelope
    dlq_item.envelope.raw_payload = {
        "number": "INC_RECOVERED_01",
        "sys_id": "sys_rec_01",
        "short_description": "Recovered RAN ticket after DLQ repair",
        "category": "RAN",
        "state": "1",
    }

    # 3. Replay dead letter item
    replay_res = pipeline.replay_dead_letter(dlq_item.item_id)
    assert replay_res.status == IngestionStatus.SUCCESS
    assert replay_res.canonical_id == "INC-SNOW-INC_RECOVERED_01"

    # 4. DLQ item should be removed on success
    assert pipeline.dlq.count() == 0

    # 5. Incident exists in canonical store exactly once
    assert pipeline.get_incident("INC-SNOW-INC_RECOVERED_01") is not None
    assert pipeline.count_incidents() == 1

    # 6. Re-submitting the exact same recovered envelope should be suppressed as duplicate
    res_dupe = pipeline.ingest_envelope(dlq_item.envelope)
    assert res_dupe.status == IngestionStatus.DUPLICATE
    assert pipeline.count_incidents() == 1


# ===========================================================================
# WORKSTREAM 3: Identity Integration & OIDC Verification
# ===========================================================================

def test_production_oidc_discovery_and_metadata_validation():
    mock_discovery = {
        "issuer": "https://auth.telecom.net",
        "jwks_uri": "https://auth.telecom.net/jwks.json",
        "id_token_signing_alg_values_supported": ["RS256", "ES256"],
    }

    def mock_http(url: str, timeout: float) -> bytes:
        if "/.well-known/openid-configuration" in url:
            return json.dumps(mock_discovery).encode("utf-8")
        if "/jwks.json" in url:
            return json.dumps({"keys": []}).encode("utf-8")
        raise ConnectionError(f"Unexpected URL: {url}")

    verifier = ProductionOIDCVerifier.discover_from_issuer(
        issuer_url="https://auth.telecom.net",
        audience="piis-telecom",
        allowed_domains=["auth.telecom.net"],
        http_client=mock_http,
    )
    assert verifier.jwks_url == "https://auth.telecom.net/jwks.json"
    assert verifier.issuer == "https://auth.telecom.net"
    assert verifier._is_configured is True


def test_production_oidc_discovery_ssrf_blocking():
    # Attempt discovery on cloud metadata IP
    with pytest.raises(SSRFBlockedError):
        ProductionOIDCVerifier.discover_from_issuer(
            issuer_url="http://169.254.169.254",
            audience="piis-telecom",
        )

    # Attempt discovery on private subnet
    with pytest.raises(SSRFBlockedError):
        ProductionOIDCVerifier.discover_from_issuer(
            issuer_url="https://192.168.1.50",
            audience="piis-telecom",
        )


def test_production_oidc_network_failure_fails_closed():
    def failing_http(url: str, timeout: float) -> bytes:
        raise ConnectionError("DNS resolution failed for idp.telecom.net")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://idp.telecom.net/jwks.json",
        issuer="https://idp.telecom.net",
        allowed_jwks_domains=["idp.telecom.net"],
        http_client=failing_http,
    )
    # Token verification must fail closed with UnauthenticatedReviewerError
    with pytest.raises(UnauthenticatedReviewerError) as exc_info:
        verifier._fetch_jwks()
    assert "Failed to retrieve JWKS" in str(exc_info.value)


# ===========================================================================
# WORKSTREAM 4: OpenTelemetry Export & Fail-Safe Tracing
# ===========================================================================

def test_opentelemetry_span_and_collector_export():
    collector = InMemorySimulatedCollector()
    configured = configure_tracing(exporter=collector)
    if not configured:
        pytest.skip("OpenTelemetry SDK not installed")

    collector.clear()
    with trace_span("piis.investigation.triage", attributes={"incident_id": "INC-TEST-01"}) as span:
        span.set_attribute("domain", "RAN")

    # Verify span was exported to simulated collector
    assert len(collector.spans) >= 1
    exported_names = [s.name for s in collector.spans]
    assert "piis.investigation.triage" in exported_names


def test_opentelemetry_w3c_context_propagation():
    headers: dict[str, str] = {}
    with trace_span("piis.root_span"):
        inject_trace_context(headers)

    assert "traceparent" in headers
    # Verify extraction
    ctx = extract_trace_context(headers)
    assert ctx is not None


def test_opentelemetry_collector_failure_is_fail_safe():
    """Verify that collector downtime (e.g. ECONNREFUSED) NEVER crashes incident processing."""
    failing_collector = InMemorySimulatedCollector(should_fail=True)
    configured = configure_tracing(exporter=failing_collector)
    if not configured:
        pytest.skip("OpenTelemetry SDK not installed")

    # Spans executed under a failing exporter must complete without raising exceptions
    processed = False
    with trace_span("piis.critical_incident_processing", attributes={"domain": "RAN"}) as span:
        span.set_attribute("action", "investigate")
        processed = True

    assert processed is True


def test_real_otlp_grpc_network_export_and_collector_resilience():
    """Verify REAL network export of OpenTelemetry spans over gRPC to a local receiver."""
    import grpc
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc

    class LocalOTLPReceiver(trace_service_pb2_grpc.TraceServiceServicer):
        def __init__(self):
            self.received_requests = []

        def Export(self, request, context):
            self.received_requests.append(request)
            return trace_service_pb2.ExportTraceServiceResponse()

    # 1. Start local gRPC OTLP receiver on an ephemeral port
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
    receiver = LocalOTLPReceiver()
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(receiver, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()

    try:
        # 2. Configure PIIS tracing to export over network to the local receiver
        endpoint = f"127.0.0.1:{port}"
        success = configure_tracing(collector_endpoint=endpoint, timeout=1.0)
        assert success is True

        # 3. Generate representative incident triage and investigation trace with parent-child hierarchy
        with trace_span("piis.incident.ingest", attributes={"incident_id": "INC-GRPC-99", "domain": "RAN"}):
            with trace_span("piis.investigation.evaluate", attributes={"step": "sufficiency", "sufficient": False}):
                pass

        flush_tracing()
        time.sleep(0.3)

        # 4. Verify receiver actually received exported spans over network
        assert len(receiver.received_requests) >= 1

        # Flatten spans
        all_spans = []
        for req in receiver.received_requests:
            for rs in req.resource_spans:
                for ss in rs.scope_spans:
                    for sp in ss.spans:
                        all_spans.append(sp)

        span_names = [s.name for s in all_spans]
        assert "piis.incident.ingest" in span_names
        assert "piis.investigation.evaluate" in span_names

        # 5. Verify trace IDs, parent-child relationships, and expected attributes
        parent_sp = next(s for s in all_spans if s.name == "piis.incident.ingest")
        child_sp = next(s for s in all_spans if s.name == "piis.investigation.evaluate")

        assert parent_sp.trace_id == child_sp.trace_id
        assert child_sp.parent_span_id == parent_sp.span_id

        # Verify child attributes
        attr_dict = {attr.key: (attr.value.string_value or attr.value.bool_value) for attr in child_sp.attributes}
        assert attr_dict.get("step") == "sufficiency"

    finally:
        # 6. Stop collector
        server.stop(0)

    # 7. Verify telemetry failure does not interrupt incident processing
    processed = False
    with trace_span("piis.incident.after_collector_stopped", attributes={"resilient": True}) as span:
        span.set_attribute("status", "completed")
        processed = True

    assert processed is True


# ===========================================================================
# WORKSTREAM 5: Strict Read-Only Integration Boundary
# ===========================================================================

def test_adapters_strict_read_only_boundary():
    adapters = [
        ServiceNowAdapter(),
        JiraServiceManagementAdapter(),
        OSSAlarmAdapter(),
        PrometheusAdapter(),
    ]

    for adapter in adapters:
        # Permitted operations must pass
        adapter.enforce_read_only_boundary("NORMALIZE")
        adapter.enforce_read_only_boundary("HEALTH_CHECK")
        adapter.enforce_read_only_boundary("READ_ONLY_INGEST")

        # Prohibited operations must raise ReadOnlyBoundaryViolationError
        for forbidden_op in [
            "CREATE_TICKET",
            "UPDATE_TICKET",
            "CLOSE_TICKET",
            "ASSIGN_TICKET",
            "EXECUTE_COMMAND",
            "MODIFY_CONFIG",
            "REBOOT_ELEMENT",
            "SEND_COMMUNICATION",
        ]:
            with pytest.raises(ReadOnlyBoundaryViolationError) as exc_info:
                adapter.enforce_read_only_boundary(forbidden_op)
            assert "violates the strict read-only telecom operational boundary" in str(exc_info.value)


def test_api_has_zero_network_mutation_routes():
    app = create_app()
    client = TestClient(app)

    # Verify that mutative command execution routes do not exist
    for forbidden_route in [
        "/api/v1/network/commands/execute",
        "/api/v1/elements/reboot",
        "/api/v1/configs/apply",
        "/api/v1/tickets/close",
    ]:
        res = client.post(forbidden_route, json={})
        assert res.status_code == 404


# ===========================================================================
# WORKSTREAM 6: Operator Dashboard & Server-Side Security
# ===========================================================================

def test_dashboard_direct_unauthenticated_request_rejected():
    app = create_app()
    client = TestClient(app)

    # Direct request without token to protected incidents endpoint
    res = client.get("/api/v1/incidents")
    assert res.status_code == 401

    # Direct request without token to audit records
    res_audit = client.get("/api/v1/audit/records")
    assert res_audit.status_code == 401


def test_direct_service_principal_review_rejected():
    app = create_app()
    client = TestClient(app)
    auth = AuthManager()

    # Mint service principal token
    svc_token = auth.mint_dev_token("poller_daemon", is_service=True)

    # Attempt direct human approval via API
    res = client.post(
        "/api/v1/incidents/INC-TEST-001/reviews",
        json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": "Automated approval attempt"},
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    # Server-side enforcement must reject with 403 Forbidden
    assert res.status_code == 403
    assert "automated service account" in res.json()["detail"].lower()


def test_direct_viewer_role_review_rejected():
    app = create_app()
    client = TestClient(app)
    auth = AuthManager()

    # Mint user without review role (e.g. SECURITY_AUDITOR who can only view audit logs)
    no_review_token = auth.mint_dev_token("dashboard_viewer", role=ApplicationRole.SECURITY_AUDITOR)
    res = client.post(
        "/api/v1/incidents/INC-TEST-001/reviews",
        json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": "Attempting unauthorized review"},
        headers={"Authorization": f"Bearer {no_review_token}"},
    )
    assert res.status_code == 403
    assert "lacks review authorization" in res.json()["detail"].lower()


def test_no_secret_tokens_in_dashboard_html():
    app = create_app()
    client = TestClient(app)

    res = client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # Verify no embedded tokens, passwords, or HMAC keys in the HTML or JS
    assert "eyJhbGci" not in html
    assert "piis-audit-key" not in html
    assert "password" not in html.lower() or 'type="password"' in html
    assert "secret" not in html.lower()
