"""Telecom operations application role hierarchy and permission matrix for PIIS."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class ApplicationRole(str, Enum):
    """Formal telecom operations application roles for PIIS."""
    NOC_L1 = "NOC_L1"
    NOC_L2 = "NOC_L2"
    NOC_L3 = "NOC_L3"
    INCIDENT_MANAGER = "INCIDENT_MANAGER"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"
    PIIS_ADMIN = "PIIS_ADMIN"
    SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL"


# Detailed permission definitions
class Permission(str, Enum):
    """Granular action permissions enforced across the API."""
    INGEST_EVENTS = "ingest:events"
    VIEW_INCIDENTS = "view:incidents"
    VIEW_INVESTIGATIONS = "view:investigations"
    TRIGGER_INVESTIGATION = "trigger:investigation"
    VIEW_TELEMETRY = "view:telemetry"
    VIEW_ALARMS = "view:alarms"
    VIEW_EVIDENCE = "view:evidence"
    VIEW_RECOMMENDATIONS = "view:recommendations"
    APPROVE_LOW_RISK_REVIEW = "review:approve_low_risk"
    APPROVE_MEDIUM_RISK_REVIEW = "review:approve_medium_risk"
    APPROVE_HIGH_RISK_REVIEW = "review:approve_high_risk"
    VIEW_AUDIT_LOGS = "view:audit_logs"
    VERIFY_AUDIT_LEDGER = "verify:audit_ledger"
    MANAGE_INTEGRATIONS = "manage:integrations"
    MANAGE_KEYS = "manage:keys"


# Role-to-Permissions Mapping enforcing least privilege
ROLE_PERMISSIONS: Dict[ApplicationRole, Set[Permission]] = {
    ApplicationRole.NOC_L1: {
        Permission.INGEST_EVENTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.TRIGGER_INVESTIGATION,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_ALARMS,
        Permission.VIEW_EVIDENCE,
        Permission.VIEW_RECOMMENDATIONS,
        Permission.APPROVE_LOW_RISK_REVIEW,
    },
    ApplicationRole.NOC_L2: {
        Permission.INGEST_EVENTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.TRIGGER_INVESTIGATION,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_ALARMS,
        Permission.VIEW_EVIDENCE,
        Permission.VIEW_RECOMMENDATIONS,
        Permission.APPROVE_LOW_RISK_REVIEW,
        Permission.APPROVE_MEDIUM_RISK_REVIEW,
    },
    ApplicationRole.NOC_L3: {
        Permission.INGEST_EVENTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.TRIGGER_INVESTIGATION,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_ALARMS,
        Permission.VIEW_EVIDENCE,
        Permission.VIEW_RECOMMENDATIONS,
        Permission.APPROVE_LOW_RISK_REVIEW,
        Permission.APPROVE_MEDIUM_RISK_REVIEW,
        Permission.APPROVE_HIGH_RISK_REVIEW,
    },
    ApplicationRole.INCIDENT_MANAGER: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_ALARMS,
        Permission.VIEW_EVIDENCE,
        Permission.VIEW_RECOMMENDATIONS,
        Permission.APPROVE_LOW_RISK_REVIEW,
        Permission.APPROVE_MEDIUM_RISK_REVIEW,
        Permission.APPROVE_HIGH_RISK_REVIEW,
        Permission.VIEW_AUDIT_LOGS,
    },
    ApplicationRole.SECURITY_AUDITOR: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.VERIFY_AUDIT_LEDGER,
    },
    ApplicationRole.PIIS_ADMIN: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_INVESTIGATIONS,
        Permission.MANAGE_INTEGRATIONS,
        Permission.MANAGE_KEYS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.VERIFY_AUDIT_LEDGER,
    },
    ApplicationRole.SERVICE_PRINCIPAL: {
        Permission.INGEST_EVENTS,
        Permission.VIEW_INCIDENTS,
    },
}
