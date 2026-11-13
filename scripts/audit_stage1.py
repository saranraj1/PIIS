#!/usr/bin/env python3
"""Stage 1 Audit: Synthetic Generator & Feature-to-Label Shortcut Analysis."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer


def main() -> None:
    data_path = Path("data/synthetic/synthetic_incidents_m2.jsonl")
    with data_path.open("r", encoding="utf-8") as f:
        incidents = [json.loads(line) for line in f if line.strip()]

    print(f"Total synthetic incidents audited: {len(incidents)}")

    # 1. Check title and description uniqueness per scenario family
    family_stats = defaultdict(lambda: {"titles": set(), "descriptions": set(), "faults": set(), "severities": set(), "support_tiers": set(), "domains": set()})

    for inc in incidents:
        fam = inc["scenario_family_id"]
        family_stats[fam]["titles"].add(inc["title"])
        family_stats[fam]["descriptions"].add(inc["description"])
        family_stats[fam]["faults"].add(inc["fault_category"])
        family_stats[fam]["severities"].add(inc["severity"])
        family_stats[fam]["support_tiers"].add(inc["support_level_label"])
        family_stats[fam]["domains"].add(inc["network_domain"])

    print("\n--- 1. SCENARIO FAMILY DETERMINISTIC ATTRIBUTE ENCODING ---")
    for fam in sorted(family_stats.keys()):
        st = family_stats[fam]
        print(
            f"Family {fam}: Fault={list(st['faults'])} | Severity={list(st['severities'])} | "
            f"Support={list(st['support_tiers'])} | Domain={list(st['domains'])} | "
            f"Unique Titles={len(st['titles'])} | Unique Descs={len(st['descriptions'])}"
        )

    # 2. Check exact duplicate text between Seed 42 and Seed 101
    train = [inc for inc in incidents if "-seed-42" in inc.get("split_group_id", "")]
    test = [inc for inc in incidents if "-seed-101" in inc.get("split_group_id", "")]

    train_combined = set(f"{inc['title']}. {inc['description']}" for inc in train)
    test_combined = [f"{inc['title']}. {inc['description']}" for inc in test]

    exact_matches = sum(1 for t in test_combined if t in train_combined)
    print("\n--- 2. CROSS-SPLIT TEXT DUPLICATION (Seed 42 Train -> Seed 101 Test) ---")
    print(f"Train holdout samples: {len(train)}")
    print(f"Test holdout samples:  {len(test)}")
    print(f"Verbatim duplicate text across splits: {exact_matches} / {len(test)} ({exact_matches / len(test) * 100:.2f}%)")

    # 3. Shortcut Token Analysis: Tokens appearing exclusively in ONE scenario family
    all_texts = [f"{inc['title']}. {inc['description']}" for inc in incidents]
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    vec.fit(all_texts)
    vocab = vec.get_feature_names_out()

    token_to_families = defaultdict(set)
    for inc in incidents:
        fam = inc["scenario_family_id"]
        text_lower = f"{inc['title']} {inc['description']}".lower()
        for tok in vocab:
            if tok in text_lower:
                token_to_families[tok].add(fam)

    single_family_tokens = {tok: list(fams)[0] for tok, fams in token_to_families.items() if len(fams) == 1}
    print("\n--- 3. FEATURE-TO-LABEL SHORTCUT ANALYSIS ---")
    print(f"Total vocabulary terms (1-2 ngrams): {len(vocab)}")
    print(f"Tokens uniquely identifying a single scenario family with 100% precision: {len(single_family_tokens)} ({len(single_family_tokens) / len(vocab) * 100:.2f}%)")

    family_shortcuts = defaultdict(list)
    for tok, fam in single_family_tokens.items():
        if len(tok.split()) == 1 and len(tok) > 3:  # unigrams of reasonable length
            family_shortcuts[fam].append(tok)

    for fam in sorted(family_shortcuts.keys()):
        print(f"   {fam} shortcuts: {family_shortcuts[fam][:8]}")

    # 4. Severity Deterministic Encoding Analysis
    print("\n--- 4. SEVERITY DETERMINISTIC ENCODING ---")
    # Check if severity is completely determined by scenario_family_id or fault_category
    fault_to_sev = defaultdict(set)
    for inc in incidents:
        fault_to_sev[inc["fault_category"]].add(inc["severity"])
    for fault, sevs in fault_to_sev.items():
        print(f"   Fault Category '{fault}' -> Severities: {list(sevs)}")


if __name__ == "__main__":
    main()
