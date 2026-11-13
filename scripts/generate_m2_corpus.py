#!/usr/bin/env python3
"""Generate reproducible M2 benchmark corpus for PIIS ML baselines.

Generates 220 validated incidents across all 11 scenario families (S00–S10)
using two distinct deterministic seeds (seed 42 and seed 101),
enabling group-aware cross-validation and strict holdout evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

from piis.synthetic.generator import TelecomScenarioGenerator


def generate_m2_corpus(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_incidents = []
    all_alarms = []
    all_telemetry = []

    families = [
        "S01", "S02", "S03", "S04", "S05",
        "S06", "S07", "S08", "S09", "S10", "S00"
    ]
    seeds = [42, 101]
    variants_per_seed = 10

    print("Generating M2 Benchmark Corpus across seeds [42, 101]...")
    for seed in seeds:
        gen = TelecomScenarioGenerator(seed=seed)
        for fam in families:
            for v in range(1, variants_per_seed + 1):
                outcome = gen.generate_scenario(fam, variant_idx=v, validate=True)
                all_incidents.append(outcome.incident)
                all_alarms.extend(outcome.alarms)
                all_telemetry.extend(outcome.telemetry)

    # Save incidents
    with output_path.open("w", encoding="utf-8") as f:
        for inc in all_incidents:
            f.write(json.dumps(inc) + "\n")

    # Also save alarms and telemetry companion files for multimodal reference
    alarms_path = output_path.parent / "synthetic_alarms_m2.jsonl"
    with alarms_path.open("w", encoding="utf-8") as f:
        for alm in all_alarms:
            f.write(json.dumps(alm) + "\n")

    telemetry_path = output_path.parent / "synthetic_telemetry_m2.jsonl"
    with telemetry_path.open("w", encoding="utf-8") as f:
        for tel in all_telemetry:
            f.write(json.dumps(tel) + "\n")

    print(f"Generated {len(all_incidents)} incidents, {len(all_alarms)} alarms, {len(all_telemetry)} telemetry records.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    out_file = Path("data/synthetic/synthetic_incidents_m2.jsonl")
    generate_m2_corpus(out_file)
