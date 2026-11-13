"""Browser verification and screenshot capture script for UI-6 / UI-6.1 Audit Ledger Workspace."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn

from piis.api.app import create_app
from piis.api.routers import incidents
from piis.auth import ApplicationRole, AuthManager
from piis.auth.dependencies import set_auth_manager
from piis.investigation.approval import (
    DiagnosticRecommendation,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
)


def _seed_sample_workflow(temp_dir: Path, auth_manager: AuthManager) -> tuple[HumanApprovalWorkflow, str]:
    ledger_path = temp_dir / "audit_log.jsonl"
    anchor_path = temp_dir / "checkpoint.json"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)

    wf = HumanApprovalWorkflow(
        signing_key=b"piis-dev-audit-key-32bytes-long!",
        key_id="piis-audit-key-2026-v2",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    r1 = DiagnosticRecommendation(
        recommendation_id="REC-SNOW-001",
        incident_id="INC-SNOW-INC0089201",
        description="Reroute Optical Carrier OC-192 to Protection Ring East",
        reason="Optical power degraded below -28 dBm threshold",
        action_type="ROUTING_CHANGE",
        supporting_evidence_ids=["EVID-PROM-01", "EVID-ALM-NOK-01"],
        source_runbook_id="RB-OPT-001",
        source_section="Section 4.2",
        expected_observation="Optical power restored to -18 dBm",
        risk_classification="READ_ONLY_SAFE",
    )

    r2 = DiagnosticRecommendation(
        recommendation_id="REC-JIRA-002",
        incident_id="INC-JIRA-NOC-452",
        description="Restart BGP session with Peer AS64512",
        reason="BGP neighbor state down on interface TenGigE0/0/0/1",
        action_type="BGP_RESET",
        supporting_evidence_ids=["EVID-ALM-ERIC-02"],
        source_runbook_id="RB-IP-CORE-009",
        source_section="Section 2.1",
        expected_observation="BGP state returns to ESTABLISHED",
        risk_classification="LOW_OBSERVABILITY",
    )

    wf.register_recommendation(r1, "INC-SNOW-INC0089201")
    wf.register_recommendation(r2, "INC-JIRA-NOC-452")

    token_alice = auth_manager.mint_dev_token("operator_alice", role=ApplicationRole.NOC_L2)
    token_bob = auth_manager.mint_dev_token("manager_bob", role=ApplicationRole.INCIDENT_MANAGER)
    auditor_token = auth_manager.mint_dev_token("auditor_eve", role=ApplicationRole.SECURITY_AUDITOR)

    wf.approve_recommendation(
        "REC-SNOW-001",
        token_alice,
        "INC-SNOW-INC0089201",
        notes="Approved optical carrier reroute after verifying redundant link reserve capacity.",
    )
    wf.reject_recommendation(
        "REC-JIRA-002",
        token_bob,
        "INC-JIRA-NOC-452",
        reason="Rejected due to pending active core maintenance window.",
    )

    return wf, auditor_token


def run_browser_verification():
    output_dir = Path("docs/ui/screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        temp_path = Path(td)
        auth_mgr = AuthManager()
        set_auth_manager(auth_mgr)
        wf, auditor_token = _seed_sample_workflow(temp_path, auth_mgr)

        app = create_app()
        incidents.set_workflow(wf)

        # Start FastAPI backend
        config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        time.sleep(1.5)
        print("[SERVER] FastAPI backend running on http://127.0.0.1:8000")

        # Start Vite preview server
        vite_proc = subprocess.Popen(
            ["npx.cmd", "vite", "preview", "--port", "5173", "--strictPort"],
            cwd="frontend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2.0)
        print("[FRONTEND] Vite preview running on http://localhost:5173")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()

                # Step 1: Navigate to settings to set bearer token in memory
                print("[BROWSER] Navigating to Settings to load in-memory token...")
                page.goto("http://localhost:5173/settings")
                page.wait_for_selector("#settings-token", timeout=10000)
                page.fill("#settings-token", auditor_token)
                page.click("button[type='submit']")
                page.wait_for_selector("text=Token loaded into memory", timeout=5000)
                print("[BROWSER] Token successfully loaded into volatile React memory.")

                # Step 2: Navigate to Audit Ledger Workspace using SPA client-side routing (preserving in-memory token)
                print("[BROWSER] Navigating via sidebar to Audit & Provenance (/audit)...")
                page.click("text=Audit & Provenance")
                page.wait_for_selector("text=Audit Ledger Workspace", timeout=10000)
                page.wait_for_selector("text=Total Ledger Blocks", timeout=10000)

                # Capture Overview Screenshot
                shot1 = output_dir / "01_audit_ledger_workspace.png"
                page.screenshot(path=str(shot1), full_page=True)
                print(f"[SCREENSHOT] Saved overview to {shot1}")

                # Step 3: Inspect Audit Provenance Flow
                print("[BROWSER] Inspecting Audit Provenance Flow...")
                flow = page.locator("text=Audit Provenance Lineage").first
                flow.scroll_into_view_if_needed()
                shot2 = output_dir / "02_audit_provenance_flow.png"
                page.screenshot(path=str(shot2))
                print(f"[SCREENSHOT] Saved provenance flow to {shot2}")

                # Step 4: Click first record row to open detail drawer
                print("[BROWSER] Clicking first record row to open detail drawer...")
                row = page.locator("tbody tr").first
                row.click()
                page.wait_for_selector("text=Audit Block #", timeout=5000)
                page.wait_for_selector("text=RFC 8785 Canonical JSON Serialization (JCS)", timeout=5000)

                # Capture Detail Drawer Screenshot
                shot3 = output_dir / "03_audit_record_detail_drawer.png"
                page.screenshot(path=str(shot3), full_page=True)
                print(f"[SCREENSHOT] Saved drawer to {shot3}")

                # Step 5: Close drawer and run verification
                print("[BROWSER] Closing drawer and executing cryptographic verification...")
                page.click("button[aria-label='Close detail drawer']")
                time.sleep(0.5)

                verify_btn = page.get_by_role("button", name="Run Cryptographic Verification")
                verify_btn.scroll_into_view_if_needed()
                verify_btn.click()
                page.wait_for_selector("text=VERIFIED & INTACT", timeout=8000)

                # Capture Verified State Screenshot
                shot4 = output_dir / "04_audit_ledger_verified_card.png"
                page.screenshot(path=str(shot4), full_page=True)
                print(f"[SCREENSHOT] Saved verified card to {shot4}")

                browser.close()
        finally:
            vite_proc.terminate()
            server.should_exit = True
            server_thread.join(timeout=2.0)
            print("[SHUTDOWN] Servers closed gracefully.")


if __name__ == "__main__":
    run_browser_verification()
