"""Data models for network impact analysis and blast radius quantification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ImpactAssessment(BaseModel):
    """Quantified blast radius and severity risk assessment for a network incident."""
    assessment_id: str
    cluster_id: str
    direct_elements: List[str]
    inferred_elements: List[str]
    total_element_count: int
    affected_domains: List[str]
    domain_count: int
    severity_risk_level: str
    risk_score: float = Field(ge=0.0, le=1.0)
    estimated_affected_subscribers: Optional[int] = None
    subscriber_impact_basis: Optional[str] = None
    epistemic_status: str = "DERIVED_ESTIMATE"
    provenance: Dict[str, Any] = Field(default_factory=dict)
