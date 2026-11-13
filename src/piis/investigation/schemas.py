"""Pydantic schemas and contracts for M5 Evidence-Grounded Investigation and Decision Support."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from piis.provenance import ProvenanceRecord


class EvidenceType(str, Enum):
    """Categorization of evidence items in the canonical investigation register."""
    TICKET_METADATA = "TICKET_METADATA"
    ML_CLASSIFICATION = "ML_CLASSIFICATION"
    SEVERITY_PREDICTION = "SEVERITY_PREDICTION"
    POLICY_ROUTING = "POLICY_ROUTING"
    TELEMETRY_ANOMALY = "TELEMETRY_ANOMALY"
    ALARM_CLUSTER = "ALARM_CLUSTER"
    TOPOLOGY_IMPACT = "TOPOLOGY_IMPACT"
    APPROVED_RUNBOOK = "APPROVED_RUNBOOK"
    HISTORICAL_CASE = "HISTORICAL_CASE"


class TrustLevel(str, Enum):
    """Trust classification levels for evidence provenance."""
    HIGH_TRUST_APPROVED = "HIGH_TRUST_APPROVED"
    MEDIUM_TRUST_VERIFIED = "MEDIUM_TRUST_VERIFIED"
    BENCHMARK_ONLY = "BENCHMARK_ONLY"
    UNVERIFIED = "UNVERIFIED"


class HypothesisStatus(str, Enum):
    """Epistemic status of a diagnostic hypothesis."""
    UNVERIFIED = "UNVERIFIED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RecommendationRisk(str, Enum):
    """Risk tier of proposed diagnostic checks."""
    READ_ONLY_SAFE = "READ_ONLY_SAFE"
    LOW_OBSERVABILITY = "LOW_OBSERVABILITY"
    DISRUPTIVE_AUDIT = "DISRUPTIVE_AUDIT"
    HIGH_RISK_MANUAL = "HIGH_RISK_MANUAL"


class ApprovalStatus(str, Enum):
    """Human approval state machine status."""
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class InvestigationEvidenceItem(BaseModel):
    """Canonical, deduplicated evidence item stored in the investigation register."""
    evidence_id: str = Field(description="Unique identifier, e.g. EVID-001")
    evidence_type: EvidenceType
    source_ref: str = Field(description="Originating artifact reference, e.g. M2-FaultCategoryClassifier or SOP-RAN-VSWR-001")
    domain: str = Field(default="CROSS_DOMAIN")
    observed_at: Optional[str] = None
    trust_classification: TrustLevel = TrustLevel.MEDIUM_TRUST_VERIFIED
    content_summary: str
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentHypothesis(BaseModel):
    """Structured, evidence-grounded diagnostic hypothesis."""
    hypothesis_id: str = Field(description="Unique identifier, e.g. HYP-001")
    description: str = Field(description="Plain-language description of candidate failure mechanism")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence items corroborating this hypothesis")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence items contradicting this hypothesis")
    evidence_source: str = Field(description="Primary source or model component originating hypothesis")
    evidence_timestamp: Optional[str] = None
    confidence_proxy: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Heuristic score combining RRF rank ratio and ML probability. Never a statistical posterior.",
    )
    confidence_rationale: str = Field(description="Explicit human-readable formula or justification for heuristic score")
    alternative_explanations: List[str] = Field(default_factory=list, description="Plausible competing root causes")
    recommended_verification_steps: List[str] = Field(default_factory=list, description="Non-destructive checks to confirm or reject")
    status: HypothesisStatus = HypothesisStatus.UNVERIFIED


class DiagnosticRecommendation(BaseModel):
    """Specific, non-destructive diagnostic troubleshooting action derived from approved runbooks."""
    recommendation_id: str = Field(description="Unique identifier, e.g. REC-001")
    incident_id: Optional[str] = Field(default=None, description="Associated canonical incident identifier")
    description: str = Field(description="Actionable diagnostic procedure")
    reason: str = Field(description="Justification linked directly to supporting evidence")
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    source_runbook_id: str = Field(description="Verified runbook identifier, e.g. SOP-RAN-VSWR-001 or HUMAN_ESCALATION")
    source_section: str = Field(description="Section hierarchy within runbook, e.g. Section 2.1: Feeder Inspection")
    preconditions: List[str] = Field(default_factory=list)
    expected_observation: str = Field(description="Quantitative threshold or status indicator expected on normal vs faulty state")
    risk_classification: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE
    human_approval_required: bool = Field(default=True, description="Strictly True. Consequential actions require human review.")
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    reviewed_by: Optional[str] = None
    review_timestamp: Optional[str] = None
    review_notes: Optional[str] = None


class EvidenceSufficiencyReport(BaseModel):
    """Analysis of evidence completeness, missing signals, contradictions, and staleness."""
    is_sufficient: bool = True
    has_missing_evidence: bool = False
    missing_evidence_details: List[str] = Field(default_factory=list)
    has_contradictions: bool = False
    contradiction_details: List[str] = Field(default_factory=list)
    has_stale_evidence: bool = False
    stale_evidence_details: List[str] = Field(default_factory=list)
    is_transient_event: bool = False


class InvestigationContext(BaseModel):
    """Top-level container holding multi-milestone synthesized evidence, hypotheses, and recommendations."""
    incident_id: str
    title: str
    network_domain: str
    created_at: str
    m2_classification: Dict[str, Any] = Field(default_factory=dict)
    m3_network_intelligence: Dict[str, Any] = Field(default_factory=dict)
    m4_retrieval: Dict[str, Any] = Field(default_factory=dict)
    evidence_register: List[InvestigationEvidenceItem] = Field(default_factory=list)
    sufficiency_report: EvidenceSufficiencyReport = Field(default_factory=EvidenceSufficiencyReport)
    hypotheses: List[IncidentHypothesis] = Field(default_factory=list)
    recommendations: List[DiagnosticRecommendation] = Field(default_factory=list)
    epistemic_status: str = "READ_ONLY_DECISION_SUPPORT"
    operator_summary_markdown: str = ""
    provenance: ProvenanceRecord


class OperatorInvestigationReport(BaseModel):
    """Customer/NOC-facing investigation briefing."""
    incident_id: str
    generated_at: str
    primary_hypothesis: Optional[IncidentHypothesis] = None
    all_hypotheses: List[IncidentHypothesis] = Field(default_factory=list)
    recommended_diagnostic_checks: List[DiagnosticRecommendation] = Field(default_factory=list)
    evidence_sufficiency: EvidenceSufficiencyReport
    blast_radius_summary: Dict[str, Any] = Field(default_factory=dict)
    human_approval_pending_count: int = 0
    full_markdown: str
