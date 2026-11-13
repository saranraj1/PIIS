"""Simulated Prometheus / OTLP telemetry service for M6 integration testing."""

from __future__ import annotations

from typing import Any, Dict, List
import time
import math


class SimulatedTelemetryPlatform:
    """Mock metrics engine generating realistic Prometheus and OTLP time series."""

    def __init__(self):
        self.start_time = time.time()

    def query_prometheus_vector(self, query: str = "vswr_ratio") -> Dict[str, Any]:
        """Simulate Prometheus HTTP query API GET /api/v1/query."""
        now_ts = time.time()
        # Sine-wave variation simulating metric oscillation
        val = 1.85 + 0.15 * math.sin(now_ts / 10.0)

        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {
                            "__name__": "vswr_ratio",
                            "instance": "GNB-RAN-701",
                            "job": "ran_gnb_telemetry",
                            "domain": "RAN",
                            "sector": "SEC-01",
                        },
                        "value": [now_ts, f"{val:.3f}"],
                    },
                    {
                        "metric": {
                            "__name__": "rsrp_dbm",
                            "instance": "GNB-RAN-701",
                            "job": "ran_gnb_telemetry",
                            "domain": "RAN",
                            "sector": "SEC-01",
                        },
                        "value": [now_ts, "-108.4"],
                    },
                ],
            },
        }

    def generate_otlp_metrics_batch(self, count: int = 2) -> List[Dict[str, Any]]:
        """Generate OpenTelemetry JSON metric items."""
        now_nano = int(time.time() * 1e9)
        return [
            {
                "name": "upf.session.drop.rate",
                "unit": "ratio",
                "network_element_id": "UPF-CORE-01",
                "point": {
                    "time_unix_nano": now_nano,
                    "as_double": 0.142,
                    "attributes": {
                        "network.domain": "CORE",
                        "service.name": "5g-upf-dataplane",
                    },
                },
            },
            {
                "name": "ip.interface.packet_drops",
                "unit": "packets/sec",
                "network_element_id": "CSR-ROUTER-99",
                "point": {
                    "time_unix_nano": now_nano,
                    "as_double": 48.0,
                    "attributes": {
                        "network.domain": "TRANSPORT",
                        "service.name": "ip-mpls-edge",
                    },
                },
            },
        ]
