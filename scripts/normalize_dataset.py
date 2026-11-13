#!/usr/bin/env python3
"""CLI utility to normalize raw telecom datasets into canonical PIIS records.

Enforces schema validation, ISO-8601 UTC timestamp conversion,
provenance preservation, and logical dataset separation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from piis.normalization.telemetry import (
    normalize_telecomts_telemetry,
    normalize_ucc5g_telemetry,
)
from piis.normalization.incidents import normalize_telecomts_incident


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_type", choices=["telecomts-telemetry", "ucc5g-telemetry", "telecomts-incidents"])
    parser.add_argument("input_path", type=Path, help="Path to raw source file")
    parser.add_argument("--output-file", "-o", type=Path, required=True, help="Destination JSONL path in data/processed/")
    parser.add_argument("--limit", "-n", type=int, default=None, help="Row limit for batch processing")
    args = parser.parse_args()

    if not args.input_path.exists():
        sys.exit(f"Error: Input file does not exist: {args.input_path}")

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"Normalizing '{args.input_path.name}' as '{args.source_type}'...")

    if args.source_type == "telecomts-telemetry":
        records = normalize_telecomts_telemetry(args.input_path, max_rows=args.limit, validate=True)
    elif args.source_type == "ucc5g-telemetry":
        records = normalize_ucc5g_telemetry(args.input_path, max_rows=args.limit, validate=True)
    elif args.source_type == "telecomts-incidents":
        records = []
        with args.input_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if args.limit and i >= args.limit:
                    break
                line = line.strip()
                if not line:
                    continue
                raw_obj = json.loads(line)
                rec = normalize_telecomts_incident(raw_obj, record_idx=i, validate=True)
                records.append(rec)
    else:
        sys.exit(f"Unsupported source type: {args.source_type}")

    # Write out as newline-delimited JSON
    with args.output_file.open("w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, default=str) + "\n")

    print(f"Successfully normalized and validated {len(records):,} records.")
    print(f"Output saved to: {args.output_file}")


if __name__ == "__main__":
    main()
