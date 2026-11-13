"""Pydantic schemas and contracts for retrieval inputs, grounded evidence, and results."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from piis.knowledge.sources import SourceType, TrustClassification
from piis.provenance import ProvenanceRecord


class RetrievalQuery(BaseModel):
    """Normalized query requesting historical runbook or troubleshooting guidance."""
    query_id: str
    query_text: str
    target_domain: Optional[str] = None
    involved_domains: List[str] = Field(default_factory=list)
    alarm_codes: List[str] = Field(default_factory=list)
    source_type_filter: Optional[List[SourceType]] = None
    trust_filter: Optional[List[TrustClassification]] = None
    subsystem: Optional[str] = None
    technology_generation: Optional[str] = None
    vendor: Optional[str] = None
    equipment_family: Optional[str] = None
    top_k: int = 5
    metadata_constraints: Dict[str, Any] = Field(default_factory=dict)


class GroundedEvidence(BaseModel):
    """Verifiable, provenance-grounded evidence passage returned to caller."""
    query_id: str
    source_id: str
    doc_id: str
    chunk_id: str
    source_title: str
    source_type: SourceType
    trust_classification: TrustClassification
    doc_version: str = "1.0.0"
    network_domain: str
    technology_generation: Optional[str] = None
    vendor: Optional[str] = None
    equipment_family: Optional[str] = None
    section_hierarchy: List[str]
    original_text: str
    retrieval_method: str              # HYBRID_RRF, BM25_ONLY, DENSE_ONLY, DETERMINISTIC_SOP
    raw_bm25_score: Optional[float] = None
    raw_dense_score: Optional[float] = None
    fused_score: float
    fused_rank: int
    confidence_proxy: float = Field(
        default=0.0,
        description="Empirical heuristic score combining RRF rank ratio and score saturation. Not a probability.",
    )
    calibrated_confidence: float = Field(
        default=0.0,
        description="Deprecated alias for confidence_proxy.",
    )
    fallback_tier: Optional[str] = None
    fallback_rationale: Optional[str] = None
    epistemic_status: str = "HISTORICAL_EVIDENCE"
    provenance: ProvenanceRecord
    security_flags: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Synchronize confidence_proxy and deprecated calibrated_confidence alias."""
        if self.confidence_proxy == 0.0 and self.calibrated_confidence != 0.0:
            object.__setattr__(self, "confidence_proxy", self.calibrated_confidence)
        elif self.calibrated_confidence == 0.0 and self.confidence_proxy != 0.0:
            object.__setattr__(self, "calibrated_confidence", self.confidence_proxy)


class RetrievalResult(BaseModel):
    """Top-level container for query response, audit trace, and fallback state."""
    query_id: str
    executed_at: str
    evidence_items: List[GroundedEvidence]
    total_candidates_evaluated: int
    filter_dropped_count: int = 0
    filter_dropped_all: bool = False
    retrieval_mode_executed: str       # HYBRID, BM25_DEGRADED, DETERMINISTIC_SOP, NO_CONFIDENT_MATCH
    primary_runbook_id: Optional[str] = None
    confidence_level: str              # HIGH, MEDIUM, LOW, NONE
    audit_trace: Dict[str, Any] = Field(default_factory=dict)
