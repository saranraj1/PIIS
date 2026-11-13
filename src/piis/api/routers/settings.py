"""Settings and configuration workspace router for PIIS."""

from __future__ import annotations

import os
from typing import Dict
from fastapi import APIRouter, Depends

from piis.api.schemas import (
    DocumentationCatalogItem,
    SettingsSystemInfoResponse,
)
from piis.auth import AuthenticatedPrincipal, Permission, require_permissions
from piis.retrieval.engine import DETERMINISTIC_SOP_MAP

router = APIRouter(prefix="/api/v1/settings", tags=["Settings & Configuration"])


@router.get(
    "/system-info",
    response_model=SettingsSystemInfoResponse,
    summary="Application System Configuration & Metadata",
    description=(
        "Retrieve authoritative application-level configuration, metadata, "
        "operational boundaries, and documentation catalog. Strictly read-only."
    ),
)
async def get_system_info(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
) -> SettingsSystemInfoResponse:
    """Return verified application system metadata and locked operational boundaries."""
    env = os.environ.get("PIIS_ENVIRONMENT", "development").lower()

    return SettingsSystemInfoResponse(
        application_name="Production Incident Intelligence System",
        application_edition="Telecom Edition (Portfolio Release)",
        core_version="1.0.0-rc2",
        api_version="1.0.0",
        active_milestone="PRODUCTION_READY",
        environment=env,
        operational_mode="read_only_decision_support",
        telecom_domains=["RAN", "Transport", "Core", "IMS", "Cloud"],
        auth_mode="IN_MEMORY_JWT_OIDC",
        rbac_enforced=True,
        service_principals_barred=True,
        retrieval_models={
            "lexical_index": "BM25 Okapi (In-Memory Index)",
            "dense_bi_encoder": "all-MiniLM-L6-v2 (Offline Local Fallback)",
            "deterministic_sop_rules": f"{len(DETERMINISTIC_SOP_MAP)} Registered Rules",
            "anomaly_detectors": "3-Sigma Z-Score & Isolation Forest",
        },
        operational_boundaries={
            "network_mutations_allowed": False,
            "production_commands_allowed": False,
            "ticket_closures_allowed": False,
            "external_egress_allowed": False,
            "autonomous_remediation_allowed": False,
            "secret_exposure_allowed": False,
        },
        documentation_catalog=[
            DocumentationCatalogItem(
                title="System Release Notes",
                path="docs/m7/M7_PORTFOLIO_RELEASE_NOTES.md",
                category="PORTFOLIO",
                description="Release notes and architecture for Telecom Edition v1.0.0.",
            ),
            DocumentationCatalogItem(
                title="Security & Reliability Audit",
                path="docs/ui/UI8_1_INDEPENDENT_AUDIT.md",
                category="VERIFICATION",
                description="Adversarial runtime health, security, and regression audit.",
            ),
            DocumentationCatalogItem(
                title="Configuration & Display Guide",
                path="docs/ui/UI9_RECONNAISSANCE.md",
                category="ARCHITECTURE",
                description="Production configuration and operational preferences guide.",
            ),
            DocumentationCatalogItem(
                title="System Architecture Specification",
                path="docs/ui/UI9_SETTINGS_WORKSPACE.md",
                category="SPECIFICATION",
                description="Settings and configuration workspace design and verification.",
            ),
        ],
        epistemic_classification="VERIFIED_CONFIGURATION",
    )


@router.get(
    "/preferences-defaults",
    summary="NOC Factory Default Display Preferences",
    description="Retrieve standardized default preferences for telecom NOC operators.",
)
async def get_preferences_defaults(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
) -> Dict[str, object]:
    """Return standard NOC factory display preferences."""
    return {
        "theme": "dark",
        "density": "comfortable",
        "timezone": "UTC",
        "time_format": "24H",
        "page_size": 25,
        "refresh_interval_seconds": 30,
        "persistence_target": "localStorage",
        "epistemic_classification": "NOC_FACTORY_DEFAULTS",
    }
