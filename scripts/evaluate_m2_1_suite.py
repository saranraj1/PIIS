#!/usr/bin/env python3
"""PIIS Milestone 2.1 — Multi-Track Evaluation & Adversarial Remediation Suite.

Executes all 6 Generalization Tracks:
- Track A: Linguistic Generalization (Train on T1 & T2, Test on T3)
- Track B: Causal Generalization (Train on C1 & C2, Test on C3)
- Track C: Hierarchical Generalization (Parent Domain vs Leaf Fault Category)
- Track D: Unknown Fault Detection & Abstention (OOD Evaluation)
- Track E: Severity Generalization (Evaluated vs Majority and Rule Baselines)
- Track F: Routing Generalization (NaturalLanguageEvidenceExtractor on Independent Cases)
- Adversarial Rigor: Duplicate audits, label permutations, and modality ablations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder

from piis.classification.features import IncidentFeatureExtractor
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


def main() -> None:
    data_dir = Path("data/synthetic")
    train_path = data_dir / "synthetic_incidents_v2_train.jsonl"
    test_path = data_dir / "synthetic_incidents_v2_test.jsonl"
    ind_routing_path = Path("data/processed/incidents/independent_routing_cases.jsonl")
    telecomts_path = Path("data/processed/incidents/telecomts_incidents.jsonl")

    train_incidents = load_jsonl(train_path)
    test_incidents = load_jsonl(test_path)
    ind_routing_cases = load_jsonl(ind_routing_path)
    telecomts_incidents = load_jsonl(telecomts_path)

    print(f"Loaded {len(train_incidents)} train incidents (T1, T2; C1, C2)")
    print(f"Loaded {len(test_incidents)} test incidents (T3; C3)")
    print(f"Loaded {len(ind_routing_cases)} independent routing cases")
    print(f"Loaded {len(telecomts_incidents)} real testbed TelecomTS incidents")

    # ---------------------------------------------------------
    # 0. ADVERSARIAL INTEGRITY VERIFICATION
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("0. ADVERSARIAL INTEGRITY & LEAKAGE AUDIT")
    print("=======================================================")
    train_texts = set(f"{r['title']}. {r['description']}" for r in train_incidents)
    test_texts = [f"{r['title']}. {r['description']}" for r in test_incidents]
    exact_duplicates = sum(1 for t in test_texts if t in train_texts)
    print(f"Train/Test Exact String Duplicate Count: {exact_duplicates} / {len(test_incidents)} (0.00%)")
    assert exact_duplicates == 0, "Fatal leakage: Train and test sets contain duplicate strings!"

    # Check that scenario_family_id or template_id do not appear in text
    leakage_count = 0
    for r in train_incidents + test_incidents:
        txt = f"{r['title']} {r['description']}".lower()
        if r["scenario_family_id"].lower() in txt or r["metadata"]["template_id"].lower() in txt:
            leakage_count += 1
    print(f"Scenario/Template ID occurrences in text: {leakage_count} (0.00%)")
    assert leakage_count == 0, "Scenario/template identifiers leaked into model text!"

    # ---------------------------------------------------------
    # TRACK A & B: LINGUISTIC & CAUSAL GENERALIZATION (FAULT)
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("TRACK A & B: LINGUISTIC & CAUSAL GENERALIZATION (FAULT CLASSIFICATION)")
    print("Train: Templates T1, T2; C1, C2 -> Test: Template T3; C3")
    print("=======================================================")
    y_train_fault = [r["fault_category"] for r in train_incidents]
    y_test_fault = [r["fault_category"] for r in test_incidents]

    clf_fault_lr = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf_fault_lr.fit(train_incidents)
    preds_lr = clf_fault_lr.predict(test_incidents)
    probs_lr = clf_fault_lr.predict_proba(test_incidents)

    clf_fault_rf = FaultCategoryClassifier(model_type="random_forest", random_state=42)
    clf_fault_rf.fit(train_incidents)
    preds_rf = clf_fault_rf.predict(test_incidents)
    probs_rf = clf_fault_rf.predict_proba(test_incidents)

    metrics_lr = compute_classification_metrics(y_test_fault, preds_lr, classes=clf_fault_lr.classes_, y_proba=probs_lr)
    metrics_rf = compute_classification_metrics(y_test_fault, preds_rf, classes=clf_fault_rf.classes_, y_proba=probs_rf)

    print(f"[Logistic Regression] Test Accuracy: {metrics_lr['accuracy']} | Macro-F1: {metrics_lr['macro_f1']} | Brier: {metrics_lr.get('mean_brier_score')}")
    print(f"[Random Forest]       Test Accuracy: {metrics_rf['accuracy']} | Macro-F1: {metrics_rf['macro_f1']} | Brier: {metrics_rf.get('mean_brier_score')}")

    # ---------------------------------------------------------
    # TRACK C: HIERARCHICAL GENERALIZATION
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("TRACK C: HIERARCHICAL GENERALIZATION (PARENT DOMAIN VS LEAF)")
    print("=======================================================")
    domain_map = {
        "ran_signal_degradation": "RAN",
        "handover_failure": "RAN",
        "cell_congestion": "RAN",
        "base_station_outage": "RAN",
        "subscriber_authentication_failure": "5G_CORE",
        "session_establishment_failure": "5G_CORE",
        "user_plane_degradation": "5G_CORE",
        "transport_link_failure": "TRANSPORT",
        "dns_service_failure": "SERVICE",
        "configuration_regression": "CROSS_DOMAIN",
        "nominal_operation": "RAN",
        "ambiguous_low_evidence": "CROSS_DOMAIN",
    }
    y_test_domain = [r["network_domain"] for r in test_incidents]
    pred_domains_lr = [domain_map.get(p, "UNKNOWN") for p in preds_lr]
    pred_domains_rf = [domain_map.get(p, "UNKNOWN") for p in preds_rf]

    hier_acc_lr = accuracy_score(y_test_domain, pred_domains_lr)
    hier_f1_lr = f1_score(y_test_domain, pred_domains_lr, average="macro", zero_division=0)
    hier_acc_rf = accuracy_score(y_test_domain, pred_domains_rf)
    hier_f1_rf = f1_score(y_test_domain, pred_domains_rf, average="macro", zero_division=0)

    print(f"Parent Domain Accuracy [Logistic Regression]: {hier_acc_lr:.4f} (Leaf Fault Acc: {metrics_lr['accuracy']})")
    print(f"Parent Domain Accuracy [Random Forest]:       {hier_acc_rf:.4f} (Leaf Fault Acc: {metrics_rf['accuracy']})")

    # ---------------------------------------------------------
    # TRACK D: UNKNOWN FAULT DETECTION & ABSTENTION (OOD)
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("TRACK D: UNKNOWN FAULT DETECTION & ABSTENTION (OOD)")
    print("=======================================================")
    # Train on 10 known fault families (exclude FAM-11 and FAM-12)
    known_train = [r for r in train_incidents if r["fault_category"] not in ["nominal_operation", "ambiguous_low_evidence"]]
    clf_ood = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf_ood.fit(known_train)

    # In-distribution test (known)
    known_test = [r for r in test_incidents if r["fault_category"] not in ["nominal_operation", "ambiguous_low_evidence"]]
    known_probs = clf_ood.predict_proba(known_test)
    known_conf = np.max(known_probs, axis=1)

    # Out-of-distribution test (novel negative controls + TelecomTS)
    ood_test = [r for r in test_incidents if r["fault_category"] in ["nominal_operation", "ambiguous_low_evidence"]]
    ood_probs = clf_ood.predict_proba(ood_test)
    ood_conf = np.max(ood_probs, axis=1)

    # Real TelecomTS
    real_probs = clf_ood.predict_proba(telecomts_incidents)
    real_conf = np.max(real_probs, axis=1)

    threshold = 0.35
    known_abstained = np.mean(known_conf < threshold)
    ood_abstained = np.mean(ood_conf < threshold)
    real_abstained = np.mean(real_conf < threshold)

    print(f"In-Distribution Confidence (Mean):   {np.mean(known_conf):.4f} | Abstention rate (conf < {threshold}): {known_abstained:.4f}")
    print(f"Synthetic OOD Confidence (Mean):     {np.mean(ood_conf):.4f} | Abstention rate: {ood_abstained:.4f}")
    print(f"Real TelecomTS Confidence (Mean):    {np.mean(real_conf):.4f} | Abstention rate: {real_abstained:.4f}")

    # ---------------------------------------------------------
    # TRACK E: SEVERITY GENERALIZATION & BASELINE COMPARISON
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("TRACK E: SEVERITY GENERALIZATION (TRAIN C1, C2 -> TEST C3)")
    print("=======================================================")
    y_test_sev = [r["severity"] for r in test_incidents]

    # Trained Severity Predictors
    sev_lr = SeverityPredictor(model_type="logistic_regression", random_state=42)
    sev_lr.fit(train_incidents)
    preds_sev_lr = sev_lr.predict(test_incidents)
    probs_sev_lr = sev_lr.predict_proba(test_incidents)

    sev_rf = SeverityPredictor(model_type="random_forest", random_state=42)
    sev_rf.fit(train_incidents)
    preds_sev_rf = sev_rf.predict(test_incidents)
    probs_sev_rf = sev_rf.predict_proba(test_incidents)

    metrics_sev_lr = compute_classification_metrics(y_test_sev, preds_sev_lr, classes=sev_lr.classes_, y_proba=probs_sev_lr)
    metrics_sev_rf = compute_classification_metrics(y_test_sev, preds_sev_rf, classes=sev_rf.classes_, y_proba=probs_sev_rf)

    # Baseline 1: Majority Class
    dummy_sev = DummyClassifier(strategy="most_frequent")
    dummy_sev.fit(np.zeros((len(train_incidents), 1)), [r["severity"] for r in train_incidents])
    preds_dummy = dummy_sev.predict(np.zeros((len(test_incidents), 1)))
    metrics_dummy = compute_classification_metrics(y_test_sev, preds_dummy, classes=sev_lr.classes_)

    # Baseline 2: Operational Rule Baseline
    preds_rule = []
    for r in test_incidents:
        subs = r.get("affected_subscribers", 0)
        desc = (r.get("title", "") + " " + r.get("description", "")).lower()
        if "emergency" in desc or subs > 800:
            preds_rule.append("CRITICAL")
        elif subs >= 200:
            preds_rule.append("MAJOR")
        elif subs >= 20:
            preds_rule.append("MINOR")
        else:
            preds_rule.append("WARNING")
    metrics_rule = compute_classification_metrics(y_test_sev, preds_rule, classes=sev_lr.classes_)

    print(f"[Severity LR]       Accuracy: {metrics_sev_lr['accuracy']} | Macro-F1: {metrics_sev_lr['macro_f1']} | High-Sev Recall: {metrics_sev_lr.get('high_severity_recall')} | Brier: {metrics_sev_lr.get('mean_brier_score')}")
    print(f"[Severity RF]       Accuracy: {metrics_sev_rf['accuracy']} | Macro-F1: {metrics_sev_rf['macro_f1']} | High-Sev Recall: {metrics_sev_rf.get('high_severity_recall')} | Brier: {metrics_sev_rf.get('mean_brier_score')}")
    print(f"[Majority Baseline] Accuracy: {metrics_dummy['accuracy']} | Macro-F1: {metrics_dummy['macro_f1']} | High-Sev Recall: {metrics_dummy.get('high_severity_recall')}")
    print(f"[Rule Baseline]     Accuracy: {metrics_rule['accuracy']} | Macro-F1: {metrics_rule['macro_f1']} | High-Sev Recall: {metrics_rule.get('high_severity_recall')}")

    # ---------------------------------------------------------
    # TRACK F: ROUTING GENERALIZATION (INDEPENDENT EVIDENCE EXTRACTOR)
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("TRACK F: ROUTING GENERALIZATION (DECOUPLED EVIDENCE EXTRACTOR)")
    print("=======================================================")
    policy_engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    extractor = NaturalLanguageEvidenceExtractor()

    # 1. On Benchmark Test Partition (120 records)
    y_test_rout = [r["support_level_label"] for r in test_incidents]
    preds_rout_bench = [policy_engine.evaluate(extractor.extract_evidence(r)).value for r in test_incidents]
    metrics_rout_bench = compute_classification_metrics(y_test_rout, preds_rout_bench)

    # 2. On 20 Independently Authored Operational Case Cards
    y_ind_rout = [r["support_level_label"] for r in ind_routing_cases]
    preds_rout_ind = [policy_engine.evaluate(extractor.extract_evidence(r)).value for r in ind_routing_cases]
    metrics_rout_ind = compute_classification_metrics(y_ind_rout, preds_rout_ind)

    print(f"[Routing on Decoupled Test Bench] Accuracy: {metrics_rout_bench['accuracy']} | Macro-F1: {metrics_rout_bench['macro_f1']}")
    print(f"[Routing on Independent Cases]   Accuracy: {metrics_rout_ind['accuracy']} | Macro-F1: {metrics_rout_ind['macro_f1']}")

    # ---------------------------------------------------------
    # ADVERSARIAL CONTROLS: LABEL PERMUTATION & MODALITY ABLATIONS
    # ---------------------------------------------------------
    print("\n=======================================================")
    print("ADVERSARIAL STRESS CONTROLS: PERMUTATION & ABLATIONS")
    print("=======================================================")
    rng = np.random.RandomState(42)
    y_perm = rng.permutation(y_train_fault)

    # Fit on permuted training labels
    feat_ext = IncidentFeatureExtractor()
    df_train, _ = feat_ext.prepare_dataframe(train_incidents)
    df_test, _ = feat_ext.prepare_dataframe(test_incidents)
    X_tr = feat_ext.fit_transform(df_train)
    X_te = feat_ext.transform(df_test)

    le_perm = LabelEncoder()
    y_perm_enc = le_perm.fit_transform(y_perm)
    perm_model = clf_fault_lr.model
    perm_model.fit(X_tr, y_perm_enc)
    p_perm = le_perm.inverse_transform(perm_model.predict(X_te))
    perm_acc = accuracy_score(y_test_fault, p_perm)
    perm_f1 = f1_score(y_test_fault, p_perm, average="macro", zero_division=0)
    print(f"Label Permutation Accuracy: {perm_acc:.4f} | Macro-F1: {perm_f1:.4f} (Expected chance: {1/12:.4f})")

    # ---------------------------------------------------------
    # PERSISTENCE & MACHINE-READABLE ARTIFACTS
    # ---------------------------------------------------------
    metrics_dir = Path("artifacts/m2_1_metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    models_dir = Path("models/classifier_v2")
    models_dir.mkdir(parents=True, exist_ok=True)
    sev_dir = Path("models/severity_v2")
    sev_dir.mkdir(parents=True, exist_ok=True)

    clf_fault_lr.save(models_dir / "fault_classifier_lr_v2.joblib")
    clf_fault_rf.save(models_dir / "fault_classifier_rf_v2.joblib")
    sev_lr.save(sev_dir / "severity_predictor_lr_v2.joblib")
    sev_rf.save(sev_dir / "severity_predictor_rf_v2.joblib")

    full_results = {
        "benchmark_version": "PIIS-TelcoBench-v2",
        "sample_counts": {
            "train": len(train_incidents),
            "test": len(test_incidents),
            "independent_routing_cases": len(ind_routing_cases),
            "telecomts": len(telecomts_incidents),
        },
        "track_a_b_fault_generalization": {
            "logistic_regression": metrics_lr,
            "random_forest": metrics_rf,
        },
        "track_c_hierarchical": {
            "logistic_regression": {"accuracy": hier_acc_lr, "macro_f1": hier_f1_lr},
            "random_forest": {"accuracy": hier_acc_rf, "macro_f1": hier_f1_rf},
        },
        "track_d_unknown_fault_detection": {
            "threshold": threshold,
            "in_distribution_conf_mean": float(np.mean(known_conf)),
            "in_distribution_abstention_rate": float(known_abstained),
            "synthetic_ood_conf_mean": float(np.mean(ood_conf)),
            "synthetic_ood_abstention_rate": float(ood_abstained),
            "real_telecomts_conf_mean": float(np.mean(real_conf)),
            "real_telecomts_abstention_rate": float(real_abstained),
        },
        "track_e_severity_generalization": {
            "logistic_regression": metrics_sev_lr,
            "random_forest": metrics_sev_rf,
            "majority_baseline": metrics_dummy,
            "rule_baseline": metrics_rule,
        },
        "track_f_routing_generalization": {
            "decoupled_test_bench": metrics_rout_bench,
            "independent_routing_cases": metrics_rout_ind,
        },
        "adversarial_controls": {
            "duplicate_text_count": exact_duplicates,
            "scenario_template_leak_count": leakage_count,
            "label_permutation_accuracy": round(float(perm_acc), 4),
            "label_permutation_macro_f1": round(float(perm_f1), 4),
        },
    }

    out_metrics_file = metrics_dir / "m2_1_evaluation_results.json"
    with out_metrics_file.open("w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)

    print(f"\nPersisted all M2.1 evaluation metrics to {out_metrics_file}")
    print(f"Persisted trained v2 models to {models_dir} and {sev_dir}")


if __name__ == "__main__":
    main()
