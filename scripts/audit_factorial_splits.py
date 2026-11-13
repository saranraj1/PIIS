#!/usr/bin/env python3
"""Audit Section A: Factorial Split Integrity and Shift Disentanglement.

Disentangles linguistic shift from causal shift:
1. Pure Linguistic Shift (Train T1, T2 across C1-C3 -> Test T3 across C1-C3)
2. Pure Causal Shift (Train C1, C2 across T1-T3 -> Test C3 across T1-T3)
3. Combined Shift (Train T1, T2 across C1, C2 -> Test T3 across C3)
4. Crossed Template Matrix (T_i -> T_j)
5. Unseen Fault Subtype with Known Parent Category
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from sklearn.metrics import accuracy_score, f1_score

from piis.classification.models import (
    FaultCategoryClassifier,
    compute_classification_metrics,
)
from piis.synthetic.generator_v2 import TelecomScenarioGeneratorV2


def generate_full_factorial_corpus(variants_per_cell: int = 5) -> List[Dict[str, Any]]:
    """Generate all 9 combinations of (Template, CausalConfig) per family."""
    gen = TelecomScenarioGeneratorV2(seed=42)
    corpus = []
    for fam in gen.FAMILIES:
        for tmpl in ["T1", "T2", "T3"]:
            for c_cfg in ["C1", "C2", "C3"]:
                for v in range(1, variants_per_cell + 1):
                    rec = gen.generate_incident(
                        scenario_family=fam,
                        template_id=tmpl,
                        causal_config_id=c_cfg,
                        variant_idx=v,
                        validate=True,
                    )
                    corpus.append(rec)
    return corpus


def evaluate_split(
    train_recs: List[Dict[str, Any]],
    test_recs: List[Dict[str, Any]],
    target_col: str = "fault_category",
) -> Dict[str, Any]:
    y_test = [r[target_col] for r in test_recs]
    clf = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    clf.fit(train_recs)
    preds = clf.predict(test_recs)
    probs = clf.predict_proba(test_recs)
    return compute_classification_metrics(y_test, preds, classes=clf.classes_, y_proba=probs)


def main() -> None:
    print("Generating full factorial corpus (540 records)...")
    corpus = generate_full_factorial_corpus(variants_per_cell=5)
    print(f"Total factorial records generated: {len(corpus)}")

    # 1. Pure Linguistic Shift: Train T1, T2 (C1..C3) -> Test T3 (C1..C3)
    train_ling = [r for r in corpus if r["metadata"]["template_id"] in ["T1", "T2"]]
    test_ling = [r for r in corpus if r["metadata"]["template_id"] == "T3"]
    res_ling = evaluate_split(train_ling, test_ling)
    print(f"\n1. Pure Linguistic Shift (T1,T2 -> T3, All Causal): Acc = {res_ling['accuracy']:.4f} | F1 = {res_ling['macro_f1']:.4f}")

    # 2. Pure Causal Shift: Train C1, C2 (T1..T3) -> Test C3 (T1..T3)
    train_causal = [r for r in corpus if r["metadata"]["causal_configuration_id"] in ["C1", "C2"]]
    test_causal = [r for r in corpus if r["metadata"]["causal_configuration_id"] == "C3"]
    res_causal = evaluate_split(train_causal, test_causal)
    print(f"2. Pure Causal Shift (C1,C2 -> C3, All Templates): Acc = {res_causal['accuracy']:.4f} | F1 = {res_causal['macro_f1']:.4f}")

    # 3. Combined Shift: Train T1, T2 (C1, C2) -> Test T3 (C3)
    train_comb = [
        r for r in corpus
        if r["metadata"]["template_id"] in ["T1", "T2"]
        and r["metadata"]["causal_configuration_id"] in ["C1", "C2"]
    ]
    test_comb = [
        r for r in corpus
        if r["metadata"]["template_id"] == "T3"
        and r["metadata"]["causal_configuration_id"] == "C3"
    ]
    res_comb = evaluate_split(train_comb, test_comb)
    print(f"3. Combined Shift (T1,T2; C1,C2 -> T3; C3):        Acc = {res_comb['accuracy']:.4f} | F1 = {res_comb['macro_f1']:.4f}")

    # 4. Crossed Template Matrix (T_i -> T_j)
    print("\n4. Crossed Template Transfer Matrix (Acc / F1):")
    template_matrix = {}
    for t_train in ["T1", "T2", "T3"]:
        template_matrix[t_train] = {}
        tr = [r for r in corpus if r["metadata"]["template_id"] == t_train]
        for t_test in ["T1", "T2", "T3"]:
            te = [r for r in corpus if r["metadata"]["template_id"] == t_test]
            m = evaluate_split(tr, te)
            template_matrix[t_train][t_test] = {"acc": m["accuracy"], "f1": m["macro_f1"]}
            print(f"   Train {t_train} -> Test {t_test}: Acc = {m['accuracy']:.4f} | F1 = {m['macro_f1']:.4f}")

    # 5. Unseen Fault Subtype with Known Parent Category
    # E.g., hold out FAM-01 (ran_signal_degradation) and FAM-07 (user_plane_degradation)
    # Test if parent network_domain is correctly predicted
    print("\n5. Unseen Fault Subtype / Category Hierarchical Generalization:")
    holdout_fams = ["FAM-01", "FAM-07"]  # RAN degradation and Core UPF drop
    train_hier = [r for r in corpus if r["scenario_family_id"] not in holdout_fams]
    test_hier = [r for r in corpus if r["scenario_family_id"] in holdout_fams]

    # Evaluate domain classifier
    clf_dom = FaultCategoryClassifier(model_type="logistic_regression", random_state=42)
    # Modify targets in place for domain prediction
    for r in train_hier:
        r["target_domain"] = r["network_domain"]
    for r in test_hier:
        r["target_domain"] = r["network_domain"]

    # We evaluate domain accuracy using IncidentFeatureExtractor
    extractor = clf_dom.extractor
    df_tr, targets_tr = extractor.prepare_dataframe(train_hier)
    df_te, targets_te = extractor.prepare_dataframe(test_hier)

    X_tr = extractor.fit_transform(df_tr)
    X_te = extractor.transform(df_te)

    from sklearn.preprocessing import LabelEncoder
    le_dom = LabelEncoder()
    y_tr_dom = le_dom.fit_transform([r["network_domain"] for r in train_hier])
    y_te_dom = [r["network_domain"] for r in test_hier]

    clf_dom.model.fit(X_tr, y_tr_dom)
    p_te_dom_enc = clf_dom.model.predict(X_te)
    p_te_dom = le_dom.inverse_transform(p_te_dom_enc)

    hier_acc = accuracy_score(y_te_dom, p_te_dom)
    hier_f1 = f1_score(y_te_dom, p_te_dom, average="macro", zero_division=0)
    print(f"   Unseen Subtypes Held Out: {holdout_fams}")
    print(f"   Parent Domain Accuracy on Held-Out Subtypes: {hier_acc:.4f} | Macro-F1: {hier_f1:.4f}")

    # Save results
    out_path = Path("artifacts/m2_1_metrics/audit_factorial_splits_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full_audit_a = {
        "pure_linguistic_shift": res_ling,
        "pure_causal_shift": res_causal,
        "combined_shift": res_comb,
        "crossed_template_matrix": template_matrix,
        "unseen_subtype_hierarchical": {
            "held_out_families": holdout_fams,
            "domain_accuracy": round(float(hier_acc), 4),
            "domain_macro_f1": round(float(hier_f1), 4),
        },
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(full_audit_a, f, indent=2)
    print(f"\nPersisted factorial audit results to {out_path}")


if __name__ == "__main__":
    main()
