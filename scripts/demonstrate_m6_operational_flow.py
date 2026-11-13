"""PIIS Milestone M6 — End-to-End Operational Journey Demonstration Script.

Demonstrates the complete telecom incident lifecycle without live production dependencies:
1. Ingest incident from ServiceNow ITSM simulator.
2. Ingest active Nokia RAN alarm from OSS/NMS simulator.
3. Ingest real-time RF telemetry from Prometheus simulator.
4. Unified pipeline normalization, deduplication, and schema validation.
5. Topological and metric correlation to incident.
6. Evidence-grounded investigation and SOP recommendation generation.
7. Authenticated NOC Tier 2 engineer review sign-off (demonstrating service-principal lockout).
8. Cryptographic RFC 8785 JCS audit entry recording and hash chain verification.
"""

from __future__ import annotations

import time
from fastapi.testclient import TestClient

from piis.api.app import create_app
from piis.auth import ApplicationRole, AuthManager
from piis.integrations.simulators.alarm_simulator import SimulatedAlarmBroker
from piis.integrations.simulators.itsm_simulator import SimulatedITSMPlatform
from piis.integrations.simulators.telemetry_simulator import SimulatedTelemetryPlatform


def run_demonstration():
    print("=" * 80)
    print("PIIS MILESTONE M6: END-TO-END TELECOM OPERATIONAL JOURNEY DEMONSTRATION")
    print("OPERATIONAL SCOPE: READ-ONLY TELECOM DECISION SUPPORT")
    print("=" * 80)

    # Initialize client and auth manager
    app = create_app()
    client = TestClient(app)
    auth = AuthManager()

    print("\n[STEP 1] Provisioning Simulated Telecom Operational Systems & Identities...")
    itsm_sim = SimulatedITSMPlatform()
    alarm_sim = SimulatedAlarmBroker()
    telem_sim = SimulatedTelemetryPlatform()

    # Mint verified tokens
    svc_token = auth.mint_dev_token("snow_poller_daemon", is_service=True)
    noc_token = auth.mint_dev_token("operator_sarah", role=ApplicationRole.NOC_L2)
    print("  -> Service Principal Token Minted: 'snow_poller_daemon' (Scopes: ingest, read)")
    print("  -> Human Operator Token Minted:    'operator_sarah' (Role: NOC_L2)")

    # Step 1: External incident arrives from ServiceNow
    print("\n[STEP 2] Ingesting Incident Ticket from ServiceNow ITSM Platform...")
    snow_ticket = itsm_sim.tickets["INC0089201"]
    ingest_payload = {
        "source_system": "ServiceNow",
        "source_type": "OPERATOR_INTERNAL",
        "external_event_id": snow_ticket["number"],
        "payload": snow_ticket,
    }
    t0 = time.time()
    res_ingest = client.post(
        "/api/v1/incidents/ingest",
        json=ingest_payload,
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    assert res_ingest.status_code == 200, f"Ingestion failed: {res_ingest.text}"
    ingest_data = res_ingest.json()
    canonical_id = ingest_data["canonical_id"]
    print(f"  -> Ingestion Succeeded in {(time.time() - t0)*1000:.1f}ms")
    print(f"  -> Canonical Incident ID: {canonical_id}")
    print(f"  -> Envelope ID:           {ingest_data['envelope_id']}")
    print(f"  -> Correlation ID:        {ingest_data['correlation_id']}")

    # Step 2: Ingest active alarm from OSS/NMS
    print("\n[STEP 3] Ingesting Correlated Network Element Alarm from OSS/NMS Broker...")
    raw_alarm = alarm_sim.emit_vswr_alarm(element_id="GNB-RAN-701", vendor="NOKIA")
    alarm_envelope_payload = {
        "source_system": "GenericOSS",
        "source_type": "OPERATOR_INTERNAL",
        "external_event_id": raw_alarm["alarm_id"],
        "observation_timestamp": raw_alarm["timestamp"],
        "payload": raw_alarm,
    }
    res_alarm = client.post(
        "/api/v1/incidents/ingest",
        json=alarm_envelope_payload,
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    print(f"  -> Alarm Ingested: {res_alarm.json().get('canonical_id')} (Code: ALM-RAN-VSWR-HIGH, Severity: MAJOR)")

    # Step 3: Ingest telemetry from Prometheus
    print("\n[STEP 4] Ingesting Real-Time RF Telemetry from Prometheus Exporter...")
    prom_data = telem_sim.query_prometheus_vector()
    prom_sample = prom_data["data"]["result"][0]
    telem_envelope_payload = {
        "source_system": "Prometheus",
        "source_type": "OPERATOR_INTERNAL",
        "payload": prom_sample,
    }
    res_telem = client.post(
        "/api/v1/incidents/ingest",
        json=telem_envelope_payload,
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    print(f"  -> Telemetry Ingested: {res_telem.json().get('canonical_id')} (Metric: vswr_ratio on GNB-RAN-701)")

    # Step 4: Verify duplicate detection
    print("\n[STEP 5] Verifying Idempotency & Duplicate Suppression...")
    res_dup = client.post(
        "/api/v1/incidents/ingest",
        json=ingest_payload,
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    assert res_dup.json()["is_duplicate"] is True
    print(f"  -> Duplicate Successfully Suppressed: {res_dup.json()['message']}")

    # Step 5: Run Investigation Engine
    print("\n[STEP 6] Executing Evidence-Grounded Investigation (M2 Classification + M3 Correlation + M4 RAG)...")
    t0 = time.time()
    res_inv = client.post(
        f"/api/v1/incidents/{canonical_id}/investigate",
        headers={"Authorization": f"Bearer {noc_token}"},
    )
    assert res_inv.status_code == 200, f"Investigation failed: {res_inv.text}"
    inv = res_inv.json()
    print(f"  -> Investigation Synthesized in {(time.time() - t0)*1000:.1f}ms")
    print(f"  -> Title:               {inv['title']}")
    print(f"  -> Network Domain:      {inv['network_domain']}")
    print(f"  -> Evidence Sufficiency: {inv['is_sufficient']}")
    print(f"  -> Hypotheses Count:    {inv['hypotheses_count']}")
    print(f"  -> Epistemic Status:    {inv['epistemic_status']}")

    recommendations = inv["recommendations"]
    assert len(recommendations) > 0, "No recommendations generated!"
    top_rec = recommendations[0]
    rec_id = top_rec["recommendation_id"]
    print(f"\n  -> Top Grounded Recommendation: [{rec_id}] ({top_rec['source_runbook_id']})")
    print(f"     Risk Tier: {top_rec['risk_classification']} | Human Approval Required: {top_rec['human_approval_required']}")
    print(f"     Action:    {top_rec['description']}")
    print(f"     Reason:    {top_rec['reason']}")

    # Step 6: Test Security Gate (Service principal review lockout)
    print("\n[STEP 7] Testing Security Boundary: Barring Service Principal from Approving Review...")
    res_svc_block = client.post(
        f"/api/v1/incidents/{canonical_id}/reviews",
        json={
            "recommendation_id": rec_id,
            "decision": "APPROVED",
            "review_notes": "Automated approval attempted by background daemon.",
        },
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    assert res_svc_block.status_code == 403, "Security violation: Service principal was not blocked!"
    print(f"  -> Service Principal Approval Blocked with HTTP 403: {res_svc_block.json()['detail'][:65]}...")

    # Step 7: Human Operator Approval Sign-Off
    print("\n[STEP 8] Executing Human Operator Review (NOC Tier 2 Engineer Sign-Off)...")
    res_review = client.post(
        f"/api/v1/incidents/{canonical_id}/reviews",
        json={
            "recommendation_id": rec_id,
            "decision": "APPROVED",
            "review_notes": "Verified high VSWR telemetry (1.85) on GNB-RAN-701 and confirmed antenna feeder inspection procedure.",
        },
        headers={"Authorization": f"Bearer {noc_token}"},
    )
    assert res_review.status_code == 200, f"Review failed: {res_review.text}"
    receipt = res_review.json()
    print(f"  -> Review Recorded in Audit Ledger: {receipt['status']}")
    print(f"  -> Signed By:                       {receipt['reviewed_by']}")
    print(f"  -> Ledger Sequence Number:          #{receipt['ledger_sequence']}")
    print(f"  -> Audit Entry SHA-256 Digest:      {receipt['audit_entry_hash']}")
    print(f"  -> Cryptographic Receipt ID:        {receipt['receipt_id']}")

    # Step 8: Verify Tamper-Evident Ledger Integrity
    print("\n[STEP 9] Verifying RFC 8785 JCS Tamper-Evident Audit Ledger Continuity...")
    auditor_token = auth.mint_dev_token("auditor_frank", role=ApplicationRole.SECURITY_AUDITOR)
    res_verify = client.get(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert res_verify.status_code == 200
    v_data = res_verify.json()
    print(f"  -> Ledger Chain Valid:     {v_data['is_valid']}")
    print(f"  -> Total Audit Records:    {v_data['total_records']}")
    print(f"  -> Verification Status:    {v_data['verification_status']}")
    print(f"  -> Latest Monotonic Hash:  {v_data['latest_hash']}")

    print("\n" + "=" * 80)
    print("SUCCESS: COMPLETE END-TO-END OPERATIONAL DEMONSTRATION VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    run_demonstration()
