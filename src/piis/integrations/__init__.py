"""PIIS Enterprise Integration Framework."""

from piis.integrations.contracts import (
    AdapterHealth,
    DeadLetterItem,
    HealthState,
    IngestionEnvelope,
    IngestionResult,
    IngestionStatus,
    IntegrationAdapter,
    IntegrationStatusLabel,
    IntegrationType,
    RateLimiter,
    ReadOnlyBoundaryViolationError,
)
from piis.integrations.itsm.servicenow import ServiceNowAdapter
from piis.integrations.itsm.jira import JiraServiceManagementAdapter
from piis.integrations.itsm.generic_rest import GenericRestITSMAdapter
from piis.integrations.telemetry.prometheus import PrometheusAdapter
from piis.integrations.telemetry.otlp import OpenTelemetryMetricsAdapter
from piis.integrations.alarms.oss_nms import AlarmLifecycleState, OSSAlarmAdapter

__all__ = [
    "AdapterHealth",
    "DeadLetterItem",
    "HealthState",
    "IngestionEnvelope",
    "IngestionResult",
    "IngestionStatus",
    "IntegrationAdapter",
    "IntegrationStatusLabel",
    "IntegrationType",
    "RateLimiter",
    "ReadOnlyBoundaryViolationError",
    "ServiceNowAdapter",
    "JiraServiceManagementAdapter",
    "GenericRestITSMAdapter",
    "PrometheusAdapter",
    "OpenTelemetryMetricsAdapter",
    "OSSAlarmAdapter",
    "AlarmLifecycleState",
]
