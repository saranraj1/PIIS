#!/usr/bin/env python3
"""CLI utility to generate reproducible synthetic scenarios for PIIS-TelcoBench.

Supports scenario families S01 through S10 plus S00 (negative controls).
Outputs records directly into data/synthetic/ or custom path,
enforcing strict JSON Schema validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from piis.synthetic.generator import TelecomScenarioGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        "-s",
        nargs="+",
        default=["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S00"],
        help="List of scenario families to generate (e.g. S01 S02 S03 S00)",
    )
    parser.add_argument("--variants-per-family", "-v", type=int, default=3, help="Variants per scenario family")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("data/synthetic"),
        help="Destination directory for synthetic files",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    generator = TelecomScenarioGenerator(seed=args.seed)

    incidents_file = args.output_dir / f"synthetic_incidents_seed{args.seed}.jsonl"
    alarms_file = args.output_dir / f"synthetic_alarms_seed{args.seed}.jsonl"
    telemetry_file = args.output_dir / f"synthetic_telemetry_seed{args.seed}.jsonl"

    all_incidents = []
    all_alarms = []
    all_telemetry = []

    print(f"Generating synthetic telecom benchmark (seed={args.seed})...")
    for fam in args.scenarios:
        for v in range(1, args.variants_per_family + 1):
            outcome = generator.generate_scenario(fam, variant_idx=v, validate=True)
            all_incidents.append(outcome.incident)
            all_alarms.extend(outcome.alarms)
            all_telemetry.extend(outcome.telemetry)

    # Export jsonl
    with incidents_file.open("w", encoding="utf-8") as f:
        for inc in all_incidents:
            f.write(json.dumps(inc) + "\n")
    with alarms_file.open("w", encoding="utf-8") as f:
        for alm in all_alarms:
            f.write(json.dumps(alm) + "\n")
    with telemetry_file.open("w", encoding="utf-8") as f:
        for tel in all_telemetry:
            f.write(json.dumps(tel) + "\n")

    print(f"Successfully generated and validated {len(all_incidents)} incidents across {len(args.scenarios)} families.")
    print(f"  Incidents: {incidents_file} ({len(all_incidents)} records)")
    print(f"  Alarms:    {alarms_file} ({len(all_alarms)} records)")
    print(f"  Telemetry: {telemetry_file} ({len(all_telemetry)} records)")


if __name__ == "__main__":
    main()
