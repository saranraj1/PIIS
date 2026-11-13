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

MOCK_INCIDENTS = [
    {
        "incident_id": "INC-2026-0001",
        "title": "High VSWR on 5G NR Sector 4B",
        "description": "Antenna impedance mismatch detected on tower gnb-cluster-tx-09, sector 4B.",
        "network_domain": "RAN",
        "fault_category": "HARDWARE_RF",
        "severity": "CRITICAL",
        "support_level_label": "L2",
        "support_level_rationale": "High customer impact in dense metropolitan sector",
        "affected_region": "US-EAST-1",
        "affected_subscribers": 14500,
        "network_element_ids": ["gnb-cluster-tx-09", "cell-sec4b"],
        "created_at": "2026-11-02T14:30:00Z",
        "resolved_at": None,
        "resolution_summary": None,
        "root_cause_confirmed": False,
        "source_type": "PUBLIC_REAL",
        "source_dataset": "ServiceNow",
        "source_record_id": "INC0089201",
    },
    {
        "incident_id": "INC-2026-0002",
        "title": "UPF N3 Interface Packet Drops",
        "description": "Elevated GTP-U packet loss observed on UPF edge instance upf-edge-core-01.",
        "network_domain": "5G_CORE",
        "fault_category": "CORE_USER_PLANE",
        "severity": "MAJOR",
        "support_level_label": "L2",
        "support_level_rationale": "Signaling latency spikes on eCPRI transport",
        "affected_region": "US-CENTRAL",
        "affected_subscribers": 8200,
        "network_element_ids": ["upf-edge-core-01"],
        "created_at": "2026-11-02T15:00:00Z",
        "resolved_at": None,
        "resolution_summary": None,
        "root_cause_confirmed": False,
        "source_type": "PUBLIC_REAL",
        "source_dataset": "Jira-JSM",
        "source_record_id": "NOC-452",
    },
    {
        "incident_id": "INC-2026-0003",
        "title": "Optical DWDM Transponder Optical Jitter",
        "description": "Bit error rate exceeded warning thresholds on DWDM transponder 04.",
        "network_domain": "TRANSPORT",
        "fault_category": "OPTICAL_LAYER",
        "severity": "MINOR",
        "support_level_label": "L1",
        "support_level_rationale": "Redundant ring link absorbed degraded traffic",
        "affected_region": "US-EAST-1",
        "affected_subscribers": 0,
        "network_element_ids": ["dwdm-ring-04"],
        "created_at": "2026-11-02T12:00:00Z",
        "resolved_at": "2026-11-02T13:30:00Z",
        "resolution_summary": "Transceiver recalibrated automatically by optical control plane.",
        "root_cause_confirmed": True,
        "source_type": "SYNTHETIC",
        "source_dataset": "OSS_NMS",
        "source_record_id": "ALM-9912",
    },
]

MOCK_HEALTH = {
    "status": "ok",
    "service": "piis-core",
    "mode": "read_only_decision_support",
}

MOCK_READY = {
    "status": "ready",
    "registered_adapters_count": 4,
    "degraded_adapters": [],
    "incidents_count": 3,
    "dead_letter_count": 0,
    "audit_ledger_records": 12,
}

MOCK_ADAPTERS = [
    {
        "adapter_id": "SNOW-ITSM-01",
        "adapter_type": "ITSM",
        "state": "HEALTHY",
        "last_heartbeat": "2026-11-03T05:00:00Z",
        "last_successful_ingestion": "2026-11-03T04:58:00Z",
        "consecutive_failures": 0,
        "error_message": None,
    },
    {
        "adapter_id": "JIRA-ITSM-01",
        "adapter_type": "ITSM",
        "state": "HEALTHY",
        "last_heartbeat": "2026-11-03T05:00:00Z",
        "last_successful_ingestion": "2026-11-03T04:55:00Z",
        "consecutive_failures": 0,
        "error_message": None,
    },
]

MOCK_AUDIT = {
    "verified": True,
    "record_count": 12,
    "tamper_detected": False,
    "root_hash": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
}

MOCK_EVIDENCE = [
    {
        "evidence_id": "EVID-001",
        "evidence_type": "TELEMETRY_ANOMALY",
        "source_ref": "Prometheus-NodeExporter",
        "domain": "RAN",
        "observed_at": "2026-11-02T14:28:00Z",
        "trust_classification": "HIGH_TRUST_APPROVED",
        "content_summary": "VSWR ratio spiked to 2.45 on antenna port 4B (threshold: 1.50)",
        "raw_metadata": {
            "metric_name": "rf_port_vswr_ratio",
            "port": "4B",
            "node": "gnb-cluster-tx-09",
            "measured_value": 2.45,
            "threshold": 1.5,
        },
    },
    {
        "evidence_id": "EVID-002",
        "evidence_type": "ALARM_CLUSTER",
        "source_ref": "OSS_NMS-NokiaNetAct",
        "domain": "RAN",
        "observed_at": "2026-11-02T14:29:10Z",
        "trust_classification": "HIGH_TRUST_APPROVED",
        "content_summary": "Major 3GPP Alarm 7101: RF Unit Antenna Line Impedance Fault",
        "raw_metadata": {
            "alarm_code": "ALM-7101",
            "severity": "MAJOR",
            "affected_unit": "RRU-4B",
        },
    },
    {
        "evidence_id": "EVID-003",
        "evidence_type": "ML_CLASSIFICATION",
        "source_ref": "M2-FaultCategoryClassifier",
        "domain": "RAN",
        "observed_at": "2026-11-02T14:30:06Z",
        "trust_classification": "MEDIUM_TRUST_VERIFIED",
        "content_summary": "Predicted Fault Category HARDWARE_RF (confidence: 0.94)",
        "raw_metadata": {
            "model_version": "v1.0.0",
            "feature_count": 32,
        },
    },
    {
        "evidence_id": "EVID-004",
        "evidence_type": "APPROVED_RUNBOOK",
        "source_ref": "SOP-RAN-VSWR-001",
        "domain": "RAN",
        "observed_at": "2026-11-02T14:30:08Z",
        "trust_classification": "HIGH_TRUST_APPROVED",
        "content_summary": "Standard Operating Procedure: 5G NR Remote Radio Unit Feeder Line & Jumper Diagnostics",
        "raw_metadata": {
            "runbook_id": "SOP-RAN-VSWR-001",
            "author": "RanEngineeringGroup",
            "revision": "3.2",
        },
    },
]

MOCK_HYPOTHESES = [
    {
        "hypothesis_id": "HYP-001",
        "description": "Physical Feeder Jumper Connector Water Ingress or Loose Coupling on Sector 4B",
        "supporting_evidence_ids": ["EVID-001", "EVID-002", "EVID-003"],
        "contradicting_evidence_ids": [],
        "evidence_source": "HybridRetrievalEngine + CausalTopology",
        "evidence_timestamp": "2026-11-02T14:30:10Z",
        "confidence_proxy": 0.88,
        "confidence_rationale": "Combined RRF rank ratio (0.85) corroborated by direct telemetry threshold excursion (EVID-001) and active 3GPP alarm (EVID-002)",
        "alternative_explanations": [
            "Internal Power Amplifier circulator failure inside RRU-4B",
            "Antenna element passive intermodulation (PIM) spike",
        ],
        "recommended_verification_steps": [
            "Query passive intermodulation (PIM) telemetry logs over last 6 hours",
            "Execute non-disruptive automated VSWR sweep test via OSS API",
        ],
        "status": "SUPPORTED",
    },
    {
        "hypothesis_id": "HYP-002",
        "description": "Transient Atmospheric Thermal Expansion on Coaxial Feeder Cable",
        "supporting_evidence_ids": ["EVID-001"],
        "contradicting_evidence_ids": ["EVID-002"],
        "evidence_source": "IsolationForest + AnomalyEngine",
        "evidence_timestamp": "2026-11-02T14:30:10Z",
        "confidence_proxy": 0.35,
        "confidence_rationale": "Low heuristic weight: Major impedance alarm contradicts purely transient expansion without sustained mismatch",
        "alternative_explanations": ["Substation supply voltage drop"],
        "recommended_verification_steps": ["Check ambient site weather sensors for rapid temperature swing"],
        "status": "REJECTED",
    },
]

MOCK_RECOMMENDATIONS = [
    {
        "recommendation_id": "REC-001",
        "description": "Execute Non-Destructive RF Port Diagnostics & Continuous Wave Return Loss Sweep",
        "reason": "Confirm whether impedance mismatch is localized to external jumper cable or internal to RRU-4B transceiver module.",
        "supporting_evidence_ids": ["EVID-001", "EVID-002"],
        "source_runbook_id": "SOP-RAN-VSWR-001",
        "source_section": "Section 3.2: Return Loss Measurement",
        "risk_classification": "READ_ONLY_SAFE",
        "human_approval_required": True,
        "approval_status": "PENDING_REVIEW",
        "reviewed_by": None,
        "review_timestamp": None,
        "review_notes": None,
    },
    {
        "recommendation_id": "REC-002",
        "description": "Verify Secondary Carrier Redundancy & Enable Cell Barring on Degraded Sector 4B",
        "reason": "Preempt customer handoff drops while maintenance crew inspects physical tower feeder line.",
        "supporting_evidence_ids": ["EVID-002", "EVID-004"],
        "source_runbook_id": "SOP-RAN-VSWR-001",
        "source_section": "Section 4.1: Traffic Offload Procedure",
        "risk_classification": "DISRUPTIVE_AUDIT",
        "human_approval_required": True,
        "approval_status": "APPROVED",
        "reviewed_by": "noc_lead_taylor@telecom.net",
        "review_timestamp": "2026-11-02T15:15:00Z",
        "review_notes": "Approved offload to LTE B66 underlay. Tower climb scheduled for 08:00 UTC.",
    },
]

MOCK_INVESTIGATION = {
    "incident_id": "INC-2026-0001",
    "title": "High VSWR on 5G NR Sector 4B",
    "network_domain": "RAN",
    "created_at": "2026-11-02T14:30:00Z",
    "is_sufficient": True,
    "missing_evidence": [],
    "contradictions": [],
    "stale_evidence": [],
    "is_transient_event": False,
    "hypotheses_count": 2,
    "hypotheses": MOCK_HYPOTHESES,
    "recommendations": MOCK_RECOMMENDATIONS,
    "epistemic_status": "READ_ONLY_DECISION_SUPPORT",
    "correlation_id": "CORR-INV-998811",
}

class SPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIST), **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/v1/") and "INC-ERROR" in self.path:
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "GATEWAY_TIMEOUT", "detail": "Backend Gateway Timeout: upstream investigation service unresponsive"}')
            return
        if self.path.startswith("/api/v1/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_INVESTIGATION).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/v1/") and "INC-ERROR" in self.path:
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "GATEWAY_TIMEOUT", "detail": "Backend Gateway Timeout: upstream investigation service unresponsive"}')
            return
        if self.path.startswith("/api/v1/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if self.path.endswith("/hypotheses"):
                self.wfile.write(json.dumps(MOCK_HYPOTHESES).encode("utf-8"))
            elif self.path.endswith("/evidence"):
                if "INC-EMPTY" in self.path:
                    self.wfile.write(b"[]")
                else:
                    self.wfile.write(json.dumps(MOCK_EVIDENCE).encode("utf-8"))
            elif self.path.endswith("/recommendations"):
                self.wfile.write(json.dumps(MOCK_RECOMMENDATIONS).encode("utf-8"))
            elif self.path.endswith("/investigation"):
                if "INC-EMPTY" in self.path:
                    empty_inv = dict(MOCK_INVESTIGATION)
                    empty_inv["hypotheses_count"] = 0
                    empty_inv["hypotheses"] = []
                    empty_inv["recommendations"] = []
                    self.wfile.write(json.dumps(empty_inv).encode("utf-8"))
                else:
                    self.wfile.write(json.dumps(MOCK_INVESTIGATION).encode("utf-8"))
            elif "/api/v1/incidents/INC-" in self.path:
                detail = {
                    "incident": MOCK_INCIDENTS[0],
                    "lineage": {
                        "canonical_id": "INC-2026-0001",
                        "envelope_id": "ENV-998877AABB",
                        "source_system": "ServiceNow",
                        "source_type": "PUBLIC_REAL",
                        "external_event_id": "INC0089201",
                        "observation_timestamp": "2026-11-02T14:30:00Z",
                        "ingested_at": "2026-11-02T14:30:05Z",
                        "raw_payload_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                }
                self.wfile.write(json.dumps(detail).encode("utf-8"))
            elif "/api/v1/incidents" in self.path:
                resp = {"items": MOCK_INCIDENTS, "total_count": len(MOCK_INCIDENTS), "limit": 20, "offset": 0}
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            elif "/api/v1/health" in self.path:
                self.wfile.write(json.dumps(MOCK_HEALTH).encode("utf-8"))
            elif "/api/v1/ready" in self.path:
                self.wfile.write(json.dumps(MOCK_READY).encode("utf-8"))
            elif "/api/v1/integrations/health" in self.path:
                self.wfile.write(json.dumps(MOCK_ADAPTERS).encode("utf-8"))
            elif "/api/v1/audit/verify" in self.path:
                self.wfile.write(json.dumps(MOCK_AUDIT).encode("utf-8"))
            else:
                self.wfile.write(b"{}")
            return

        file_path = FRONTEND_DIST / self.path.lstrip("/").split("?")[0]
        if not file_path.exists() and not self.path.startswith("/assets"):
            self.path = "/index.html"
        return super().do_GET()

def start_server(port=4173):
    TCPServer.allow_reuse_address = True
    server = TCPServer(("127.0.0.1", port), SPAHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def capture_screenshots():
    port = 4173
    print(f"Starting SPA server for {FRONTEND_DIST} on port {port}...")
    server = start_server(port)
    time.sleep(1)

    url = f"http://127.0.0.1:{port}"
    print(f"Launching Playwright to capture screenshots from {url}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # -------------------------------------------------------------
        # 1. UI-3 Investigation Workspace - Dark Theme
        # -------------------------------------------------------------
        print("1. Capturing Investigation Workspace (Dark)...")
        page.goto(f"{url}/investigation?id=INC-2026-0001")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("text=High VSWR on 5G NR Sector 4B", timeout=10000)
        page.wait_for_selector("text=EVIDENCE SUFFICIENT & FRESH", timeout=10000)
        page.wait_for_selector("text=HYP-001", timeout=10000)
        time.sleep(1)
        p1 = OUTPUT_DIR / "ui3_investigation_workspace_dark.png"
        page.screenshot(path=str(p1), full_page=True)
        print(f"Saved: {p1}")

        # -------------------------------------------------------------
        # 2. UI-3 Investigation Workspace - Light Theme
        # -------------------------------------------------------------
        print("2. Toggling to Light Theme...")
        toggle_button = page.locator('button[aria-label="Toggle light/dark theme mode"]')
        if toggle_button.count() > 0:
            toggle_button.click()
        else:
            page.evaluate("document.documentElement.classList.remove('dark'); localStorage.setItem('piis_theme_preference', 'light');")
        time.sleep(1)
        p2 = OUTPUT_DIR / "ui3_investigation_workspace_light.png"
        page.screenshot(path=str(p2), full_page=True)
        print(f"Saved: {p2}")

        # Switch back to dark theme
        page.evaluate("document.documentElement.classList.add('dark'); localStorage.setItem('piis_theme_preference', 'dark');")
        time.sleep(0.5)

        # -------------------------------------------------------------
        # 3. UI-3 Evidence Register Expanded
        # -------------------------------------------------------------
        print("3. Capturing Evidence Register Expanded...")
        page.goto(f"{url}/investigation?id=INC-2026-0001")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("button:has-text('Evidence Register')", timeout=10000)
        page.locator("button:has-text('Evidence Register')").click()
        page.wait_for_selector("text=EVID-001", timeout=10000)
        time.sleep(0.5)
        # Expand EVID-001 metadata
        page.locator("button[aria-label='Toggle raw metadata for EVID-001']").click()
        time.sleep(0.5)
        p3 = OUTPUT_DIR / "ui3_evidence_register_expanded.png"
        page.screenshot(path=str(p3), full_page=True)
        print(f"Saved: {p3}")

        # -------------------------------------------------------------
        # 4. UI-3 Hypothesis Analysis Expanded
        # -------------------------------------------------------------
        print("4. Capturing Hypothesis Analysis Expanded...")
        page.goto(f"{url}/investigation?id=INC-2026-0001")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("button:has-text('Hypothesis Analysis')", timeout=10000)
        page.locator("button:has-text('Hypothesis Analysis')").click()
        page.wait_for_selector("text=Mathematical Rationale", timeout=10000)
        time.sleep(0.5)
        p4 = OUTPUT_DIR / "ui3_hypothesis_analysis_expanded.png"
        page.screenshot(path=str(p4), full_page=True)
        print(f"Saved: {p4}")

        # -------------------------------------------------------------
        # 5. UI-3 Pending Human-Review State
        # -------------------------------------------------------------
        print("5. Capturing Pending Review State in Recommendations...")
        page.goto(f"{url}/investigation?id=INC-2026-0001")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("button:has-text('Recommendations & Approval')", timeout=10000)
        page.locator("button:has-text('Recommendations & Approval')").click()
        page.wait_for_selector("text=REC-001", timeout=10000)
        page.wait_for_selector("text=PENDING REVIEW", timeout=10000)
        time.sleep(0.5)
        p5 = OUTPUT_DIR / "ui3_pending_review_state.png"
        page.screenshot(path=str(p5), full_page=True)
        print(f"Saved: {p5}")

        # -------------------------------------------------------------
        # 6. UI-3 Empty Evidence State
        # -------------------------------------------------------------
        print("6. Capturing Empty Evidence State...")
        page.goto(f"{url}/investigation?id=INC-EMPTY-01")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("button:has-text('Evidence Register')", timeout=10000)
        page.locator("button:has-text('Evidence Register')").click()
        page.wait_for_selector("text=No Correlated Evidence Registered", timeout=10000)
        time.sleep(0.5)
        p6 = OUTPUT_DIR / "ui3_empty_evidence_state.png"
        page.screenshot(path=str(p6), full_page=True)
        print(f"Saved: {p6}")

        # -------------------------------------------------------------
        # 7. UI-3 API Failure State
        # -------------------------------------------------------------
        print("7. Capturing API Failure State...")
        page.goto(f"{url}/investigation?id=INC-ERROR-01")
        page.wait_for_selector("#main-content", timeout=10000)
        page.wait_for_selector("text=Failed to Load Investigation Context", timeout=15000)
        time.sleep(1)
        p7 = OUTPUT_DIR / "ui3_api_failure_state.png"
        page.screenshot(path=str(p7), full_page=True)
        print(f"Saved: {p7}")

        browser.close()

    server.shutdown()
    print("All 7 UI-3 screenshots successfully captured!")

if __name__ == "__main__":
    capture_screenshots()
