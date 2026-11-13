"""Playwright visual evidence capture script for PIIS UI-9 Settings & Configuration Workspace."""

import json
from pathlib import Path
import threading
import time
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from playwright.sync_api import sync_playwright

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "ui" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MOCK_SYSTEM_INFO = {
    "application_name": "Production Incident Intelligence System",
    "application_edition": "Telecom Edition (Portfolio Release)",
    "core_version": "1.0.0-rc2",
    "api_version": "1.0.0",
    "active_milestone": "UI-9",
    "environment": "development",
    "operational_mode": "read_only_decision_support",
    "telecom_domains": ["RAN", "Transport", "Core", "IMS", "Cloud"],
    "auth_mode": "IN_MEMORY_JWT_OIDC",
    "rbac_enforced": True,
    "service_principals_barred": True,
    "retrieval_models": {
        "lexical_index": "BM25 Okapi (In-Memory Index)",
        "dense_bi_encoder": "all-MiniLM-L6-v2 (Offline Local Fallback)",
        "deterministic_sop_rules": "15 Registered Rules",
        "anomaly_detectors": "3-Sigma Z-Score & Isolation Forest",
    },
    "operational_boundaries": {
        "network_mutations_allowed": False,
        "production_commands_allowed": False,
        "ticket_closures_allowed": False,
        "external_egress_allowed": False,
        "autonomous_remediation_allowed": False,
        "secret_exposure_allowed": False,
    },
    "documentation_catalog": [
        {
            "title": "M7 Portfolio Release Notes",
            "path": "docs/m7/M7_PORTFOLIO_RELEASE_NOTES.md",
            "category": "PORTFOLIO",
            "description": "Release notes and architecture for M7 Portfolio Edition RC2.",
        },
        {
            "title": "UI-8.1 Independent Audit",
            "path": "docs/ui/UI8_1_INDEPENDENT_AUDIT.md",
            "category": "VERIFICATION",
            "description": "Adversarial runtime health, security, and regression audit.",
        },
        {
            "title": "UI-9 Settings Reconnaissance",
            "path": "docs/ui/UI9_RECONNAISSANCE.md",
            "category": "ARCHITECTURE",
            "description": "Pre-implementation audit of configuration and preferences.",
        },
        {
            "title": "UI-9 Settings Specification",
            "path": "docs/ui/UI9_SETTINGS_WORKSPACE.md",
            "category": "SPECIFICATION",
            "description": "Settings and configuration workspace design and verification.",
        },
    ],
    "epistemic_classification": "VERIFIED_CONFIGURATION",
}

MOCK_PERSISTENCE = {
    "audit_ledger_status": "AVAILABLE",
    "audit_ledger_records_count": 2,
    "ledger_head_sequence": 2,
    "checkpoint_anchor_status": "MONOTONIC_ANCHORED",
    "checkpoint_sequence": 2,
    "hmac_key_provider_status": "LocalDevKeyProvider",
    "disk_fsync_supported": True,
    "last_verification_timestamp": "2026-11-04T12:00:00Z",
    "external_trust_anchor_connected": False,
    "trust_anchor_limitation_disclosure": "Portfolio disconnected boundary",
}

MOCK_INTEGRATIONS = [
    {
        "integration_id": "SNOW-ITSM-01",
        "name": "ServiceNow ITSM Connector",
        "category": "ITSM",
        "provider_type": "SERVICENOW",
        "adapter_class": "ServiceNowAdapter",
        "connection_mode": "REST_PULL",
        "operational_status": "AVAILABLE",
        "status_label": "LOCALLY VERIFIED",
        "capabilities": ["INCIDENT_INGESTION"],
        "data_direction": "INGESTION_ONLY",
        "rate_limit_rps": 50,
        "last_heartbeat": "2026-11-04T12:00:00Z",
        "consecutive_failures": 0,
    },
    {
        "integration_id": "JIRA-ITSM-01",
        "name": "Jira Service Management",
        "category": "ITSM",
        "provider_type": "JIRA",
        "adapter_class": "JiraServiceManagementAdapter",
        "connection_mode": "WEBHOOK_PUSH",
        "operational_status": "AVAILABLE",
        "status_label": "LOCALLY VERIFIED",
        "capabilities": ["INCIDENT_INGESTION"],
        "data_direction": "INGESTION_ONLY",
        "rate_limit_rps": 50,
        "last_heartbeat": "2026-11-04T12:00:00Z",
        "consecutive_failures": 0,
    },
    {
        "integration_id": "PROM-TELEM-01",
        "name": "Prometheus Telemetry Scraper",
        "category": "TELEMETRY",
        "provider_type": "PROMETHEUS",
        "adapter_class": "PrometheusAdapter",
        "connection_mode": "SCRAPE_TARGET",
        "operational_status": "AVAILABLE",
        "status_label": "LOCALLY VERIFIED",
        "capabilities": ["METRICS_PULL"],
        "data_direction": "INGESTION_ONLY",
        "rate_limit_rps": 100,
        "last_heartbeat": "2026-11-04T12:00:00Z",
        "consecutive_failures": 0,
    },
    {
        "integration_id": "OSS-ALARM-01",
        "name": "Nokia NetAct OSS/NMS Alarm Sink",
        "category": "OSS_NMS_ALARM",
        "provider_type": "OSS_NMS",
        "adapter_class": "OSSAlarmAdapter",
        "connection_mode": "ALARM_EVENT_STREAM",
        "operational_status": "AVAILABLE",
        "status_label": "LOCALLY VERIFIED",
        "capabilities": ["ALARM_INGESTION"],
        "data_direction": "INGESTION_ONLY",
        "rate_limit_rps": 200,
        "last_heartbeat": "2026-11-04T12:00:00Z",
        "consecutive_failures": 0,
    },
]


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
        if self.path.startswith("/api/v1/settings/system-info"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_SYSTEM_INFO).encode("utf-8"))
            return

        if self.path.startswith("/api/v1/system-health/persistence"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_PERSISTENCE).encode("utf-8"))
            return

        if self.path.startswith("/api/v1/integrations"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_INTEGRATIONS).encode("utf-8"))
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


def start_server(port=4179):
    TCPServer.allow_reuse_address = True
    server = TCPServer(("127.0.0.1", port), SPAHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def capture_screenshots():
    server = start_server(4179)
    print("Serving frontend dist on http://127.0.0.1:4179")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Appearance Tab - Dark Mode
        print("1. Capturing Appearance Tab (Dark Mode)...")
        page.goto("http://127.0.0.1:4179/settings")
        page.wait_for_selector("text=Settings & Configuration Workspace", timeout=15000)
        time.sleep(1)
        p1 = OUTPUT_DIR / "01_ui9_settings_appearance_dark.png"
        page.screenshot(path=str(p1), full_page=True)
        print(f"Saved: {p1}")

        # 2. Appearance Tab - Light Mode
        print("2. Switching to Light Theme...")
        page.locator("button:has-text('Light')").first.click()
        time.sleep(1)
        p2 = OUTPUT_DIR / "02_ui9_settings_appearance_light.png"
        page.screenshot(path=str(p2), full_page=True)
        print(f"Saved: {p2}")

        # Switch back to dark mode
        page.locator("button:has-text('Dark (NOC)')").first.click()
        time.sleep(0.5)

        # 3. User & Session Tab
        print("3. Switching to User & Session Tab...")
        page.locator("button:has-text('User & Session')").click()
        page.wait_for_selector("text=Zero-Persistence In-Memory Authentication Guarantee:", timeout=10000)
        time.sleep(1)
        p3 = OUTPUT_DIR / "03_ui9_settings_user_session.png"
        page.screenshot(path=str(p3), full_page=True)
        print(f"Saved: {p3}")

        # 4. Application Config Tab
        print("4. Switching to Application Config Tab...")
        page.locator("button:has-text('Application Config')").click()
        page.wait_for_selector("text=Operational Boundary Guarantees", timeout=10000)
        time.sleep(1)
        p4 = OUTPUT_DIR / "04_ui9_settings_application_config.png"
        page.screenshot(path=str(p4), full_page=True)
        print(f"Saved: {p4}")

        # 5. Security & Trust Tab
        print("5. Switching to Security & Trust Tab...")
        page.locator("button:has-text('Security & Trust')").click()
        page.wait_for_selector("text=Portfolio Boundary & Disconnected External Prerequisites", timeout=10000)
        time.sleep(1)
        p5 = OUTPUT_DIR / "05_ui9_settings_security_trust.png"
        page.screenshot(path=str(p5), full_page=True)
        print(f"Saved: {p5}")

        # 6. Integration Config Tab
        print("6. Switching to Integration Config Tab...")
        page.locator("button:has-text('Integration Config')").click()
        page.wait_for_selector("text=Telecom Protocol Adapters Pool", timeout=10000)
        time.sleep(1)
        p6 = OUTPUT_DIR / "06_ui9_settings_integrations_config.png"
        page.screenshot(path=str(p6), full_page=True)
        print(f"Saved: {p6}")

        # 7. About & System Info Tab
        print("7. Switching to About & System Info Tab...")
        page.locator("button:has-text('About & System Info')").click()
        page.wait_for_selector("text=Authoritative Documentation Suite", timeout=10000)
        time.sleep(1)
        p7 = OUTPUT_DIR / "07_ui9_settings_about_system.png"
        page.screenshot(path=str(p7), full_page=True)
        print(f"Saved: {p7}")

        # 8. Mobile Viewport (375x812)
        print("8. Capturing Mobile Responsive Viewport...")
        mobile_context = browser.new_context(viewport={"width": 375, "height": 812})
        mobile_page = mobile_context.new_page()
        mobile_page.goto("http://127.0.0.1:4179/settings")
        mobile_page.wait_for_selector("text=Settings & Configuration Workspace", timeout=10000)
        time.sleep(1)
        p8 = OUTPUT_DIR / "08_ui9_settings_mobile_responsive.png"
        mobile_page.screenshot(path=str(p8), full_page=True)
        print(f"Saved: {p8}")

        browser.close()

    server.shutdown()
    print("All UI-9 screenshots successfully captured!")


if __name__ == "__main__":
    capture_screenshots()
