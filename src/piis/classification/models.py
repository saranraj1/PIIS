"""Classifier and severity prediction baselines for PIIS incident intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import LabelEncoder

from piis.classification.features import IncidentFeatureExtractor


class FaultCategoryClassifier:
    """Production wrapper for incident fault category classification."""

    def __init__(
        self,
        model_type: str = "logistic_regression",
        max_tfidf_features: int = 500,
        random_state: int = 42,
    ):
        self.model_type = model_type
        self.random_state = random_state
        self.max_tfidf_features = max_tfidf_features

        self.extractor = IncidentFeatureExtractor(
            max_tfidf_features=self.max_tfidf_features
        )
        self.label_encoder = LabelEncoder()

        if model_type == "logistic_regression":
            self.model = LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=self.random_state,
            )
        elif model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                class_weight="balanced",
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Unsupported model_type: {model_type}")

        self._is_fitted = False

    def fit(self, incidents: List[Dict[str, Any]]) -> FaultCategoryClassifier:
        """Fit feature extractor and classifier on a list of incident dictionaries."""
        df_feat, targets = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        y = self.label_encoder.fit_transform(targets["fault_category"])

        X = self.extractor.fit_transform(df_feat)
        self.model.fit(X, y)
        self._is_fitted = True
        return self

    def predict(self, incidents: List[Dict[str, Any]]) -> List[str]:
        """Predict fault categories for incident dictionaries."""
        if not self._is_fitted:
            raise RuntimeError("Classifier must be fitted before predict().")
        df_feat, _ = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        X = self.extractor.transform(df_feat)
        y_pred = self.model.predict(X)
        return list(self.label_encoder.inverse_transform(y_pred))

    def predict_proba(self, incidents: List[Dict[str, Any]]) -> np.ndarray:
        """Predict class probabilities for incident dictionaries."""
        if not self._is_fitted:
            raise RuntimeError("Classifier must be fitted before predict_proba().")
        df_feat, _ = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        X = self.extractor.transform(df_feat)
        return self.model.predict_proba(X)

    @property
    def classes_(self) -> List[str]:
        return list(self.label_encoder.classes_)

    def save(self, output_path: Path) -> None:
        """Persist model bundle including feature extractor and label encoder."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model_type": self.model_type,
            "random_state": self.random_state,
            "max_tfidf_features": self.max_tfidf_features,
            "extractor": self.extractor,
            "label_encoder": self.label_encoder,
            "model": self.model,
            "classes": self.classes_,
        }
        joblib.dump(bundle, output_path)

        # Also write human-readable metadata sidecar
        meta_path = output_path.with_suffix(".json")
        meta = {
            "model_type": self.model_type,
            "random_state": self.random_state,
            "max_tfidf_features": self.max_tfidf_features,
            "classes": self.classes_,
            "feature_names": self.extractor.get_feature_names() if self._is_fitted else [],
        }
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> FaultCategoryClassifier:
        """Load persisted model bundle."""
        bundle = joblib.load(path)
        inst = cls(
            model_type=bundle["model_type"],
            max_tfidf_features=bundle["max_tfidf_features"],
            random_state=bundle["random_state"],
        )
        inst.extractor = bundle["extractor"]
        inst.label_encoder = bundle["label_encoder"]
        inst.model = bundle["model"]
        inst._is_fitted = True
        return inst


class SeverityPredictor:
    """Production wrapper for incident severity prediction."""

    SEVERITY_ORDER = ["WARNING", "MINOR", "MAJOR", "CRITICAL"]

    def __init__(
        self,
        model_type: str = "logistic_regression",
        max_tfidf_features: int = 500,
        random_state: int = 42,
    ):
        self.model_type = model_type
        self.random_state = random_state
        self.max_tfidf_features = max_tfidf_features

        self.extractor = IncidentFeatureExtractor(
            max_tfidf_features=self.max_tfidf_features
        )
        self.label_encoder = LabelEncoder()

        if model_type == "logistic_regression":
            self.model = LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=self.random_state,
            )
        elif model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                class_weight="balanced",
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Unsupported model_type: {model_type}")

        self._is_fitted = False

    def fit(self, incidents: List[Dict[str, Any]]) -> SeverityPredictor:
        df_feat, targets = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        y = self.label_encoder.fit_transform(targets["severity"])

        X = self.extractor.fit_transform(df_feat)
        self.model.fit(X, y)
        self._is_fitted = True
        return self

    def predict(self, incidents: List[Dict[str, Any]]) -> List[str]:
        if not self._is_fitted:
            raise RuntimeError("SeverityPredictor must be fitted before predict().")
        df_feat, _ = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        X = self.extractor.transform(df_feat)
        y_pred = self.model.predict(X)
        return list(self.label_encoder.inverse_transform(y_pred))

    def predict_proba(self, incidents: List[Dict[str, Any]]) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("SeverityPredictor must be fitted before predict_proba().")
        df_feat, _ = self.extractor.prepare_dataframe(incidents, strict_quarantine=True)
        X = self.extractor.transform(df_feat)
        return self.model.predict_proba(X)

    @property
    def classes_(self) -> List[str]:
        return list(self.label_encoder.classes_)

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model_type": self.model_type,
            "random_state": self.random_state,
            "max_tfidf_features": self.max_tfidf_features,
            "extractor": self.extractor,
            "label_encoder": self.label_encoder,
            "model": self.model,
            "classes": self.classes_,
        }
        joblib.dump(bundle, output_path)

        meta_path = output_path.with_suffix(".json")
        meta = {
            "model_type": self.model_type,
            "random_state": self.random_state,
            "max_tfidf_features": self.max_tfidf_features,
            "classes": self.classes_,
        }
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> SeverityPredictor:
        bundle = joblib.load(path)
        inst = cls(
            model_type=bundle["model_type"],
            max_tfidf_features=bundle["max_tfidf_features"],
            random_state=bundle["random_state"],
        )
        inst.extractor = bundle["extractor"]
        inst.label_encoder = bundle["label_encoder"]
        inst.model = bundle["model"]
        inst._is_fitted = True
        return inst


def compute_classification_metrics(
    y_true: List[str],
    y_pred: List[str],
    classes: Optional[List[str]] = None,
    y_proba: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compute comprehensive classification metrics including Macro-F1, per-class PR, and confusion matrix."""
    labels = sorted(list(classes or set(y_true).union(set(y_pred))))

    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0))
    macro_precision = float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    macro_recall = float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))

    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_norm = confusion_matrix(y_true, y_pred, labels=labels, normalize="true")

    metrics = {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "total_samples": len(y_true),
        "labels": labels,
        "per_class": {
            cls_name: {
                "precision": round(float(report[cls_name]["precision"]), 4),
                "recall": round(float(report[cls_name]["recall"]), 4),
                "f1_score": round(float(report[cls_name]["f1-score"]), 4),
                "support": int(report[cls_name]["support"]),
            }
            for cls_name in labels
            if cls_name in report
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_normalized": np.round(cm_norm, 4).tolist(),
    }

    # High severity recall (for severity tasks)
    high_sev_labels = [lbl for lbl in ["CRITICAL", "MAJOR"] if lbl in labels]
    if high_sev_labels:
        high_sev_true = [1 if y in high_sev_labels else 0 for y in y_true]
        high_sev_pred = [1 if y in high_sev_labels else 0 for y in y_pred]
        high_sev_recall = float(recall_score(high_sev_true, high_sev_pred, zero_division=0))
        metrics["high_severity_recall"] = round(high_sev_recall, 4)

    # Multi-class one-vs-rest Brier score if probabilities provided
    if y_proba is not None and len(labels) == y_proba.shape[1]:
        brier_scores = []
        for idx, lbl in enumerate(labels):
            y_bin = [1.0 if y == lbl else 0.0 for y in y_true]
            p_bin = y_proba[:, idx]
            brier_scores.append(float(np.mean((np.array(y_bin) - p_bin) ** 2)))
        metrics["mean_brier_score"] = round(float(np.mean(brier_scores)), 4)
        metrics["per_class_brier_score"] = {
            lbl: round(score, 4) for lbl, score in zip(labels, brier_scores)
        }

    return metrics
