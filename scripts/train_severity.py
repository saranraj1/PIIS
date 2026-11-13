#!/usr/bin/env python3
"""Train and evaluate baseline severity prediction models for PIIS.

Evaluates pre-resolution operational severity (CRITICAL, MAJOR, MINOR, WARNING)
using strict prediction-time feature contracts.
Includes:
1. 5-Fold Stratified Group Cross-Validation.
2. Independent Seed Holdout (Seed 42 Train -> Seed 101 Test).
3. High-severity recall (CRITICAL + MAJOR).
4. Probability calibration analysis and multi-class Brier score.
5. Serialization of trained severity predictor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.model_selection import StratifiedGroupKFold
import yaml

from piis.classification.features import IncidentFeatureExtractor
from piis.classification.models import (
    SeverityPredictor,
    compute_classification_metrics,
)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("configs/experiments/m2_severity_prediction.yaml"),
        help="Path to severity experiment config YAML",
    )
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 1. Load Data
    bench_path = Path(cfg["data"]["benchmark_path"])
    incidents = load_jsonl(bench_path)
    print(f"Loaded {len(incidents)} incidents from {bench_path}")

    extractor = IncidentFeatureExtractor(
        max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"]
    )
    df_feat, targets = extractor.prepare_dataframe(incidents, strict_quarantine=True)

    y_sev = targets["severity"].to_numpy()
    groups = targets["split_group_id"].to_numpy()

    # 2. 5-Fold Stratified Group Cross-Validation
    n_splits = cfg["evaluation"].get("cv_folds", 5)
    print(f"\n--- Running {n_splits}-Fold Stratified Group CV for Severity Prediction ---")
    sgkf = StratifiedGroupKFold(n_splits=n_splits)

    models_to_test = ["logistic_regression", "random_forest"]
    cv_results: Dict[str, Dict[str, List[float]]] = {
        m: {"accuracy": [], "macro_f1": [], "high_severity_recall": [], "brier_score": []}
        for m in models_to_test
    }

    for fold_idx, (train_idx, val_idx) in enumerate(sgkf.split(df_feat, y_sev, groups=groups), 1):
        train_records = [incidents[i] for i in train_idx]
        val_records = [incidents[i] for i in val_idx]
        y_val = [y_sev[i] for i in val_idx]

        for m_type in models_to_test:
            clf = SeverityPredictor(
                model_type=m_type,
                max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"],
                random_state=cfg["random_seed"],
            )
            clf.fit(train_records)
            preds = clf.predict(val_records)
            probs = clf.predict_proba(val_records)

            m_metrics = compute_classification_metrics(
                y_val, preds, classes=clf.classes_, y_proba=probs
            )
            cv_results[m_type]["accuracy"].append(m_metrics["accuracy"])
            cv_results[m_type]["macro_f1"].append(m_metrics["macro_f1"])
            cv_results[m_type]["high_severity_recall"].append(m_metrics.get("high_severity_recall", 0.0))
            cv_results[m_type]["brier_score"].append(m_metrics.get("mean_brier_score", 0.0))

    cv_summary: Dict[str, Any] = {}
    for m_type, scores in cv_results.items():
        cv_summary[m_type] = {
            "accuracy_mean": round(float(np.mean(scores["accuracy"])), 4),
            "macro_f1_mean": round(float(np.mean(scores["macro_f1"])), 4),
            "high_severity_recall_mean": round(float(np.mean(scores["high_severity_recall"])), 4),
            "brier_score_mean": round(float(np.mean(scores["brier_score"])), 4),
            "macro_f1_std": round(float(np.std(scores["macro_f1"])), 4),
            "folds": scores,
        }
        print(
            f"[{m_type} CV] Macro-F1: {cv_summary[m_type]['macro_f1_mean']} "
            f"(+/- {cv_summary[m_type]['macro_f1_std']}) | "
            f"High-Severity Recall: {cv_summary[m_type]['high_severity_recall_mean']} | "
            f"Mean Brier: {cv_summary[m_type]['brier_score_mean']}"
        )

    # 3. Independent Seed Holdout (Train: Seed 42 -> Test: Seed 101)
    print("\n--- Independent Seed Holdout (Seed 42 Train -> Seed 101 Test) ---")
    train_holdout = [inc for inc in incidents if "-seed-42" in inc.get("split_group_id", "")]
    test_holdout = [inc for inc in incidents if "-seed-101" in inc.get("split_group_id", "")]
    y_test_true = [inc["severity"] for inc in test_holdout]

    holdout_eval: Dict[str, Any] = {}
    best_clf: SeverityPredictor | None = None
    calibration_data: Dict[str, Any] = {}

    for m_type in models_to_test:
        clf = SeverityPredictor(
            model_type=m_type,
            max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"],
            random_state=cfg["random_seed"],
        )
        clf.fit(train_holdout)
        preds = clf.predict(test_holdout)
        probs = clf.predict_proba(test_holdout)

        h_metrics = compute_classification_metrics(
            y_test_true, preds, classes=clf.classes_, y_proba=probs
        )
        holdout_eval[m_type] = h_metrics

        print(
            f"[{m_type} Holdout] Test Accuracy: {h_metrics['accuracy']} | "
            f"Macro-F1: {h_metrics['macro_f1']} | "
            f"High-Severity Recall: {h_metrics.get('high_severity_recall', 'N/A')} | "
            f"Mean Brier: {h_metrics.get('mean_brier_score', 'N/A')}"
        )

        # Compute calibration curve for High Severity (CRITICAL or MAJOR)
        high_sev_binary = np.array([1 if y in ["CRITICAL", "MAJOR"] else 0 for y in y_test_true])
        # Find index of CRITICAL and MAJOR in classes_
        high_sev_indices = [idx for idx, c in enumerate(clf.classes_) if c in ["CRITICAL", "MAJOR"]]
        high_sev_probs = np.sum(probs[:, high_sev_indices], axis=1)

        prob_true, prob_pred = calibration_curve(
            high_sev_binary, high_sev_probs, n_bins=5, strategy="uniform"
        )
        calibration_data[m_type] = {
            "high_severity_prob_true": [round(float(p), 4) for p in prob_true],
            "high_severity_prob_pred": [round(float(p), 4) for p in prob_pred],
        }

        if m_type == "logistic_regression":
            best_clf = clf

    # 4. Save Model Artifact
    models_dir = Path(cfg["outputs"]["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    if best_clf:
        best_clf.save(models_dir / "severity_classifier.joblib")
    print(f"Persisted trained severity model to {models_dir / 'severity_classifier.joblib'}")

    # 5. Persist Metrics and Calibration Artifacts
    metrics_path = Path(cfg["outputs"]["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    full_metrics = {
        "experiment_id": cfg["experiment_id"],
        "dataset_path": str(bench_path),
        "total_samples": len(incidents),
        "cv_results": cv_summary,
        "holdout_results": holdout_eval,
        "calibration_analysis": calibration_data,
    }
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(full_metrics, f, indent=2)

    cm_path = Path(cfg["outputs"]["confusion_matrix_path"])
    with cm_path.open("w", encoding="utf-8") as f:
        json.dump({
            "labels": holdout_eval["logistic_regression"]["labels"],
            "logistic_regression_raw": holdout_eval["logistic_regression"]["confusion_matrix"],
            "logistic_regression_norm": holdout_eval["logistic_regression"]["confusion_matrix_normalized"],
            "random_forest_raw": holdout_eval["random_forest"]["confusion_matrix"],
            "random_forest_norm": holdout_eval["random_forest"]["confusion_matrix_normalized"],
        }, f, indent=2)

    cal_path = metrics_path.parent / "severity_calibration_curve.json"
    with cal_path.open("w", encoding="utf-8") as f:
        json.dump(calibration_data, f, indent=2)

    print(f"Saved severity metrics to {metrics_path}")
    print(f"Saved severity confusion matrix to {cm_path}")
    print(f"Saved calibration curve to {cal_path}")


if __name__ == "__main__":
    main()
