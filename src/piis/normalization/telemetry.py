"""Normalization pipeline for telecom telemetry metrics to canonical schema."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonschema
import pandas as pd

from piis.provenance import SourceType

# Load canonical telemetry schema once for validation
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "telemetry.schema.json"
with SCHEMA_PATH.open("r", encoding="utf-8") as f:
    TELEMETRY_SCHEMA = json.load(f)
VALIDATOR = jsonschema.Draft202012Validator(
    TELEMETRY_SCHEMA,
    format_checker=jsonschema.FormatChecker()
)


def validate_canonical_telemetry(record: Dict[str, Any]) -> None:
    """Validate a single telemetry record against canonical schema."""
    errors = list(VALIDATOR.iter_errors(record))
    if errors:
        msg = "; ".join(f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors)
        raise jsonschema.ValidationError(f"Invalid canonical telemetry record: {msg}")


def normalize_telecomts_telemetry(
    file_path: Path,
    incident_id: Optional[str] = None,
    base_epoch: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    max_rows: Optional[int] = None,
    validate: bool = True,
) -> List[Dict[str, Any]]:
    """Transform TelecomTS metrics.csv into canonical telemetry records."""
    df = pd.read_csv(file_path, nrows=max_rows, low_memory=False)
    file_stem = file_path.stem
    records: List[Dict[str, Any]] = []

    # Columns to explode into canonical observations: (col_name, canonical_metric, unit)
    metric_mappings = [
        ("RSRP", "RSRP", "dBm"),
        ("DL_BLER", "DL_BLER", "ratio"),
        ("DL_MCS", "DL_MCS", "index"),
        ("UL_BLER", "UL_BLER", "ratio"),
        ("UL_MCS", "UL_MCS", "index"),
        ("UL_SNR", "UL_SNR", "dB"),
        ("PRB_Utilization_DL", "PRB_UTIL_DL", "ratio"),
        ("PRB_Utilization_UL", "PRB_UTIL_UL", "ratio"),
        ("TX_Bytes", "TX_THROUGHPUT", "bytes/sec"),
        ("RX_Bytes", "RX_THROUGHPUT", "bytes/sec"),
    ]

    for row_idx, row in df.iterrows():
        raw_ts = row["timestamp"]
        # Handle string datetime or numeric relative seconds
        if isinstance(raw_ts, (int, float)):
            dt = base_epoch + pd.to_timedelta(float(raw_ts), unit="s")
            dt_str = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"
            rel_sec = float(raw_ts)
        else:
            # Parse string datetime (e.g. '2025-01-01 00:00:00.100')
            ts_str = str(raw_ts).strip()
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            except ValueError:
                dt = pd.to_datetime(ts_str).tz_localize(timezone.utc)
            dt_str = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"
            rel_sec = float(row_idx * 0.1)

        dl_proto = str(row.get("DL_Protocol")) if pd.notna(row.get("DL_Protocol")) else "NONE"
        ul_proto = str(row.get("UL_Protocol")) if pd.notna(row.get("UL_Protocol")) else "NONE"
        ground_truth_jamming = bool(row.get("Jamming") == 1) if "Jamming" in row else False

        for col_name, canonical_metric, unit in metric_mappings:
            if col_name in row and pd.notna(row[col_name]):
                val = float(row[col_name])
                # Scale TX/RX 100ms counts to 1-sec equivalent rates
                if "THROUGHPUT" in canonical_metric:
                    val = float(val * 10.0)

                obs_id = f"TELTS-OBS-{file_stem}-{row_idx:06d}-{canonical_metric}"
                record: Dict[str, Any] = {
                    "schema_version": "1.0",
                    "observation_id": obs_id,
                    "incident_id": incident_id,
                    "timestamp": dt_str,
                    "network_element_id": "GNB-TESTBED-5G-01",
                    "network_domain": "RAN",
                    "metric_name": canonical_metric,
                    "metric_value": val,
                    "unit": unit,
                    "source_type": SourceType.PUBLIC_REAL.value,
                    "source_dataset": "AliMaatouk/TelecomTS",
                    "source_record_id": f"row_{row_idx}",
                    "original_timezone": "UTC",
                    "metadata": {
                        "relative_timestamp_sec": rel_sec,
                        "dl_protocol": dl_proto,
                        "ul_protocol": ul_proto,
                        "ground_truth_anomaly": ground_truth_jamming,
                    },
                }

                if validate:
                    validate_canonical_telemetry(record)
                records.append(record)

    return records


def normalize_ucc5g_telemetry(
    file_path: Path,
    incident_id: Optional[str] = None,
    max_rows: Optional[int] = None,
    validate: bool = True,
) -> List[Dict[str, Any]]:
    """Transform UCC 5G production trace CSV into canonical telemetry records."""
    df = pd.read_csv(file_path, nrows=max_rows, low_memory=False)
    file_stem = file_path.stem
    records: List[Dict[str, Any]] = []

    # Map G-NetTrack columns to canonical metric observations
    metric_cols = [
        ("RSRP", "RSRP", "dBm"),
        ("RSRQ", "RSRQ", "dB"),
        ("SNR", "SNR", "dB"),
        ("CQI", "CQI", "index"),
        ("DL_bitrate", "DL_BITRATE", "kbps"),
        ("UL_bitrate", "UL_BITRATE", "kbps"),
    ]

    for row_idx, row in df.iterrows():
        raw_ts = str(row["Timestamp"])
        # Format in UCC traces: YYYY.MM.DD_HH.MM.SS
        try:
            dt = datetime.strptime(raw_ts, "%Y.%m.%d_%H.%M.%S").replace(tzinfo=timezone.utc)
            dt_str = dt.isoformat().replace("+00:00", "Z")
        except ValueError:
            dt_str = pd.to_datetime(raw_ts).isoformat() + "Z"

        node_hex = str(row.get("NODEHEX", "")).strip()
        cell_hex = str(row.get("CELLHEX", "")).strip()
        cell_id = str(row.get("CellID", "")).strip()
        net_mode = str(row.get("NetworkMode", "5G")).strip()

        ne_id = f"CELL-{node_hex}-{cell_hex}" if node_hex and cell_hex else f"CELL-{cell_id}"
        domain = "RAN" if "5G" in net_mode or "LTE" in net_mode else "RAN_LEGACY"

        speed_val = None
        if pd.notna(row.get("Speed")) and str(row.get("Speed")).strip() != "-":
            try:
                speed_val = float(row["Speed"])
            except ValueError:
                pass

        meta: Dict[str, Any] = {
            "network_mode": net_mode,
            "handset_state": str(row.get("State", "")).strip(),
            "operator": str(row.get("Operatorname", "")).strip(),
            "speed_kmh": speed_val,
        }

        if pd.notna(row.get("Latitude")) and pd.notna(row.get("Longitude")):
            try:
                meta["latitude"] = float(row["Latitude"])
                meta["longitude"] = float(row["Longitude"])
            except ValueError:
                pass

        for raw_col, canonical_metric, unit in metric_cols:
            raw_val = row.get(raw_col)
            if pd.notna(raw_val) and str(raw_val).strip() != "-":
                try:
                    val = float(raw_val)
                except ValueError:
                    continue

                obs_id = f"UCC5G-OBS-{file_stem}-{row_idx:05d}-{canonical_metric}"
                record = {
                    "schema_version": "1.0",
                    "observation_id": obs_id,
                    "incident_id": incident_id,
                    "timestamp": dt_str,
                    "network_element_id": ne_id,
                    "network_domain": domain,
                    "metric_name": canonical_metric,
                    "metric_value": val,
                    "unit": unit,
                    "source_type": SourceType.PUBLIC_REAL.value,
                    "source_dataset": "uccmisl/5Gdataset",
                    "source_record_id": f"row_{row_idx}",
                    "original_timezone": "Europe/Dublin",
                    "metadata": dict(meta),
                }

                if validate:
                    validate_canonical_telemetry(record)
                records.append(record)

    return records
