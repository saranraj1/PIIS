#!/usr/bin/env python3
"""CLI utility to profile dataset files for PIIS Milestone 1.

Generates complete machine-readable profiling reports:
- profile.json
- column_summary.csv
- missingness_report.csv
- duplicate_report.json
- label_distribution.csv
- temporal_profile.json
- data_quality_report.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from piis.ingestion.profiling import DatasetProfiler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to dataset file (CSV, JSON, JSONL, Parquet)")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Directory to write profile artifacts (defaults to artifacts/data_profiles/<file_stem>)",
    )
    parser.add_argument(
        "--sample-rows",
        "-n",
        type=int,
        default=None,
        help="Optional row limit for quick profiling of massive files",
    )
    args = parser.parse_args()

    if not args.file.exists():
        sys.exit(f"Error: Target file does not exist: {args.file}")

    target_dir = args.output_dir or Path("artifacts/data_profiles") / args.file.stem

    print(f"Profiling '{args.file.name}' [{args.file.stat().st_size:,} bytes]...")
    profiler = DatasetProfiler(args.file, sample_rows=args.sample_rows)
    summary = profiler.run_and_export(target_dir)

    print(f"Profile complete for {summary['file_name']}:")
    print(f"  Rows: {summary['row_count']:,} | Columns: {summary['column_count']:,}")
    print(f"  SHA-256: {summary['sha256']}")
    print(f"  Artifacts exported to: {target_dir}")
    print("  Generated: profile.json, column_summary.csv, missingness_report.csv,")
    print("             duplicate_report.json, label_distribution.csv, temporal_profile.json,")
    print("             data_quality_report.md")


if __name__ == "__main__":
    main()
