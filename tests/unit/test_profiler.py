"""Unit tests for automated dataset profiler."""

import json
from pathlib import Path
import pandas as pd
import pytest

from piis.ingestion.profiling import DatasetProfiler, compute_sha256, load_dataset_file


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "sample_metrics.csv"
    data = {
        "timestamp": [
            "2026-03-01 10:00:00",
            "2026-03-01 10:00:01",
            "2026-03-01 10:00:02",
            "2026-03-01 10:00:03",
            "2026-03-01 10:00:04",
        ],
        "RSRP": [-80.0, -82.5, -85.0, -115.0, -81.0],  # -115 is an outlier
        "DL_BLER": [0.01, 0.02, 0.01, 0.35, 0.01],
        "protocol": ["TCP", "TCP", None, "UDP", "TCP"],
        "anomaly_label": [0, 0, 0, 1, 0],
    }
    pd.DataFrame(data).to_csv(p, index=False)
    return p


@pytest.fixture
def sample_parquet(sample_csv: Path, tmp_path: Path) -> Path:
    df = pd.read_csv(sample_csv)
    p = tmp_path / "sample_metrics.parquet"
    df.to_parquet(p, index=False)
    return p


def test_compute_sha256(sample_csv: Path):
    h1 = compute_sha256(sample_csv)
    h2 = compute_sha256(sample_csv)
    assert len(h1) == 64
    assert h1 == h2


def test_load_dataset_file(sample_csv: Path, sample_parquet: Path):
    df_csv, fmt_csv = load_dataset_file(sample_csv)
    assert fmt_csv == "csv"
    assert len(df_csv) == 5

    df_pq, fmt_pq = load_dataset_file(sample_parquet)
    assert fmt_pq == "parquet"
    assert len(df_pq) == 5


def test_profiler_reports_and_artifacts(sample_csv: Path, tmp_path: Path):
    out_dir = tmp_path / "profile_out"
    profiler = DatasetProfiler(sample_csv)
    summary = profiler.run_and_export(out_dir)

    assert summary["row_count"] == 5
    assert summary["column_count"] == 5
    assert (out_dir / "profile.json").exists()
    assert (out_dir / "column_summary.csv").exists()
    assert (out_dir / "missingness_report.csv").exists()
    assert (out_dir / "duplicate_report.json").exists()
    assert (out_dir / "label_distribution.csv").exists()
    assert (out_dir / "temporal_profile.json").exists()
    assert (out_dir / "data_quality_report.md").exists()

    # Check missingness
    missing_df = pd.read_csv(out_dir / "missingness_report.csv")
    proto_row = missing_df[missing_df["column_name"] == "protocol"]
    assert proto_row["missing_count"].values[0] == 1
    assert proto_row["missing_pct"].values[0] == 20.0

    # Check temporal profile
    temp = json.loads((out_dir / "temporal_profile.json").read_text(encoding="utf-8"))
    assert temp["has_temporal_data"] is True
    assert temp["sampling_intervals"]["median_interval_seconds"] == 1.0
