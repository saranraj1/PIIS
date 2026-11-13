"""Telemetry Anomaly Detection Pipeline.

Orchestrates preprocessing, denoising, statistical dynamic thresholding,
and unsupervised Isolation Forest scoring into canonical TelemetryAnomaly events.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from piis.anomaly.isolation_forest import IsolationForestDetector
from piis.anomaly.models import AnomalySeverity, MetricViolation, TelemetryAnomaly
from piis.anomaly.statistical import StatisticalThresholdDetector
from piis.provenance import ProvenanceRecord, SourceType


class TelemetryAnomalyPipeline:
    """End-to-end pipeline for telecom telemetry anomaly detection."""

    def __init__(
        self,
        statistical_detector: Optional[StatisticalThresholdDetector] = None,
        ml_detector: Optional[IsolationForestDetector] = None,
        score_threshold: float = 0.55,
        version: str = "1.0.0",
    ):
        """Initialize telemetry anomaly detection pipeline.

        Args:
            statistical_detector: Statistical dynamic threshold detector.
            ml_detector: Fitted IsolationForest detector (optional).
            score_threshold: Minimum fused score to emit a TelemetryAnomaly.
            version: Model and pipeline version string.
        """
        self.stat_detector = statistical_detector or StatisticalThresholdDetector(k_sigma=2.5)
        self.ml_detector = ml_detector
        self.score_threshold = score_threshold
        self.version = version

    def _denoise_and_impute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply noise suppression and strictly causal forward imputation on raw telemetry.

        Temporal Causality Guarantees:
        - Strictly causal rolling operations (center=False, no future lookahead).
        - No backward filling (.bfill() forbidden); missing values use ffill or neutral zero.
        - Spike filtering uses historical moving median and historical rolling std.
        """
        if df.empty:
            return df

        df = df.copy()
        # Ensure timestamp is parsed and sorted chronologically
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp_dt").reset_index(drop=True)

        cleaned_groups = []
        for (ne_id, metric), group in df.groupby(["network_element_id", "metric_name"]):
            group = group.copy()
            # Strictly causal forward-fill up to 3 missing steps; any leading unobserved values fill with 0.0
            group["metric_value"] = group["metric_value"].ffill(limit=3).fillna(0.0)

            # Strictly causal 3-step rolling median (center=False: looks only at t-2, t-1, t)
            if len(group) >= 3:
                med = group["metric_value"].rolling(3, center=False, min_periods=1).median()
                # Causal rolling standard deviation over past 5 samples
                rolling_std = group["metric_value"].rolling(5, center=False, min_periods=1).std().fillna(1e-6)
                rolling_std = np.maximum(rolling_std, 1e-6)

                diff = (group["metric_value"] - med).abs()
                spike_mask = diff > (1.5 * rolling_std)
                group.loc[spike_mask, "metric_value"] = med.loc[spike_mask]

            cleaned_groups.append(group)

        return pd.concat(cleaned_groups, ignore_index=True) if cleaned_groups else df

    def process_records(
        self,
        records: List[Dict[str, Any]],
        dataset_name: str = "UnknownTelemetry",
        source_type: SourceType = SourceType.PUBLIC_REAL,
    ) -> List[TelemetryAnomaly]:
        """Process list of canonical telemetry dictionary records and return detected anomalies."""
        if not records:
            return []

        df = pd.DataFrame(records)
        return self.process_dataframe(df, dataset_name=dataset_name, source_type=source_type)

    def process_dataframe(
        self,
        df: pd.DataFrame,
        dataset_name: str = "UnknownTelemetry",
        source_type: SourceType | str = SourceType.PUBLIC_REAL,
    ) -> List[TelemetryAnomaly]:
        """Process telemetry DataFrame and return structured TelemetryAnomaly events."""
        if df.empty or "metric_value" not in df.columns:
            return []

        st = SourceType(source_type) if isinstance(source_type, str) else source_type
        clean_df = self._denoise_and_impute(df)
        anomalies: List[TelemetryAnomaly] = []

        # Process per network element
        for ne_id, ne_group in clean_df.groupby("network_element_id"):
            ne_id_str = str(ne_id)
            domain = str(ne_group["network_domain"].iloc[0]) if "network_domain" in ne_group.columns else "RAN"

            # 1. Run statistical dynamic thresholding
            stat_violations = self.stat_detector.detect_batch(ne_group)

            # 2. Run ML Isolation Forest if fitted
            ml_scores: Optional[np.ndarray] = None
            ml_confs: Optional[np.ndarray] = None
            if self.ml_detector and self.ml_detector.is_fitted:
                try:
                    ml_scores, ml_confs = self.ml_detector.score(ne_group)
                except Exception:
                    ml_scores, ml_confs = None, None

            # 3. Fuse scores and construct anomaly windows
            # Aggregate violations by time window / slice
            timestamps = sorted(ne_group["timestamp"].unique())
            if not timestamps:
                continue

            # Group violations by timestamp
            violations_by_time: Dict[str, List[MetricViolation]] = {}
            for v in stat_violations:
                if v.timestamp:
                    violations_by_time.setdefault(v.timestamp, []).append(v)
                else:
                    # Fallback matching
                    matching = ne_group[
                        (ne_group["metric_name"] == v.metric_name)
                        & (ne_group["metric_value"] == v.observed_value)
                    ]
                    if not matching.empty:
                        t_str = str(matching["timestamp"].iloc[0])
                        violations_by_time.setdefault(t_str, []).append(v)

            # Check if any violation or high ML score exists
            for idx, t_str in enumerate(timestamps):
                t_violations = violations_by_time.get(t_str, [])
                ml_score = float(ml_scores[idx]) if ml_scores is not None and idx < len(ml_scores) else 0.0
                ml_conf = float(ml_confs[idx]) if ml_confs is not None and idx < len(ml_confs) else 0.5

                # Compute statistical score
                if t_violations:
                    max_sigma = max(v.deviation_sigmas for v in t_violations)
                    stat_score = float(min(1.0, max_sigma / 5.0))
                else:
                    stat_score = 0.0

                fused_score = max(stat_score, ml_score)
                if fused_score >= self.score_threshold:
                    # Determine severity
                    if fused_score >= 0.85 or (t_violations and any(v.deviation_sigmas >= 4.0 for v in t_violations)):
                        sev = AnomalySeverity.CRITICAL
                    elif fused_score >= 0.70 or (t_violations and any(v.deviation_sigmas >= 3.0 for v in t_violations)):
                        sev = AnomalySeverity.MAJOR
                    elif fused_score >= 0.50:
                        sev = AnomalySeverity.MINOR
                    else:
                        sev = AnomalySeverity.WARNING

                    # Collect observation IDs for this timestamp
                    obs_ids = []
                    if "observation_id" in ne_group.columns:
                        obs_ids = ne_group[ne_group["timestamp"] == t_str]["observation_id"].dropna().astype(str).tolist()

                    # Compute deterministic anomaly ID
                    id_hash = hashlib.sha256(f"{ne_id_str}_{t_str}_{fused_score:.3f}".encode()).hexdigest()[:12]
                    anomaly_id = f"ANOM-{ne_id_str}-{id_hash}"

                    prov = ProvenanceRecord(
                        source_type=st,
                        source_dataset=dataset_name,
                        source_record_id=obs_ids[0] if obs_ids else anomaly_id,
                        transformation_version=self.version,
                        metadata={
                            "fused_score": round(fused_score, 4),
                            "stat_score": round(stat_score, 4),
                            "ml_score": round(ml_score, 4),
                            "violating_metric_count": len(t_violations),
                        },
                    )

                    anomalies.append(
                        TelemetryAnomaly(
                            anomaly_id=anomaly_id,
                            start_timestamp=t_str,
                            end_timestamp=t_str,
                            network_element_id=ne_id_str,
                            network_domain=domain,
                            anomaly_score=round(fused_score, 4),
                            confidence=round(ml_conf if ml_scores is not None else 0.85, 4),
                            severity=sev,
                            affected_metrics=t_violations,
                            detector_type="ENSEMBLE" if ml_scores is not None else "STATISTICAL_DYNAMIC_EWMA",
                            epistemic_status="STATISTICAL_INFERENCE",
                            source_observation_ids=obs_ids,
                            provenance=prov.to_dict(),
                        )
                    )

        return anomalies
