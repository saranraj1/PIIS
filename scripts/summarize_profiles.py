import json
from pathlib import Path
import pandas as pd

profiles = [
    'SRC-002-jammer_metrics',
    'SRC-002-congestion_metrics',
    'SRC-002-normal_mobile_metrics',
    'SRC-002-jammer_chunked',
    'SRC-005-ucc_5g_drive',
    'SRC-005-ucc_5g_static'
]

print("=== DATA QUALITY SYNTHESIS ===")
for p in profiles:
    dir_p = Path("artifacts/data_profiles") / p
    prof = json.loads((dir_p / "profile.json").read_text(encoding="utf-8"))
    dups = json.loads((dir_p / "duplicate_report.json").read_text(encoding="utf-8"))
    temp = json.loads((dir_p / "temporal_profile.json").read_text(encoding="utf-8"))
    missing_df = pd.read_csv(dir_p / "missingness_report.csv")
    high_missing = missing_df[missing_df["missing_pct"] > 0]
    col_df = pd.read_csv(dir_p / "column_summary.csv")
    label_df = pd.read_csv(dir_p / "label_distribution.csv")
    
    rows = prof["row_count"]
    cols = prof["column_count"]
    dup_c = dups["duplicate_rows_count"]
    dup_p = dups["duplicate_rows_percentage"]
    print(f"-- Profile: {p} --")
    print(f"   Rows: {rows:,}, Cols: {cols}")
    print(f"   Duplicates: {dup_c} ({dup_p}%)")
    if "timestamp_duplicate_count" in dups:
        ts_c = dups["timestamp_duplicate_count"]
        ts_p = dups["timestamp_duplicate_percentage"]
        print(f"   Timestamp dups: {ts_c} ({ts_p}%)")
    print(f"   Columns with missing: {len(high_missing)}")
    for _, r in high_missing.iterrows():
        print(f"     Column '{r['column_name']}': {r['missing_count']} missing ({r['missing_pct']}%) -> {r['missingness_tier']}")
    print(f"   Total Outliers (IQR): {col_df['outliers_count'].sum()}")
    if not label_df.empty:
        print("   Labels:")
        for _, lr in label_df.iterrows():
            print(f"     {lr['column_name']} = {lr['label_value']}: {lr['count']} ({lr['percentage']}%)")
    if temp.get("has_temporal_data"):
        span_h = temp.get("duration_human")
        span_s = temp.get("duration_seconds")
        print(f"   Time span: {span_h} ({span_s}s)")
        intervals = temp.get("sampling_intervals", {})
        med = intervals.get("median_interval_seconds")
        hz = intervals.get("estimated_cadence_hz")
        print(f"   Sampling median: {med}s (cadence: {hz} Hz)")
    print()
