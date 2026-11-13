# M7 Enterprise Integration Status & Qualification Matrix

## Production Incident Intelligence System (PIIS — Telecom Edition)
**Milestone:** M7 Portfolio Edition (Release Candidate v1.0.0-rc2)  
**Standard:** Transparent Enterprise Integration Qualification  
**Scope:** Strictly Read-Only Decision Support

---

## 1. Enterprise Integration Qualification Matrix

PIIS adheres to a strict policy of **honest qualification labeling**. Simulated or locally verified components are never represented as live enterprise integrations. Every integration adapter is evaluated across six criteria:

| Integration System | Adapter Class | Operational Qualification Status | Canonical Schema Compliance | Simulated Capabilities | Live Enterprise Gap | Path to Production Integration |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ServiceNow ITSM** | `ServiceNowAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | JSON Schema Draft 2020-12 (`incident.schema.json`). Priority (`1`–`5`) mapped to canonical severity (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`). | Realistic incident generation, multi-tenant sys_ids, CMDB CI linking, priority mapping, pagination, simulated HTTP 429 rate limits. | No active ServiceNow production tenant subscription; OAuth2 Client Credentials flow tested via local token verifier. | 1. Acquire ServiceNow dev tenant.<br>2. Configure OAuth2 Client Credentials grant.<br>3. Map custom telecom fields (`u_network_domain`, `u_affected_subscribers`). |
| **Jira Service Management (JSM)** | `JiraServiceManagementAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | JSON Schema Draft 2020-12 (`incident.schema.json`). Atlassian Document Format (ADF) parser extracts clean text. | JQL search query simulation (`project = NOC`), ADF rich text parsing, priority translation (`High` -> `MAJOR`), issue key mapping. | No corporate Jira Cloud instance; webhook signature validation tested via HMAC mock. | 1. Connect to Jira Cloud instance.<br>2. Configure Jira automation webhook on incident creation.<br>3. Store Atlassian API token in KMS. |
| **Generic REST / Webhook Source** | `GenericRestITSMAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | Configurable field mappings to canonical incident schema. | Flexible key mapping (`ticket_num`, `telecom_layer`, `urgency_level`), arbitrary JSON envelope unwrapping. | Dependent on proprietary customer NOC ticketing schemas. | 1. Provide field mapping dictionary in configuration.<br>2. Configure mutual TLS (mTLS) endpoint. |
| **Prometheus / Alertmanager** | `PrometheusAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | JSON Schema Draft 2020-12 (`telemetry.schema.json`). Telecom unit auto-resolution (`vswr` -> `ratio`, `rsrp` -> `dBm`). | Prometheus HTTP API vector query simulation (`GET /api/v1/query`), dynamic oscillating telemetry generation, instance label extraction. | No live Prometheus server querying physical eNodeB/gNodeB base stations. | 1. Connect Prometheus adapter URL to production PromQL endpoint.<br>2. Configure scrape interval & vector evaluation rules. |
| **OpenTelemetry (OTLP)** | `OpenTelemetryMetricsAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | JSON Schema Draft 2020-12 (`telemetry.schema.json`). Nanosecond UNIX epoch timestamp normalization. | OTLP JSON gauge and sum metrics batch ingestion, `service.name` and attribute extraction, packet loss ratio parsing. | Telemetry emitted from mock UPF session generator rather than live 5G User Plane Function. | 1. Deploy OpenTelemetry Collector with OTLP HTTP/gRPC receiver.<br>2. Route collector pipeline to PIIS `/api/v1/incidents/ingest`. |
| **Telecom OSS/NMS Alarm Feed** | `OSSAlarmAdapter` | **LOCALLY VERIFIED**<br>**SIMULATED**<br>**CONTRACT TESTED**<br>**EXTERNALLY UNVERIFIED** | JSON Schema Draft 2020-12 (`alarm.schema.json`). Full 3GPP 32.111-2 lifecycle states (`ACTIVE`, `ACKNOWLEDGED`, `CLEARED`). | Multi-vendor alarm code mapping (Nokia `7100` -> `ALM-RAN-VSWR-HIGH`, Ericsson `A102`), VSWR feeder fault generator, core drop generator. | Alarms generated in memory; no physical connection to live Ericsson ENM, Nokia NetAct, or Huawei U2000. | 1. Connect Kafka consumer or REST webhook to OSS alarm bus.<br>2. Expand vendor code translation dictionary. |

---

## 2. Capability Flags & Read-Only Enforcement

Every adapter in PIIS defines explicit, testable capability flags:

```python
class IntegrationAdapter(ABC):
    READ_ONLY: bool = True
    MUTATION_ALLOWED: bool = False
    SAFE_HTTP_METHODS: frozenset[str] = frozenset(["GET", "HEAD"])
    DEFAULT_STATUS_LABELS: tuple[str, ...] = (
        IntegrationStatusLabel.LOCALLY_VERIFIED.value,
        IntegrationStatusLabel.SIMULATED.value,
        IntegrationStatusLabel.CONTRACT_TESTED.value,
        IntegrationStatusLabel.EXTERNALLY_UNVERIFIED.value,
    )
```

### Safety Prohibitions:
- Outbound mutative HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) raise `ReadOnlyBoundaryViolationError`.
- Forbidden operational tasks (`CREATE_TICKET`, `UPDATE_TICKET`, `CLOSE_TICKET`, `EXECUTE_COMMAND`, `MODIFY_CONFIG`, `REBOOT_ELEMENT`) raise `ReadOnlyBoundaryViolationError`.
- Allowed tasks are strictly read-only and ingestive: `["NORMALIZE", "HEALTH_CHECK", "READ_ONLY_INGEST"]`.

---

## 3. Resilience and Failure Mode Handling

All adapters have been verified against realistic enterprise failure modes:

1. **HTTP 429 Rate Limiting:**
   - Adapters enforce token-bucket rate limiters.
   - When requests exceed limits, payloads are safely rejected with `IngestionStatus.RATE_LIMITED` and queued into the Dead-Letter Queue (DLQ).
2. **Schema Invalidation:**
   - Payloads missing mandatory fields or violating schema constraints fail closed with `IngestionStatus.VALIDATION_FAILED` and are routed to DLQ for operator inspection.
3. **Idempotency & Alert Storms:**
   - Ingesting identical events (same source system and event ID) returns `IngestionStatus.DUPLICATE` with `is_duplicate=True` and matches the existing canonical record, preventing duplicate incident creation.
