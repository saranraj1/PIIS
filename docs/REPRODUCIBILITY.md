# PIIS Milestone 1 Reproducibility Guide

- **Environment:** Python 3.11+ on Windows / Linux / macOS
- **Last Verified:** 2026-10-31

---

## 1. Environment Setup

```bash
# 1. Activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install package in editable mode with development dependencies
pip install -e ".[dev]"

# 3. Verify linting and test suite
ruff check src tests scripts
pytest -v
```

---

## 2. Dataset Acquisition

Acquire permitted public-real datasets:

```bash
# TelecomTS (5G Testbed Multimodal Telemetry - MIT License)
python -c "
import urllib.request
from pathlib import Path
base = 'https://huggingface.co/datasets/AliMaatouk/TelecomTS/resolve/main/'
files = [
    ('anomalous/jammer/File/raw/metrics.csv', Path('data/raw/SRC-002/jammer_metrics.csv')),
    ('anomalous/jammer/File/processed/chunked.jsonl', Path('data/raw/SRC-002/jammer_chunked.jsonl')),
    ('normal/mobile/File/raw/metrics.csv', Path('data/raw/SRC-002/normal_mobile_metrics.csv')),
    ('normal/stationary/Zone_A/congestion/File/raw/metrics.csv', Path('data/raw/SRC-002/congestion_metrics.csv'))
]
for remote, local in files:
    local.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(base + remote, local)
"

# UCC 5G Production Dataset (GPL-3.0 License)
python -c "
import urllib.request, zipfile
from pathlib import Path
zip_path = Path('data/raw/SRC-005/5G-production-dataset.zip')
zip_path.parent.mkdir(parents=True, exist_ok=True)
urllib.request.urlretrieve('https://raw.githubusercontent.com/uccmisl/5Gdataset/master/5G-production-dataset.zip', zip_path)
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(Path('data/raw/SRC-005/unpacked'))
"
```

---

## 3. Automated Profiling

Run comprehensive profiling across acquired datasets:

```bash
# Profile TelecomTS Jammer Telemetry
python scripts/profile_dataset.py data/raw/SRC-002/jammer_metrics.csv -o artifacts/data_profiles/SRC-002-jammer_metrics

# Profile TelecomTS Multi-modal Diagnostic Records
python scripts/profile_dataset.py data/raw/SRC-002/jammer_chunked.jsonl -o artifacts/data_profiles/SRC-002-jammer_chunked

# Profile UCC 5G Vehicular Drive-Test Traces
python scripts/profile_dataset.py data/raw/SRC-005/unpacked/5G-production-dataset/Amazon_Prime/Driving/animated-AdventureTime/B_2019.11.28_07.27.57.csv -o artifacts/data_profiles/SRC-005-ucc_5g_drive
```

---

## 4. Normalization Pipeline

Normalize raw records into canonical schemas under `data/processed/`:

```bash
# Normalize incidents
python scripts/normalize_dataset.py telecomts-incidents data/raw/SRC-002/jammer_chunked.jsonl -o data/processed/incidents/telecomts_incidents.jsonl

# Normalize telemetry
python scripts/normalize_dataset.py telecomts-telemetry data/raw/SRC-002/jammer_metrics.csv -o data/processed/telemetry/telecomts_jammer_telemetry.jsonl --limit 500
python scripts/normalize_dataset.py ucc5g-telemetry data/raw/SRC-005/unpacked/5G-production-dataset/Amazon_Prime/Driving/animated-AdventureTime/B_2019.11.28_07.27.57.csv -o data/processed/telemetry/ucc5g_drive_telemetry.jsonl --limit 500
```

---

## 5. Synthetic Scenario Generation

Generate controlled, reproducible synthetic scenarios:

```bash
python scripts/generate_synthetic.py --seed 42 --variants-per-family 3 -o data/synthetic/
```

---

## 6. Verification and Test Suite

```bash
pytest -v
```
All 24 unit and schema tests should pass cleanly.
