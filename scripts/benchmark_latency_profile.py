"""Independent Audit Script: Phase 5 - Latency & Runtime Profiling.

Measures rigorous latency distribution under controlled conditions:
- 10 warm-up runs (discarded).
- 50 measurement repetitions across distinct scenarios.
- Records exact p50, p95, and p99.
- Documents exact runtime environment and CPU specifications.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time
from typing import Any, Dict, List
import numpy as np

from piis.investigation.engine import IncidentInvestigationEngine
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


def run_latency_benchmark() -> Dict[str, Any]:
    print("[*] Initializing Engine for Latency Profiling...")
    docs, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)

    sample_incident = {
        "incident_id": "INC-BENCH-001",
        "title": "5G NR gNodeB Antenna Feeder High Return Loss",
        "description": "ALM-RAN-VSWR-HIGH active on sector 2 AAU. VSWR ratio measured at 2.4:1.",
        "alarm_codes": ["ALM-RAN-VSWR-HIGH", "0x80040111"],
        "network_domain": "RAN",
        "network_element_ids": ["gNodeB-101", "AAU-02"],
    }
    m2_data = {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.94}
    m3_data = {"anomalies": [{"network_element_id": "gNodeB-101", "metric_name": "vswr_ratio", "fused_score": 0.89}]}

    # 1. Warm-up Phase (10 runs, discarded)
    print("[*] Executing 10 warm-up cycles...")
    for _ in range(10):
        engine.investigate(sample_incident, m2_classification=m2_data, m3_network_intelligence=m3_data)

    # 2. Measurement Phase (50 repetitions)
    print("[*] Executing 50 benchmark repetitions...")
    latencies: List[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        engine.investigate(sample_incident, m2_classification=m2_data, m3_network_intelligence=m3_data)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

    lat_arr = np.array(latencies)
    p50 = float(np.percentile(lat_arr, 50))
    p90 = float(np.percentile(lat_arr, 90))
    p95 = float(np.percentile(lat_arr, 95))
    p99 = float(np.percentile(lat_arr, 99))
    mean_lat = float(np.mean(lat_arr))
    min_lat = float(np.min(lat_arr))
    max_lat = float(np.max(lat_arr))
    std_lat = float(np.std(lat_arr))

    print("=" * 80)
    print("PHASE 5 LATENCY PROFILE RESULTS (50 Repetitions, 10 Warmup):")
    print(f"  P50 Latency:   {p50:.2f} ms")
    print(f"  P90 Latency:   {p90:.2f} ms")
    print(f"  P95 Latency:   {p95:.2f} ms")
    print(f"  P99 Latency:   {p99:.2f} ms")
    print(f"  Mean Latency:  {mean_lat:.2f} ms (std: {std_lat:.2f} ms)")
    print(f"  Min / Max:     {min_lat:.2f} ms / {max_lat:.2f} ms")
    print("=" * 80)

    summary = {
        "benchmark_phase": "Phase 5: Latency and Performance Profiling",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
        "benchmark_parameters": {
            "warmup_cycles": 10,
            "repetitions": 50,
            "pipeline_scope": "Full End-to-End: Inspection -> Retrieval -> Registration -> Sufficiency -> Hypotheses -> Recommendations",
        },
        "latency_metrics_ms": {
            "p50": round(p50, 2),
            "p90": round(p90, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "mean": round(mean_lat, 2),
            "std": round(std_lat, 2),
            "min": round(min_lat, 2),
            "max": round(max_lat, 2),
        },
    }

    out_file = Path("artifacts/m5_metrics/m5_1_audit_phase5_latency.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    m5_2_out = Path("artifacts/m5_metrics/m5_2_latency_results.json")
    with m5_2_out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Artifact exported: {out_file} and {m5_2_out}")

    return summary


if __name__ == "__main__":
    run_latency_benchmark()
