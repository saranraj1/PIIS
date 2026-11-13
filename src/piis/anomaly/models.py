"""Data contracts and Pydantic models for telemetry anomaly detection."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnomalySeverity(str, Enum):
    """Categorical severity for detected telemetry anomalies."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    WARNING = "WARNING"


class MetricViolation(BaseModel):
    """Details of a single metric exceeding dynamic or statistical boundaries."""
    metric_name: str
    observed_value: float
    expected_mean: float
    deviation_sigmas: float
    unit: Optional[str] = None
    direction: str = "SURGE"  # SURGE or DROP
    timestamp: Optional[str] = None
    observation_id: Optional[str] = None


class TelemetryAnomaly(BaseModel):
    """Structured telemetry anomaly event produced by PIIS Network Intelligence."""
    anomaly_id: str
    start_timestamp: str
    end_timestamp: str
    network_element_id: str
    network_domain: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: AnomalySeverity
    affected_metrics: List[MetricViolation]
    detector_type: str
    epistemic_status: str = "STATISTICAL_INFERENCE"
    source_observation_ids: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
