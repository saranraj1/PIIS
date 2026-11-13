"""Unit tests for M5 investigation and decision support schemas."""

import pytest
from pydantic import ValidationError

from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    EvidenceSufficiencyReport,
    EvidenceType,
    HypothesisStatus,
    IncidentHypothesis,
    InvestigationContext,
    InvestigationEvidenceItem,
    RecommendationRisk,
    TrustLevel,
)
from piis.provenance import ProvenanceRecord, SourceType


def test_evidence_item_creation():
    item = InvestigationEvidenceItem(
        evidence_id="EVID-001",
        evidence_type=EvidenceType.TICKET_METADATA,
        source_ref="IncidentTicket-INC-1001",
        domain="RAN",
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="Antenna VSWR spike on sector 2",
    )
    assert item.evidence_id == "EVID-001"
    assert item.evidence_type == EvidenceType.TICKET_METADATA
    assert item.trust_classification == TrustLevel.HIGH_TRUST_APPROVED


def test_incident_hypothesis_contract():
    hypo = IncidentHypothesis(
        hypothesis_id="HYP-001",
        description="Feeder water ingress causing high reflected power",
        supporting_evidence_ids=["EVID-001", "EVID-002"],
        contradicting_evidence_ids=[],
        evidence_source="M4-RetrievedRunbook-SOP-RAN-VSWR-001",
        confidence_proxy=0.85,
        confidence_rationale="High RRF rank + exact alarm match",
        status=HypothesisStatus.SUPPORTED,
    )
    assert hypo.hypothesis_id == "HYP-001"
    assert hypo.confidence_proxy == 0.85
    assert hypo.status == HypothesisStatus.SUPPORTED
    assert len(hypo.supporting_evidence_ids) == 2


def test_incident_hypothesis_bounds():
    # Confidence proxy must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        IncidentHypothesis(
            hypothesis_id="HYP-INVALID",
            description="Test",
            evidence_source="Test",
            confidence_proxy=1.5,  # Invalid
            confidence_rationale="Test",
        )


def test_diagnostic_recommendation_contract():
    rec = DiagnosticRecommendation(
        recommendation_id="REC-001",
        description="Sweep feeder line with Anritsu Site Master",
        reason="Verify high VSWR reading",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1",
        expected_observation="VSWR <= 1.3:1",
        risk_classification=RecommendationRisk.LOW_OBSERVABILITY,
        human_approval_required=True,
    )
    assert rec.recommendation_id == "REC-001"
    assert rec.human_approval_required is True
    assert rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert rec.risk_classification == RecommendationRisk.LOW_OBSERVABILITY


def test_evidence_sufficiency_report():
    report = EvidenceSufficiencyReport(
        is_sufficient=False,
        has_missing_evidence=True,
        missing_evidence_details=["Zero alarm codes present in ticket"],
    )
    assert not report.is_sufficient
    assert report.has_missing_evidence
    assert len(report.missing_evidence_details) == 1


def test_investigation_context_structure():
    prov = ProvenanceRecord(
        source_type=SourceType.DERIVED,
        source_dataset="PIIS-InvestigationEngine",
        source_record_id="INV-001",
        checksum_sha256="abcd" * 16,
    )
    ctx = InvestigationContext(
        incident_id="INC-001",
        title="Antenna VSWR Degraded",
        network_domain="RAN",
        created_at="2026-11-01T12:00:00Z",
        epistemic_status="READ_ONLY_DECISION_SUPPORT",
        provenance=prov,
    )
    assert ctx.incident_id == "INC-001"
    assert ctx.epistemic_status == "READ_ONLY_DECISION_SUPPORT"
    assert ctx.provenance.source_record_id == "INV-001"
