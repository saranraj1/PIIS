#!/usr/bin/env python3
"""Train and evaluate baseline fault category classifiers for PIIS.

Executes:
1. 5-Fold Stratified Group Cross-Validation (disjoint groups across folds).
2. Independent Seed Holdout (Seed 42 Train -> Seed 101 Test).
3. Out-Of-Distribution (OOD) Real Testbed Evaluation on TelecomTS.
4. Error analysis and confusion matrix generation.
5. Model artifact serialization with metadata sidecars.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
import yaml

from piis.classification.features import IncidentFeatureExtractor
from piis.classification.models import (
    FaultCategoryClassifier,
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
        default=Path("configs/experiments/m2_fault_classification.yaml"),
        help="Path to experiment configuration YAML",
    )
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 1. Load Data
    bench_path = Path(cfg["data"]["train_benchmark_path"])
    ood_path = Path(cfg["data"]["ood_real_holdout_path"])

    incidents = load_jsonl(bench_path)
    real_incidents = load_jsonl(ood_path)
    print(f"Loaded {len(incidents)} benchmark incidents from {bench_path}")
    print(f"Loaded {len(real_incidents)} real testbed incidents from {ood_path}")

    # Extract dataframe and target series for splitting
    extractor = IncidentFeatureExtractor(
        max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"]
    )
    df_feat, targets = extractor.prepare_dataframe(incidents, strict_quarantine=True)

    y_fault = targets["fault_category"].to_numpy()
    groups = targets["split_group_id"].to_numpy()

    # 2. 5-Fold Stratified Group Cross-Validation
    n_splits = cfg["evaluation"].get("cv_folds", 5)
    print(f"\n--- Running {n_splits}-Fold Stratified Group Cross-Validation ---")
    sgkf = StratifiedGroupKFold(n_splits=n_splits)

    models_to_test = ["logistic_regression", "random_forest"]
    cv_results: Dict[str, Dict[str, List[float]]] = {
        m: {"accuracy": [], "macro_f1": [], "weighted_f1": []} for m in models_to_test
    }

    for fold_idx, (train_idx, val_idx) in enumerate(sgkf.split(df_feat, y_fault, groups=groups), 1):
        train_records = [incidents[i] for i in train_idx]
        val_records = [incidents[i] for i in val_idx]
        y_val = [y_fault[i] for i in val_idx]

        for m_type in models_to_test:
            clf = FaultCategoryClassifier(
                model_type=m_type,
                max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"],
                random_state=cfg["random_seed"],
            )
            clf.fit(train_records)
            preds = clf.predict(val_records)
            m_metrics = compute_classification_metrics(y_val, preds, classes=sorted(list(set(y_val))))
            cv_results[m_type]["accuracy"].append(m_metrics["accuracy"])
            cv_results[m_type]["macro_f1"].append(m_metrics["macro_f1"])
            cv_results[m_type]["weighted_f1"].append(m_metrics["weighted_f1"])

    cv_summary: Dict[str, Any] = {}
    for m_type, scores in cv_results.items():
        cv_summary[m_type] = {
            "accuracy_mean": round(float(np.mean(scores["accuracy"])), 4),
            "accuracy_std": round(float(np.std(scores["accuracy"])), 4),
            "macro_f1_mean": round(float(np.mean(scores["macro_f1"])), 4),
            "macro_f1_std": round(float(np.std(scores["macro_f1"])), 4),
            "weighted_f1_mean": round(float(np.mean(scores["weighted_f1"])), 4),
            "weighted_f1_std": round(float(np.std(scores["weighted_f1"])), 4),
            "folds": scores,
        }
        print(
            f"[{m_type}] CV Macro-F1: {cv_summary[m_type]['macro_f1_mean']} "
            f"(+/- {cv_summary[m_type]['macro_f1_std']}) | "
            f"Accuracy: {cv_summary[m_type]['accuracy_mean']}"
        )

    # 3. Independent Seed Holdout Evaluation (Train: Seed 42, Test: Seed 101)
    print("\n--- Independent Seed Holdout (Seed 42 Train -> Seed 101 Test) ---")
    train_holdout = [inc for inc in incidents if "-seed-42" in inc.get("split_group_id", "")]
    test_holdout = [inc for inc in incidents if "-seed-101" in inc.get("split_group_id", "")]
    print(f"Train holdout: {len(train_holdout)} records | Test holdout: {len(test_holdout)} records")

    holdout_eval: Dict[str, Any] = {}
    best_clf: FaultCategoryClassifier | None = None
    best_rf: FaultCategoryClassifier | None = None

    y_test_true = [inc["fault_category"] for inc in test_holdout]

    for m_type in models_to_test:
        clf = FaultCategoryClassifier(
            model_type=m_type,
            max_tfidf_features=cfg["feature_extraction"]["max_tfidf_features"],
            random_state=cfg["random_seed"],
        )
        clf.fit(train_holdout)
        preds = clf.predict(test_holdout)
        probs = clf.predict_proba(test_holdout)
        h_metrics = compute_classification_metrics(y_test_true, preds, classes=clf.classes_, y_proba=probs)
        holdout_eval[m_type] = h_metrics

        print(
            f"[{m_type} Holdout] Test Accuracy: {h_metrics['accuracy']} | "
            f"Macro-F1: {h_metrics['macro_f1']} | "
            f"Mean Brier: {h_metrics.get('mean_brier_score', 'N/A')}"
        )

        if m_type == "logistic_regression":
            best_clf = clf
        elif m_type == "random_forest":
            best_rf = clf

    # 4. Out-of-Distribution (OOD) Real Testbed Evaluation (TelecomTS)
    print("\n--- OOD Evaluation on Real Testbed (SRC-002: TelecomTS Jamming) ---")
    ood_preds_lr = best_clf.predict(real_incidents) if best_clf else []
    ood_preds_rf = best_rf.predict(real_incidents) if best_rf else []

    ood_dist_lr = pd.Series(ood_preds_lr).value_counts().to_dict()
    ood_dist_rf = pd.Series(ood_preds_rf).value_counts().to_dict()
    print("Logistic Regression OOD Predictions on TelecomTS:", ood_dist_lr)
    print("Random Forest OOD Predictions on TelecomTS:", ood_dist_rf)

    # 5. Error Analysis on Test Holdout
    error_cases = []
    lr_preds = best_clf.predict(test_holdout) if best_clf else []
    for inc, true_lbl, pred_lbl in zip(test_holdout, y_test_true, lr_preds):
        if true_lbl != pred_lbl:
            error_cases.append({
                "incident_id": inc["incident_id"],
                "scenario_family_id": inc["scenario_family_id"],
                "true_fault": true_lbl,
                "predicted_fault": pred_lbl,
                "title": inc["title"],
                "description": inc["description"],
                "network_domain": inc["network_domain"],
            })

    print(f"\nIdentified {len(error_cases)} error cases in test holdout for Logistic Regression.")

    # 6. Save Model Artifacts
    models_dir = Path(cfg["outputs"]["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    if best_clf:
        best_clf.save(models_dir / "logistic_regression.joblib")
    if best_rf:
        best_rf.save(models_dir / "random_forest.joblib")
    print(f"Persisted trained model artifacts to {models_dir}")

    # 7. Save Machine-Readable Metrics
    metrics_path = Path(cfg["outputs"]["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    full_metrics = {
        "experiment_id": cfg["experiment_id"],
        "dataset_provenance": {
            "synthetic_corpus": str(bench_path),
            "synthetic_count": len(incidents),
            "real_holdout": str(ood_path),
            "real_count": len(real_incidents),
        },
        "cv_results": cv_summary,
        "holdout_results": holdout_eval,
        "ood_real_testbed_distribution": {
            "logistic_regression": ood_dist_lr,
            "random_forest": ood_dist_rf,
        },
        "error_analysis_summary": {
            "total_test_samples": len(test_holdout),
            "error_count": len(error_cases),
            "error_rate": round(len(error_cases) / max(1, len(test_holdout)), 4),
        },
    }
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(full_metrics, f, indent=2)

    # Confusion matrix
    cm_path = Path(cfg["outputs"]["confusion_matrix_path"])
    with cm_path.open("w", encoding="utf-8") as f:
        json.dump({
            "labels": holdout_eval["logistic_regression"]["labels"],
            "logistic_regression_raw": holdout_eval["logistic_regression"]["confusion_matrix"],
            "logistic_regression_norm": holdout_eval["logistic_regression"]["confusion_matrix_normalized"],
            "random_forest_raw": holdout_eval["random_forest"]["confusion_matrix"],
            "random_forest_norm": holdout_eval["random_forest"]["confusion_matrix_normalized"],
        }, f, indent=2)

    # Error analysis log
    err_path = Path(cfg["outputs"]["error_analysis_path"])
    with err_path.open("w", encoding="utf-8") as f:
        json.dump(error_cases, f, indent=2)

    print(f"Saved machine-readable metrics to {metrics_path}")
    print(f"Saved confusion matrix to {cm_path}")
    print(f"Saved error analysis to {err_path}")


if __name__ == "__main__":
    main()
