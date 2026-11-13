"""Milestone M7-D: Integration Verification for Enterprise Adapters, Simulators, and Read-Only Boundaries.

Verifies:
1. Strict read-only operational boundary enforcement across all enterprise adapters.
2. Capability flags (READ_ONLY=True, MUTATION_ALLOWED=False) and safe HTTP method enforcement.
3. Integration qualification status labeling (LOCALLY VERIFIED, SIMULATED, CONTRACT TESTED, EXTERNALLY UNVERIFIED).
4. ServiceNow ITSM adapter schema normalization and contract validation.
5. Jira Service Management adapter schema normalization and ADF parsing.
6. Generic REST / Webhook adapter customizable normalization.
7. Prometheus / Alertmanager metrics adapter normalization and unit mapping.
8. OpenTelemetry (OTLP) metrics adapter normalization.
9. OSS/NMS alarm feed adapter with multi-vendor code translation and 3GPP lifecycle tracking.
10. Failure modes handling: rate limiting, schema violations, and Dead Letter Queue (DLQ) routing.
11. Idempotent re-ingestion deduplication across adapters.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from piis.integrations import (
    GenericRestITSMAdapter,
    IngestionEnvelope,
    IngestionStatus,
    IntegrationStatusLabel,
    JiraServiceManagementAdapter,
    OpenTelemetryMetricsAdapter,
    OSSAlarmAdapter,
    PrometheusAdapter,
    RateLimiter,
    ReadOnlyBoundaryViolationError,
    ServiceNowAdapter,
)
from piis.integrations.simulators.alarm_simulator import SimulatedAlarmBroker
from piis.integrations.simulators.itsm_simulator import SimulatedITSMPlatform
from piis.integrations.simulators.telemetry_simulator import SimulatedTelemetryPlatform
from piis.pipeline.unified import UnifiedIngestionPipeline


@pytest.fixture
def pipeline(tmp_path: Path) -> UnifiedIngestionPipeline:
    """Create a clean isolated ingestion pipeline for testing."""
    return UnifiedIngestionPipeline()


# -----------------------------------------------------------------------------
# 1. READ-ONLY OPERATIONAL BOUNDARY & CAPABILITY FLAGS
# -----------------------------------------------------------------------------

def test_read_only_boundary_and_capability_flags():
    """Verify that every adapter strictly enforces read-only flags and blocks mutative methods."""
    adapters = [
        ServiceNowAdapter(),
        JiraServiceManagementAdapter(),
        GenericRestITSMAdapter(),
        PrometheusAdapter(),
        OpenTelemetryMetricsAdapter(),
        OSSAlarmAdapter(),
    ]

    for adapter in adapters:
        # Check capability flags
        assert adapter.READ_ONLY is True
        assert adapter.MUTATION_ALLOWED is False
        assert adapter.is_read_only is True
        assert adapter.mutation_allowed is False

        # Safe HTTP methods must be allowed
        adapter.validate_http_method("GET")
        adapter.validate_http_method("get")
        adapter.validate_http_method("HEAD")
        adapter.validate_http_method("head")

        # Mutative HTTP methods must raise ReadOnlyBoundaryViolationError
        for unsafe_method in ["POST", "PUT", "PATCH", "DELETE", "post", "delete"]:
            with pytest.raises(ReadOnlyBoundaryViolationError) as exc_info:
                adapter.validate_http_method(unsafe_method)
            assert "violates the strict read-only telecom operational boundary" in str(exc_info.value)

        # Forbidden operational commands must be rejected
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
            with pytest.raises(ReadOnlyBoundaryViolationError):
                adapter.enforce_read_only_boundary(forbidden_op)

        # Allowed read-only operational commands must pass
        for allowed_op in ["NORMALIZE", "HEALTH_CHECK", "READ_ONLY_INGEST"]:
            adapter.enforce_read_only_boundary(allowed_op)


def test_integration_qualification_status_labels():
    """Verify that all adapters carry transparent qualification labels."""
    expected_labels = {
        IntegrationStatusLabel.LOCALLY_VERIFIED.value,
        IntegrationStatusLabel.SIMULATED.value,
        IntegrationStatusLabel.CONTRACT_TESTED.value,
        IntegrationStatusLabel.EXTERNALLY_UNVERIFIED.value,
    }

    adapters = [
        ServiceNowAdapter(),
        JiraServiceManagementAdapter(),
        GenericRestITSMAdapter(),
        PrometheusAdapter(),
        OpenTelemetryMetricsAdapter(),
        OSSAlarmAdapter(),
    ]

    for adapter in adapters:
        assert hasattr(adapter, "status_labels")
        labels_set = set(adapter.status_labels)
        assert expected_labels.issubset(labels_set)
        assert IntegrationStatusLabel.EXTERNALLY_UNVERIFIED.value in adapter.status_labels
        assert IntegrationStatusLabel.LOCALLY_VERIFIED.value in adapter.status_labels


# -----------------------------------------------------------------------------
# 2. ADAPTER SCHEMA NORMALIZATION & CONTRACTS
# -----------------------------------------------------------------------------

def test_servicenow_adapter_contract_and_normalization(pipeline: UnifiedIngestionPipeline):
    """Test ServiceNow ITSM ticket normalization, priority mapping, and pipeline ingestion."""
    adapter = ServiceNowAdapter(adapter_id="SNOW-TEST-01")
    pipeline.register_adapter(adapter)

    sim_itsm = SimulatedITSMPlatform()
    snow_data = sim_itsm.tickets["INC0089201"]

    env = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload=snow_data,
        external_event_id=snow_data["number"],
    )

    res = pipeline.ingest_envelope(env, adapter_id="SNOW-TEST-01")
    assert res.status == IngestionStatus.SUCCESS
    assert res.canonical_id is not None
    assert "INC-SNOW-INC0089201" in res.canonical_id

    # Verify stored canonical record adheres to schema
    stored = pipeline.get_incident(res.canonical_id)
    assert stored is not None
    assert stored["network_domain"] == "RAN"
    assert stored["severity"] == "MAJOR"  # priority 2 -> MAJOR
    assert stored["support_level_label"] == "L1"
    assert "GNB-RAN-701" in stored["network_element_ids"]
    assert stored["metadata"]["servicenow_number"] == "INC0089201"


def test_jira_adapter_contract_and_normalization(pipeline: UnifiedIngestionPipeline):
    """Test Jira Service Management issue normalization, ADF parsing, and priority mapping."""
    adapter = JiraServiceManagementAdapter(adapter_id="JIRA-TEST-01")
    pipeline.register_adapter(adapter)

    sim_itsm = SimulatedITSMPlatform()
    jira_resp = sim_itsm.fetch_jira_issues()
    jira_issue = jira_resp["issues"][0]

    env = IngestionEnvelope.create(
        source_system="JiraServiceManagement",
        source_type="ITSM",
        raw_payload=jira_issue,
        external_event_id=jira_issue["key"],
    )

    res = pipeline.ingest_envelope(env, adapter_id="JIRA-TEST-01")
    assert res.status == IngestionStatus.SUCCESS
    assert res.canonical_id is not None
    assert "NOC-452" in res.canonical_id

    stored = pipeline.get_incident(res.canonical_id)
    assert stored is not None
    assert stored["severity"] == "MAJOR"  # High -> MAJOR
    assert "CSR-ROUTER-99" in stored["network_element_ids"]
    assert stored["network_domain"] == "TRANSPORT"


def test_generic_rest_adapter_normalization(pipeline: UnifiedIngestionPipeline):
    """Test Generic REST adapter with custom key mapping."""
    custom_mapping = {
        "id": "ticket_num",
        "title": "headline",
        "description": "body",
        "domain": "telecom_layer",
        "severity": "urgency_level",
        "elements": "nodes",
    }
    adapter = GenericRestITSMAdapter(
        adapter_id="GENERIC-TEST-01",
        source_system="CustomNocPortal",
        field_mapping=custom_mapping,
    )
    pipeline.register_adapter(adapter)

    payload = {
        "ticket_num": "CUSTOM-9912",
        "headline": "Microwave link fade margin warning",
        "body": "Excessive atmospheric attenuation observed on microwave path MW-HOP-12.",
        "telecom_layer": "TRANSPORT",
        "urgency_level": "WARNING",
        "nodes": ["MW-NODE-A", "MW-NODE-B"],
        "subscribers": 450,
    }

    env = IngestionEnvelope.create(
        source_system="CustomNocPortal",
        source_type="ITSM",
        raw_payload=payload,
        external_event_id="CUSTOM-9912",
    )

    res = pipeline.ingest_envelope(env, adapter_id="GENERIC-TEST-01")
    assert res.status == IngestionStatus.SUCCESS
    stored = pipeline.get_incident(res.canonical_id)
    assert stored is not None
    assert stored["severity"] == "WARNING"
    assert stored["network_domain"] == "TRANSPORT"
    assert "MW-NODE-A" in stored["network_element_ids"]


def test_prometheus_adapter_contract_and_normalization(pipeline: UnifiedIngestionPipeline):
    """Test Prometheus metrics normalization and unit mapping."""
    adapter = PrometheusAdapter(adapter_id="PROM-TEST-01")
    pipeline.register_adapter(adapter)

    sim_telem = SimulatedTelemetryPlatform()
    prom_data = sim_telem.query_prometheus_vector("vswr_ratio")
    vector_item = prom_data["data"]["result"][0]

    env = IngestionEnvelope.create(
        source_system="Prometheus",
        source_type="TELEMETRY",
        raw_payload=vector_item,
        external_event_id="PROM-VSWR-QUERY",
    )

    res = pipeline.ingest_envelope(env, adapter_id="PROM-TEST-01")
    assert res.status == IngestionStatus.SUCCESS

    # Verify telemetry observations stored for element
    obs_list = pipeline.get_element_telemetry("GNB-RAN-701")
    assert len(obs_list) >= 1
    assert any(obs["metric_name"] == "vswr_ratio" for obs in obs_list)


def test_opentelemetry_adapter_contract_and_normalization(pipeline: UnifiedIngestionPipeline):
    """Test OpenTelemetry metrics ingestion and nano-timestamp parsing."""
    adapter = OpenTelemetryMetricsAdapter(adapter_id="OTLP-TEST-01")
    pipeline.register_adapter(adapter)

    sim_telem = SimulatedTelemetryPlatform()
    otlp_batch = sim_telem.generate_otlp_metrics_batch(count=1)
    otlp_item = otlp_batch[0]

    env = IngestionEnvelope.create(
        source_system="OpenTelemetry",
        source_type="TELEMETRY",
        raw_payload=otlp_item,
        external_event_id="OTLP-EVT-01",
    )

    res = pipeline.ingest_envelope(env, adapter_id="OTLP-TEST-01")
    assert res.status == IngestionStatus.SUCCESS

    obs_list = pipeline.get_element_telemetry("5g-upf-dataplane")
    assert len(obs_list) >= 1
    assert any("upf.session.drop.rate" in obs["metric_name"] for obs in obs_list)


def test_oss_nms_alarm_adapter_normalization_and_lifecycle(pipeline: UnifiedIngestionPipeline):
    """Test OSS/NMS alarm mapping: multi-vendor alarm codes and 3GPP severity."""
    adapter = OSSAlarmAdapter(adapter_id="OSS-TEST-01")
    pipeline.register_adapter(adapter)

    sim_broker = SimulatedAlarmBroker()
    vswr_alarm = sim_broker.emit_vswr_alarm(element_id="GNB-RAN-701", vendor="NOKIA")

    env = IngestionEnvelope.create(
        source_system="GenericOSS",
        source_type="OSS_NMS_ALARM",
        raw_payload=vswr_alarm,
        external_event_id=vswr_alarm["alarm_id"],
    )

    res = pipeline.ingest_envelope(env, adapter_id="OSS-TEST-01")
    assert res.status == IngestionStatus.SUCCESS

    alarms = pipeline.get_element_alarms("GNB-RAN-701")
    assert len(alarms) >= 1
    stored_alarm = alarms[0]
    assert stored_alarm["alarm_code"] == "ALM-RAN-VSWR-HIGH"  # Nokia 7100 translated!
    assert stored_alarm["severity"] == "MAJOR"
    assert stored_alarm["metadata"]["vendor"] == "NOKIA"


# -----------------------------------------------------------------------------
# 3. FAILURE MODES, RATE LIMITING, SCHEMA VIOLATION & DLQ ROUTING
# -----------------------------------------------------------------------------

def test_adapter_rate_limiting_triggers_dlq(pipeline: UnifiedIngestionPipeline):
    """Verify that when an adapter rate limit is exhausted, payload is rejected and routed to DLQ."""
    # Strict limiter allowing 0 tokens
    strict_limiter = RateLimiter(requests_per_second=0.0, burst=0)
    adapter = ServiceNowAdapter(adapter_id="SNOW-RATE-LIMIT", rate_limiter=strict_limiter)
    pipeline.register_adapter(adapter)

    payload = {"number": "INC9999", "short_description": "Rate limit test"}
    env = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload=payload,
        external_event_id="INC9999",
    )

    res = pipeline.ingest_envelope(env, adapter_id="SNOW-RATE-LIMIT")
    assert res.status == IngestionStatus.RATE_LIMITED
    assert res.error is not None
    assert "Rate limit exceeded" in res.error

    # Verify DLQ received the item
    dlq_items = pipeline.dlq.list_items()
    assert len(dlq_items) >= 1
    assert any(item.failure_reason == "RATE_LIMITED" for item in dlq_items)


def test_schema_violation_triggers_dlq(pipeline: UnifiedIngestionPipeline):
    """Verify that invalid schema payloads fail validation and are routed to DLQ."""
    adapter = ServiceNowAdapter(adapter_id="SNOW-SCHEMA-VAL")
    pipeline.register_adapter(adapter)

    # Empty payload missing required incident fields
    invalid_payload = {"some_irrelevant_key": 12345}
    env = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload=invalid_payload,
        external_event_id="BAD-PAYLOAD-01",
    )

    res = pipeline.ingest_envelope(env, adapter_id="SNOW-SCHEMA-VAL")
    assert res.status in [IngestionStatus.FAILED, IngestionStatus.VALIDATION_FAILED]

    # Verify routed to DLQ
    dlq_items = pipeline.dlq.list_items()
    assert len(dlq_items) >= 1
    assert any(item.envelope.external_event_id == "BAD-PAYLOAD-01" for item in dlq_items)


def test_idempotent_reingestion_prevents_duplicate_incidents(pipeline: UnifiedIngestionPipeline):
    """Verify that sending identical payloads twice returns DUPLICATE status and does not create duplicate records."""
    adapter = ServiceNowAdapter(adapter_id="SNOW-IDEMP")
    pipeline.register_adapter(adapter)

    sim_itsm = SimulatedITSMPlatform()
    payload = sim_itsm.tickets["INC0089202"]

    env1 = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload=payload,
        external_event_id="INC0089202",
    )
    env2 = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload=payload,
        external_event_id="INC0089202",
    )

    res1 = pipeline.ingest_envelope(env1, adapter_id="SNOW-IDEMP")
    assert res1.status == IngestionStatus.SUCCESS
    first_canonical_id = res1.canonical_id

    # Ingest duplicate
    res2 = pipeline.ingest_envelope(env2, adapter_id="SNOW-IDEMP")
    assert res2.status == IngestionStatus.DUPLICATE
    assert res2.is_duplicate is True
    assert res2.canonical_id == first_canonical_id

    # Exactly one incident exists in repository
    assert len(pipeline._incidents) == 1
