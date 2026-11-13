"""Browser verification and screenshot capture script for UI-8 System Health & Operations Workspace."""

from __future__ import annotations

from pathlib import Path
import subprocess
import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn

from piis.api.app import create_app
from piis.api.routers.incidents import get_pipeline, get_workflow
from piis.auth import ApplicationRole, AuthManager
from piis.auth.dependencies import set_auth_manager


def run_ui8_browser_verification():
    output_dir = Path("docs/ui/screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)

    auth_mgr = AuthManager()
    set_auth_manager(auth_mgr)
    admin_token = auth_mgr.mint_dev_token(principal_id="admin_frank", role=ApplicationRole.PIIS_ADMIN)

    # Initialize app, pipeline & workflow
    app = create_app()
    pipeline = get_pipeline()
    _ = get_workflow()
    pipeline._seed_reference_activity()

    # Start FastAPI backend
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1.5)
    print("[SERVER] FastAPI backend running on http://127.0.0.1:8000")

    # Start Vite preview server
    vite_proc = subprocess.Popen(
        ["npx.cmd", "vite", "preview", "--port", "5173", "--host", "127.0.0.1"],
        cwd="frontend",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for servers to respond
    import urllib.request
    print("[WAIT] Waiting for backend and frontend servers to be ready...")
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5173", timeout=1):
                break
        except Exception:
            time.sleep(0.5)
    print("[FRONTEND] Vite preview running and reachable on http://127.0.0.1:5173")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            # Step 1: Set token via settings
            print("[BROWSER] Navigating to Settings to load in-memory token...")
            page.goto("http://127.0.0.1:5173/settings")
            page.wait_for_selector("#settings-token", timeout=10000)
            page.fill("#settings-token", admin_token)
            page.click("button[type='submit']")
            page.wait_for_selector("text=Token loaded into memory", timeout=5000)
            print("[BROWSER] Token loaded successfully.")

            # Step 2: Navigate to System Health
            print("[BROWSER] Navigating via sidebar to System Health (/system)...")
            page.click("text=System Health")
            page.wait_for_selector("text=System Health & Operations Workspace", timeout=10000)
            page.wait_for_selector("text=Aggregate Status", timeout=10000)
            time.sleep(1.5)

            # Screenshot 1: Overview
            shot1 = output_dir / "01_ui8_system_health_overview.png"
            page.screenshot(path=str(shot1), full_page=True)
            print(f"[SCREENSHOT] Saved overview to {shot1}")

            # Step 3: Search filter in registry
            print("[BROWSER] Testing component registry search filter...")
            page.fill("input[placeholder*='Search component']", "gateway")
            time.sleep(1.0)
            shot2 = output_dir / "02_ui8_system_health_filtered_registry.png"
            page.screenshot(path=str(shot2))
            print(f"[SCREENSHOT] Saved filtered registry to {shot2}")

            # Step 4: Open Diagnostics Drawer
            print("[BROWSER] Clearing search and opening diagnostics drawer for first component...")
            page.fill("input[placeholder*='Search component']", "")
            time.sleep(0.5)
            diag_btn = page.locator("button:has-text('Diagnostics')").first
            diag_btn.click()
            page.wait_for_selector("text=Diagnostic Telemetry & Attributes", timeout=6000)
            time.sleep(1.0)
            shot3 = output_dir / "03_ui8_system_health_component_drawer.png"
            page.screenshot(path=str(shot3), full_page=True)
            print(f"[SCREENSHOT] Saved component drawer to {shot3}")

            # Close drawer
            page.click("button:has-text('Close Diagnostics')")
            time.sleep(0.5)

            # Step 5: Ingestion & DLQ Pipeline tab
            print("[BROWSER] Navigating to Ingestion & DLQ Pipeline tab...")
            page.click("button:has-text('Ingestion & DLQ Pipeline')")
            page.wait_for_selector("text=Ingested Envelopes", timeout=8000)
            page.wait_for_selector("text=Dead-Letter Quarantine (DLQ)", timeout=8000)
            time.sleep(1.0)
            shot4 = output_dir / "04_ui8_system_health_ingestion_dlq.png"
            page.screenshot(path=str(shot4), full_page=True)
            print(f"[SCREENSHOT] Saved ingestion tab to {shot4}")

            # Step 6: AI & Retrieval Subsystem tab
            print("[BROWSER] Navigating to AI & Retrieval Subsystem tab...")
            page.click("button:has-text('AI & Retrieval Subsystem')")
            page.wait_for_selector("text=Investigation Engine", timeout=8000)
            page.wait_for_selector("text=Dense Bi-Encoder Vector Search", timeout=8000)
            time.sleep(1.0)
            shot5 = output_dir / "05_ui8_system_health_intelligence_subsystem.png"
            page.screenshot(path=str(shot5), full_page=True)
            print(f"[SCREENSHOT] Saved intelligence tab to {shot5}")

            # Step 7: Persistence & Audit Parity tab
            print("[BROWSER] Navigating to Persistence & Audit Parity tab...")
            page.click("button:has-text('Persistence & Audit Parity')")
            page.wait_for_selector("text=Audit Ledger Status", timeout=8000)
            page.wait_for_selector("text=Immutable Trust Anchor Limitation Disclosure", timeout=8000)
            time.sleep(1.0)
            shot6 = output_dir / "06_ui8_system_health_persistence_audit.png"
            page.screenshot(path=str(shot6), full_page=True)
            print(f"[SCREENSHOT] Saved persistence tab to {shot6}")

            # Step 8: Health Events Timeline tab
            print("[BROWSER] Navigating to Health Events Timeline tab...")
            page.click("button:has-text('Health Events Timeline')")
            page.wait_for_selector("text=Observation Details", timeout=8000)
            time.sleep(1.0)
            shot7 = output_dir / "07_ui8_system_health_events_timeline.png"
            page.screenshot(path=str(shot7), full_page=True)
            print(f"[SCREENSHOT] Saved events tab to {shot7}")

            # Step 9: Dependency Topology Map tab
            print("[BROWSER] Navigating to Dependency Topology Map tab...")
            page.click("button:has-text('Dependency Topology Map')")
            page.wait_for_selector("text=Architecturally Grounded Dependency Topology Map", timeout=8000)
            page.wait_for_selector("text=1. Edge & Ingestion Layer", timeout=8000)
            time.sleep(1.0)
            shot8 = output_dir / "08_ui8_system_health_dependency_topology.png"
            page.screenshot(path=str(shot8), full_page=True)
            print(f"[SCREENSHOT] Saved dependency topology to {shot8}")

            # Step 10: Mobile responsive screenshot
            print("[BROWSER] Capturing mobile layout viewport...")
            mobile_context = browser.new_context(viewport={"width": 375, "height": 812})
            mobile_page = mobile_context.new_page()
            mobile_page.goto("http://127.0.0.1:5173/system")
            time.sleep(1.5)
            shot9 = output_dir / "09_ui8_system_health_mobile_responsive.png"
            mobile_page.screenshot(path=str(shot9), full_page=True)
            print(f"[SCREENSHOT] Saved mobile layout to {shot9}")

            browser.close()
    finally:
        vite_proc.terminate()
        server.should_exit = True
        server_thread.join(timeout=2.0)
        print("[SHUTDOWN] Servers closed gracefully.")


if __name__ == "__main__":
    run_ui8_browser_verification()
