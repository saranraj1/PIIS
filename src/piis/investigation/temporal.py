"""PIIS M5.5 Temporal Evidence Integrity & Configurable Freshness Policy Subsystem.

Remediates FIND-M5.4-001 by implementing formal, configurable temporal evaluation
across all evidence types and sources:
- Distinguishes:
  * Observation time (when the physical/network probe recorded measurement).
  * Ingestion time (when PIIS ingested the record).
  * Incident creation time (when the ticket was opened).
  * Processing time (when the investigation engine evaluates evidence).
- Enforces source-specific freshness thresholds (telemetry, alarms, config changes, runbooks).
- Handles clock skew tolerance, future-dated observations, naive timezone normalization,
  and missing timestamps.
- Preserves historical contextual evidence without conflating it with current-state confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from piis.investigation.schemas import EvidenceType, InvestigationEvidenceItem


class EvidenceTemporalStatus(str, Enum):
    """Temporal classification for an evidence item."""
    FRESH = "FRESH"
    STALE = "STALE"
    HISTORICAL_CONTEXT = "HISTORICAL_CONTEXT"
    MISSING_TIMESTAMP = "MISSING_TIMESTAMP"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    FUTURE_DATED = "FUTURE_DATED"
    CLOCK_SKEW_ACCEPTED = "CLOCK_SKEW_ACCEPTED"
    DELAYED_INGESTION = "DELAYED_INGESTION"


class FreshnessPolicy(BaseModel):
    """Source- and type-specific evidence freshness rules."""
    evidence_type: EvidenceType
    max_age_seconds: float = Field(
        description="Maximum permitted age in seconds before evidence is flagged as stale for current confirmation."
    )
    clock_skew_tolerance_seconds: float = Field(
        default=60.0,
        description="Maximum permitted forward skew in seconds to accommodate edge NTP variations."
    )
    can_serve_as_historical_context: bool = Field(
        default=True,
        description="Whether stale or historical records can still provide comparative contextual value."
    )
    requires_fresh_confirmation: bool = Field(
        default=True,
        description="Whether this evidence type must be fresh to support a current active fault hypothesis."
    )


# Default enterprise telecom freshness policies
DEFAULT_FRESHNESS_POLICIES: Dict[EvidenceType, FreshnessPolicy] = {
    # Real-time probe telemetry: 1 hour maximum freshness window for active operations
    EvidenceType.TELEMETRY_ANOMALY: FreshnessPolicy(
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        max_age_seconds=3600.0, # 1 hour
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
    # Correlated alarm cluster: 2 hours maximum
    EvidenceType.ALARM_CLUSTER: FreshnessPolicy(
        evidence_type=EvidenceType.ALARM_CLUSTER,
        max_age_seconds=7200.0, # 2 hours
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
    # Incident ticket metadata: 4 hours
    EvidenceType.TICKET_METADATA: FreshnessPolicy(
        evidence_type=EvidenceType.TICKET_METADATA,
        max_age_seconds=14400.0, # 4 hours
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
    # Topological blast radius assessment: 24 hours
    EvidenceType.TOPOLOGY_IMPACT: FreshnessPolicy(
        evidence_type=EvidenceType.TOPOLOGY_IMPACT,
        max_age_seconds=86400.0, # 24 hours
        clock_skew_tolerance_seconds=120.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=False,
    ),
    # Historical incident cases: 1 year (valuable as historical context, never current confirmation)
    EvidenceType.HISTORICAL_CASE: FreshnessPolicy(
        evidence_type=EvidenceType.HISTORICAL_CASE,
        max_age_seconds=31536000.0, # 1 year
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=False,
    ),
    # Approved standard operating procedures (runbooks): 1 year
    EvidenceType.APPROVED_RUNBOOK: FreshnessPolicy(
        evidence_type=EvidenceType.APPROVED_RUNBOOK,
        max_age_seconds=31536000.0, # 1 year
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=False,
    ),
    # ML model predictions: 2 hours
    EvidenceType.ML_CLASSIFICATION: FreshnessPolicy(
        evidence_type=EvidenceType.ML_CLASSIFICATION,
        max_age_seconds=7200.0,
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
    EvidenceType.SEVERITY_PREDICTION: FreshnessPolicy(
        evidence_type=EvidenceType.SEVERITY_PREDICTION,
        max_age_seconds=7200.0,
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
    EvidenceType.POLICY_ROUTING: FreshnessPolicy(
        evidence_type=EvidenceType.POLICY_ROUTING,
        max_age_seconds=7200.0,
        clock_skew_tolerance_seconds=60.0,
        can_serve_as_historical_context=True,
        requires_fresh_confirmation=True,
    ),
}


class TemporalEvaluationResult(BaseModel):
    """Detailed temporal evaluation outcome for an individual evidence item."""
    evidence_id: str
    evidence_type: EvidenceType
    observed_at_utc: Optional[str] = None
    ingested_at_utc: Optional[str] = None
    reference_time_utc: str
    age_seconds: Optional[float] = None
    ingestion_delay_seconds: Optional[float] = None
    temporal_status: EvidenceTemporalStatus
    is_current_confirmation: bool
    status_detail: str


def parse_utc_timestamp(ts: Any) -> Tuple[Optional[datetime], Optional[str]]:
    """Parse an arbitrary timestamp input into a UTC-aware datetime.
    
    Returns:
        (datetime_obj, parsing_note)
        If parsing fails or timestamp is missing, datetime_obj is None.
    """
    if ts is None or ts == "":
        return None, "MISSING_TIMESTAMP"

    if isinstance(ts, (int, float)):
        # Epoch seconds
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc), "PARSED_FROM_EPOCH_SECONDS"
        except (ValueError, OverflowError, OSError):
            return None, "INVALID_EPOCH_TIMESTAMP"

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            # Naive datetime: assume UTC but flag explicitly
            return ts.replace(tzinfo=timezone.utc), "NAIVE_DATETIME_CONVERTED_TO_UTC"
        return ts.astimezone(timezone.utc), "DATETIME_CONVERTED_TO_UTC"

    if not isinstance(ts, str):
        return None, "INVALID_TIMESTAMP_TYPE"

    s = ts.strip()
    if not s:
        return None, "EMPTY_TIMESTAMP_STRING"

    # Normalize trailing Z to +00:00 for fromisoformat compatibility
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc), "NAIVE_ISO_CONVERTED_TO_UTC"
        return dt.astimezone(timezone.utc), "PARSED_ISO_UTC"
    except ValueError:
        pass

    # Common fallback formats
    formats = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc), "NAIVE_STRPTIME_CONVERTED_TO_UTC"
            return dt.astimezone(timezone.utc), "PARSED_STRPTIME_UTC"
        except ValueError:
            continue

    return None, f"UNPARSEABLE_TIMESTAMP_FORMAT: '{ts}'"


class TemporalEvidenceEvaluator:
    """Evaluates temporal validity, staleness, clock skew, and historical relevance of evidence."""

    def __init__(self, policies: Optional[Dict[EvidenceType, FreshnessPolicy]] = None):
        self.policies = dict(DEFAULT_FRESHNESS_POLICIES)
        if policies:
            self.policies.update(policies)

    def evaluate_item(
        self,
        item: InvestigationEvidenceItem,
        reference_time: datetime,
        created_at: Optional[datetime] = None,
        ingested_at: Optional[datetime] = None,
    ) -> TemporalEvaluationResult:
        """Evaluate temporal status for a single evidence item against reference and incident creation times."""
        policy = self.policies.get(
            item.evidence_type,
            FreshnessPolicy(
                evidence_type=item.evidence_type,
                max_age_seconds=3600.0,
                clock_skew_tolerance_seconds=60.0,
                can_serve_as_historical_context=True,
                requires_fresh_confirmation=True,
            ),
        )

        ref_utc = reference_time.astimezone(timezone.utc)
        ref_str = ref_utc.isoformat()

        # Parse observation timestamp
        raw_obs = item.observed_at or item.raw_metadata.get("timestamp") or item.raw_metadata.get("observed_at")
        obs_dt, obs_note = parse_utc_timestamp(raw_obs)

        # Parse ingestion timestamp if available
        raw_ing = ingested_at or item.raw_metadata.get("ingested_at") or item.raw_metadata.get("received_at")
        ing_dt, ing_note = parse_utc_timestamp(raw_ing)

        ingestion_delay_s = None
        if obs_dt and ing_dt:
            ingestion_delay_s = round((ing_dt - obs_dt).total_seconds(), 3)

        if obs_dt is None:
            # Missing or invalid timestamp
            status = (
                EvidenceTemporalStatus.MISSING_TIMESTAMP
                if obs_note == "MISSING_TIMESTAMP" or obs_note == "EMPTY_TIMESTAMP_STRING"
                else EvidenceTemporalStatus.INVALID_TIMESTAMP
            )
            return TemporalEvaluationResult(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                observed_at_utc=None,
                ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                reference_time_utc=ref_str,
                age_seconds=None,
                ingestion_delay_seconds=ingestion_delay_s,
                temporal_status=status,
                is_current_confirmation=False,
                status_detail=f"{status.value}: {obs_note}. Missing timestamp cannot confirm current operational state.",
            )

        # Compute age against processing reference time
        age_ref = (ref_utc - obs_dt).total_seconds()
        
        # If incident creation time is provided, also compute observation age relative to incident creation
        age_created = None
        if created_at:
            created_utc = created_at.astimezone(timezone.utc)
            age_created = (created_utc - obs_dt).total_seconds()

        # Effective age for freshness evaluation: if telemetry was already old when the ticket was opened,
        # or if the ticket itself is old relative to processing time, both indicate staleness.
        age_seconds = age_ref
        if age_created is not None and age_created > age_seconds:
            age_seconds = age_created

        obs_str = obs_dt.isoformat()

        # 1. Future timestamp & clock skew check
        if age_ref < 0:
            forward_skew_seconds = abs(age_ref)
            if forward_skew_seconds <= policy.clock_skew_tolerance_seconds:
                return TemporalEvaluationResult(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    observed_at_utc=obs_str,
                    ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                    reference_time_utc=ref_str,
                    age_seconds=round(age_ref, 3),
                    ingestion_delay_seconds=ingestion_delay_s,
                    temporal_status=EvidenceTemporalStatus.CLOCK_SKEW_ACCEPTED,
                    is_current_confirmation=True,
                    status_detail=(
                        f"Observation is {forward_skew_seconds:.1f}s in the future, "
                        f"within clock-skew tolerance ({policy.clock_skew_tolerance_seconds:.1f}s). Accepted."
                    ),
                )
            else:
                return TemporalEvaluationResult(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    observed_at_utc=obs_str,
                    ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                    reference_time_utc=ref_str,
                    age_seconds=round(age_ref, 3),
                    ingestion_delay_seconds=ingestion_delay_s,
                    temporal_status=EvidenceTemporalStatus.FUTURE_DATED,
                    is_current_confirmation=False,
                    status_detail=(
                        f"FUTURE_DATED: Observation timestamp is {forward_skew_seconds:.1f}s in future, "
                        f"exceeding clock-skew tolerance ({policy.clock_skew_tolerance_seconds:.1f}s). Rejected as current state."
                    ),
                )

        # 2. Delayed ingestion analysis (Observation age strictly governs operational truth!)
        has_delayed_ingestion = False
        if ingestion_delay_s and ingestion_delay_s > policy.max_age_seconds:
            has_delayed_ingestion = True

        # 2b. Inherently historical records (Historical incidents provide contextual similarity, not current confirmation)
        if item.evidence_type == EvidenceType.HISTORICAL_CASE:
            return TemporalEvaluationResult(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                observed_at_utc=obs_str,
                ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                reference_time_utc=ref_str,
                age_seconds=round(age_seconds, 3),
                ingestion_delay_seconds=ingestion_delay_s,
                temporal_status=EvidenceTemporalStatus.HISTORICAL_CONTEXT,
                is_current_confirmation=False,
                status_detail=(
                    f"HISTORICAL_CONTEXT: Retained for similarity and procedural guidance ({age_seconds:.1f}s old). "
                    f"Does NOT assert current live network state."
                ),
            )

        # 3. Staleness check against policy threshold
        if age_seconds > policy.max_age_seconds:
            if item.evidence_type in (EvidenceType.HISTORICAL_CASE, EvidenceType.APPROVED_RUNBOOK):
                return TemporalEvaluationResult(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    observed_at_utc=obs_str,
                    ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                    reference_time_utc=ref_str,
                    age_seconds=round(age_seconds, 3),
                    ingestion_delay_seconds=ingestion_delay_s,
                    temporal_status=EvidenceTemporalStatus.HISTORICAL_CONTEXT,
                    is_current_confirmation=False,
                    status_detail=(
                        "HISTORICAL_CONTEXT: Retained for similarity and procedural guidance. "
                        "Does NOT assert current live network state."
                    ),
                )
            else:
                delayed_suffix = (
                    f" (Delayed ingestion: arrived {ingestion_delay_s:.1f}s after measurement, but observation time governs)"
                    if has_delayed_ingestion
                    else ""
                )
                return TemporalEvaluationResult(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    observed_at_utc=obs_str,
                    ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
                    reference_time_utc=ref_str,
                    age_seconds=round(age_seconds, 3),
                    ingestion_delay_seconds=ingestion_delay_s,
                    temporal_status=EvidenceTemporalStatus.STALE,
                    is_current_confirmation=False,
                    status_detail=(
                        f"STALE: Evidence age ({age_seconds:.1f}s) exceeds maximum permitted age "
                        f"({policy.max_age_seconds:.1f}s) for {item.evidence_type.value}.{delayed_suffix} "
                        f"Cannot confirm active fault."
                    ),
                )

        # 4. Fresh observation
        status = EvidenceTemporalStatus.FRESH
        detail = f"FRESH: Evidence age ({age_seconds:.1f}s) is within operational threshold ({policy.max_age_seconds:.1f}s)."
        if obs_note and "NAIVE" in obs_note:
            detail += " [Note: Naive timestamp normalized to UTC]."

        return TemporalEvaluationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            observed_at_utc=obs_str,
            ingested_at_utc=ing_dt.isoformat() if ing_dt else None,
            reference_time_utc=ref_str,
            age_seconds=round(age_seconds, 3),
            ingestion_delay_seconds=ingestion_delay_s,
            temporal_status=status,
            is_current_confirmation=True,
            status_detail=detail,
        )

    def evaluate_register(
        self,
        evidence_register: List[InvestigationEvidenceItem],
        incident: Dict[str, Any],
        reference_time: Optional[datetime] = None,
    ) -> Tuple[List[TemporalEvaluationResult], List[str], List[str]]:
        """Evaluate the entire investigation register for an incident.
        
        Returns:
            (eval_results, stale_details, temporal_defect_details)
        """
        ref_dt = reference_time or datetime.now(timezone.utc)

        created_dt = None
        if incident.get("created_at"):
            created_dt, _ = parse_utc_timestamp(incident["created_at"])

        raw_ing = incident.get("ingested_at") or incident.get("received_at")
        ing_dt, _ = parse_utc_timestamp(raw_ing)

        results: List[TemporalEvaluationResult] = []
        stale_details: List[str] = []
        temporal_defect_details: List[str] = []

        for item in evidence_register:
            res = self.evaluate_item(
                item,
                reference_time=ref_dt,
                created_at=created_dt,
                ingested_at=ing_dt,
            )
            results.append(res)

            if res.temporal_status == EvidenceTemporalStatus.STALE:
                stale_details.append(f"[{item.evidence_id} {item.source_ref}] {res.status_detail}")
            elif res.temporal_status in (
                EvidenceTemporalStatus.MISSING_TIMESTAMP,
                EvidenceTemporalStatus.INVALID_TIMESTAMP,
                EvidenceTemporalStatus.FUTURE_DATED,
            ):
                temporal_defect_details.append(f"[{item.evidence_id} {item.source_ref}] {res.status_detail}")

        return results, stale_details, temporal_defect_details
