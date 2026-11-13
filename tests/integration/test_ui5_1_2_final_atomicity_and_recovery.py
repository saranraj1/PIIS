"""Final Atomicity, Evidence Recovery, and Durability Verification Tests for Milestone UI-5.1.2.

Verifies:
1. Checkpoint-anchor failure after durable ledger append:
   - Compensating disk truncation restores ledger to pre-write state.
   - Preserves state consistency across ledger, anchor, in-memory structures, recommendation state, and restart recovery.
   - Same-process retry succeeds without duplicate sequence numbers.
   - Catastrophic rollback failure fails closed with AuditTrailDiscontinuityError.
   - Head entry ahead of anchor detected as unanchored desynchronization on startup.
2. Restored recommendation evidence safety:
   - Restored recommendations present is_sufficient=False and has_missing_evidence=True in review queue.
   - Approval of restored recommendation without verified live evidence is blocked by backend (HTTP 400).
   - Rejection of restored recommendation is permitted and recorded in audit ledger.
   - Fresh investigation with sufficient evidence allows subsequent approval.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    AuditTrailDiscontinuityError,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
    LedgerRollbackDetectedError,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


@pytest.fixture
def atomicity_setup(tmp_path):
    """Setup isolated workflow with real tempfile JSONL ledger and checkpoint anchor."""
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "atomicity_audit_ledger.jsonl"
    anchor_path = tmp_path / "atomicity_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    workflow = HumanApprovalWorkflow(
        signing_key=b"piis-atomicity-audit-key-32bytes!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    return {
        "auth": auth_mgr,
        "verifier": verifier,
        "workflow": workflow,
        "ledger_path": ledger_path,
        "anchor": anchor,
        "anchor_path": anchor_path,
        "tmp_path": tmp_path,
    }


def _create_rec(
    rec_id: str = "REC-ATOM-001",
    incident_id: str = "INC-ATOM-100",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=f"Diagnostic action for {rec_id}",
        reason="Testing UI-5.1.2 atomicity and recovery guarantees",
        supporting_evidence_ids=["EVID-TELEM-001"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1: Feeder Sweep",
        expected_observation="VSWR reflection < 1.3",
        risk_classification=risk,
        human_approval_required=True,
    )


# ==============================================================================
# SECTION 1: CHECKPOINT-ANCHOR FAILURE AFTER DURABLE LEDGER APPEND
# ==============================================================================

def test_checkpoint_anchor_failure_triggers_compensating_disk_rollback(atomicity_setup):
    """Exact sequence: JSONL written -> flush/fsync succeed -> anchor fails -> compensating rollback.

    Proves all 5 dimensions remain 100% consistent:
    1. Disk ledger truncated back to pre-write state.
    2. Checkpoint anchor remains at pre-write sequence.
    3. In-memory audit trail length unchanged.
    4. In-memory recommendation status reverted to PENDING_REVIEW.
    5. Same-process retry succeeds without duplicate sequence numbers.
    6. Restart recovery loads pre-write state cleanly without divergence.
    """
    wf = atomicity_setup["workflow"]
    token = atomicity_setup["auth"].mint_dev_token("OP-ATOM-01", role=ApplicationRole.NOC_L2)
    ledger_path = atomicity_setup["ledger_path"]
    anchor = atomicity_setup["anchor"]

    rec = _create_rec("REC-FAIL-ANCHOR", "INC-FA-01")
    wf.register_recommendation(rec, "INC-FA-01")

    # Baseline: 1 SUBMITTED entry in ledger and anchor
    assert len(ledger_path.read_text(encoding="utf-8").strip().splitlines()) == 1
    chk = anchor.get_latest_checkpoint()
    assert chk is not None
    assert chk["sequence_number"] == 1

    # Injected anchor failure during approval
    with patch.object(
        anchor,
        "record_checkpoint",
        side_effect=IOError("Simulated external anchor storage failure"),
    ):
        with pytest.raises(IOError, match="Simulated external anchor storage failure"):
            wf.approve_recommendation(
                "REC-FAIL-ANCHOR",
                token,
                "INC-FA-01",
                "Approve under anchor failure",
            )

    # 1. Disk ledger: truncated back to 1 line (compensating rollback succeeded!)
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    # 2. Checkpoint anchor: still at sequence 1
    chk_after = anchor.get_latest_checkpoint()
    assert chk_after["sequence_number"] == 1

    # 3. In-memory audit trail: exactly 1 entry
    assert len(wf.get_audit_trail()) == 1

    # 4. In-memory recommendation: rolled back to PENDING_REVIEW
    current_rec = wf.get_recommendation("REC-FAIL-ANCHOR")
    assert current_rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert current_rec.reviewed_by is None

    # 5. Same-process retry: operator retries after anchor is restored -> succeeds cleanly
    retried = wf.approve_recommendation(
        "REC-FAIL-ANCHOR",
        token,
        "INC-FA-01",
        "Successful approval on retry",
    )
    assert retried.approval_status == ApprovalStatus.APPROVED
    assert len(wf.get_audit_trail()) == 2
    assert wf.get_audit_trail()[-1].sequence_number == 2

    # Ledger on disk now has exactly 2 lines with clean sequences (1, 2) - NO duplicate seq 2!
    lines_retry = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines_retry) == 2

    # 6. Restart recovery: fresh workflow loads cleanly
    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-atomicity-audit-key-32bytes!",
        verifier=atomicity_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    loaded = fresh_wf.load_from_ledger()
    assert loaded == 2
    restored_rec = fresh_wf.get_recommendation("REC-FAIL-ANCHOR")
    assert restored_rec.approval_status == ApprovalStatus.APPROVED
    assert restored_rec.reviewed_by == "OP-ATOM-01"


def test_catastrophic_rollback_failure_raises_fatal_atomicity_error(atomicity_setup):
    """If anchor fails AND disk rollback truncation also fails, raises AuditTrailDiscontinuityError."""
    wf = atomicity_setup["workflow"]
    token = atomicity_setup["auth"].mint_dev_token("OP-ATOM-02", role=ApplicationRole.NOC_L2)
    anchor = atomicity_setup["anchor"]

    rec = _create_rec("REC-CATASTROPHIC", "INC-CAT-01")
    wf.register_recommendation(rec, "INC-CAT-01")

    # Patch Path.open so append succeeds on 'a', but truncation fails on 'r+'
    real_open = Path.open

    def mock_open(self, mode="r", *args, **kwargs):
        if mode == "r+":
            raise OSError(30, "Read-only file system: cannot truncate")
        return real_open(self, mode, *args, **kwargs)

    with patch.object(anchor, "record_checkpoint", side_effect=IOError("Anchor failed")):
        with patch.object(Path, "open", mock_open):
            with pytest.raises(AuditTrailDiscontinuityError, match="FATAL ATOMICITY FAILURE"):
                wf.approve_recommendation(
                    "REC-CATASTROPHIC",
                    token,
                    "INC-CAT-01",
                    "Notes",
                )


def test_unanchored_ledger_head_detected_on_restart(atomicity_setup):
    """If ledger is ahead of external anchor on restart, load_from_ledger fails closed."""
    ledger_path = atomicity_setup["ledger_path"]
    anchor = atomicity_setup["anchor"]
    token = atomicity_setup["auth"].mint_dev_token("OP-ATOM-03", role=ApplicationRole.NOC_L2)
    wf = atomicity_setup["workflow"]

    rec = _create_rec("REC-DESYNC", "INC-DESYNC-01")
    wf.register_recommendation(rec, "INC-DESYNC-01")
    wf.approve_recommendation("REC-DESYNC", token, "INC-DESYNC-01", "Valid approval")

    # Overwrite anchor file directly with sequence 1 (simulating an unanchored second entry in the ledger)
    anchor_path = atomicity_setup["anchor_path"]
    anchor_path.write_text(
        '{"audit_id":"AUD-0001","entry_sha256":"' + ("1" * 64) + '","hmac_signature":"sig-01","sequence_number":1,"timestamp_utc":"2026-11-03T12:00:00Z"}\n',
        encoding="utf-8",
    )

    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-atomicity-audit-key-32bytes!",
        verifier=atomicity_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ANCHOR DESYNCHRONIZATION"):
        restarted_wf.load_from_ledger()


# ==============================================================================
# SECTION 2: RESTORED RECOMMENDATION EVIDENCE SAFETY
# ==============================================================================

def test_restored_recommendation_evidence_safety_lifecycle(tmp_path):
    """Trace approval endpoint behavior on restored recommendation without evidence."""
    from fastapi.testclient import TestClient
    from piis.api.app import app
    from piis.api.routers.incidents import get_pipeline, get_workflow
    from piis.pipeline.unified import UnifiedIngestionPipeline

    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "restored_test_ledger.jsonl"
    anchor_path = tmp_path / "restored_test_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    # 1. Pre-restart: register recommendation in ledger
    pre_wf = HumanApprovalWorkflow(
        signing_key=b"piis-restored-evidence-test-key32!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    rec = _create_rec("REC-RESTORED-01", "INC-RESTORED-10")
    pre_wf.register_recommendation(rec, "INC-RESTORED-10")

    # 2. Restart: new pipeline (empty cache) and workflow loading from ledger
    restarted_pipeline = UnifiedIngestionPipeline()
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-restored-evidence-test-key32!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    restarted_wf.load_from_ledger()

    app.dependency_overrides[get_pipeline] = lambda: restarted_pipeline
    app.dependency_overrides[get_workflow] = lambda: restarted_wf

    client = TestClient(app)
    operator_token = auth_mgr.mint_dev_token("OP-REVIEWER-01", role=ApplicationRole.NOC_L2)
    headers = {"Authorization": f"Bearer {operator_token}"}

    try:
        # A. Check review queue: restored item has is_sufficient=False, has_missing_evidence=True
        q_res = client.get("/api/v1/incidents/reviews/queue", headers=headers)
        assert q_res.status_code == 200
        items = q_res.json()["items"]
        assert len(items) == 1
        q_item = items[0]
        assert q_item["recommendation_id"] == "REC-RESTORED-01"
        assert q_item["is_sufficient"] is False
        assert q_item["has_missing_evidence"] is True
        assert q_item["source_runbook_id"] == "RESTORED_LEDGER"
        assert q_item["supporting_evidence_ids"] == []

        # B. Attempt approval: BLOCKED by backend because evidence is missing/unverified
        appr_res = client.post(
            "/api/v1/incidents/INC-RESTORED-10/reviews",
            json={
                "recommendation_id": "REC-RESTORED-01",
                "decision": "APPROVED",
                "review_notes": "Attempting approval without fresh evidence",
            },
            headers=headers,
        )
        assert appr_res.status_code == 400
        assert "Cannot approve recommendation" in appr_res.json()["detail"]
        assert "missing or unverified evidence" in appr_res.json()["detail"]

        # C. Rejection: PERMITTED because rejecting unverified/stale actions is safe
        rej_res = client.post(
            "/api/v1/incidents/INC-RESTORED-10/reviews",
            json={
                "recommendation_id": "REC-RESTORED-01",
                "decision": "REJECTED",
                "review_notes": "Stale recommendation rejected: live evidence unavailable after reboot",
            },
            headers=headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["decision"] == "REJECTED"
        assert rej_res.json()["status"] == "RECORDED_IN_AUDIT_CHAIN"

    finally:
        app.dependency_overrides.clear()


def test_fresh_evidence_investigation_allows_subsequent_approval(tmp_path):
    """When a fresh investigation establishes evidence sufficiency, approval is permitted."""
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from piis.api.app import app
    from piis.api.routers.incidents import get_pipeline, get_workflow
    from piis.investigation.schemas import EvidenceSufficiencyReport, InvestigationContext
    from piis.pipeline.unified import UnifiedIngestionPipeline
    from piis.provenance import ProvenanceRecord, SourceType

    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "fresh_evidence_ledger.jsonl"
    anchor_path = tmp_path / "fresh_evidence_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    wf = HumanApprovalWorkflow(
        signing_key=b"piis-fresh-evidence-test-key-32b!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    rec = _create_rec("REC-RESTORED-02", "INC-FRESH-20")
    wf.register_recommendation(rec, "INC-FRESH-20")

    # Restart scenario
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-fresh-evidence-test-key-32b!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    restarted_wf.load_from_ledger()

    pipeline = UnifiedIngestionPipeline()
    # Inject active incident and cached investigation with sufficient evidence
    with pipeline._lock:
        pipeline._incidents["INC-FRESH-20"] = {
            "incident_id": "INC-FRESH-20",
            "title": "Restored Incident with Re-verified Telemetry",
            "severity": "MAJOR",
            "network_domain": "RAN",
        }
        pipeline._investigations["INC-FRESH-20"] = InvestigationContext(
            incident_id="INC-FRESH-20",
            title="Restored Incident with Re-verified Telemetry",
            network_domain="RAN",
            created_at=datetime.now(timezone.utc).isoformat(),
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="live-telemetry",
                source_record_id="REC-FRESH-20",
            ),
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=True,
                has_contradictions=False,
                has_missing_evidence=False,
                missing_evidence_details=[],
            ),
        )

    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_workflow] = lambda: restarted_wf

    client = TestClient(app)
    operator_token = auth_mgr.mint_dev_token("OP-REVIEWER-02", role=ApplicationRole.NOC_L2)
    headers = {"Authorization": f"Bearer {operator_token}"}

    try:
        # Approval succeeds because fresh investigation verified evidence sufficiency
        appr_res = client.post(
            "/api/v1/incidents/INC-FRESH-20/reviews",
            json={
                "recommendation_id": "REC-RESTORED-02",
                "decision": "APPROVED",
                "review_notes": "Re-verified via fresh telemetry sweep and SOP check",
            },
            headers=headers,
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["decision"] == "APPROVED"
        assert appr_res.json()["status"] == "RECORDED_IN_AUDIT_CHAIN"

    finally:
        app.dependency_overrides.clear()

