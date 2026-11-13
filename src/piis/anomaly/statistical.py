"""Statistical dynamic thresholding for telecom KPI telemetry streams.

Implements EWMA dynamic envelopes and rolling Z-score with asymmetric
telecom operational sensitivity (e.g. drop-only vs surge-only penalties).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from piis.anomaly.models import MetricViolation


# Standard telecom operational metric profiles
METRIC_PROFILES: Dict[str, str] = {
    "RSRP": "DROP",
    "RSRQ": "DROP",
    "SINR": "DROP",
    "UL_SNR": "DROP",
    "DL_MCS": "DROP",
    "UL_MCS": "DROP",
    "TX_THROUGHPUT": "DROP",
    "RX_THROUGHPUT": "DROP",
    "DL_BLER": "SURGE",
    "UL_BLER": "SURGE",
    "PRB_UTIL_DL": "SURGE",
    "PRB_UTIL_UL": "SURGE",
    "LATENCY": "SURGE",
    "PACKET_LOSS": "SURGE",
    "TEMPERATURE": "TWO_SIDED",
    "VOLTAGE": "TWO_SIDED",
}


class StatisticalThresholdDetector:
    """Dynamic threshold anomaly detector using rolling statistics and EWMA."""

    def __init__(
        self,
        alpha: float = 0.1,
        beta: float = 0.05,
        k_sigma: float = 2.5,
        min_samples: int = 10,
        epsilon: float = 1e-6,
    ):
        """Initialize statistical detector.

        Args:
            alpha: Center EWMA adaptation rate.
            beta: Variance EWMA adaptation rate.
            k_sigma: Number of standard deviations for threshold envelope.
            min_samples: Minimum warm-up samples before flagging anomalies.
            epsilon: Numerical stability constant for zero-variance guards.
        """
        self.alpha = alpha
        self.beta = beta
        self.k_sigma = k_sigma
        self.min_samples = min_samples
        self.epsilon = epsilon

        # State tracking per metric: metric_name -> (mean, variance, sample_count)
        self._state: Dict[str, Tuple[float, float, int]] = {}

    def reset(self) -> None:
        """Reset internal online state."""
        self._state.clear()

    def update_and_evaluate(
        self,
        metric_name: str,
        value: float,
        unit: Optional[str] = None,
        timestamp: Optional[str] = None,
        observation_id: Optional[str] = None,
    ) -> Optional[MetricViolation]:
        """Update online EWMA statistics and evaluate whether current sample is anomalous."""
        if math.isnan(value) or math.isinf(value):
            return None

        profile = METRIC_PROFILES.get(metric_name.upper(), "TWO_SIDED")

        if metric_name not in self._state:
            # First observation: initialize state with proportional prior variance
            init_std = max(abs(value) * 0.1, 0.01)
            self._state[metric_name] = (value, init_std ** 2, 1)
            return None

        current_mean, current_var, count = self._state[metric_name]
        current_std = math.sqrt(max(current_var, self.epsilon))

        # Check for warm-up period
        if count < self.min_samples:
            # Still in warm-up: update running stats without flagging
            new_mean = self.alpha * value + (1.0 - self.alpha) * current_mean
            new_var = self.beta * ((value - new_mean) ** 2) + (1.0 - self.beta) * current_var
            self._state[metric_name] = (new_mean, new_var, count + 1)
            return None

        # Compute deviation
        deviation = value - current_mean
        sigmas = deviation / current_std

        # Check violation based on metric sensitivity profile
        is_violation = False
        direction = "SURGE" if sigmas > 0 else "DROP"

        if profile == "SURGE" and sigmas >= self.k_sigma:
            is_violation = True
        elif profile == "DROP" and sigmas <= -self.k_sigma:
            is_violation = True
        elif profile == "TWO_SIDED" and abs(sigmas) >= self.k_sigma:
            is_violation = True

        # Only update EWMA state if not a severe anomaly (to avoid polluting baseline)
        if not is_violation or abs(sigmas) < (self.k_sigma * 1.5):
            new_mean = self.alpha * value + (1.0 - self.alpha) * current_mean
            new_var = self.beta * ((value - new_mean) ** 2) + (1.0 - self.beta) * current_var
            self._state[metric_name] = (new_mean, new_var, count + 1)

        if is_violation:
            return MetricViolation(
                metric_name=metric_name,
                observed_value=float(value),
                expected_mean=float(current_mean),
                deviation_sigmas=float(abs(sigmas)),
                unit=unit,
                direction=direction,
                timestamp=timestamp,
                observation_id=observation_id,
            )

        return None

    def detect_batch(
        self,
        df: pd.DataFrame,
        metric_col: str = "metric_value",
        metric_name_col: str = "metric_name",
        window_size: int = 30,
    ) -> List[MetricViolation]:
        """Detect anomalies in a batch DataFrame using rolling window statistics."""
        violations: List[MetricViolation] = []
        if df.empty:
            return violations

        for metric_name, group in df.groupby(metric_name_col):
            profile = METRIC_PROFILES.get(str(metric_name).upper(), "TWO_SIDED")
            series = group[metric_col].dropna()
            if len(series) < self.min_samples:
                continue

            rolling_mean = series.rolling(window=window_size, min_periods=self.min_samples).mean()
            rolling_std = series.rolling(window=window_size, min_periods=self.min_samples).std().fillna(self.epsilon)
            rolling_std = np.maximum(rolling_std, self.epsilon)

            z_scores = (series - rolling_mean) / rolling_std

            for idx, val in series.items():
                z = z_scores.loc[idx]
                if pd.isna(z):
                    continue

                is_viol = False
                direction = "SURGE" if z > 0 else "DROP"

                if profile == "SURGE" and z >= self.k_sigma:
                    is_viol = True
                elif profile == "DROP" and z <= -self.k_sigma:
                    is_viol = True
                elif profile == "TWO_SIDED" and abs(z) >= self.k_sigma:
                    is_viol = True

                if is_viol:
                    unit_val = group.loc[idx, "unit"] if "unit" in group.columns else None
                    ts_val = group.loc[idx, "timestamp"] if "timestamp" in group.columns else None
                    obs_val = group.loc[idx, "observation_id"] if "observation_id" in group.columns else None
                    violations.append(
                        MetricViolation(
                            metric_name=str(metric_name),
                            observed_value=float(val),
                            expected_mean=float(rolling_mean.loc[idx]),
                            deviation_sigmas=float(abs(z)),
                            unit=str(unit_val) if pd.notna(unit_val) else None,
                            direction=direction,
                            timestamp=str(ts_val) if pd.notna(ts_val) else None,
                            observation_id=str(obs_val) if pd.notna(obs_val) else None,
                        )
                    )

        return violations
