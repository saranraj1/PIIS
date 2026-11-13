"""Incident ingestion, investigation, retrieval, and review endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from piis.api.schemas import (
    DiagnosticRecommendationItem,
    IncidentIngestRequest,
    IncidentIngestResponse,
    InvestigationHypothesisItem,
    InvestigationResponse,
    PaginatedResponse,
    ReviewHistoryItem,
    ReviewQueueItem,
    ReviewQueueResponse,
    ReviewResponse,
    ReviewSubmissionRequest,
)
from piis.auth import (
    ApplicationRole,
    AuthenticatedPrincipal,
    Permission,
    require_human_operator,
    require_permissions,
)
from piis.auth.dependencies import security_scheme
from fastapi.security import HTTPAuthorizationCredentials
from piis.integrations.contracts import IngestionEnvelope, IngestionStatus
from piis.investigation.approval import (
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    InsufficientPrivilegeError,
)
from piis.observability.logging import get_correlation_id
from piis.observability.metrics import (
    record_duplicate,
    record_failure,
    record_ingestion,
    record_investigation,
    record_review,
)
from piis.observability.tracing import trace_span
from piis.pipeline.unified import UnifiedIngestionPipeline

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents & Investigations"])

# Explicit evidence freshness and clock-skew boundaries (UI-5.1.4)
EVIDENCE_MAX_AGE_SECONDS: float = 3600.0  # 1 hour per TELEMETRY_ANOMALY freshness policy
CLOCK_SKEW_TOLERANCE_SECONDS: float = 60.0  # 60s max allowed future clock skew tolerance

# Global singletons managed by app lifecycle
_pipeline: Optional[UnifiedIngestionPipeline] = None
_workflow: Optional[HumanApprovalWorkflow] = None


def get_pipeline() -> UnifiedIngestionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = UnifiedIngestionPipeline()
        from piis.integrations import (
            GenericRestITSMAdapter,
            JiraServiceManagementAdapter,
            OpenTelemetryMetricsAdapter,
            OSSAlarmAdapter,
            PrometheusAdapter,
            ServiceNowAdapter,
        )
        _pipeline.register_adapter(ServiceNowAdapter())
        _pipeline.register_adapter(JiraServiceManagementAdapter())
        _pipeline.register_adapter(GenericRestITSMAdapter())
        _pipeline.register_adapter(PrometheusAdapter())
        _pipeline.register_adapter(OpenTelemetryMetricsAdapter())
        _pipeline.register_adapter(OSSAlarmAdapter(vendor_hint="NOKIA"))
    return _pipeline


def set_pipeline(pipeline: UnifiedIngestionPipeline) -> None:
    global _pipeline
    _pipeline = pipeline


def get_workflow() -> HumanApprovalWorkflow:
    global _workflow
    if _workflow is None:
        from piis.auth.dependencies import get_auth_manager
        from piis.investigation.approval import FileBasedCheckpointAnchor
        auth_mgr = get_auth_manager()
        ledger_env = os.environ.get("PIIS_LEDGER_PATH")
        ledger_path = Path(ledger_env) if ledger_env else None
        anchor_env = os.environ.get("PIIS_ANCHOR_PATH")
        anchor_path = Path(anchor_env) if anchor_env else (ledger_path.parent / "checkpoint.json" if ledger_path else None)
        anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path) if anchor_path else None
        _workflow = HumanApprovalWorkflow(
            signing_key=b"piis-dev-audit-key-32bytes-long!",
            verifier=auth_mgr.verifier,
            ledger_path=ledger_path,
            checkpoint_anchor=anchor,
        )
        if ledger_path and ledger_path.exists():
            _workflow.load_from_ledger(ledger_path)
    return _workflow


def set_workflow(workflow: HumanApprovalWorkflow) -> None:
    global _workflow
    _workflow = workflow


@router.post(
    "/ingest",
    response_model=IncidentIngestResponse,
    summary="Ingest Incident Record",
    description="Idempotent ingestion endpoint accepting incident envelopes from ITSM platforms (ServiceNow, Jira).",
)
async def ingest_incident(
    req: IncidentIngestRequest,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.INGEST_EVENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> IncidentIngestResponse:
    corr_id = get_correlation_id()
    start_ts = time.time()

    with trace_span("ingest_incident", {"source_system": req.source_system}):
        envelope = IngestionEnvelope.create(
            source_system=req.source_system,
            source_type=req.source_type,
            raw_payload=req.payload,
            external_event_id=req.external_event_id,
            observation_timestamp=req.observation_timestamp,
            metadata=req.metadata,
        )

        result = pipeline.ingest_envelope(envelope)
        latency = time.time() - start_ts

        if result.is_duplicate:
            record_duplicate(req.source_system)
        elif result.status == IngestionStatus.SUCCESS:
            record_ingestion(req.source_system, "SUCCESS", latency)
        else:
            record_failure(req.source_system, result.status.value)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Ingestion rejected: {result.error}",
            )

        return IncidentIngestResponse(
            status=result.status.value,
            envelope_id=result.envelope_id,
            canonical_id=result.canonical_id,
            message=result.message,
            is_duplicate=result.is_duplicate,
            correlation_id=corr_id,
            details=result.details,
        )


@router.get(
    "",
    response_model=PaginatedResponse[Dict[str, Any]],
    summary="List Canonical Incidents",
    description="Retrieve paginated list of canonical telecom incidents.",
)
async def list_incidents(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    domain: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> PaginatedResponse[Dict[str, Any]]:
    all_incidents = pipeline.list_incidents(limit=1000, offset=0)

    # Optional filtering
    filtered = all_incidents
    if domain:
        filtered = [inc for inc in filtered if inc.get("network_domain") == domain.upper()]
    if severity:
        filtered = [inc for inc in filtered if inc.get("severity") == severity.upper()]

    total = len(filtered)
    page = filtered[offset : offset + limit]

    return PaginatedResponse(
        items=page,
        total_count=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/reviews/queue",
    response_model=ReviewQueueResponse,
    summary="Get Human Review Queue",
    description="Retrieve all reviewable diagnostic recommendations across incidents awaiting or possessing human review.",
)
async def get_review_queue(
    status: Optional[str] = Query(default=None, description="Filter by approval status: PENDING_REVIEW, APPROVED, REJECTED, ALL"),
    domain: Optional[str] = Query(default=None, description="Filter by network domain: RAN, 5G_CORE, TRANSPORT, etc."),
    risk: Optional[str] = Query(default=None, description="Filter by risk classification: READ_ONLY_SAFE, LOW_OBSERVABILITY, etc."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_RECOMMENDATIONS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> ReviewQueueResponse:
    # 1. Gather all recommendations from workflow and cached investigations
    all_queue_items: Dict[str, ReviewQueueItem] = {}

    # Check cached investigations in pipeline
    with pipeline._lock:
        cached_investigations = dict(pipeline._investigations)

    for inc_id, ctx in cached_investigations.items():
        inc = pipeline.get_incident(inc_id) or {}
        for r in ctx.recommendations:
            wf_rec = workflow.get_recommendation(r.recommendation_id)
            active_rec = wf_rec if wf_rec is not None else r

            queue_item = ReviewQueueItem(
                recommendation_id=active_rec.recommendation_id,
                incident_id=inc_id,
                incident_title=inc.get("title") or f"Incident {inc_id}",
                incident_severity=inc.get("severity") or "UNKNOWN",
                network_domain=ctx.network_domain or inc.get("network_domain") or "CROSS_DOMAIN",
                description=active_rec.description,
                reason=active_rec.reason,
                supporting_evidence_ids=active_rec.supporting_evidence_ids or [],
                source_runbook_id=active_rec.source_runbook_id,
                source_section=getattr(active_rec, "source_section", None),
                risk_classification=active_rec.risk_classification.value if hasattr(active_rec.risk_classification, "value") else str(active_rec.risk_classification),
                human_approval_required=active_rec.human_approval_required,
                approval_status=active_rec.approval_status.value if hasattr(active_rec.approval_status, "value") else str(active_rec.approval_status),
                reviewed_by=active_rec.reviewed_by,
                review_timestamp=active_rec.review_timestamp,
                review_notes=active_rec.review_notes,
                is_sufficient=ctx.sufficiency_report.is_sufficient if hasattr(ctx, "sufficiency_report") else True,
                has_contradictions=ctx.sufficiency_report.has_contradictions if hasattr(ctx, "sufficiency_report") else False,
                has_missing_evidence=ctx.sufficiency_report.has_missing_evidence if hasattr(ctx, "sufficiency_report") else False,
                created_at=inc.get("created_at") or getattr(ctx, "created_at", None),
            )
            all_queue_items[active_rec.recommendation_id] = queue_item

    # Also check any recommendations registered directly in workflow
    for wf_rec in workflow.list_recommendations():
        if wf_rec.recommendation_id not in all_queue_items:
            inc_id = workflow.get_recommendation_incident(wf_rec.recommendation_id) or "UNKNOWN"
            inc = pipeline.get_incident(inc_id) if inc_id != "UNKNOWN" else {}
            inc = inc or {}
            is_restored_ledger = (
                wf_rec.source_runbook_id == "RESTORED_LEDGER"
                or not wf_rec.supporting_evidence_ids
            )
            cached_ctx = pipeline.get_investigation(inc_id) if inc_id != "UNKNOWN" else None
            is_suff = (
                cached_ctx.sufficiency_report.is_sufficient
                if cached_ctx and hasattr(cached_ctx, "sufficiency_report")
                else not is_restored_ledger
            )
            has_miss = (
                cached_ctx.sufficiency_report.has_missing_evidence
                if cached_ctx and hasattr(cached_ctx, "sufficiency_report")
                else is_restored_ledger
            )
            has_contra = (
                cached_ctx.sufficiency_report.has_contradictions
                if cached_ctx and hasattr(cached_ctx, "sufficiency_report")
                else False
            )

            queue_item = ReviewQueueItem(
                recommendation_id=wf_rec.recommendation_id,
                incident_id=inc_id,
                incident_title=inc.get("title") or f"Incident {inc_id}",
                incident_severity=inc.get("severity") or "UNKNOWN",
                network_domain=inc.get("network_domain") or "CROSS_DOMAIN",
                description=wf_rec.description,
                reason=wf_rec.reason,
                supporting_evidence_ids=wf_rec.supporting_evidence_ids or [],
                source_runbook_id=wf_rec.source_runbook_id,
                source_section=getattr(wf_rec, "source_section", None),
                risk_classification=wf_rec.risk_classification.value if hasattr(wf_rec.risk_classification, "value") else str(wf_rec.risk_classification),
                human_approval_required=wf_rec.human_approval_required,
                approval_status=wf_rec.approval_status.value if hasattr(wf_rec.approval_status, "value") else str(wf_rec.approval_status),
                reviewed_by=wf_rec.reviewed_by,
                review_timestamp=wf_rec.review_timestamp,
                review_notes=wf_rec.review_notes,
                is_sufficient=is_suff,
                has_contradictions=has_contra,
                has_missing_evidence=has_miss,
                created_at=inc.get("created_at"),
            )
            all_queue_items[wf_rec.recommendation_id] = queue_item

    items_list = list(all_queue_items.values())

    # Baseline counts before status filtering
    pending_count = sum(1 for item in items_list if item.approval_status == "PENDING_REVIEW")
    approved_count = sum(1 for item in items_list if item.approval_status == "APPROVED")
    rejected_count = sum(1 for item in items_list if item.approval_status == "REJECTED")

    # Apply filters
    filtered = items_list
    if status and status.upper() != "ALL":
        filtered = [item for item in filtered if item.approval_status.upper() == status.upper()]
    if domain and domain.upper() != "ALL":
        filtered = [item for item in filtered if item.network_domain.upper() == domain.upper()]
    if risk and risk.upper() != "ALL":
        filtered = [item for item in filtered if item.risk_classification.upper() == risk.upper()]

    total_filtered = len(filtered)
    page = filtered[offset : offset + limit]

    return ReviewQueueResponse(
        items=page,
        total_count=total_filtered,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=Dict[str, Any],
    summary="Get Canonical Incident",
    description="Retrieve full canonical incident record by ID.",
)
async def get_incident_details(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> Dict[str, Any]:
    inc = pipeline.get_incident(incident_id)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
            headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
        )
    lineage = pipeline.get_lineage(incident_id)
    return {
        "incident": inc,
        "lineage": lineage,
    }


@router.post(
    "/{incident_id}/investigate",
    response_model=InvestigationResponse,
    summary="Trigger Incident Investigation",
    description="Execute multi-stage investigation engine, synthesizing telemetry, correlation, and historical runbooks.",
)
async def investigate_incident(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.TRIGGER_INVESTIGATION)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> InvestigationResponse:
    corr_id = get_correlation_id()
    start_ts = time.time()

    with trace_span("investigate_incident", {"incident_id": incident_id}):
        ctx = pipeline.investigate_incident(incident_id)
        if not ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        latency = time.time() - start_ts
        record_investigation(
            domain=ctx.network_domain,
            latency=latency,
            recommendations=len(ctx.recommendations),
            safe_abstain=not ctx.sufficiency_report.is_sufficient,
            reason="INCONCLUSIVE" if not ctx.sufficiency_report.is_sufficient else "",
        )

        # Register recommendations into HumanApprovalWorkflow state machine
        for rec in ctx.recommendations:
            try:
                workflow.register_recommendation(rec, incident_id=incident_id)
            except Exception:
                pass  # Ignore if already registered

        # Format recommendations
        rec_items = [
            DiagnosticRecommendationItem(
                recommendation_id=r.recommendation_id,
                incident_id=incident_id,
                description=r.description,
                reason=r.reason,
                supporting_evidence_ids=r.supporting_evidence_ids,
                source_runbook_id=r.source_runbook_id,
                source_section=getattr(r, "source_section", None),
                risk_classification=r.risk_classification.value if hasattr(r.risk_classification, "value") else str(r.risk_classification),
                human_approval_required=r.human_approval_required,
                approval_status=r.approval_status.value if hasattr(r.approval_status, "value") else str(r.approval_status),
                reviewed_by=r.reviewed_by,
                review_timestamp=r.review_timestamp,
                review_notes=r.review_notes,
            )
            for r in ctx.recommendations
        ]

        hyp_items = [
            InvestigationHypothesisItem(
                hypothesis_id=h.hypothesis_id,
                description=h.description,
                supporting_evidence_ids=h.supporting_evidence_ids,
                contradicting_evidence_ids=h.contradicting_evidence_ids,
                evidence_source=h.evidence_source,
                evidence_timestamp=h.evidence_timestamp,
                confidence_proxy=h.confidence_proxy,
                confidence_rationale=h.confidence_rationale,
                alternative_explanations=h.alternative_explanations,
                recommended_verification_steps=h.recommended_verification_steps,
                status=h.status.value if hasattr(h.status, "value") else str(h.status),
            )
            for h in ctx.hypotheses
        ]

        return InvestigationResponse(
            incident_id=ctx.incident_id,
            title=ctx.title,
            network_domain=ctx.network_domain,
            created_at=ctx.created_at,
            is_sufficient=ctx.sufficiency_report.is_sufficient,
            missing_evidence=ctx.sufficiency_report.missing_evidence_details,
            contradictions=ctx.sufficiency_report.contradiction_details,
            stale_evidence=ctx.sufficiency_report.stale_evidence_details,
            is_transient_event=ctx.sufficiency_report.is_transient_event,
            hypotheses_count=len(ctx.hypotheses),
            hypotheses=hyp_items,
            recommendations=rec_items,
            epistemic_status=ctx.epistemic_status,
            correlation_id=corr_id,
        )


@router.get(
    "/{incident_id}/investigation",
    response_model=InvestigationResponse,
    summary="Get Investigation Context",
    description="Retrieve full investigation context including sufficiency, staleness, hypotheses, and recommendations in read-only mode.",
)
async def get_investigation_context(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INVESTIGATIONS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> InvestigationResponse:
    incident = pipeline.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
            headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
        )
    ctx = pipeline.get_investigation(incident_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation not yet generated for incident '{incident_id}'. Trigger investigation via POST /api/v1/incidents/{incident_id}/investigate.",
            headers={"X-PIIS-Error-Code": "INVESTIGATION_NOT_YET_GENERATED"},
        )
    corr_id = get_correlation_id()

    rec_items = [
        DiagnosticRecommendationItem(
            recommendation_id=r.recommendation_id,
            incident_id=incident_id,
            description=r.description,
            reason=r.reason,
            supporting_evidence_ids=r.supporting_evidence_ids,
            source_runbook_id=r.source_runbook_id,
            source_section=getattr(r, "source_section", None),
            risk_classification=r.risk_classification.value if hasattr(r.risk_classification, "value") else str(r.risk_classification),
            human_approval_required=r.human_approval_required,
            approval_status=r.approval_status.value if hasattr(r.approval_status, "value") else str(r.approval_status),
            reviewed_by=r.reviewed_by,
            review_timestamp=r.review_timestamp,
            review_notes=r.review_notes,
        )
        for r in ctx.recommendations
    ]

    hyp_items = [
        InvestigationHypothesisItem(
            hypothesis_id=h.hypothesis_id,
            description=h.description,
            supporting_evidence_ids=h.supporting_evidence_ids,
            contradicting_evidence_ids=h.contradicting_evidence_ids,
            evidence_source=h.evidence_source,
            evidence_timestamp=h.evidence_timestamp,
            confidence_proxy=h.confidence_proxy,
            confidence_rationale=h.confidence_rationale,
            alternative_explanations=h.alternative_explanations,
            recommended_verification_steps=h.recommended_verification_steps,
            status=h.status.value if hasattr(h.status, "value") else str(h.status),
        )
        for h in ctx.hypotheses
    ]

    return InvestigationResponse(
        incident_id=ctx.incident_id,
        title=ctx.title,
        network_domain=ctx.network_domain,
        created_at=ctx.created_at,
        is_sufficient=ctx.sufficiency_report.is_sufficient,
        missing_evidence=ctx.sufficiency_report.missing_evidence_details,
        contradictions=ctx.sufficiency_report.contradiction_details,
        stale_evidence=ctx.sufficiency_report.stale_evidence_details,
        is_transient_event=ctx.sufficiency_report.is_transient_event,
        hypotheses_count=len(ctx.hypotheses),
        hypotheses=hyp_items,
        recommendations=rec_items,
        epistemic_status=ctx.epistemic_status,
        correlation_id=corr_id,
    )


@router.get(
    "/{incident_id}/hypotheses",
    response_model=List[InvestigationHypothesisItem],
    summary="Get Investigation Hypotheses",
    description="Retrieve ranked diagnostic hypotheses with confidence proxies and evidence mappings.",
)
async def get_incident_hypotheses(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INVESTIGATIONS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> List[InvestigationHypothesisItem]:
    incident = pipeline.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
            headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
        )
    ctx = pipeline.get_investigation(incident_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation not yet generated for incident '{incident_id}'. Trigger investigation via POST /api/v1/incidents/{incident_id}/investigate.",
            headers={"X-PIIS-Error-Code": "INVESTIGATION_NOT_YET_GENERATED"},
        )
    return [
        InvestigationHypothesisItem(
            hypothesis_id=item.hypothesis_id,
            description=item.description,
            supporting_evidence_ids=item.supporting_evidence_ids,
            contradicting_evidence_ids=item.contradicting_evidence_ids,
            evidence_source=item.evidence_source,
            evidence_timestamp=item.evidence_timestamp,
            confidence_proxy=item.confidence_proxy,
            confidence_rationale=item.confidence_rationale,
            alternative_explanations=item.alternative_explanations,
            recommended_verification_steps=item.recommended_verification_steps,
            status=item.status.value if hasattr(item.status, "value") else str(item.status),
        )
        for item in ctx.hypotheses
    ]


@router.get(
    "/{incident_id}/evidence",
    response_model=List[Dict[str, Any]],
    summary="Get Investigation Evidence Register",
    description="Inspect ranked historical cases, anomaly signals, and runbooks supporting the investigation.",
)
async def get_incident_evidence(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_EVIDENCE)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> List[Dict[str, Any]]:
    incident = pipeline.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
            headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
        )
    ctx = pipeline.get_investigation(incident_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation not yet generated for incident '{incident_id}'. Trigger investigation via POST /api/v1/incidents/{incident_id}/investigate.",
            headers={"X-PIIS-Error-Code": "INVESTIGATION_NOT_YET_GENERATED"},
        )
    return [item.model_dump() for item in ctx.evidence_register]


@router.get(
    "/{incident_id}/recommendations",
    response_model=List[DiagnosticRecommendationItem],
    summary="Get Investigation Recommendations",
    description="Retrieve actionable diagnostic recommendations and their current approval status.",
)
async def get_incident_recommendations(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_RECOMMENDATIONS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> List[DiagnosticRecommendationItem]:
    incident = pipeline.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
            headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
        )
    ctx = pipeline.get_investigation(incident_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation not yet generated for incident '{incident_id}'. Trigger investigation via POST /api/v1/incidents/{incident_id}/investigate.",
            headers={"X-PIIS-Error-Code": "INVESTIGATION_NOT_YET_GENERATED"},
        )
    return [
        DiagnosticRecommendationItem(
            recommendation_id=r.recommendation_id,
            incident_id=incident_id,
            description=r.description,
            reason=r.reason,
            supporting_evidence_ids=r.supporting_evidence_ids,
            source_runbook_id=r.source_runbook_id,
            source_section=getattr(r, "source_section", None),
            risk_classification=r.risk_classification.value if hasattr(r.risk_classification, "value") else str(r.risk_classification),
            human_approval_required=r.human_approval_required,
            approval_status=r.approval_status.value if hasattr(r.approval_status, "value") else str(r.approval_status),
            reviewed_by=r.reviewed_by,
            review_timestamp=r.review_timestamp,
            review_notes=r.review_notes,
        )
        for r in ctx.recommendations
    ]


@router.post(
    "/{incident_id}/reviews",
    response_model=ReviewResponse,
    summary="Submit Human Operator Review Decision",
    description="Cryptographically sign an approval or rejection decision. Service accounts are barred.",
)
async def submit_human_review(
    incident_id: str,
    review_req: ReviewSubmissionRequest,
    principal: AuthenticatedPrincipal = Depends(require_human_operator),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
) -> ReviewResponse:
    # Role validation: NOC_L1/L2/L3 or INCIDENT_MANAGER
    allowed_roles = {
        ApplicationRole.NOC_L1,
        ApplicationRole.NOC_L2,
        ApplicationRole.NOC_L3,
        ApplicationRole.INCIDENT_MANAGER,
    }
    if not any(r in allowed_roles for r in principal.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Operator '{principal.principal_id}' lacks review authorization",
        )

    decision_norm = review_req.decision.upper().strip()
    if decision_norm not in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review decision must be 'APPROVED' or 'REJECTED'",
        )

    raw_token = credentials.credentials if credentials else principal.principal_id

    try:
        if decision_norm == "APPROVED":
            target_rec = workflow.get_recommendation(review_req.recommendation_id)
            is_restored = (
                target_rec is not None
                and (
                    getattr(target_rec, "source_runbook_id", "") == "RESTORED_LEDGER"
                    or not getattr(target_rec, "supporting_evidence_ids", None)
                )
            )

            # Retrieve active investigation context from pipeline if present or if required by restored item
            ctx = pipeline.get_investigation(incident_id)
            if not ctx and is_restored:
                ctx = pipeline.investigate_incident(incident_id)

            if is_restored and not ctx:
                raise ValueError(
                    f"Cannot approve recommendation '{review_req.recommendation_id}' with missing or unverified evidence. "
                    f"Original telemetry and runbook context are unavailable after restart. "
                    f"A fresh investigation with verified telemetry is required before approval can be granted."
                )

            # Enforce 5-way fresh evidence binding whenever active investigation context is present
            if ctx is not None:
                # 1. Incident ID binding
                if getattr(ctx, "incident_id", None) and ctx.incident_id != incident_id:
                    raise ValueError(
                        f"Investigation incident mismatch: Evidence belongs to incident '{ctx.incident_id}', "
                        f"not requested incident '{incident_id}'."
                    )

                # 2. Recommendation ID binding
                ctx_recs = getattr(ctx, "recommendations", None) or []
                if ctx_recs and not any(r.recommendation_id == review_req.recommendation_id for r in ctx_recs):
                    raise ValueError(
                        f"Investigation recommendation mismatch: Active investigation for incident '{incident_id}' "
                        f"does not contain recommendation '{review_req.recommendation_id}'."
                    )

                # 3. Evidence sufficiency and completeness
                suff = getattr(ctx, "sufficiency_report", None)
                if not suff or not getattr(suff, "is_sufficient", False) or getattr(suff, "has_missing_evidence", False):
                    raise ValueError(
                        f"Cannot approve recommendation '{review_req.recommendation_id}': Evidence is insufficient "
                        f"or missing required observations."
                    )

                # 4. Evidence freshness at approval submission time (max 1 hour / 3600s per TELEMETRY_ANOMALY policy; 60s max clock skew)
                created_at_raw = getattr(ctx, "created_at", None)
                if not created_at_raw or not str(created_at_raw).strip():
                    raise ValueError(
                        f"Cannot approve recommendation '{review_req.recommendation_id}': Linked investigation "
                        f"evidence is missing mandatory created_at timestamp."
                    )

                created_at_str = str(created_at_raw).strip()
                try:
                    if created_at_str.endswith("Z"):
                        created_dt = datetime.fromisoformat(created_at_str[:-1] + "+00:00")
                    else:
                        created_dt = datetime.fromisoformat(created_at_str)
                except Exception as pe:
                    raise ValueError(
                        f"Investigation created_at timestamp '{created_at_str}' is invalid or unparseable: {pe}"
                    ) from pe

                if created_dt.tzinfo is None:
                    raise ValueError(
                        f"Cannot approve recommendation '{review_req.recommendation_id}': Linked investigation "
                        f"created_at timestamp '{created_at_str}' is timezone-naive. Timezone-aware UTC timestamp required."
                    )

                created_dt_utc = created_dt.astimezone(timezone.utc)
                now_dt = datetime.now(timezone.utc)
                age_sec = (now_dt - created_dt_utc).total_seconds()

                if age_sec < -CLOCK_SKEW_TOLERANCE_SECONDS:
                    lead_sec = int(abs(age_sec))
                    raise ValueError(
                        f"Cannot approve recommendation '{review_req.recommendation_id}': Linked investigation "
                        f"evidence timestamp '{created_at_str}' is future-dated beyond allowed clock skew "
                        f"({lead_sec}s ahead, max allowed skew is {int(CLOCK_SKEW_TOLERANCE_SECONDS)}s)."
                    )

                if age_sec > EVIDENCE_MAX_AGE_SECONDS:
                    raise ValueError(
                        f"Cannot approve recommendation '{review_req.recommendation_id}': Linked investigation "
                        f"evidence is stale (generated {int(age_sec)}s ago, max allowed age is {int(EVIDENCE_MAX_AGE_SECONDS)}s). "
                        f"A fresh investigation is required."
                    )

            updated_rec = workflow.approve_recommendation(
                recommendation_id=review_req.recommendation_id,
                operator_id=raw_token,
                incident_id=incident_id,
                notes=review_req.review_notes,
            )
        else:
            updated_rec = workflow.reject_recommendation(
                recommendation_id=review_req.recommendation_id,
                operator_id=raw_token,
                incident_id=incident_id,
                reason=review_req.review_notes,
            )
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ke),
        )
    except IllegalStateTransitionError as ie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ie),
        )
    except InsufficientPrivilegeError as ipe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ipe),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval workflow rejected review: {str(e)}",
        )

    # Get latest audit entry
    trail = workflow.get_audit_trail()
    latest_entry = trail[-1] if trail else None
    entry_hash = latest_entry.entry_sha256 if latest_entry else "UNKNOWN_HASH"
    seq_num = latest_entry.sequence_number if latest_entry else 0

    record_review(decision_norm, principal.roles[0].value if principal.roles else "UNKNOWN")

    return ReviewResponse(
        incident_id=incident_id,
        recommendation_id=review_req.recommendation_id,
        decision=decision_norm,
        reviewed_by=principal.principal_id,
        review_timestamp=updated_rec.review_timestamp or "",
        audit_entry_hash=entry_hash,
        ledger_sequence=seq_num,
        status="RECORDED_IN_AUDIT_CHAIN",
        receipt_id=f"RCPT-{entry_hash[:16].upper()}",
    )


@router.get(
    "/{incident_id}/reviews",
    response_model=List[ReviewHistoryItem],
    summary="Get Incident Review Decision History",
    description="Retrieve all cryptographic review audit records recorded for an incident.",
)
async def get_incident_reviews(
    incident_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_RECOMMENDATIONS)),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> List[ReviewHistoryItem]:
    trail = workflow.get_audit_trail()
    matching = [
        ReviewHistoryItem(
            audit_id=e.audit_id,
            sequence_number=e.sequence_number,
            incident_id=e.incident_id,
            recommendation_id=e.recommendation_id,
            action=e.action,
            previous_status=e.previous_status.value if hasattr(e.previous_status, "value") else str(e.previous_status),
            new_status=e.new_status.value if hasattr(e.new_status, "value") else str(e.new_status),
            operator_id=e.operator_id,
            reviewer_role=e.reviewer_role,
            timestamp_utc=e.timestamp_utc,
            notes=e.notes,
            entry_sha256=e.entry_sha256,
            hmac_signature=e.hmac_signature,
        )
        for e in trail
        if e.incident_id == incident_id and e.action in {"APPROVED", "REJECTED", "MODIFIED"}
    ]
    return matching
