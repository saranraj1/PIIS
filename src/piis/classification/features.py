"""Feature extraction and engineering pipelines for PIIS incident models.

Adheres strictly to PredictionTimeFeatureContract to eliminate post-incident leakage.
Supports TF-IDF text representation, categorical network domains, and scaled tabular indicators.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from piis.normalization.contracts import PredictionTimeFeatureContract


class IncidentFeatureExtractor:
    """Extracts leakage-safe prediction-time feature matrices from raw or normalized incident dictionaries."""

    def __init__(
        self,
        max_tfidf_features: int = 500,
        ngram_range: Tuple[int, int] = (1, 2),
        contract: Optional[PredictionTimeFeatureContract] = None,
    ):
        self.contract = contract or PredictionTimeFeatureContract()
        self.max_tfidf_features = max_tfidf_features
        self.ngram_range = ngram_range

        self.text_pipeline = TfidfVectorizer(
            max_features=self.max_tfidf_features,
            ngram_range=self.ngram_range,
            stop_words="english",
            sublinear_tf=True,
        )

        self.domain_encoder = OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
        )

        self.numeric_scaler = StandardScaler()

        self.transformer: Optional[ColumnTransformer] = None
        self._is_fitted = False

    def _build_transformer(self) -> ColumnTransformer:
        return ColumnTransformer(
            transformers=[
                ("text", self.text_pipeline, "text_content"),
                ("domain", self.domain_encoder, ["network_domain"]),
                ("numeric", self.numeric_scaler, ["log_subscribers", "element_count"]),
            ],
            remainder="drop",
            sparse_threshold=0.0,
        )

    def prepare_dataframe(
        self,
        incidents: List[Dict[str, Any]],
        strict_quarantine: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
        """Sanitize incidents and format into a feature-ready DataFrame and target series.

        Args:
            incidents: List of incident records.
            strict_quarantine: If True, executes PredictionTimeFeatureContract on every record.

        Returns:
            Tuple of (features_df, targets_dict)
        """
        rows = []
        target_faults = []
        target_severities = []
        target_support_levels = []
        group_ids = []
        scenario_families = []
        incident_ids = []

        for inc in incidents:
            if strict_quarantine:
                sanitized = self.contract.sanitize_incident_record(inc)
            else:
                sanitized = inc

            # Text features: Combine title and description available at triage time
            title = str(sanitized.get("title") or "").strip()
            desc = str(sanitized.get("description") or "").strip()
            text_combined = f"{title}. {desc}".strip()

            network_domain = str(sanitized.get("network_domain") or "UNKNOWN")
            subscribers = float(sanitized.get("affected_subscribers") or 0.0)
            element_ids = sanitized.get("network_element_ids") or []
            element_count = float(len(element_ids))

            rows.append({
                "incident_id": sanitized.get("incident_id", ""),
                "text_content": text_combined,
                "network_domain": network_domain,
                "affected_subscribers": subscribers,
                "log_subscribers": float(np.log1p(max(0.0, subscribers))),
                "element_count": element_count,
            })

            # Record targets and group metadata from original ground truth
            target_faults.append(inc.get("fault_category", "unknown"))
            target_severities.append(inc.get("severity", "UNKNOWN"))
            target_support_levels.append(inc.get("support_level_label", "HUMAN_REVIEW"))
            group_ids.append(inc.get("split_group_id", inc.get("incident_id", "")))
            scenario_families.append(inc.get("scenario_family_id", "UNKNOWN"))
            incident_ids.append(inc.get("incident_id", ""))

        df_features = pd.DataFrame(rows)
        targets = {
            "fault_category": pd.Series(target_faults, name="fault_category"),
            "severity": pd.Series(target_severities, name="severity"),
            "support_level_label": pd.Series(target_support_levels, name="support_level_label"),
            "split_group_id": pd.Series(group_ids, name="split_group_id"),
            "scenario_family_id": pd.Series(scenario_families, name="scenario_family_id"),
            "incident_id": pd.Series(incident_ids, name="incident_id"),
        }

        return df_features, targets

    def fit(self, df_features: pd.DataFrame) -> IncidentFeatureExtractor:
        """Fit feature transformer strictly on training data."""
        self.transformer = self._build_transformer()
        self.transformer.fit(df_features)
        self._is_fitted = True
        return self

    def transform(self, df_features: pd.DataFrame) -> np.ndarray:
        """Transform features into numerical array."""
        if not self._is_fitted or self.transformer is None:
            raise RuntimeError("IncidentFeatureExtractor must be fitted before calling transform().")
        return self.transformer.transform(df_features)

    def fit_transform(self, df_features: pd.DataFrame) -> np.ndarray:
        """Fit and transform in one step on training data."""
        return self.fit(df_features).transform(df_features)

    def get_feature_names(self) -> List[str]:
        """Return the names of all transformed features."""
        if not self._is_fitted or self.transformer is None:
            raise RuntimeError("IncidentFeatureExtractor must be fitted to get feature names.")
        return list(self.transformer.get_feature_names_out())
