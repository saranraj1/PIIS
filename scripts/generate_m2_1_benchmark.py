#!/usr/bin/env python3
"""Generate PIIS-TelcoBench-v2 Benchmark Corpus and Human Review Sample.

Outputs:
1. data/synthetic/synthetic_incidents_v2_train.jsonl (240 incidents)
2. data/synthetic/synthetic_incidents_v2_test.jsonl (120 incidents)
3. data/synthetic/synthetic_incidents_v2_combined.jsonl (360 incidents)
4. docs/data/M2_HUMAN_REVIEW_SAMPLE.jsonl (36 stratified evaluation cards)
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from piis.synthetic.generator_v2 import TelecomScenarioGeneratorV2


def main() -> None:
    out_dir = Path("data/synthetic")
    out_dir.mkdir(parents=True, exist_ok=True)

    gen = TelecomScenarioGeneratorV2(seed=42)
    print("Generating PIIS-TelcoBench-v2 benchmark...")
    train_records, test_records = gen.generate_benchmark_v2(variants_per_combo=5, validate=True)
    all_records = train_records + test_records

    train_path = out_dir / "synthetic_incidents_v2_train.jsonl"
    test_path = out_dir / "synthetic_incidents_v2_test.jsonl"
    combined_path = out_dir / "synthetic_incidents_v2_combined.jsonl"

    with train_path.open("w", encoding="utf-8") as f:
        for r in train_records:
            f.write(json.dumps(r) + "\n")

    with test_path.open("w", encoding="utf-8") as f:
        for r in test_records:
            f.write(json.dumps(r) + "\n")

    with combined_path.open("w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    print(f"Generated {len(train_records)} train records and {len(test_records)} test records.")

    # 1. Verification of Zero Cross-Split Duplicates
    train_texts = set(f"{r['title']}. {r['description']}" for r in train_records)
    test_texts = [f"{r['title']}. {r['description']}" for r in test_records]
    exact_matches = sum(1 for t in test_texts if t in train_texts)
    print(f"Cross-split text duplicates: {exact_matches} / {len(test_records)} ({exact_matches / len(test_records) * 100:.2f}%)")
    assert exact_matches == 0, "Duplicate text found between train and test holdout!"

    # 2. Verification of Severity Diversity per Fault Category
    fault_to_sev = defaultdict(set)
    for r in all_records:
        fault_to_sev[r["fault_category"]].add(r["severity"])

    print("\n--- Severity Coverage per Fault Category ---")
    for fault, sevs in sorted(fault_to_sev.items()):
        print(f"   {fault}: {list(sevs)}")
        if fault not in ["nominal_operation", "ambiguous_low_evidence"]:
            assert len(sevs) >= 2, f"Fault {fault} lacks severity diversity!"

    # 3. Verification of Support Tier Diversity per Fault Category
    fault_to_supp = defaultdict(set)
    for r in all_records:
        fault_to_supp[r["fault_category"]].add(r["support_level_label"])

    print("\n--- Support Tier Coverage per Fault Category ---")
    for fault, tiers in sorted(fault_to_supp.items()):
        print(f"   {fault}: {list(tiers)}")

    # 4. Generate 10% Stratified Human Review Sample
    review_dir = Path("docs/data")
    review_dir.mkdir(parents=True, exist_ok=True)
    review_sample_path = review_dir / "M2_HUMAN_REVIEW_SAMPLE.jsonl"

    # Select 3 samples per family across different templates and configs
    review_records = []
    for fam in gen.FAMILIES:
        fam_recs = [r for r in all_records if r["scenario_family_id"] == fam]
        # Pick 1 from T1, 1 from T2, 1 from T3
        for tmpl in ["T1", "T2", "T3"]:
            matches = [r for r in fam_recs if r["metadata"]["template_id"] == tmpl]
            if matches:
                sample_item = dict(matches[0])
                sample_item["review_card"] = {
                    "rubric": "Assess technical coherence, realistic telecom phrasing, and severity rationale.",
                    "scenario_family": fam,
                    "template_id": tmpl,
                    "causal_config": sample_item["metadata"]["causal_configuration_id"],
                    "service_criticality": sample_item["metadata"]["service_criticality"],
                    "redundancy_state": sample_item["metadata"]["redundancy_state"],
                    "human_adjudication": "PENDING_AUDIT",
                }
                review_records.append(sample_item)

    with review_sample_path.open("w", encoding="utf-8") as f:
        for r in review_records:
            f.write(json.dumps(r) + "\n")

    print(f"\nExported {len(review_records)} stratified human review sample cards to {review_sample_path}")
    print("Severity distribution in benchmark:", Counter(r["severity"] for r in all_records))
    print("Support tier distribution in benchmark:", Counter(r["support_level_label"] for r in all_records))


if __name__ == "__main__":
    main()
