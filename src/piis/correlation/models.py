"""Data models for telecom temporal and alarm correlation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CorrelationRationale(BaseModel):
    """Auditable justification for linking two operational events together."""
    event_id_a: str
    event_id_b: str
    time_delta_seconds: float
    hop_distance: Optional[int]
    topology_relation: Optional[str]
    affinity_score: float = Field(ge=0.0, le=1.0)
    rationale_text: str


class CorrelatedIncidentCluster(BaseModel):
    """Coherent cluster of correlated alarms and telemetry anomalies representing an incident candidate."""
    cluster_id: str
    earliest_timestamp: str
    latest_timestamp: str
    primary_domain: str
    involved_domains: List[str]
    direct_alarm_ids: List[str] = Field(default_factory=list)
    telemetry_anomaly_ids: List[str] = Field(default_factory=list)
    affected_elements: List[str] = Field(default_factory=list)
    correlation_edges: List[CorrelationRationale] = Field(default_factory=list)
    root_cause_hypothesis: Optional[str] = None
    epistemic_status: str = "HYPOTHESIS"
    provenance: Dict[str, Any] = Field(default_factory=dict)
