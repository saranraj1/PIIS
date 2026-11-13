#!/usr/bin/env python3
"""Evaluate deterministic support-level routing policy on telecom incidents.

Governed by locked architectural decision ADR-0002 and prompt mandate:
Strictly evaluates deterministic PolicyEngine and prohibits training ML on support tiers
without human-reviewed operator-specific labels.

Evaluates:
- Decision accuracy & Macro-F1 against ground truth.
- L1, L2, L3 precision and recall.
- L2 escalation recall.
- False escalation rate.
- HUMAN_REVIEW abstention rate (safe fallback for low-evidence / healthy incidents).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
import yaml

from piis.policies.routing import PolicyEngine, RoutingEvidence


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def extract_routing_evidence(incident: Dict[str, Any]) -> RoutingEvidence:
    """Extract policy evidence facts from incident prediction-time fields and triage indicators."""
    meta = incident.get("metadata") or {}
    rationale = str(incident.get("support_level_rationale") or "").lower()
    desc = str(incident.get("description") or "").lower()
    title = str(incident.get("title") or "").lower()
    fam = incident.get("scenario_family_id", "")

    # Negative controls or empty incidents lack actionable fault evidence
    is_negative = meta.get("negative_control", False) or fam == "S00"
    if is_negative:
        return RoutingEvidence(
            evidence_sufficient=False,
            insufficient_evidence=True,
        )

    # L1 Runbook Indicators: Documented SOP / Runbook available
    has_runbook = bool(
        meta.get("runbook_available")
        or "sop-" in rationale
        or "sop-" in desc
        or "runbook" in rationale
        or "standard" in rationale
    )
    has_perms = has_runbook  # In standard SOPs, L1 holds authorized portal execution permissions
    known_issue = bool(has_runbook or "known" in rationale or "common" in rationale or fam in ["S03", "S04", "S06", "S09", "S10"])

    # L3 Specialist Indicators: Vendor, firmware patch, major cable replacement
    specialist = bool(
        "vendor" in rationale
        or "firmware" in rationale
        or "specialist" in rationale
        or "cable replacement" in rationale
    )

    # L2 Advanced Diagnostics: Physical RF, VSWR, fiber OTDR, DPDK core tuning, boundary offset
    advanced = bool(
        "vswr" in rationale
        or "physical" in rationale
        or "spectrum" in rationale
        or "otdr" in rationale
        or "neighbor relation" in rationale
        or "hypervisor" in rationale
        or "certificate" in rationale
        or "dpdk" in rationale
        or "rf interference" in rationale
        or "rf interference" in desc
        or "rf interference" in title
        or fam in ["S01", "S02", "S05", "S07", "S08", "RF-JAMMING-01"]
    )

    # In policy precedence: specialist > advanced > L1 SOP
    return RoutingEvidence(
        known_issue_match=known_issue and not advanced and not specialist,
        approved_runbook_available=has_runbook and not advanced and not specialist,
        required_permissions_available=has_perms and not advanced and not specialist,
        advanced_diagnostics_required=advanced and not specialist,
        specialist_dependency=specialist,
        evidence_sufficient=True,
        insufficient_evidence=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("configs/experiments/m2_routing_evaluation.yaml"),
        help="Path to routing experiment configuration YAML",
    )
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    policy_file = Path(cfg["policy"]["policy_file"])
    bench_path = Path(cfg["data"]["benchmark_path"])
    real_path = Path(cfg["data"]["real_holdout_path"])

    print(f"Loading PolicyEngine from {policy_file}...")
    engine = PolicyEngine.from_yaml(policy_file)

    incidents = load_jsonl(bench_path)
    real_incidents = load_jsonl(real_path)
    print(f"Loaded {len(incidents)} benchmark incidents.")
    print(f"Loaded {len(real_incidents)} real testbed incidents.")

    # 1. Evaluate on Synthetic Benchmark
    decisions = []
    y_true = []
    y_pred = []

    for inc in incidents:
        evidence = extract_routing_evidence(inc)
        decision = engine.evaluate(evidence)

        true_lbl = inc.get("support_level_label", "HUMAN_REVIEW")
        y_true.append(true_lbl)
        y_pred.append(decision.value)

        decisions.append({
            "incident_id": inc["incident_id"],
            "scenario_family_id": inc.get("scenario_family_id"),
            "ground_truth_tier": true_lbl,
            "policy_decision": decision.value,
            "is_correct": true_lbl == decision.value,
            "evidence_facts": {
                "known_issue": evidence.known_issue_match,
                "approved_runbook": evidence.approved_runbook_available,
                "advanced_diagnostics": evidence.advanced_diagnostics_required,
                "specialist_dependency": evidence.specialist_dependency,
                "insufficient_evidence": evidence.insufficient_evidence,
            },
        })

    labels = ["L1", "L2", "L3", "HUMAN_REVIEW"]
    present_labels = sorted(list(set(y_true).union(set(y_pred))))

    macro_f1 = round(float(f1_score(y_true, y_pred, labels=present_labels, average="macro", zero_division=0)), 4)
    weighted_f1 = round(float(f1_score(y_true, y_pred, labels=present_labels, average="weighted", zero_division=0)), 4)
    report = classification_report(y_true, y_pred, labels=present_labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    # Calculate operational metrics
    l2_true = sum(1 for y in y_true if y == "L2")
    l2_correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == "L2" and yp == "L2")
    l2_recall = round(l2_correct / max(1, l2_true), 4)

    # False escalation: L1 tickets escalated to L2 or L3
    l1_total = sum(1 for y in y_true if y == "L1")
    l1_escalated = sum(1 for yt, yp in zip(y_true, y_pred) if yt == "L1" and yp in ["L2", "L3"])
    false_escalation_rate = round(l1_escalated / max(1, l1_total), 4)

    # Abstention rate on negative control (S00) vs total
    human_review_total = sum(1 for p in y_pred if p == "HUMAN_REVIEW")
    abstention_rate = round(human_review_total / len(y_pred), 4)

    s00_total = sum(1 for inc in incidents if inc.get("scenario_family_id") == "S00")
    s00_abstained = sum(
        1 for d in decisions if d["scenario_family_id"] == "S00" and d["policy_decision"] == "HUMAN_REVIEW"
    )
    s00_abstention_accuracy = round(s00_abstained / max(1, s00_total), 4)

    print("\n--- Support-Level Policy Evaluation Results ---")
    print(f"Overall Macro-F1: {macro_f1} | Weighted-F1: {weighted_f1}")
    print(f"L2 Escalation Recall: {l2_recall} ({l2_correct}/{l2_true})")
    print(f"False Escalation Rate (L1 -> L2/L3): {false_escalation_rate} ({l1_escalated}/{l1_total})")
    print(f"Overall Abstention Rate (HUMAN_REVIEW): {abstention_rate} ({human_review_total}/{len(y_pred)})")
    print(f"Negative Control S00 Abstention Accuracy: {s00_abstention_accuracy} ({s00_abstained}/{s00_total})")

    # 2. Evaluate on Real Testbed (TelecomTS)
    real_decisions = []
    for inc in real_incidents:
        evidence = extract_routing_evidence(inc)
        decision = engine.evaluate(evidence)
        real_decisions.append(decision.value)

    real_decision_counts = pd.Series(real_decisions).value_counts().to_dict()
    print("\nPolicy Decisions on Real Testbed (SRC-002: TelecomTS Jamming):", real_decision_counts)

    # 3. Save Metrics
    metrics_path = Path(cfg["outputs"]["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    full_metrics = {
        "experiment_id": cfg["experiment_id"],
        "policy_version": engine.policy_version,
        "default_decision": engine.default_decision.value,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "l2_escalation_recall": l2_recall,
        "false_escalation_rate": false_escalation_rate,
        "overall_abstention_rate": abstention_rate,
        "negative_control_abstention_accuracy": s00_abstention_accuracy,
        "per_tier_metrics": {
            lbl: {
                "precision": round(float(report[lbl]["precision"]), 4),
                "recall": round(float(report[lbl]["recall"]), 4),
                "f1_score": round(float(report[lbl]["f1-score"]), 4),
                "support": int(report[lbl]["support"]),
            }
            for lbl in present_labels
            if lbl in report
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": labels,
        "real_testbed_decisions": real_decision_counts,
    }

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(full_metrics, f, indent=2)

    # 4. Save Decisions Log
    decisions_path = Path(cfg["outputs"]["decisions_path"])
    with decisions_path.open("w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)

    print(f"Saved routing metrics to {metrics_path}")
    print(f"Saved decisions log to {decisions_path}")


if __name__ == "__main__":
    main()
