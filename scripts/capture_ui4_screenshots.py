"""Screenshot capture script for UI-4 Network Intelligence Workspace."""

import threading
import time
import json
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MOCK_OVERVIEW = {
    "total_elements": 13,
    "elements_by_domain": {
        "RAN": 7,
        "TRANSPORT": 4,
        "5G_CORE": 4,
        "SERVICE": 1,
    },
    "total_links": 12,
    "active_alarms_count": 2,
    "correlated_clusters_count": 1,
    "active_anomalies_count": 1,
    "last_sync_timestamp": "2026-11-03T12:00:00Z",
    "topology_version": "1.0.0-reference",
    "epistemic_status": "OBSERVED_FACT",
    "provenance": {
        "source_model": "TelecomTopologyGraph",
        "integrity_hash": "sha256-ui4-mock-overview",
    },
}

MOCK_TOPOLOGY = {
    "nodes": [
        {"element_id": "AMF-CORE-01", "domain": "5G_CORE", "element_type": "AMF", "site_id": "CORE", "nominal_subscribers": 100000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "SMF-CORE-01", "domain": "5G_CORE", "element_type": "SMF", "site_id": "CORE", "nominal_subscribers": 100000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "UPF-CORE-PRIMARY", "domain": "5G_CORE", "element_type": "UPF", "site_id": "CORE", "nominal_subscribers": 50000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "UPF-CORE-SECONDARY", "domain": "5G_CORE", "element_type": "UPF", "site_id": "CORE", "nominal_subscribers": 50000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "IMS-CORE-01", "domain": "SERVICE", "element_type": "IMS", "site_id": "CORE", "nominal_subscribers": 80000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "RTR-IPMPLS-AGG01", "domain": "TRANSPORT", "element_type": "ROUTER", "site_id": "AGG01", "nominal_subscribers": None, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "RTR-IPMPLS-AGG02", "domain": "TRANSPORT", "element_type": "ROUTER", "site_id": "AGG02", "nominal_subscribers": None, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "SW-ACCESS-SITE01", "domain": "TRANSPORT", "element_type": "SWITCH", "site_id": "SITE01", "nominal_subscribers": None, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "SW-ACCESS-SITE02", "domain": "TRANSPORT", "element_type": "SWITCH", "site_id": "SITE02", "nominal_subscribers": None, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "GNB-TESTBED-5G-01", "domain": "RAN", "element_type": "GNB", "site_id": "SITE01", "nominal_subscribers": 5000, "active_alarm_count": 1, "has_anomaly": True, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "CELL-101", "domain": "RAN", "element_type": "CELL", "site_id": "SITE01", "nominal_subscribers": 1500, "active_alarm_count": 1, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "CELL-102", "domain": "RAN", "element_type": "CELL", "site_id": "SITE01", "nominal_subscribers": 1500, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
        {"element_id": "CELL-103", "domain": "RAN", "element_type": "CELL", "site_id": "SITE01", "nominal_subscribers": 2000, "active_alarm_count": 0, "has_anomaly": False, "epistemic_status": "OBSERVED_FACT"},
    ],
    "links": [
        {"source": "AMF-CORE-01", "target": "SMF-CORE-01", "relation": "n11_control", "is_dependency": False, "direction": "bidirectional"},
        {"source": "SMF-CORE-01", "target": "UPF-CORE-PRIMARY", "relation": "n4_session", "is_dependency": True, "direction": "downstream"},
        {"source": "UPF-CORE-PRIMARY", "target": "RTR-IPMPLS-AGG01", "relation": "n3_interface", "is_dependency": True, "direction": "downstream"},
        {"source": "RTR-IPMPLS-AGG01", "target": "SW-ACCESS-SITE01", "relation": "backhaul_fiber", "is_dependency": True, "direction": "downstream"},
        {"source": "SW-ACCESS-SITE01", "target": "GNB-TESTBED-5G-01", "relation": "fronthaul", "is_dependency": True, "direction": "downstream"},
        {"source": "GNB-TESTBED-5G-01", "target": "CELL-101", "relation": "serves_cell", "is_dependency": True, "direction": "downstream"},
        {"source": "GNB-TESTBED-5G-01", "target": "CELL-102", "relation": "serves_cell", "is_dependency": True, "direction": "downstream"},
        {"source": "GNB-TESTBED-5G-01", "target": "CELL-103", "relation": "serves_cell", "is_dependency": True, "direction": "downstream"},
    ],
    "epistemic_status": "COMPUTED_TOPOLOGY",
}

MOCK_IMPACT = {
    "target_element": "GNB-TESTBED-5G-01",
    "direct_elements": ["GNB-TESTBED-5G-01"],
    "inferred_elements": ["CELL-101", "CELL-102", "CELL-103"],
    "total_element_count": 4,
    "affected_domains": ["RAN"],
    "severity_risk_level": "MAJOR",
    "risk_score": 0.65,
    "estimated_affected_subscribers": 10000,
    "subscriber_impact_basis": "Aggregated nominal capacity across 4 direct/inferred elements from registered topology metadata. Not dynamically observed from active UE counters.",
    "epistemic_status": "DERIVED_ESTIMATE",
    "provenance": {"source": "NetworkImpactAnalyzer"},
}

MOCK_ALARMS = {
    "alarms": [
        {
            "alarm_id": "ALM-RAN-7100",
            "network_element_id": "GNB-TESTBED-5G-01",
            "network_domain": "RAN",
            "alarm_code": "7100",
            "probable_cause": "High VSWR on antenna feeder sector 4B",
            "severity": "CRITICAL",
            "timestamp": "2026-11-03T12:00:00Z",
            "cluster_id": "CLUST-RAN-A1B2",
            "epistemic_status": "OBSERVED_FACT",
        },
        {
            "alarm_id": "ALM-RAN-CELLDEG",
            "network_element_id": "CELL-101",
            "network_domain": "RAN",
            "alarm_code": "CELL-DEG-01",
            "probable_cause": "Radio link degradation / CQI drop",
            "severity": "MAJOR",
            "timestamp": "2026-11-03T12:01:30Z",
            "cluster_id": "CLUST-RAN-A1B2",
            "epistemic_status": "OBSERVED_FACT",
        },
    ],
    "clusters": [
        {
            "cluster_id": "CLUST-RAN-A1B2",
            "dominant_domain": "RAN",
            "event_count": 2,
            "affected_elements": ["GNB-TESTBED-5G-01", "CELL-101"],
            "mean_confidence": 0.88,
            "rationales": [
                "Alarm 7100 on GNB-TESTBED-5G-01 and CELL-DEG-01 on CELL-101 occurred 90.0s apart with hop distance 1.",
                "Cross-domain affinity (RAN <-> RAN): 1.00. Semantic compatibility (1.00): Shared fault category (RADIO_CAPACITY).",
            ],
            "epistemic_status": "HYPOTHESIS",
        }
    ],
    "total_alarms": 2,
    "total_clusters": 1,
}

MOCK_TELEMETRY = {
    "element_id": "GNB-TESTBED-5G-01",
    "series": [
        {
            "metric_name": "prb_utilization_pct",
            "unit": "%",
            "timestamps": [
                "2026-11-03T11:40:00Z",
                "2026-11-03T11:45:00Z",
                "2026-11-03T11:50:00Z",
                "2026-11-03T11:55:00Z",
                "2026-11-03T12:00:00Z",
                "2026-11-03T12:05:00Z",
                "2026-11-03T12:10:00Z",
            ],
            "values": [42.1, 44.5, 43.8, 45.0, 89.2, 94.6, 92.1],
            "is_imputed": [False, False, False, False, False, False, False],
        },
        {
            "metric_name": "vswr_ratio",
            "unit": "ratio",
            "timestamps": [
                "2026-11-03T11:40:00Z",
                "2026-11-03T11:45:00Z",
                "2026-11-03T11:50:00Z",
                "2026-11-03T11:55:00Z",
                "2026-11-03T12:00:00Z",
                "2026-11-03T12:05:00Z",
                "2026-11-03T12:10:00Z",
            ],
            "values": [1.12, 1.15, 1.14, 1.18, 2.45, 2.68, 2.60],
            "is_imputed": [False, False, False, False, False, False, False],
        },
    ],
    "anomalies": [
        {
            "anomaly_id": "ANOM-RAN-01",
            "metric_name": "vswr_ratio",
            "timestamp": "2026-11-03T12:00:00Z",
            "observed_value": 2.45,
            "expected_value": 1.15,
            "threshold_value": 1.50,
            "severity": "CRITICAL",
            "score": 0.94,
            "epistemic_status": "MODEL_PREDICTION",
        }
    ],
    "epistemic_status": "OBSERVED_FACT",
}


class SPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIST), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/v1/network/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if "overview" in self.path:
                self.wfile.write(json.dumps(MOCK_OVERVIEW).encode("utf-8"))
            elif "topology" in self.path:
                self.wfile.write(json.dumps(MOCK_TOPOLOGY).encode("utf-8"))
            elif "impact" in self.path:
                self.wfile.write(json.dumps(MOCK_IMPACT).encode("utf-8"))
            elif "alarms" in self.path:
                self.wfile.write(json.dumps(MOCK_ALARMS).encode("utf-8"))
            elif "telemetry" in self.path:
                self.wfile.write(json.dumps(MOCK_TELEMETRY).encode("utf-8"))
            else:
                self.wfile.write(b"{}")
            return

        if self.path.startswith("/api/v1/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            return

        file_path = FRONTEND_DIST / self.path.lstrip("/").split("?")[0]
        if not file_path.exists() and not self.path.startswith("/assets"):
            self.path = "/index.html"
        return super().do_GET()


def start_server(port=4174):
    TCPServer.allow_reuse_address = True
    server = TCPServer(("127.0.0.1", port), SPAHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


def capture_screenshots():
    port = 4174
    print(f"Starting UI-4 SPA server on port {port}...")
    server = start_server(port)
    time.sleep(1)

    url = f"http://127.0.0.1:{port}"
    print(f"Capturing screenshots from {url}/network...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. UI-4 Network Intelligence Workspace - Dark Theme
        print("1. Capturing Network Intelligence Workspace (Dark)...")
        page.goto(f"{url}/network")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("text=Network Intelligence Workspace", timeout=10000)
        page.wait_for_selector("text=Registered Topology Elements", timeout=10000)
        page.wait_for_selector("text=GNB-TESTBED-5G-01", timeout=10000)
        time.sleep(1)
        p1 = OUTPUT_DIR / "ui4_network_workspace_dark.png"
        page.screenshot(path=str(p1), full_page=True)
        print(f"Saved: {p1}")

        # 2. UI-4 Network Intelligence Workspace - Light Theme
        print("2. Toggling to Light Theme...")
        toggle_button = page.locator('button[aria-label="Toggle light/dark theme mode"]')
        if toggle_button.count() > 0:
            toggle_button.click()
        else:
            page.evaluate("document.documentElement.classList.remove('dark'); localStorage.setItem('piis_theme_preference', 'light');")
        time.sleep(1)
        p2 = OUTPUT_DIR / "ui4_network_workspace_light.png"
        page.screenshot(path=str(p2), full_page=True)
        print(f"Saved: {p2}")

        # Switch back to dark theme
        page.evaluate("document.documentElement.classList.add('dark'); localStorage.setItem('piis_theme_preference', 'dark');")
        time.sleep(0.5)

        # 3. Element Detail Drawer Open
        print("3. Clicking GNB-TESTBED-5G-01 to open Element Detail Drawer...")
        page.locator("button:has-text('GNB-TESTBED-5G-01')").first.click()
        page.wait_for_selector("text=Nominal Subscribers:", timeout=10000)
        time.sleep(1)
        p3 = OUTPUT_DIR / "ui4_topology_element_selected.png"
        page.screenshot(path=str(p3), full_page=True)
        print(f"Saved: {p3}")

        # 4. Network Impact Assessment
        print("4. Capturing Network Impact Assessment Section...")
        page.wait_for_selector("text=Network Impact & Blast Radius Assessment", timeout=10000)
        page.wait_for_selector("text=Epistemic Grounding Notice:", timeout=10000)
        time.sleep(0.5)
        p4 = OUTPUT_DIR / "ui4_network_impact_assessment.png"
        page.screenshot(path=str(p4), full_page=True)
        print(f"Saved: {p4}")

        # 5. Raw Alarms Table
        print("5. Switching to Raw Alarms Table...")
        alarms_tab = page.locator("button:has-text('Alarms (2)')")
        if alarms_tab.count() > 0:
            alarms_tab.click()
            page.wait_for_selector("text=High VSWR on antenna feeder sector 4B", timeout=10000)
            time.sleep(0.5)
            p5 = OUTPUT_DIR / "ui4_alarm_intelligence_raw_alarms.png"
            page.screenshot(path=str(p5), full_page=True)
            print(f"Saved: {p5}")

        # 6. Telemetry Anomaly Chart
        print("6. Capturing Telemetry Time-Series with Anomaly Markers...")
        page.wait_for_selector("text=Telemetry Time-Series & Anomaly Stream", timeout=10000)
        time.sleep(0.5)
        p6 = OUTPUT_DIR / "ui4_telemetry_anomaly_chart.png"
        page.screenshot(path=str(p6), full_page=True)
        print(f"Saved: {p6}")

        browser.close()

    server.shutdown()
    print("All UI-4 screenshots successfully captured!")


if __name__ == "__main__":
    capture_screenshots()
