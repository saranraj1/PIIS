"""Browser verification and screenshot capture script for UI-7 Integrations Workspace."""

from __future__ import annotations

from pathlib import Path
import subprocess
import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn

from piis.api.app import create_app
from piis.api.routers.incidents import get_pipeline
from piis.auth import ApplicationRole, AuthManager
from piis.auth.dependencies import set_auth_manager


def run_ui7_browser_verification():
    output_dir = Path("docs/ui/screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)

    auth_mgr = AuthManager()
    set_auth_manager(auth_mgr)
    admin_token = auth_mgr.mint_dev_token(principal_id="admin_frank", role=ApplicationRole.PIIS_ADMIN)

    # Initialize app & pipeline
    app = create_app()
    pipeline = get_pipeline()
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

            # Step 1: Set token via settings
            print("[BROWSER] Navigating to Settings to load in-memory token...")
            page.goto("http://localhost:5173/settings")
            page.wait_for_selector("#settings-token", timeout=10000)
            page.fill("#settings-token", admin_token)
            page.click("button[type='submit']")
            page.wait_for_selector("text=Token loaded into memory", timeout=5000)
            print("[BROWSER] Token successfully loaded into volatile React memory.")

            # Step 2: Navigate to Integrations & DLQ
            print("[BROWSER] Navigating via sidebar to Integrations & DLQ (/integrations)...")
            page.click("text=Integrations & DLQ")
            page.wait_for_selector("text=Integrations Workspace", timeout=10000)
            page.wait_for_selector("text=Total Adapters", timeout=10000)
            time.sleep(1.5)

            # Screenshot 1: Overview
            shot1 = output_dir / "01_ui7_integrations_overview.png"
            page.screenshot(path=str(shot1), full_page=True)
            print(f"[SCREENSHOT] Saved overview to {shot1}")

            # Step 3: Category filtering
            print("[BROWSER] Testing category filter (ITSM)...")
            page.click("button:has-text('ITSM')")
            time.sleep(1.0)
            shot2 = output_dir / "02_ui7_integrations_filtered.png"
            page.screenshot(path=str(shot2))
            print(f"[SCREENSHOT] Saved filtered registry to {shot2}")

            # Step 4: Reset category, click first row to open detail drawer
            print("[BROWSER] Resetting category and opening detail drawer for first adapter...")
            page.click("button:has-text('All Categories')")
            time.sleep(1.0)
            row = page.locator("tbody tr").first
            row.click()
            page.wait_for_selector("text=Read-Only Boundary Enforcement", timeout=6000)
            page.wait_for_selector("text=Sanitized Configuration Parameters", timeout=6000)
            time.sleep(1.0)

            shot3 = output_dir / "03_ui7_integrations_detail_drawer.png"
            page.screenshot(path=str(shot3), full_page=True)
            print(f"[SCREENSHOT] Saved detail drawer to {shot3}")

            # Step 5: Close drawer
            print("[BROWSER] Closing detail drawer...")
            page.click("button[aria-label='Close detail drawer']")
            page.wait_for_selector("[role='dialog']", state="detached", timeout=5000)
            time.sleep(1.0)

            # Step 6: Pipeline Data Flow Topology tab
            print("[BROWSER] Navigating to Pipeline Data Flow Topology tab...")
            page.click("button:has-text('Pipeline Data Flow Topology')")
            page.wait_for_selector("text=End-to-End Telecom Intelligence Data Flow", timeout=8000)
            page.wait_for_selector("text=Simulated Telecom Sources", timeout=8000)
            time.sleep(1.0)

            shot4 = output_dir / "04_ui7_integrations_data_flow.png"
            page.screenshot(path=str(shot4), full_page=True)
            print(f"[SCREENSHOT] Saved data flow topology to {shot4}")

            # Step 7: Activity Stream tab
            print("[BROWSER] Navigating to Activity Stream tab...")
            page.click("button:has-text('Activity Stream')")
            page.wait_for_selector("text=Operational Event Stream", timeout=8000)
            time.sleep(1.0)

            shot5 = output_dir / "05_ui7_integrations_activity_stream.png"
            page.screenshot(path=str(shot5), full_page=True)
            print(f"[SCREENSHOT] Saved activity stream to {shot5}")

            # Step 8: Dead-Letter Quarantine tab
            print("[BROWSER] Navigating to Dead-Letter Quarantine (DLQ) tab...")
            page.click("button:has-text('Dead-Letter Quarantine (DLQ)')")
            page.wait_for_selector("text=Dead-Letter Quarantine Repository", timeout=8000)
            time.sleep(1.0)

            shot6 = output_dir / "06_ui7_integrations_dlq_quarantine.png"
            page.screenshot(path=str(shot6), full_page=True)
            print(f"[SCREENSHOT] Saved DLQ quarantine to {shot6}")

            browser.close()
    finally:
        vite_proc.terminate()
        server.should_exit = True
        server_thread.join(timeout=2.0)
        print("[SHUTDOWN] Servers closed gracefully.")


if __name__ == "__main__":
    run_ui7_browser_verification()
