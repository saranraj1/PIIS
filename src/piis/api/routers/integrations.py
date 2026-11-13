"""Integration adapter health, registry, data flow, and dead-letter queue management endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status

from piis.api.routers.incidents import get_pipeline
from piis.api.schemas import (
    AdapterHealthResponse,
    DataFlowEdgeItem,
    DataFlowResponse,
    DataFlowStageItem,
    DeadLetterItemResponse,
    IntegrationActivityItem,
    IntegrationConfigField,
    IntegrationDetailResponse,
    IntegrationRegistryItem,
    IntegrationSummaryResponse,
    PaginatedResponse,
)
from piis.auth import (
    ApplicationRole,
    AuthenticatedPrincipal,
    Permission,
    require_human_operator,
    require_permissions,
    require_roles,
)
from piis.integrations.contracts import HealthState, IntegrationAdapter
from piis.pipeline.unified import UnifiedIngestionPipeline

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations & Health"])


# ---------------------------------------------------------------------------
# Metadata Catalog for Configured Enterprise Telecom Adapters (Portfolio Edition)
# ---------------------------------------------------------------------------

_ADAPTER_METADATA: Dict[str, Dict[str, Any]] = {
    "ITSM-SERVICENOW-01": {
        "name": "ServiceNow Incident Connector",
        "description": (
            "Bi-directional ingestion gateway translating ServiceNow Table API incident schemas "
            "into PIIS canonical records with automated priority mapping and field normalization."
        ),
        "category": "ITSM",
        "provider_type": "ServiceNow",
        "connection_mode": "LOCAL SIMULATION",
        "status_label": "LOCALLY VERIFIED (SIMULATED)",
        "capabilities": ["READ_ONLY_INGEST", "CANONICAL_NORMALIZATION", "SCHEMA_VALIDATION"],
        "authentication_model": "OAuth 2.0 Bearer Token (Local Reference Token)",
        "config_fields": [
            IntegrationConfigField(
                name="instance_url",
                field_type="url",
                description="Target ServiceNow telecom enterprise instance URL",
                sanitized_value="https://telecom.service-now.com",
            ),
            IntegrationConfigField(
                name="api_version",
                field_type="string",
                description="ServiceNow Table API REST specification version",
                sanitized_value="v2",
            ),
            IntegrationConfigField(
                name="table_name",
                field_type="string",
                description="Target schema table for telecom incident records",
                sanitized_value="incident",
            ),
            IntegrationConfigField(
                name="client_id",
                field_type="string",
                description="OAuth client registration identifier",
                sanitized_value="piis-telecom-consumer-app",
            ),
        ],
        "known_limitations": [
            "Runs against local synthetic fixtures; no outbound live enterprise tenant connection.",
            "Mutative operations (CREATE/UPDATE/CLOSE ticket) are architecturally barred by ReadOnlyBoundaryViolationError.",
            "Rate-limited to 25.0 req/s with 50-token burst protection.",
        ],
        "provenance_info": {
            "source_authority": "Synthesized ServiceNow REST API Spec (Portfolio Edition)",
            "verification_status": "CONTRACT_TESTED",
            "epistemic_classification": "LOCAL_SIMULATION",
        },
    },
    "ITSM-JIRA-01": {
        "name": "Jira Service Management Connector",
        "description": (
            "Ingestion bridge consuming Jira Service Management issue webhooks and translating "
            "Atlassian incident fields into PIIS canonical representations."
        ),
        "category": "ITSM",
        "provider_type": "Jira Service Management",
        "connection_mode": "LOCAL SIMULATION",
        "status_label": "LOCALLY VERIFIED (SIMULATED)",
        "capabilities": ["READ_ONLY_INGEST", "CANONICAL_NORMALIZATION", "SCHEMA_VALIDATION"],
        "authentication_model": "Atlassian API Token (Local Simulated Auth)",
        "config_fields": [
            IntegrationConfigField(
                name="cloud_url",
                field_type="url",
                description="Atlassian Cloud organization endpoint",
                sanitized_value="https://telecom.atlassian.net",
            ),
            IntegrationConfigField(
                name="project_key",
                field_type="string",
                description="Telecom Network Operations Center project key",
                sanitized_value="NOC",
            ),
            IntegrationConfigField(
                name="issue_type",
                field_type="string",
                description="Jira issue type representing network service outages",
                sanitized_value="Incident",
            ),
            IntegrationConfigField(
                name="api_user",
                field_type="string",
                description="Service account principal for webhook authorization",
                sanitized_value="telecom-ops-bot@internal.corp",
            ),
        ],
        "known_limitations": [
            "Inbound webhook normalization only; ticket status transitions are barred.",
            "Jira comments or assignments cannot be created from PIIS.",
            "Rate-limited to 20.0 req/s with 40-token burst protection.",
        ],
        "provenance_info": {
            "source_authority": "Atlassian Jira REST v3 Ingestion Contract",
            "verification_status": "CONTRACT_TESTED",
            "epistemic_classification": "LOCAL_SIMULATION",
        },
    },
    "ITSM-GENERIC-01": {
        "name": "Generic REST Ticketing Adapter",
        "description": (
            "Configurable JSON mapping adapter supporting arbitrary legacy OSS ticketing formats "
            "with dynamic field-to-canonical path resolution."
        ),
        "category": "ITSM",
        "provider_type": "Generic REST ITSM",
        "connection_mode": "LOCAL SIMULATION",
        "status_label": "LOCALLY VERIFIED (SIMULATED)",
        "capabilities": ["READ_ONLY_INGEST", "CANONICAL_NORMALIZATION", "DYNAMIC_MAPPING"],
        "authentication_model": "HMAC-SHA256 Header Signature (Local Key)",
        "config_fields": [
            IntegrationConfigField(
                name="ingest_endpoint",
                field_type="endpoint",
                description="HTTP POST ingress endpoint for proprietary systems",
                sanitized_value="/api/v1/incidents/ingest",
            ),
            IntegrationConfigField(
                name="schema_profile",
                field_type="string",
                description="Target schema normalization profile",
                sanitized_value="3GPP_TELECOM_GENERIC_V1",
            ),
            IntegrationConfigField(
                name="content_type",
                field_type="string",
                description="Expected payload encoding format",
                sanitized_value="application/json",
            ),
        ],
        "known_limitations": [
            "Passive ingestion receiver only; does not maintain persistent outbound sessions.",
            "Requires compliant envelope structure or payloads are directed to DLQ.",
        ],
        "provenance_info": {
            "source_authority": "PIIS Generic Ingestion Specification",
            "verification_status": "LOCALLY_VERIFIED",
            "epistemic_classification": "LOCAL_SIMULATION",
        },
    },
    "TELEM-PROM-01": {
        "name": "Prometheus KPI Metrics Scraper",
        "description": (
            "Telemetry polling adapter converting Prometheus query/vector metrics "
            "(VSWR, RSRP, SINR, BLER, PRB) into PIIS time-series observation frames."
        ),
        "category": "TELEMETRY",
        "provider_type": "Prometheus",
        "connection_mode": "REFERENCE IMPLEMENTATION",
        "status_label": "LOCALLY VERIFIED (REFERENCE)",
        "capabilities": ["METRIC_POLLING", "TIME_SERIES_NORMALIZATION", "UNIT_CONVERSION"],
        "authentication_model": "Mutual TLS / Internal Service Mesh (Simulated)",
        "config_fields": [
            IntegrationConfigField(
                name="prometheus_url",
                field_type="url",
                description="Internal Prometheus server scrape endpoint",
                sanitized_value="http://prometheus:9090",
            ),
            IntegrationConfigField(
                name="scrape_interval",
                field_type="interval",
                description="Telemetry sampling frequency",
                sanitized_value="15s",
            ),
            IntegrationConfigField(
                name="query_timeout",
                field_type="timeout",
                description="Prometheus HTTP API query timeout",
                sanitized_value="5000ms",
            ),
            IntegrationConfigField(
                name="metric_prefix",
                field_type="string",
                description="Prefix filter for telecommunication metric series",
                sanitized_value="ran_kpi_",
            ),
        ],
        "known_limitations": [
            "Executes vector queries against local reference metrics generators.",
            "No live gNodeB cell scrape connectivity in portfolio edition.",
        ],
        "provenance_info": {
            "source_authority": "Prometheus Metric Exposition Format / OpenMetrics",
            "verification_status": "CONTRACT_TESTED",
            "epistemic_classification": "REFERENCE_DATA",
        },
    },
    "TELEM-OTLP-01": {
        "name": "OpenTelemetry Metrics Ingress (OTLP)",
        "description": (
            "High-throughput OpenTelemetry metric streaming gateway normalizing OTLP JSON "
            "data points into canonical RAN/Core network telemetry series."
        ),
        "category": "TELEMETRY",
        "provider_type": "OpenTelemetry",
        "connection_mode": "REFERENCE IMPLEMENTATION",
        "status_label": "LOCALLY VERIFIED (REFERENCE)",
        "capabilities": ["OTLP_INGEST", "STREAM_NORMALIZATION", "ANOMALY_INPUT"],
        "authentication_model": "gRPC/HTTP Ingest Header (Local Secret)",
        "config_fields": [
            IntegrationConfigField(
                name="otlp_protocol",
                field_type="protocol",
                description="OpenTelemetry protocol transport variant",
                sanitized_value="OTLP/HTTP JSON v1",
            ),
            IntegrationConfigField(
                name="listen_port",
                field_type="port",
                description="Ingress collector HTTP listening port",
                sanitized_value="4318",
            ),
            IntegrationConfigField(
                name="compression",
                field_type="string",
                description="Permitted payload compression encodings",
                sanitized_value="gzip, none",
            ),
            IntegrationConfigField(
                name="batch_max_size",
                field_type="number",
                description="Maximum records evaluated in a single streaming burst",
                sanitized_value="512",
            ),
        ],
        "known_limitations": [
            "Evaluates structured local OTLP JSON metric frames.",
            "Distributed remote agent telemetry aggregation is simulated locally.",
        ],
        "provenance_info": {
            "source_authority": "OpenTelemetry Protocol v1.0 Specification",
            "verification_status": "CONTRACT_TESTED",
            "epistemic_classification": "REFERENCE_DATA",
        },
    },
    "ALARM-OSS-01": {
        "name": "OSS/NMS Multi-Vendor Alarm Broker",
        "description": (
            "Standard 3GPP 32.111-2 alarm ingestion broker with vendor-specific code translation "
            "for Nokia NetAct, Ericsson ENM, and Huawei U2000."
        ),
        "category": "OSS_NMS_ALARM",
        "provider_type": "Nokia NetAct / Ericsson OSS",
        "connection_mode": "LOCAL SIMULATION",
        "status_label": "LOCALLY VERIFIED (SIMULATED)",
        "capabilities": ["ALARM_INGEST", "3GPP_SEVERITY_NORMALIZATION", "CORRELATION_TAGGING"],
        "authentication_model": "Corba / Kafka SASL_PLAINTEXT (Simulated Broker)",
        "config_fields": [
            IntegrationConfigField(
                name="vendor_profile",
                field_type="string",
                description="Current active vendor translation dictionary",
                sanitized_value="NOKIA (3GPP Rel 17)",
            ),
            IntegrationConfigField(
                name="alarm_stream",
                field_type="stream",
                description="Telemetry Kafka broker topic for raw fault events",
                sanitized_value="raw_oss_alarms_topic",
            ),
            IntegrationConfigField(
                name="heartbeat_timeout",
                field_type="timeout",
                description="Broker connection timeout before degraded classification",
                sanitized_value="30s",
            ),
        ],
        "known_limitations": [
            "Synthesized alarm feed mimicking live 3GPP fault logs.",
            "Alarm clearance or active acknowledgment on physical NMS is permanently disallowed.",
        ],
        "provenance_info": {
            "source_authority": "3GPP TS 32.111-2 Fault Management Specification",
            "verification_status": "LOCALLY_VERIFIED",
            "epistemic_classification": "LOCAL_SIMULATION",
        },
    },
}


def _resolve_adapter_metadata(adapter: IntegrationAdapter) -> Dict[str, Any]:
    """Resolve full metadata for an adapter with safe fallback defaults."""
    aid = adapter.adapter_id
    if aid in _ADAPTER_METADATA:
        return _ADAPTER_METADATA[aid]

    # Dynamic fallback for arbitrary runtime-registered adapters
    cat = adapter.adapter_type.value if hasattr(adapter.adapter_type, "value") else str(adapter.adapter_type)
    return {
        "name": f"{adapter.source_system} Adapter",
        "description": f"Standard read-only {cat} integration adapter for {adapter.source_system}.",
        "category": cat,
        "provider_type": adapter.source_system,
        "connection_mode": "LOCAL SIMULATION",
        "status_label": "LOCALLY VERIFIED (SIMULATED)",
        "capabilities": ["READ_ONLY_INGEST", "CANONICAL_NORMALIZATION"],
        "authentication_model": "Local Reference Authentication",
        "config_fields": [
            IntegrationConfigField(
                name="source_system",
                field_type="string",
                description="Registered source system identifier",
                sanitized_value=adapter.source_system,
            ),
        ],
        "known_limitations": [
            "Read-only boundary strictly enforced.",
            "Simulated environment with no live production network connectivity.",
        ],
        "provenance_info": {
            "source_authority": "PIIS Runtime Adapter Contract",
            "verification_status": "LOCALLY_VERIFIED",
            "epistemic_classification": "LOCAL_SIMULATION",
        },
    }


# ---------------------------------------------------------------------------
# DLQ Payload Sanitization & Truth-in-Health Protections
# ---------------------------------------------------------------------------

SENSITIVE_FIELD_PATTERNS = {
    "password",
    "token",
    "secret",
    "authorization",
    "private_key",
    "privatekey",
    "credential",
    "apikey",
    "api_key",
    "access_token",
    "client_secret",
    "auth_header",
    "bearer_token",
    "jwt",
    "session_key",
    "cookie",
}


def _sanitize_dict_payload(data: Any) -> Any:
    """Recursively redact sensitive credentials, tokens, and secrets in nested structures."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sens in k_lower for sens in SENSITIVE_FIELD_PATTERNS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = _sanitize_dict_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_dict_payload(item) for item in data]
    return data


def _prepare_sanitized_dlq_payload(
    payload: Dict[str, Any], max_bytes: int = 32768
) -> Tuple[Dict[str, Any], int, bool]:
    """Sanitize sensitive keys and enforce strict bounding on quarantined payload sizes.
    
    Returns: (sanitized_payload, raw_size_bytes, is_redacted)
    """
    raw_json = json.dumps(payload, default=str)
    raw_size = len(raw_json.encode("utf-8"))

    sanitized = _sanitize_dict_payload(payload)
    is_redacted = True

    sanitized_json = json.dumps(sanitized, default=str)
    if len(sanitized_json.encode("utf-8")) > max_bytes:
        truncated_preview = sanitized_json[:1024]
        return {
            "_truncated": True,
            "_original_size_bytes": raw_size,
            "_truncation_notice": f"Payload truncated: exceeded {max_bytes} bytes security boundary",
            "_preview": truncated_preview + "...[TRUNCATED]",
        }, raw_size, is_redacted

    return sanitized, raw_size, is_redacted


def _compute_health_freshness(last_heartbeat: Optional[str]) -> str:
    """Compute heartbeat freshness without inventing availability."""
    if not last_heartbeat:
        return "UNKNOWN"
    try:
        hb_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - hb_dt).total_seconds()
        if age_seconds < 120:
            return "FRESH"
        elif age_seconds < 600:
            return "STALE"
        else:
            return "EXPIRED"
    except Exception:
        return "UNKNOWN"


def _map_operational_status(health: Optional[Any]) -> str:
    """Map adapter health to UI operational status under strict truth-in-health semantics.
    
    If health is missing or last_heartbeat is absent, never report AVAILABLE.
    """
    if health is None:
        return "UNAVAILABLE"

    # Support passing either HealthState directly or an AdapterHealth object
    if isinstance(health, HealthState):
        state = health
        last_hb = "PRESENT"
    else:
        state = getattr(health, "state", None)
        last_hb = getattr(health, "last_heartbeat", None)

    if not last_hb:
        return "DEGRADED"

    if state == HealthState.HEALTHY:
        return "AVAILABLE"
    if state == HealthState.DEGRADED:
        return "DEGRADED"
    return "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Workspace Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[IntegrationRegistryItem],
    summary="List Registered Integration Adapters",
    description="Inspect configured enterprise integration adapters, connection modes, status labels, and rate limits.",
)
async def list_integrations(
    category: Optional[str] = Query(default=None, description="Filter by category (ITSM, TELEMETRY, OSS_NMS_ALARM)"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status (AVAILABLE, DEGRADED, UNAVAILABLE)"),
    search: Optional[str] = Query(default=None, description="Case-insensitive search string across name, id, and provider"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> List[IntegrationRegistryItem]:
    adapters = pipeline.list_adapters()
    items: List[IntegrationRegistryItem] = []

    for health in adapters:
        adapter = pipeline._adapters.get(health.adapter_id)
        if not adapter:
            continue
        meta = _resolve_adapter_metadata(adapter)
        op_status = _map_operational_status(health)
        freshness = _compute_health_freshness(health.last_heartbeat)

        # Filters
        if category and meta["category"].upper() != category.strip().upper():
            continue
        if status_filter and op_status.upper() != status_filter.strip().upper():
            continue
        if search:
            q = search.strip().lower()
            target_str = f"{adapter.adapter_id} {meta['name']} {meta['provider_type']} {meta['description']}".lower()
            if q not in target_str:
                continue

        items.append(
            IntegrationRegistryItem(
                integration_id=adapter.adapter_id,
                name=meta["name"],
                category=meta["category"],
                provider_type=meta["provider_type"],
                adapter_class=type(adapter).__name__,
                connection_mode=meta["connection_mode"],
                operational_status=op_status,
                status_label=meta["status_label"],
                capabilities=meta["capabilities"],
                data_direction="INBOUND_ONLY",
                rate_limit_rps=float(getattr(adapter.rate_limiter, "rate", 20.0)),
                last_heartbeat=health.last_heartbeat,
                last_successful_ingestion=health.last_successful_ingestion,
                consecutive_failures=health.consecutive_failures,
                error_message=health.error_message,
                external_connectivity="NOT_CONNECTED (LOCAL SIMULATION / REFERENCE ONLY)",
                health_freshness=freshness,
            )
        )

    return items


@router.get(
    "/summary",
    response_model=IntegrationSummaryResponse,
    summary="Integration Ecosystem Summary Metrics",
    description="Aggregate operational statistics, simulated vs reference adapter breakdown, DLQ counts, and readiness.",
)
async def get_integrations_summary(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> IntegrationSummaryResponse:
    adapters = pipeline.list_adapters()
    total = len(adapters)
    avail = sum(1 for a in adapters if a.state == HealthState.HEALTHY)
    degraded = sum(1 for a in adapters if a.state == HealthState.DEGRADED)
    unavail = sum(1 for a in adapters if a.state == HealthState.UNHEALTHY)

    sim_count = 0
    ref_count = 0
    categories_breakdown: Dict[str, int] = {}
    last_hb: Optional[str] = None

    for a in adapters:
        ad = pipeline._adapters.get(a.adapter_id)
        if ad:
            meta = _resolve_adapter_metadata(ad)
            cat = meta["category"]
            categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1
            if meta["connection_mode"] == "REFERENCE IMPLEMENTATION":
                ref_count += 1
            else:
                sim_count += 1
        if not last_hb or (a.last_heartbeat and a.last_heartbeat > last_hb):
            last_hb = a.last_heartbeat

    overall_readiness = "OPERATIONAL" if (degraded == 0 and unavail == 0) else "DEGRADED"

    return IntegrationSummaryResponse(
        total_adapters=total,
        available_count=avail,
        degraded_count=degraded,
        unavailable_count=unavail,
        simulated_count=sim_count,
        reference_count=ref_count,
        last_health_check=last_hb,
        overall_readiness=overall_readiness,
        total_dlq_count=pipeline.dlq.count(),
        total_ingested_events=pipeline.count_ingested_events(),
        categories_breakdown=categories_breakdown,
        epistemic_status="REFERENCE_DATA",
    )


@router.get(
    "/data-flow",
    response_model=DataFlowResponse,
    summary="Pipeline Data Flow Topology",
    description="Inspect the 8 end-to-end pipeline stages from simulated source ingress to the Human Review Hub.",
)
async def get_data_flow_topology(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> DataFlowResponse:
    dlq_count = pipeline.dlq.count()
    active_adapters = len(pipeline._adapters)
    ingested_events = pipeline.count_ingested_events()

    stages = [
        DataFlowStageItem(
            stage_id="STAGE_SOURCES",
            title="Simulated Telecom Sources",
            subtitle="Synthetic Feeds & Replays",
            status="HEALTHY",
            epistemic_badge="SIMULATED_DATA",
            description="Mock enterprise ITSM, OSS alarm brokers, and RAN telemetry time-series generators.",
            is_simulated=True,
            order=1,
            active_count=active_adapters,
        ),
        DataFlowStageItem(
            stage_id="STAGE_ADAPTERS",
            title="Integration Adapter Boundary",
            subtitle="Read-Only Ingestion Gateways",
            status="HEALTHY",
            epistemic_badge="OBSERVED_FACT",
            description="Strict read-only protocol adapters enforcing safe HTTP methods (GET/HEAD) and schema translation.",
            is_simulated=False,
            order=2,
            active_count=active_adapters,
        ),
        DataFlowStageItem(
            stage_id="STAGE_SECURITY",
            title="Security & Defanging Gate",
            subtitle="Sanitization & Input Validation",
            status="HEALTHY",
            epistemic_badge="DETERMINISTIC_RULE",
            description="Defangs command injections, script payloads, and path traversals before memory admission.",
            is_simulated=False,
            order=3,
            active_count=ingested_events,
        ),
        DataFlowStageItem(
            stage_id="STAGE_NORMALIZATION",
            title="Canonical Normalization",
            subtitle="Unified Telecommunications Schema",
            status="HEALTHY",
            epistemic_badge="CANONICAL_MAPPING",
            description="Standardizes heterogeneous vendor payloads into 3GPP-aligned incident, alarm, and KPI contracts.",
            is_simulated=False,
            order=4,
            active_count=pipeline.count_incidents(),
        ),
        DataFlowStageItem(
            stage_id="STAGE_DEDUPLICATION",
            title="Correlation & Idempotency",
            subtitle="Signature Deduplication Engine",
            status="HEALTHY",
            epistemic_badge="DETERMINISTIC_RULE",
            description="Computes SHA-256 fingerprint signatures to prevent duplicate alert storms and reconcile identical faults.",
            is_simulated=False,
            order=5,
            active_count=ingested_events,
        ),
        DataFlowStageItem(
            stage_id="STAGE_DLQ",
            title="Dead-Letter Quarantine",
            subtitle="Failed Payload Isolation",
            status="HEALTHY" if dlq_count == 0 else "WARNING",
            epistemic_badge="AUDIT_RECOVERY",
            description="Isolates malformed or unparseable payloads for operator inspection and audited replay.",
            is_simulated=False,
            order=6,
            active_count=dlq_count,
        ),
        DataFlowStageItem(
            stage_id="STAGE_PROVENANCE",
            title="Cryptographic Provenance",
            subtitle="SHA-256 Lineage & Immutability",
            status="HEALTHY",
            epistemic_badge="CRYPTOGRAPHIC_PROOF",
            description="Attaches immutable source lineage metadata, envelope UUIDs, and observation timestamps.",
            is_simulated=False,
            order=7,
            active_count=pipeline.count_incidents(),
        ),
        DataFlowStageItem(
            stage_id="STAGE_REVIEW",
            title="Human Review Hub",
            subtitle="Advisory Decision Support & Governance",
            status="HEALTHY",
            epistemic_badge="HUMAN_GOVERNANCE",
            description="Delivers synthesized telecom intelligence to human incident commanders with zero autonomous mutation.",
            is_simulated=False,
            order=8,
            active_count=1,
        ),
    ]

    edges = [
        DataFlowEdgeItem(source="STAGE_SOURCES", target="STAGE_ADAPTERS", label="Raw Envelopes"),
        DataFlowEdgeItem(source="STAGE_ADAPTERS", target="STAGE_SECURITY", label="Envelopes Ingested"),
        DataFlowEdgeItem(source="STAGE_SECURITY", target="STAGE_NORMALIZATION", label="Sanitized Payloads"),
        DataFlowEdgeItem(source="STAGE_NORMALIZATION", target="STAGE_DEDUPLICATION", label="Canonical Records"),
        DataFlowEdgeItem(source="STAGE_DEDUPLICATION", target="STAGE_DLQ", label="Rejected Payloads"),
        DataFlowEdgeItem(source="STAGE_DEDUPLICATION", target="STAGE_PROVENANCE", label="Correlated Events"),
        DataFlowEdgeItem(source="STAGE_PROVENANCE", target="STAGE_REVIEW", label="Audited Intelligence"),
    ]

    return DataFlowResponse(
        stages=stages,
        edges=edges,
        active_adapters_count=active_adapters,
        quarantined_items_count=dlq_count,
        pipeline_health="HEALTHY",
        epistemic_classification="REFERENCE_DATA",
    )


@router.get(
    "/activity",
    response_model=PaginatedResponse[IntegrationActivityItem],
    summary="Integration Activity Stream",
    description="Paginated audit stream of integration events, health checks, ingestion outcomes, and dead-letter actions.",
)
async def list_integration_activity(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    integration_id: Optional[str] = Query(default=None, description="Filter by integration / adapter ID"),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status (SUCCESS, HEALTHY, FAILED)"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> PaginatedResponse[IntegrationActivityItem]:
    events, total = pipeline.list_activity(
        limit=limit,
        offset=offset,
        adapter_id=integration_id,
        event_type=event_type,
        status=status_filter,
    )

    items = [
        IntegrationActivityItem(
            event_id=e["event_id"],
            timestamp=e["timestamp"],
            adapter_id=e["adapter_id"],
            source_system=e["source_system"],
            event_type=e["event_type"],
            status=e["status"],
            details=e["details"],
            canonical_id=e.get("canonical_id"),
            envelope_id=e.get("envelope_id"),
            epistemic_tag=e.get("epistemic_tag", "SIMULATED_EVENT"),
        )
        for e in events
    ]

    return PaginatedResponse(
        items=items,
        total_count=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/health",
    response_model=List[AdapterHealthResponse],
    summary="List Adapter Health States",
    description="Inspect operational connectivity, heartbeat, and failure counters for all registered integration adapters.",
)
async def list_adapter_health(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> List[AdapterHealthResponse]:
    health_list = pipeline.list_adapters()
    return [
        AdapterHealthResponse(
            adapter_id=h.adapter_id,
            adapter_type=h.adapter_type.value,
            state=h.state.value,
            last_heartbeat=h.last_heartbeat,
            last_successful_ingestion=h.last_successful_ingestion,
            consecutive_failures=h.consecutive_failures,
            error_message=h.error_message,
        )
        for h in health_list
    ]


@router.get(
    "/dead-letter",
    response_model=PaginatedResponse[DeadLetterItemResponse],
    summary="List Dead-Letter Items",
    description="Inspect unparseable or rejected ingestion events routed to the dead-letter queue with server-side payload redaction.",
)
async def list_dead_letter_items(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_roles(ApplicationRole.PIIS_ADMIN, ApplicationRole.INCIDENT_MANAGER)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> PaginatedResponse[DeadLetterItemResponse]:
    items = pipeline.dlq.list_items(limit=limit, offset=offset)
    total = pipeline.dlq.count()

    res_items = []
    for it in items:
        sanitized_payload, payload_size, is_redacted = _prepare_sanitized_dlq_payload(it.envelope.raw_payload)
        res_items.append(
            DeadLetterItemResponse(
                item_id=it.item_id,
                envelope_id=it.envelope.envelope_id,
                source_system=it.envelope.source_system,
                failure_reason=it.failure_reason,
                error_details=it.error_details,
                attempt_count=it.attempt_count,
                first_failed_at=it.first_failed_at,
                last_failed_at=it.last_failed_at,
                raw_payload=sanitized_payload,
                is_redacted=is_redacted,
                payload_size_bytes=payload_size,
                epistemic_classification="QUARANTINED_UNTRUSTED",
            )
        )

    return PaginatedResponse(
        items=res_items,
        total_count=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/dead-letter/{item_id}/retry",
    response_model=Dict[str, Any],
    summary="Retry Dead-Letter Envelope",
    description="Attempt re-ingestion of a dead-letter item through the unified pipeline.",
)
async def retry_dead_letter_item(
    item_id: str,
    human: AuthenticatedPrincipal = Depends(require_human_operator),
    principal: AuthenticatedPrincipal = Depends(require_roles(ApplicationRole.PIIS_ADMIN)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> Dict[str, Any]:
    dlq_item = pipeline.dlq.get(item_id)
    if not dlq_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dead-letter item '{item_id}' not found",
        )

    res = pipeline.replay_dead_letter(item_id)
    if res.status.value in {"SUCCESS", "DUPLICATE"}:
        return {
            "status": "RETRY_SUCCEEDED",
            "item_id": item_id,
            "canonical_id": res.canonical_id,
            "message": res.message,
            "replay_scope": "LOCAL_IN_MEMORY_PIPELINE_ONLY",
            "external_mutation_performed": False,
            "audit_ledger_mutation_performed": False,
        }

    return {
        "status": "RETRY_FAILED",
        "item_id": item_id,
        "error": res.error,
        "attempts": dlq_item.attempt_count,
        "replay_scope": "LOCAL_IN_MEMORY_PIPELINE_ONLY",
        "external_mutation_performed": False,
        "audit_ledger_mutation_performed": False,
    }


@router.get(
    "/{integration_id}",
    response_model=IntegrationDetailResponse,
    summary="Get Integration Adapter Specification",
    description="Retrieve comprehensive adapter configuration, capabilities, read-only boundary constraints, and recent activity. All secrets are strictly omitted.",
)
async def get_integration_detail(
    integration_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> IntegrationDetailResponse:
    adapter = pipeline._adapters.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration adapter '{integration_id}' not registered in unified pipeline",
        )

    meta = _resolve_adapter_metadata(adapter)
    health = adapter.get_health()
    op_status = _map_operational_status(health)

    recent_events, _ = pipeline.list_activity(limit=10, offset=0, adapter_id=integration_id)

    health_response = AdapterHealthResponse(
        adapter_id=health.adapter_id,
        adapter_type=health.adapter_type.value,
        state=health.state.value,
        last_heartbeat=health.last_heartbeat,
        last_successful_ingestion=health.last_successful_ingestion,
        consecutive_failures=health.consecutive_failures,
        error_message=health.error_message,
    )

    return IntegrationDetailResponse(
        integration_id=adapter.adapter_id,
        name=meta["name"],
        description=meta["description"],
        category=meta["category"],
        provider_type=meta["provider_type"],
        adapter_class=type(adapter).__name__,
        connection_mode=meta["connection_mode"],
        operational_status=op_status,
        status_label=meta["status_label"],
        capabilities=meta["capabilities"],
        data_direction="INBOUND_ONLY",
        supported_operations=sorted(list(adapter.ALLOWED_OPERATIONS)),
        forbidden_operations=sorted(list(adapter.FORBIDDEN_OPERATIONS)),
        read_only_boundary_enforced=True,
        authentication_model=meta["authentication_model"],
        required_config_fields=meta["config_fields"],
        health=health_response,
        recent_activity=recent_events,
        known_limitations=meta["known_limitations"],
        provenance_info=meta["provenance_info"],
        external_connectivity="NOT_CONNECTED (LOCAL SIMULATION / REFERENCE ONLY)",
    )


@router.get(
    "/{integration_id}/health",
    response_model=AdapterHealthResponse,
    summary="Get Specific Adapter Health",
    description="Inspect operational health and heartbeat for an individual registered adapter.",
)
async def get_single_adapter_health(
    integration_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> AdapterHealthResponse:
    adapter = pipeline._adapters.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration adapter '{integration_id}' not found",
        )

    h = adapter.get_health()
    return AdapterHealthResponse(
        adapter_id=h.adapter_id,
        adapter_type=h.adapter_type.value,
        state=h.state.value,
        last_heartbeat=h.last_heartbeat,
        last_successful_ingestion=h.last_successful_ingestion,
        consecutive_failures=h.consecutive_failures,
        error_message=h.error_message,
    )
