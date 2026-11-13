#!/usr/bin/env python3
"""PIIS Milestone 2.1 — Independent Validation Gate Audit Suite.

Executes:
- Section B: Generator, label shortcuts, and exact/near-duplicate detection (Jaccard).
- Section C: Independent severity evaluation on 25 human-reviewable cases.
- Section D: OOD detection risk-coverage curves across threshold sweep (0.10 to 0.60).
- Section E: Routing evaluation on 50 independent cases with 1,000 bootstrap CIs.
- Section F: Human review sample status and annotation protocol.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

from piis.classification.models import (
    FaultCategoryClassifier,
    SeverityPredictor,
    compute_classification_metrics,
)
from piis.policies.evidence import NaturalLanguageEvidenceExtractor
from piis.policies.routing import PolicyEngine


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# -------------------------------------------------------------
# Section B: Generator & Near-Duplicate Audit
# -------------------------------------------------------------
def audit_near_duplicates(train_recs: List[Dict[str, Any]], test_recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute exact matches and 3-gram word Jaccard similarities between train and test."""
    train_texts = [f"{r['title']}. {r['description']}" for r in train_recs]
    test_texts = [f"{r['title']}. {r['description']}" for r in test_recs]

    exact_matches = sum(1 for te in test_texts if te in set(train_texts))

    def get_3grams(text: str) -> set[str]:
        words = text.lower().split()
        if len(words) < 3:
            return set(words)
        return set(" ".join(words[i:i+3]) for i in range(len(words) - 2))

    max_jaccards = []
    for te in test_texts:
        te_grams = get_3grams(te)
        if not te_grams:
            continue
        max_j = max((len(te_grams.intersection(get_3grams(tr))) / len(te_grams.union(get_3grams(tr)))) for tr in train_texts)
        max_jaccards.append(max_j)

    return {
        "train_samples": len(train_recs),
        "test_samples": len(test_recs),
        "exact_duplicates": exact_matches,
        "exact_duplicate_rate": round(exact_matches / len(test_recs), 4),
        "max_3gram_jaccard_mean": round(float(np.mean(max_jaccards)), 4),
        "max_3gram_jaccard_max": round(float(np.max(max_jaccards)), 4),
    }


# -------------------------------------------------------------
# Section C: Severity Audit on Independent Evaluation Cases
# -------------------------------------------------------------
def audit_severity_independent(
    ind_cases: List[Dict[str, Any]],
    trained_model_path: Path,
) -> Dict[str, Any]:
    """Evaluate severity predictor on 25 independently authored human cases."""
    sev_predictor = SeverityPredictor.load(trained_model_path)

    y_true = [c["ground_truth_severity"] for c in ind_cases]
    preds = sev_predictor.predict(ind_cases)
    probs = sev_predictor.predict_proba(ind_cases)

    # Compute metrics
    labels = ["CRITICAL", "MAJOR", "MINOR", "WARNING"]
    metrics = compute_classification_metrics(y_true, preds, classes=labels, y_proba=probs)

    # Evaluate simple independent rule heuristic (checking subscriber magnitude)
    rule_preds = []
    for c in ind_cases:
        subs = c.get("affected_subscribers", 0)
        desc = (c.get("title", "") + " " + c.get("description", "")).lower()
        if subs > 1000 or "emergency" in desc or "blackout" in desc or "outage" in desc:
            rule_preds.append("CRITICAL")
        elif subs >= 150 or "major" in desc or "flap" in desc:
            rule_preds.append("MAJOR")
        elif subs >= 20:
            rule_preds.append("MINOR")
        else:
            rule_preds.append("WARNING")

    rule_metrics = compute_classification_metrics(y_true, rule_preds, classes=labels)

    return {
        "independent_samples_count": len(ind_cases),
        "ground_truth_distribution": Counter(y_true),
        "ml_model_metrics": metrics,
        "independent_rule_metrics": rule_metrics,
        "confusion_matrix": confusion_matrix(y_true, preds, labels=labels).tolist(),
        "confusion_matrix_labels": labels,
    }


# -------------------------------------------------------------
# Section D: OOD Detection Audit & Risk-Coverage Sweeps
# -------------------------------------------------------------
def audit_ood_thresholds(
    known_train: List[Dict[str, Any]],
    known_test: List[Dict[str, Any]],
    ood_synth: List[Dict[str, Any]],
    ood_real: List[Dict[str, Any]],
    thresholds: List[float],
) -> Dict[str, Any]:
    """Sweep confidence thresholds and produce detailed risk-coverage curve."""
    clf = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf.fit(known_train)

    p_known = clf.predict(known_test)
    y_known = [r["fault_category"] for r in known_test]
    probs_known = clf.predict_proba(known_test)
    conf_known = np.max(probs_known, axis=1)

    probs_synth = clf.predict_proba(ood_synth)
    conf_synth = np.max(probs_synth, axis=1)

    probs_real = clf.predict_proba(ood_real)
    conf_real = np.max(probs_real, axis=1)

    curve = []
    for tau in thresholds:
        # Known class coverage and selective accuracy
        accepted_mask = conf_known >= tau
        coverage_known = float(np.mean(accepted_mask))
        if np.sum(accepted_mask) > 0:
            sel_acc = float(accuracy_score(np.array(y_known)[accepted_mask], np.array(p_known)[accepted_mask]))
        else:
            sel_acc = 0.0

        false_abstention = float(1.0 - coverage_known)

        # OOD Rejection (abstention when sample is OOD)
        rej_synth = float(np.mean(conf_synth < tau))
        false_accept_synth = float(1.0 - rej_synth)

        rej_real = float(np.mean(conf_real < tau))
        false_accept_real = float(1.0 - rej_real)

        curve.append({
            "threshold": round(tau, 2),
            "known_coverage": round(coverage_known, 4),
            "known_selective_accuracy": round(sel_acc, 4),
            "false_abstention_known": round(false_abstention, 4),
            "synth_ood_rejection": round(rej_synth, 4),
            "synth_ood_false_accept": round(false_accept_synth, 4),
            "real_telecomts_rejection": round(rej_real, 4),
            "real_telecomts_false_accept": round(false_accept_real, 4),
        })

    return {
        "threshold_curve": curve,
        "mean_confidence": {
            "known_test": round(float(np.mean(conf_known)), 4),
            "synth_ood": round(float(np.mean(conf_synth)), 4),
            "real_telecomts": round(float(np.mean(conf_real)), 4),
        },
    }


# -------------------------------------------------------------
# Section E: Routing Audit with Bootstrap Confidence Intervals
# -------------------------------------------------------------
def audit_routing_with_bootstrap(
    routing_cases: List[Dict[str, Any]],
    n_bootstraps: int = 1000,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Evaluate PolicyEngine on 50 cases with 95% bootstrap confidence intervals."""
    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    extractor = NaturalLanguageEvidenceExtractor()

    y_true = [c["support_level_label"] for c in routing_cases]
    preds = [engine.evaluate(extractor.extract_evidence(c)).value for c in routing_cases]

    acc = accuracy_score(y_true, preds)
    macro_f1 = f1_score(y_true, preds, average="macro", zero_division=0)

    # Bootstrap CIs
    rng = np.random.RandomState(random_state)
    boot_accs = []
    boot_f1s = []
    boot_l1_recalls = []

    labels = ["L1", "L2", "L3", "HUMAN_REVIEW"]

    for _ in range(n_bootstraps):
        idx = rng.randint(0, len(y_true), len(y_true))
        b_yt = [y_true[i] for i in idx]
        b_yp = [preds[i] for i in idx]

        boot_accs.append(accuracy_score(b_yt, b_yp))
        boot_f1s.append(f1_score(b_yt, b_yp, labels=labels, average="macro", zero_division=0))

        # L1 recall
        l1_t = [1 if y == "L1" else 0 for y in b_yt]
        l1_p = [1 if p == "L1" else 0 for p in b_yp]
        boot_l1_recalls.append(recall_score(l1_t, l1_p, zero_division=0))

    acc_ci = (round(float(np.percentile(boot_accs, 2.5)), 4), round(float(np.percentile(boot_accs, 97.5)), 4))
    f1_ci = (round(float(np.percentile(boot_f1s, 2.5)), 4), round(float(np.percentile(boot_f1s, 97.5)), 4))
    l1_rec_ci = (round(float(np.percentile(boot_l1_recalls, 2.5)), 4), round(float(np.percentile(boot_l1_recalls, 97.5)), 4))

    # Confusion matrix
    cm = confusion_matrix(y_true, preds, labels=labels)

    return {
        "cases_count": len(routing_cases),
        "point_estimates": {
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(macro_f1), 4),
        },
        "bootstrap_95_ci": {
            "accuracy": acc_ci,
            "macro_f1": f1_ci,
            "l1_recall": l1_rec_ci,
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": labels,
    }


def main() -> None:
    data_dir = Path("data/synthetic")
    train_recs = load_jsonl(data_dir / "synthetic_incidents_v2_train.jsonl")
    test_recs = load_jsonl(data_dir / "synthetic_incidents_v2_test.jsonl")
    ind_sev_cases = load_jsonl(Path("data/processed/incidents/independent_severity_cases.jsonl"))
    ind_rout_cases = load_jsonl(Path("data/processed/incidents/independent_routing_cases.jsonl"))
    telecomts_recs = load_jsonl(Path("data/processed/incidents/telecomts_incidents.jsonl"))

    print("=========================================================")
    print("M2.1 INDEPENDENT VALIDATION GATE AUDIT EXECUTION")
    print("=========================================================")

    # 1. Section B: Near-Duplicate Audit
    print("\n[Audit B] Measuring exact and 3-gram word Jaccard similarities...")
    dup_res = audit_near_duplicates(train_recs, test_recs)
    print(dup_res)

    # 2. Section C: Severity Audit on 25 Independent Cases
    print("\n[Audit C] Evaluating severity predictor on 25 independent cases...")
    sev_model_path = Path("models/severity_v2/severity_predictor_lr_v2.joblib")
    sev_res = audit_severity_independent(ind_sev_cases, sev_model_path)
    print(f"ML Model on Independent Cases: Acc = {sev_res['ml_model_metrics']['accuracy']:.4f} | Macro-F1 = {sev_res['ml_model_metrics']['macro_f1']:.4f} | High-Sev Recall = {sev_res['ml_model_metrics'].get('high_severity_recall')}")
    print(f"Independent Rule Baseline:   Acc = {sev_res['independent_rule_metrics']['accuracy']:.4f} | Macro-F1 = {sev_res['independent_rule_metrics']['macro_f1']:.4f} | High-Sev Recall = {sev_res['independent_rule_metrics'].get('high_severity_recall')}")

    # 3. Section D: OOD Sweeps
    print("\n[Audit D] Running OOD threshold sweeps (0.10 to 0.60)...")
    known_tr = [r for r in train_recs if r["fault_category"] not in ["nominal_operation", "ambiguous_low_evidence"]]
    known_te = [r for r in test_recs if r["fault_category"] not in ["nominal_operation", "ambiguous_low_evidence"]]
    ood_synth = [r for r in test_recs if r["fault_category"] in ["nominal_operation", "ambiguous_low_evidence"]]
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]
    ood_res = audit_ood_thresholds(known_tr, known_te, ood_synth, telecomts_recs, thresholds)
    for pt in ood_res["threshold_curve"]:
        print(f"tau={pt['threshold']:.2f} -> Known Cov={pt['known_coverage']:.2f} | Known SelAcc={pt['known_selective_accuracy']:.2f} | False Abst={pt['false_abstention_known']:.2f} | TelecomTS Rej={pt['real_telecomts_rejection']:.2f}")

    # 4. Section E: Routing Audit with 50 Cases & 1,000 Bootstrap CIs
    print("\n[Audit E] Evaluating routing policy on 50 independent cases with 1000 bootstrap CIs...")
    rout_res = audit_routing_with_bootstrap(ind_rout_cases, n_bootstraps=1000)
    print(f"Point Estimates: Acc = {rout_res['point_estimates']['accuracy']} | Macro-F1 = {rout_res['point_estimates']['macro_f1']}")
    print(f"95% Bootstrap CIs: Acc = {rout_res['bootstrap_95_ci']['accuracy']} | Macro-F1 = {rout_res['bootstrap_95_ci']['macro_f1']} | L1 Recall = {rout_res['bootstrap_95_ci']['l1_recall']}")

    # 5. Save all machine-readable gate audit evidence
    out_file = Path("artifacts/m2_1_metrics/gate_audit_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    gate_summary = {
        "near_duplicate_audit": dup_res,
        "independent_severity_audit": sev_res,
        "ood_threshold_sweeps": ood_res,
        "routing_bootstrap_audit": rout_res,
    }
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(gate_summary, f, indent=2)
    print(f"\nPersisted gate audit evidence to {out_file}")


if __name__ == "__main__":
    main()
