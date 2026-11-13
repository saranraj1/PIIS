"""Robust automated dataset profiling engine for PIIS telecom records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file efficiently in 1MB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dataset_file(path: Path, nrows: Optional[int] = None) -> Tuple[pd.DataFrame, str]:
    """Load heterogeneous dataset files (CSV, compressed CSV, JSON, JSONL, Parquet) into DataFrame.
    
    Returns:
        (DataFrame, format_detected)
    """
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    name_lower = path.name.lower()
    
    # 1. Parquet
    if name_lower.endswith(".parquet") or name_lower.endswith(".pq"):
        df = pd.read_parquet(path)
        if nrows:
            df = df.iloc[:nrows]
        return df, "parquet"

    # 2. Compressed CSV (.csv.gz, .csv.zip, .csv.bz2)
    if name_lower.endswith(".csv.gz"):
        df = pd.read_csv(path, compression="gzip", nrows=nrows, low_memory=False)
        return df, "csv_gzip"
    if name_lower.endswith(".csv.bz2"):
        df = pd.read_csv(path, compression="bz2", nrows=nrows, low_memory=False)
        return df, "csv_bz2"
    if name_lower.endswith(".csv.zip"):
        df = pd.read_csv(path, compression="zip", nrows=nrows, low_memory=False)
        return df, "csv_zip"

    # 3. Standard CSV
    if name_lower.endswith(".csv"):
        df = pd.read_csv(path, nrows=nrows, low_memory=False)
        return df, "csv"

    # 4. JSONL / NDJSON
    if name_lower.endswith(".jsonl") or name_lower.endswith(".ndjson"):
        df = pd.read_json(path, lines=True, nrows=nrows)
        return df, "jsonl"

    # 5. JSON (array or records object)
    if name_lower.endswith(".json"):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            for candidate_key in ("data", "records", "items", "samples", "incidents", "metrics"):
                if candidate_key in data and isinstance(data[candidate_key], list):
                    data = data[candidate_key]
                    break
        if isinstance(data, list):
            if nrows:
                data = data[:nrows]
            df = pd.json_normalize(data)
            return df, "json"
        df = pd.json_normalize([data])
        return df, "json"

    raise ValueError(f"Unsupported file format: {path.suffix} ({path.name})")


class DatasetProfiler:
    """Comprehensive telecom dataset profiling engine."""

    def __init__(self, file_path: Path, sample_rows: Optional[int] = None):
        self.file_path = file_path
        self.sample_rows = sample_rows
        self.df, self.file_format = load_dataset_file(file_path, sample_rows)
        self.file_size = file_path.stat().st_size
        self.sha256 = compute_sha256(file_path)

    def analyze_columns(self) -> pd.DataFrame:
        """Compute exhaustive column-level statistics."""
        records = []
        n_rows = len(self.df)

        for col in self.df.columns:
            series = self.df[col]
            missing_count = int(series.isna().sum())
            missing_pct = float(round((missing_count / n_rows) * 100, 3)) if n_rows > 0 else 0.0
            non_null = series.dropna()
            non_null_count = len(non_null)
            # Handle unhashable types (e.g. nested dicts/lists in JSONL)
            try:
                unique_count = int(series.nunique(dropna=False))
            except TypeError:
                # Fallback: convert unhashable elements to json string representation
                safe_series = series.apply(lambda x: json.dumps(x, default=str) if isinstance(x, (dict, list)) else x)
                unique_count = int(safe_series.nunique(dropna=False))
            cardinality_ratio = float(round(unique_count / n_rows, 4)) if n_rows > 0 else 0.0
            is_unique_id = bool(unique_count == n_rows and n_rows > 0)

            # Numeric metrics (exclude boolean series from quantile/outlier calculations)
            is_numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
            num_min = float(non_null.min()) if is_numeric and non_null_count > 0 else None
            num_max = float(non_null.max()) if is_numeric and non_null_count > 0 else None
            num_mean = float(round(non_null.mean(), 4)) if is_numeric and non_null_count > 0 else None
            num_std = float(round(non_null.std(), 4)) if is_numeric and non_null_count > 1 else None
            num_median = float(non_null.median()) if is_numeric and non_null_count > 0 else None

            # Outlier detection using 1.5 * IQR for numeric columns
            outliers_count = 0
            if is_numeric and non_null_count >= 4:
                q25 = float(non_null.quantile(0.25))
                q75 = float(non_null.quantile(0.75))
                iqr = q75 - q25
                if iqr > 0:
                    lower_bound = q25 - 1.5 * iqr
                    upper_bound = q75 + 1.5 * iqr
                    outliers_count = int(((non_null < lower_bound) | (non_null > upper_bound)).sum())

            records.append({
                "column_name": str(col),
                "dtype": str(series.dtype),
                "total_count": n_rows,
                "non_null_count": non_null_count,
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "unique_count": unique_count,
                "cardinality_ratio": cardinality_ratio,
                "is_unique_id": is_unique_id,
                "numeric_min": num_min,
                "numeric_max": num_max,
                "numeric_mean": num_mean,
                "numeric_std": num_std,
                "numeric_median": num_median,
                "outliers_count": outliers_count,
            })

        return pd.DataFrame(records)

    def analyze_missingness(self) -> pd.DataFrame:
        """Produce structured missingness audit."""
        cols_df = self.analyze_columns()
        missing_df = cols_df[["column_name", "total_count", "missing_count", "missing_pct"]].copy()

        def classify_missing(pct: float) -> str:
            if pct == 0.0:
                return "COMPLETE"
            if pct < 5.0:
                return "LOW_MISSING (<5%)"
            if pct < 25.0:
                return "MODERATE_MISSING (5-25%)"
            if pct < 100.0:
                return "HIGH_MISSING (25-99%)"
            return "ALL_MISSING (100%)"

        missing_df["missingness_tier"] = missing_df["missing_pct"].apply(classify_missing)
        return missing_df.sort_values(by="missing_pct", ascending=False)

    def analyze_duplicates(self) -> Dict[str, Any]:
        """Audit full-row and key duplicates."""
        n_rows = len(self.df)
        try:
            dup_rows = int(self.df.duplicated().sum())
        except TypeError:
            # Handle unhashable objects by converting cells to json strings
            safe_df = self.df.map(lambda x: json.dumps(x, default=str) if isinstance(x, (dict, list)) else x)
            dup_rows = int(safe_df.duplicated().sum())
        dup_pct = float(round((dup_rows / n_rows) * 100, 3)) if n_rows > 0 else 0.0

        res: Dict[str, Any] = {
            "total_rows": n_rows,
            "duplicate_rows_count": dup_rows,
            "duplicate_rows_percentage": dup_pct,
            "is_unique_dataset": bool(dup_rows == 0),
        }

        # Check candidate timestamp duplicate rate if timestamp column is present
        ts_cols = [c for c in self.df.columns if "time" in str(c).lower() or "date" in str(c).lower()]
        if ts_cols:
            primary_ts = ts_cols[0]
            try:
                ts_dups = int(self.df[primary_ts].duplicated().sum())
            except TypeError:
                safe_ts = self.df[primary_ts].apply(lambda x: json.dumps(x, default=str) if isinstance(x, (dict, list)) else x)
                ts_dups = int(safe_ts.duplicated().sum())
            res["primary_timestamp_column"] = primary_ts
            res["timestamp_duplicate_count"] = ts_dups
            res["timestamp_duplicate_percentage"] = float(round((ts_dups / n_rows) * 100, 3)) if n_rows > 0 else 0.0

        return res

    def analyze_labels(self) -> pd.DataFrame:
        """Identify discrete target labels and categorical distributions."""
        records = []
        n_rows = len(self.df)

        for col in self.df.columns:
            series = self.df[col]
            # Identify columns that are candidates for categorical labels or targets
            is_categorical = pd.api.types.is_object_dtype(series) or pd.api.types.is_bool_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype)
            try:
                nunique = series.nunique(dropna=True)
            except TypeError:
                safe_series = series.apply(lambda x: json.dumps(x, default=str) if isinstance(x, (dict, list)) else x)
                nunique = safe_series.nunique(dropna=True)
                series = safe_series

            # Look for explicit label names or low-cardinality discrete columns (2 to 30 categories)
            col_name_lower = str(col).lower()
            is_named_target = any(k in col_name_lower for k in ("jamming", "fault", "state", "mode", "severity", "label", "target", "status", "category", "operator"))

            if (is_categorical and nunique <= 30) or (is_named_target and nunique <= 50):
                val_counts = series.value_counts(dropna=False)
                for val, count in val_counts.items():
                    val_str = "<NULL>" if pd.isna(val) else str(val)
                    pct = float(round((count / n_rows) * 100, 3)) if n_rows > 0 else 0.0
                    records.append({
                        "column_name": str(col),
                        "label_value": val_str,
                        "count": int(count),
                        "percentage": pct,
                    })

        if not records:
            return pd.DataFrame(columns=["column_name", "label_value", "count", "percentage"])
        return pd.DataFrame(records)

    def analyze_temporal(self) -> Dict[str, Any]:
        """Compute timestamp coverage, range, frequency, and sampling intervals."""
        ts_candidates = [
            c for c in self.df.columns
            if any(k in str(c).lower() for k in ("time", "date", "timestamp"))
        ]

        if not ts_candidates:
            return {
                "has_temporal_data": False,
                "message": "No timestamp or date column identified."
            }

        primary_ts = ts_candidates[0]
        series = self.df[primary_ts].dropna()

        # Parse timestamps safely
        try:
            # Check if numeric epoch (seconds or ms)
            if pd.api.types.is_numeric_dtype(series):
                min_val = series.min()
                if min_val > 1e11:  # likely milliseconds
                    dt_series = pd.to_datetime(series, unit="ms", errors="coerce")
                else:  # likely seconds or relative
                    dt_series = pd.to_datetime(series, unit="s", errors="coerce")
            else:
                dt_series = pd.to_datetime(series, errors="coerce")
            
            valid_dts = dt_series.dropna().sort_values()
            if len(valid_dts) == 0:
                return {
                    "has_temporal_data": False,
                    "primary_column": primary_ts,
                    "message": "Timestamp column could not be parsed to datetime."
                }

            min_dt = valid_dts.iloc[0]
            max_dt = valid_dts.iloc[-1]
            diffs = valid_dts.diff().dropna().dt.total_seconds()

            sampling_metrics = {}
            if len(diffs) > 0:
                sampling_metrics = {
                    "median_interval_seconds": float(round(diffs.median(), 4)),
                    "mean_interval_seconds": float(round(diffs.mean(), 4)),
                    "min_interval_seconds": float(round(diffs.min(), 4)),
                    "max_interval_seconds": float(round(diffs.max(), 4)),
                    "std_interval_seconds": float(round(diffs.std(), 4)) if len(diffs) > 1 else 0.0,
                    "estimated_cadence_hz": float(round(1.0 / diffs.median(), 2)) if diffs.median() > 0 else "burst_or_irregular",
                    "zero_interval_count": int((diffs == 0).sum()),
                }

            return {
                "has_temporal_data": True,
                "primary_timestamp_column": primary_ts,
                "min_timestamp": min_dt.isoformat(),
                "max_timestamp": max_dt.isoformat(),
                "duration_seconds": float((max_dt - min_dt).total_seconds()),
                "duration_human": str(max_dt - min_dt),
                "valid_timestamp_count": int(len(valid_dts)),
                "unparseable_timestamp_count": int(len(series) - len(valid_dts)),
                "sampling_intervals": sampling_metrics,
            }
        except Exception as e:
            return {
                "has_temporal_data": False,
                "primary_column": primary_ts,
                "error": str(e)
            }

    def generate_markdown_report(self, profile_summary: Dict[str, Any], col_df: pd.DataFrame, missing_df: pd.DataFrame) -> str:
        """Generate comprehensive GitHub-flavored Markdown quality report."""
        lines = [
            f"# Data Quality & Profiling Report: `{self.file_path.name}`",
            "",
            f"- **Source File:** `{self.file_path}`",
            f"- **File Format:** `{self.file_format.upper()}`",
            f"- **File Size:** {self.file_size:,} bytes ({round(self.file_size / (1024*1024), 2)} MB)",
            f"- **SHA-256:** `{self.sha256}`",
            f"- **Total Rows Profiled:** {len(self.df):,}",
            f"- **Total Columns:** {len(self.df.columns):,}",
            "",
            "## 1. Summary Highlights",
            "",
            f"- **Duplicate Rows:** {profile_summary['duplicates']['duplicate_rows_count']:,} ({profile_summary['duplicates']['duplicate_rows_percentage']}%)",
            f"- **Columns with Missing Data:** {len(missing_df[missing_df['missing_count'] > 0])} / {len(self.df.columns)}",
            f"- **Total Outlier Points Detected (IQR method):** {col_df['outliers_count'].sum():,}",
            "",
            "## 2. Column-Level Statistics",
            "",
            "| Column Name | Type | Missing % | Unique Count | Min | Median | Max | Outliers |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for _, row in col_df.iterrows():
            min_str = f"{row['numeric_min']:.2f}" if row['numeric_min'] is not None else "-"
            med_str = f"{row['numeric_median']:.2f}" if row['numeric_median'] is not None else "-"
            max_str = f"{row['numeric_max']:.2f}" if row['numeric_max'] is not None else "-"
            out_str = f"{row['outliers_count']:,}" if row['outliers_count'] > 0 else "0"
            lines.append(f"| `{row['column_name']}` | {row['dtype']} | {row['missing_pct']}% | {row['unique_count']:,} | {min_str} | {med_str} | {max_str} | {out_str} |")

        lines.extend([
            "",
            "## 3. Missingness Analysis",
            "",
            "| Column Name | Missing Count | Missing % | Tier |",
            "| :--- | :--- | :--- | :--- |",
        ])

        for _, row in missing_df.head(15).iterrows():
            lines.append(f"| `{row['column_name']}` | {row['missing_count']:,} | {row['missing_pct']}% | {row['missingness_tier']} |")

        temp = profile_summary["temporal"]
        lines.extend([
            "",
            "## 4. Temporal Characteristics",
            "",
        ])
        if temp.get("has_temporal_data"):
            lines.extend([
                f"- **Primary Timestamp Column:** `{temp['primary_timestamp_column']}`",
                f"- **Start Timestamp:** `{temp['min_timestamp']}`",
                f"- **End Timestamp:** `{temp['max_timestamp']}`",
                f"- **Total Span:** {temp['duration_human']} ({temp['duration_seconds']:,} seconds)",
            ])
            intervals = temp.get("sampling_intervals", {})
            if intervals:
                lines.extend([
                    f"- **Median Interval:** {intervals.get('median_interval_seconds')} seconds",
                    f"- **Estimated Frequency:** {intervals.get('estimated_cadence_hz')} Hz",
                    f"- **Interval Jitter (Std Dev):** {intervals.get('std_interval_seconds')} seconds",
                    f"- **Zero-Interval / Duplicate Timestamps:** {intervals.get('zero_interval_count'):,}",
                ])
        else:
            lines.append("- *No temporal timestamp column detected in this dataset.*")

        lines.extend([
            "",
            "## 5. Telecom Operational Integrity Assessment",
            "",
            "> [!NOTE]",
            "> All raw inputs are preserved immutably. Profiling does not drop or mutate any rows.",
            "> Feature extraction pipelines must respect temporal order and prevent post-incident leakage.",
            ""
        ])

        return "\n".join(lines)

    def run_and_export(self, output_dir: Path) -> Dict[str, Any]:
        """Execute full profiling suite and export all required M1.3 artifacts."""
        output_dir.mkdir(parents=True, exist_ok=True)

        col_df = self.analyze_columns()
        missing_df = self.analyze_missingness()
        dup_dict = self.analyze_duplicates()
        labels_df = self.analyze_labels()
        temp_dict = self.analyze_temporal()

        # Compile profile.json
        profile_json: Dict[str, Any] = {
            "source_file": str(self.file_path),
            "file_name": self.file_path.name,
            "format": self.file_format,
            "file_size_bytes": self.file_size,
            "sha256": self.sha256,
            "row_count": len(self.df),
            "column_count": len(self.df.columns),
            "columns": list(map(str, self.df.columns)),
            "duplicates": dup_dict,
            "temporal": temp_dict,
            "sample_records": json.loads(self.df.head(5).to_json(orient="records", date_format="iso")),
        }

        # Export artifacts
        # 1. profile.json
        (output_dir / "profile.json").write_text(json.dumps(profile_json, indent=2, default=str), encoding="utf-8")
        # 2. column_summary.csv
        col_df.to_csv(output_dir / "column_summary.csv", index=False)
        # 3. missingness_report.csv
        missing_df.to_csv(output_dir / "missingness_report.csv", index=False)
        # 4. duplicate_report.json
        (output_dir / "duplicate_report.json").write_text(json.dumps(dup_dict, indent=2), encoding="utf-8")
        # 5. label_distribution.csv
        labels_df.to_csv(output_dir / "label_distribution.csv", index=False)
        # 6. temporal_profile.json
        (output_dir / "temporal_profile.json").write_text(json.dumps(temp_dict, indent=2, default=str), encoding="utf-8")
        # 7. data_quality_report.md
        md_content = self.generate_markdown_report(profile_json, col_df, missing_df)
        (output_dir / "data_quality_report.md").write_text(md_content, encoding="utf-8")

        return profile_json
