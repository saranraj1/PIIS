"""Evaluation script for telemetry anomaly detection (Milestone 3).

Evaluates Statistical Dynamic Thresholding, Isolation Forest, and Ensemble Pipeline
against TelecomTS real-world 5G jamming telemetry and synthetic telemetry streams.
Exports metrics to artifacts/m3_metrics/anomaly_detection_eval.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score

from piis.anomaly.isolation_forest import IsolationForestDetector
from piis.anomaly.pipeline import TelemetryAnomalyPipeline
from piis.anomaly.statistical import StatisticalThresholdDetector


def evaluate_telecomts(file_path: Path) -> Dict[str, Any]:
    """Evaluate anomaly detection on real TelecomTS 5G jammer telemetry."""
    records: List[Dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    df = pd.DataFrame(records)
    gt_series = df.groupby("timestamp").apply(
        lambda g: bool(g["metadata"].iloc[0].get("ground_truth_anomaly", False)),
        include_groups=False,
    )
    timestamps = gt_series.index.tolist()
    y_true = gt_series.values.astype(int)

    # 1. Isolation Forest Evaluation
    # Train on first half (nominal baseline)
    half_idx = len(df) // 2
    train_df = df.iloc[:half_idx]

    if_detector = IsolationForestDetector(contamination=0.08, random_state=42)
    if_detector.fit(train_df)
    if_scores, if_confs = if_detector.score(df)

    if_pr_auc = float(average_precision_score(y_true, if_scores))
    if_roc_auc = float(roc_auc_score(y_true, if_scores))
    if_preds = (if_scores >= 0.50).astype(int)
    p_if, r_if, f1_if, _ = precision_recall_fscore_support(y_true, if_preds, average="binary", zero_division=0)

    # 2. Statistical Dynamic Thresholding Evaluation
    stat_detector = StatisticalThresholdDetector(k_sigma=2.5)
    stat_violations = stat_detector.detect_batch(df)
    viol_timestamps = set(v.timestamp for v in stat_violations if v.timestamp)
    stat_preds = np.array([1 if t in viol_timestamps else 0 for t in timestamps])
    p_stat, r_stat, f1_stat, _ = precision_recall_fscore_support(y_true, stat_preds, average="binary", zero_division=0)

    # Compute continuous statistical and hybrid scores for ranking metrics
    viol_by_t = {}
    for v in stat_violations:
        if v.timestamp:
            viol_by_t.setdefault(v.timestamp, []).append(v)

    stat_scores = []
    fused_scores = []
    for idx, t in enumerate(timestamps):
        v_list = viol_by_t.get(t, [])
        if v_list:
            max_sig = max(v.deviation_sigmas for v in v_list)
            s_stat = min(1.0, max_sig / 5.0)
        else:
            s_stat = 0.0
        stat_scores.append(s_stat)
        fused_scores.append(max(s_stat, if_scores[idx]))

    stat_scores_arr = np.array(stat_scores)
    fused_scores_arr = np.array(fused_scores)
    stat_roc_auc = float(roc_auc_score(y_true, stat_scores_arr))
    stat_pr_auc = float(average_precision_score(y_true, stat_scores_arr))
    hybrid_roc_auc = float(roc_auc_score(y_true, fused_scores_arr))
    hybrid_pr_auc = float(average_precision_score(y_true, fused_scores_arr))

    # 3. Full Ensemble Pipeline Evaluation
    pipeline = TelemetryAnomalyPipeline(
        statistical_detector=stat_detector,
        ml_detector=if_detector,
        score_threshold=0.50,
    )
    anomalies = pipeline.process_dataframe(df, dataset_name="TelecomTS", source_type=records[0].get("source_type"))
    detected_timestamps = set(a.start_timestamp for a in anomalies)
    pipeline_preds = np.array([1 if t in detected_timestamps else 0 for t in timestamps])
    p_pipe, r_pipe, f1_pipe, _ = precision_recall_fscore_support(y_true, pipeline_preds, average="binary", zero_division=0)

    # Compute Detection Delay & False Alarm Rate
    anom_indices = np.where(y_true == 1)[0]
    first_anom_idx = int(anom_indices[0]) if len(anom_indices) > 0 else 0

    det_indices = np.where(pipeline_preds == 1)[0]
    det_in_episode = [idx for idx in det_indices if idx >= first_anom_idx]
    first_det_idx = int(det_in_episode[0]) if det_in_episode else None
    detection_delay_timesteps = (first_det_idx - first_anom_idx) if first_det_idx is not None else None

    # False Alarm Rate in nominal phase (before onset)
    nominal_preds = pipeline_preds[:first_anom_idx]
    far_nominal = float(np.mean(nominal_preds)) if len(nominal_preds) > 0 else 0.0

    tp = int(np.sum((y_true == 1) & (pipeline_preds == 1)))
    fp = int(np.sum((y_true == 0) & (pipeline_preds == 1)))
    fn = int(np.sum((y_true == 1) & (pipeline_preds == 0)))
    tn = int(np.sum((y_true == 0) & (pipeline_preds == 0)))

    return {
        "dataset": "AliMaatouk/TelecomTS",
        "total_timesteps": len(timestamps),
        "total_observations": len(df),
        "ground_truth_anomalies": int(np.sum(y_true)),
        "ground_truth_nominal": int(np.sum(y_true == 0)),
        "models": {
            "isolation_forest": {
                "pr_auc": round(if_pr_auc, 4),
                "roc_auc": round(if_roc_auc, 4),
                "precision": round(float(p_if), 4),
                "recall": round(float(r_if), 4),
                "f1_score": round(float(f1_if), 4),
            },
            "statistical_dynamic_threshold": {
                "roc_auc": round(stat_roc_auc, 4),
                "pr_auc": round(stat_pr_auc, 4),
                "precision": round(float(p_stat), 4),
                "recall": round(float(r_stat), 4),
                "f1_score": round(float(f1_stat), 4),
                "violating_metric_count": len(stat_violations),
            },
            "ensemble_pipeline": {
                "hybrid_continuous_fused_roc_auc": round(hybrid_roc_auc, 4),
                "hybrid_continuous_fused_pr_auc": round(hybrid_pr_auc, 4),
                "precision": round(float(p_pipe), 4),
                "recall": round(float(r_pipe), 4),
                "f1_score": round(float(f1_pipe), 4),
                "detection_delay_timesteps": detection_delay_timesteps,
                "false_alarm_rate_nominal": round(far_nominal, 4),
                "confusion_matrix": {
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                },
                "total_emitted_anomalies": len(anomalies),
            },
        },
    }


def main():
    root = Path(__file__).resolve().parents[1]
    telecomts_path = root / "data" / "processed" / "telemetry" / "telecomts_jammer_telemetry.jsonl"
    out_dir = root / "artifacts" / "m3_metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Running TelecomTS Telemetry Anomaly Detection Benchmark...")
    results = evaluate_telecomts(telecomts_path)

    out_file = out_dir / "anomaly_detection_eval.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Results exported to {out_file}")
    print("\nBenchmark Summary:")
    print(f"TelecomTS Ground-Truth Anomalies: {results['ground_truth_anomalies']} / {results['total_timesteps']}")
    print(f"Isolation Forest ROC-AUC: {results['models']['isolation_forest']['roc_auc']:.4f}")
    print(f"Statistical Dynamic ROC-AUC: {results['models']['statistical_dynamic_threshold']['roc_auc']:.4f}")
    print(f"Hybrid Fused Ensemble ROC-AUC: {results['models']['ensemble_pipeline']['hybrid_continuous_fused_roc_auc']:.4f}")
    print(f"Hybrid Fused Ensemble PR-AUC: {results['models']['ensemble_pipeline']['hybrid_continuous_fused_pr_auc']:.4f}")
    print(f"Statistical Detector Recall: {results['models']['statistical_dynamic_threshold']['recall']:.4f}")
    print(f"Ensemble Pipeline Precision: {results['models']['ensemble_pipeline']['precision']:.4f}")
    print(f"Ensemble Pipeline Recall: {results['models']['ensemble_pipeline']['recall']:.4f}")
    print(f"Ensemble Pipeline F1: {results['models']['ensemble_pipeline']['f1_score']:.4f}")
    print(f"Detection Delay: {results['models']['ensemble_pipeline']['detection_delay_timesteps']} timesteps")
    print(f"Nominal Phase False Alarm Rate: {results['models']['ensemble_pipeline']['false_alarm_rate_nominal']:.4f}")


if __name__ == "__main__":
    main()
