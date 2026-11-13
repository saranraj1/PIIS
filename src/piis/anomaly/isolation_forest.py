"""Unsupervised multi-metric anomaly detection using Isolation Forest."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


class IsolationForestDetector:
    """Multi-metric telecom telemetry anomaly detector using Isolation Forest."""

    def __init__(
        self,
        contamination: float = 0.08,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        """Initialize Isolation Forest detector.

        Args:
            contamination: Expected proportion of outliers in the data.
            n_estimators: Number of isolation trees in ensemble.
            random_state: Deterministic random seed for reproducibility.
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.feature_columns: List[str] = []
        self.is_fitted: bool = False

    def _prepare_feature_matrix(
        self,
        df: pd.DataFrame,
        time_col: str = "timestamp",
        metric_col: str = "metric_value",
        metric_name_col: str = "metric_name",
    ) -> pd.DataFrame:
        """Pivot long-format canonical telemetry into wide multi-metric feature table."""
        if df.empty:
            return pd.DataFrame()

        # Pivot metrics by timestamp and network element
        id_cols = [time_col]
        if "network_element_id" in df.columns:
            id_cols.append("network_element_id")

        pivoted = df.pivot_table(
            index=id_cols,
            columns=metric_name_col,
            values=metric_col,
            aggfunc="mean",
        )

        # Handle missing values: strictly causal forward fill, leading unobserved filled with 0.0
        pivoted = pivoted.ffill().fillna(0.0)

        # Compute dynamic first differences (velocity of degradation)
        diff_df = pivoted.diff().fillna(0.0)
        diff_df.columns = [f"{col}_diff" for col in diff_df.columns]

        # Combine raw levels and first differences
        features = pd.concat([pivoted, diff_df], axis=1)
        return features

    def fit(
        self,
        df: pd.DataFrame,
        time_col: str = "timestamp",
        metric_col: str = "metric_value",
        metric_name_col: str = "metric_name",
    ) -> IsolationForestDetector:
        """Fit Isolation Forest on nominal or baseline telemetry."""
        features = self._prepare_feature_matrix(
            df,
            time_col=time_col,
            metric_col=metric_col,
            metric_name_col=metric_name_col,
        )
        if features.empty or len(features) < 10:
            raise ValueError(f"Insufficient telemetry samples for fitting ({len(features)} rows).")

        self.feature_columns = list(features.columns)
        self.model.fit(features.values)
        self.is_fitted = True
        return self

    def score(
        self,
        df: pd.DataFrame,
        time_col: str = "timestamp",
        metric_col: str = "metric_value",
        metric_name_col: str = "metric_name",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute continuous anomaly scores and confidence for telemetry data.

        Returns:
            Tuple of (anomaly_scores, confidence_scores) aligned with pivoted index.
        """
        if not self.is_fitted:
            raise RuntimeError("IsolationForestDetector must be fitted before scoring.")

        features = self._prepare_feature_matrix(
            df,
            time_col=time_col,
            metric_col=metric_col,
            metric_name_col=metric_name_col,
        )

        # Align features with training columns
        for col in self.feature_columns:
            if col not in features.columns:
                features[col] = 0.0
        features = features[self.feature_columns]

        # Scikit-learn score_samples returns negative values (lower = more anomalous)
        # Decision boundary is approximately at offset_ (negative value around -0.5)
        raw_scores = self.model.score_samples(features.values)
        offset = self.model.offset_

        # Map to continuous anomaly score in [0.0, 1.0] where 1.0 is extremely anomalous
        # score = 0.5 - (raw_score - offset) scaled
        calibrated_scores = np.clip(0.5 - (raw_scores - offset) * 2.0, 0.0, 1.0)

        # Confidence: distance from decision threshold
        distance_from_thresh = np.abs(raw_scores - offset)
        confidence = np.clip(0.5 + distance_from_thresh * 2.0, 0.5, 1.0)

        return calibrated_scores, confidence

    def save(self, file_path: Path) -> None:
        """Serialize detector to disk."""
        state = {
            "model": self.model,
            "feature_columns": self.feature_columns,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "is_fitted": self.is_fitted,
        }
        file_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(state, file_path)

    @classmethod
    def load(cls, file_path: Path) -> IsolationForestDetector:
        """Load detector from disk."""
        state: Dict[str, Any] = joblib.load(file_path)
        detector = cls(
            contamination=state["contamination"],
            n_estimators=state["n_estimators"],
            random_state=state["random_state"],
        )
        detector.model = state["model"]
        detector.feature_columns = state["feature_columns"]
        detector.is_fitted = state["is_fitted"]
        return detector
