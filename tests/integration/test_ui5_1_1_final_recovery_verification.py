"""Final Persistence Failure, Partial-Write, and Recovery Verification Tests for Milestone UI-5.1.1.

Verifies:
1. Partial-write failure testing (pre-write failure, truncated record, post-write caller drop, disk-full simulation, fsync).
2. Restart recovery behaviors across clean, truncated, tampered, and failed states.
3. Pending recommendation durability vs ephemeral telemetry evidence boundaries.
4. Concurrency deployment boundaries (single-process thread locking vs multi-process isolation requirements).
5. Integrity invariants (no false approvals, no silent record loss, fail-closed on corrupt/tampered records).
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from unittest.mock import patch
import pytest

from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    AuditTrailDiscontinuityError,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    IsolatedTestTokenVerifier,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


@pytest.fixture
def recovery_setup(tmp_path):
    """Setup isolated workflow with real tempfile JSONL ledger and checkpoint anchor."""
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "recovery_audit_ledger.jsonl"
    anchor_path = tmp_path / "recovery_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    workflow = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
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


def _create_test_rec(
    rec_id: str = "REC-REC-001",
    incident_id: str = "INC-REC-100",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=f"Diagnostic check for {rec_id}",
        reason="Testing UI-5.1.1 recovery guarantees",
        supporting_evidence_ids=["EVID-TELEM-001", "EVID-ALARM-002"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 3.1: Sweep Inspection",
        expected_observation="VSWR reflection < 1.3",
        risk_classification=risk,
        human_approval_required=True,
    )


# ==============================================================================
# SECTION 1: PARTIAL-WRITE FAILURE TESTING
# ==============================================================================

def test_case_1_pre_write_failure_rolls_back_cleanly(recovery_setup):
    """Failure before any bytes hit disk rolls back in-memory state; ledger remains clean."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-REC-01", role=ApplicationRole.NOC_L2)
    ledger_path = recovery_setup["ledger_path"]

    rec = _create_test_rec("REC-FAIL-PRE", "INC-PRE-01")
    wf.register_recommendation(rec, "INC-PRE-01")

    # Initial state: 1 valid SUBMITTED entry in ledger
    initial_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(initial_lines) == 1

    # Simulate pre-write I/O error (e.g. disk permission denied)
    with patch.object(Path, "open", side_effect=PermissionError("Simulated write permission denied")):
        with pytest.raises(PermissionError):
            wf.approve_recommendation("REC-FAIL-PRE", token, "INC-PRE-01", "Pre-write failure notes")

    # 1. In-memory recommendation rolls back to PENDING_REVIEW
    current_rec = wf.get_recommendation("REC-FAIL-PRE")
    assert current_rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert current_rec.reviewed_by is None
    assert current_rec.review_timestamp is None

    # 2. In-memory audit trail does NOT contain a phantom entry
    assert len(wf.get_audit_trail()) == 1
    assert wf.get_audit_trail()[-1].action == "SUBMITTED"

    # 3. Disk ledger remains exactly 1 clean line
    lines_after = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines_after) == 1

    # 4. Restart succeeds cleanly without errors
    new_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=recovery_setup["anchor"],
    )
    loaded = new_wf.load_from_ledger()
    assert loaded == 1
    valid, errors = new_wf.verify_audit_trail()
    assert valid is True
    assert errors == []


def test_case_2_partial_jsonl_write_fails_closed_on_restart(recovery_setup):
    """A partial/truncated JSON line on disk is detected as corrupted and fails closed on restart."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-REC-02", role=ApplicationRole.NOC_L2)
    ledger_path = recovery_setup["ledger_path"]

    rec = _create_test_rec("REC-FAIL-PARTIAL", "INC-PARTIAL-01")
    wf.register_recommendation(rec, "INC-PARTIAL-01")
    wf.approve_recommendation("REC-FAIL-PARTIAL", token, "INC-PARTIAL-01", "Complete valid approval")

    # Append half a JSON string to simulate a process crash midway through line write
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"audit_id": "AUD-0003", "sequence_number": 3, "schema_version": "2.0", "action": "APP')

    # Restarting PIIS and loading ledger MUST fail closed
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        restarted_wf.load_from_ledger()

    assert "corrupted or invalid ledger entry at line 3" in str(exc_info.value).lower()
    # In-memory state of restarted workflow remains unpolluted
    assert len(restarted_wf.get_audit_trail()) == 0


def test_case_3_post_write_caller_drop_preserves_terminal_state(recovery_setup):
    """If record is completely written to disk but caller drops, terminal state is preserved and retries are safe."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-REC-03", role=ApplicationRole.NOC_L2)
    ledger_path = recovery_setup["ledger_path"]

    rec = _create_test_rec("REC-POST-DROP", "INC-DROP-01")
    wf.register_recommendation(rec, "INC-DROP-01")

    # Normal approval writes entry cleanly
    updated = wf.approve_recommendation("REC-POST-DROP", token, "INC-DROP-01", "Approved before client drop")
    assert updated.approval_status == ApprovalStatus.APPROVED

    # Simulate process restart after client disconnected before receiving response
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=recovery_setup["anchor"],
    )
    loaded = restarted_wf.load_from_ledger()
    assert loaded == 2  # SUBMITTED + APPROVED

    # 1. State is terminal APPROVED
    restored_rec = restarted_wf.get_recommendation("REC-POST-DROP")
    assert restored_rec.approval_status == ApprovalStatus.APPROVED
    assert restored_rec.reviewed_by == "OP-REC-03"

    # 2. Subsequent retry by caller returns IllegalStateTransitionError (409 Conflict)
    with pytest.raises(IllegalStateTransitionError):
        restarted_wf.approve_recommendation(
            "REC-POST-DROP",
            token,
            "INC-DROP-01",
            "Duplicate retry by caller",
        )

    # 3. Decision receipt is retrievable via audit trail
    history = [e for e in restarted_wf.get_audit_trail() if e.recommendation_id == "REC-POST-DROP" and e.action == "APPROVED"]
    assert len(history) == 1
    receipt_entry = history[0]
    assert receipt_entry.operator_id == "OP-REC-03"
    assert len(receipt_entry.entry_sha256) == 64


def test_case_5_disk_full_enospc_simulation_rolls_back(recovery_setup):
    """Simulated disk full (ENOSPC) triggers clean rollback; retry succeeds when space is restored."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-REC-05", role=ApplicationRole.NOC_L2)

    rec = _create_test_rec("REC-ENOSPC-01", "INC-ENOSPC-01")
    wf.register_recommendation(rec, "INC-ENOSPC-01")

    # Simulate ENOSPC during file write using mock path object
    class EnospcFile:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def write(self, *args, **kwargs):
            raise OSError(28, "No space left on device")
        def flush(self):
            pass
        def fileno(self):
            return 1

    class EnospcPath:
        def open(self, *args, **kwargs):
            return EnospcFile()
        def exists(self):
            return True
        def stat(self):
            class Stat:
                st_size = 100
            return Stat()

    real_path = wf._ledger_path
    wf._ledger_path = EnospcPath()
    try:
        with pytest.raises(OSError) as exc_info:
            wf.approve_recommendation("REC-ENOSPC-01", token, "INC-ENOSPC-01", "Notes under full disk")
        assert exc_info.value.errno == 28
    finally:
        wf._ledger_path = real_path

    # Verify rollback: status is PENDING_REVIEW, not APPROVED
    assert wf.get_recommendation("REC-ENOSPC-01").approval_status == ApprovalStatus.PENDING_REVIEW
    # Audit trail did not append failed entry
    assert len(wf.get_audit_trail()) == 1

    # Retry without disk full error: succeeds cleanly
    success = wf.approve_recommendation("REC-ENOSPC-01", token, "INC-ENOSPC-01", "Notes after space cleared")
    assert success.approval_status == ApprovalStatus.APPROVED
    assert len(wf.get_audit_trail()) == 2


def test_case_6_fsync_execution_verified(recovery_setup):
    """Verify that file write invokes f.flush() and os.fsync() to guarantee hardware persistence."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-REC-06", role=ApplicationRole.NOC_L2)

    rec = _create_test_rec("REC-FSYNC-01", "INC-FSYNC-01")
    wf.register_recommendation(rec, "INC-FSYNC-01")

    with patch("os.fsync") as mock_fsync:
        wf.approve_recommendation("REC-FSYNC-01", token, "INC-FSYNC-01", "Notes for fsync check")
        assert mock_fsync.called
        assert mock_fsync.call_count >= 1


# ==============================================================================
# SECTION 2: PENDING RECOMMENDATION RECOVERY
# ==============================================================================

def test_pending_recommendation_durability_from_audit_ledger(recovery_setup):
    """Registered recommendations in PENDING_REVIEW are restored from SUBMITTED audit ledger entries."""
    wf = recovery_setup["workflow"]
    ledger_path = recovery_setup["ledger_path"]

    rec = _create_test_rec("REC-PENDING-DURABLE", "INC-PENDING-01")
    wf.register_recommendation(rec, "INC-PENDING-01")

    # Restart workflow
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=recovery_setup["anchor"],
    )
    loaded = restarted_wf.load_from_ledger()
    assert loaded == 1

    restored = restarted_wf.get_recommendation("REC-PENDING-DURABLE")
    assert restored is not None
    assert restored.approval_status == ApprovalStatus.PENDING_REVIEW
    assert restored.incident_id == "INC-PENDING-01"
    assert restarted_wf.get_recommendation_incident("REC-PENDING-DURABLE") == "INC-PENDING-01"

    # Restored pending item can now be approved
    token = recovery_setup["auth"].mint_dev_token("OP-REC-RESTORE", role=ApplicationRole.NOC_L2)
    approved = restarted_wf.approve_recommendation("REC-PENDING-DURABLE", token, "INC-PENDING-01", "Approved after restart")
    assert approved.approval_status == ApprovalStatus.APPROVED


def test_ephemeral_telemetry_limitation_disclosure(recovery_setup):
    """Audit ledger restores recommendation metadata and status, but raw telemetry evidence is ephemeral."""
    wf = recovery_setup["workflow"]
    ledger_path = recovery_setup["ledger_path"]

    rec = _create_test_rec("REC-EVID-LIMIT", "INC-LIMIT-01")
    wf.register_recommendation(rec, "INC-LIMIT-01")

    # Restart workflow from ledger
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
    )
    restarted_wf.load_from_ledger()

    restored = restarted_wf.get_recommendation("REC-EVID-LIMIT")
    assert restored is not None
    # Audit log stores content hash, not raw evidence items
    assert restored.source_runbook_id == "RESTORED_LEDGER"
    assert restored.supporting_evidence_ids == []
    # Binding check verifies content hash matches recorded hash
    assert restarted_wf.verify_recommendation_binding("REC-EVID-LIMIT") is True


# ==============================================================================
# SECTION 3: CONCURRENCY DEPLOYMENT BOUNDARY
# ==============================================================================

def test_single_process_thread_lock_protects_concurrent_threads(recovery_setup):
    """threading.RLock within a single process completely protects against state races and ledger corruption."""
    wf = recovery_setup["workflow"]
    token = recovery_setup["auth"].mint_dev_token("OP-THREAD", role=ApplicationRole.NOC_L2)

    rec = _create_test_rec("REC-THREAD-RACE", "INC-THREAD-01")
    wf.register_recommendation(rec, "INC-THREAD-01")

    def worker_action(worker_id):
        try:
            decision = "APPROVED" if worker_id % 2 == 0 else "REJECTED"
            if decision == "APPROVED":
                wf.approve_recommendation("REC-THREAD-RACE", token, "INC-THREAD-01", f"Worker {worker_id} approve")
            else:
                wf.reject_recommendation("REC-THREAD-RACE", token, "INC-THREAD-01", f"Worker {worker_id} reject")
            return "SUCCESS"
        except IllegalStateTransitionError:
            return "CONFLICT"

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker_action, range(8)))

    successes = [r for r in results if r == "SUCCESS"]
    conflicts = [r for r in results if r == "CONFLICT"]

    assert len(successes) == 1
    assert len(conflicts) == 7

    # Hash chain and HMACs on disk remain perfectly intact
    valid, errors = wf.verify_audit_trail()
    assert valid is True
    assert errors == []


def test_multi_workflow_instance_conflict_disclosure(recovery_setup):
    """Two independent HumanApprovalWorkflow instances sharing the same ledger without coordination break sequence."""
    ledger_path = recovery_setup["ledger_path"]
    # Workflow A
    wf_a = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
    )
    # Workflow B (simulating another process / instance)
    wf_b = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
    )

    rec1 = _create_test_rec("REC-MULTI-01", "INC-M1")
    rec2 = _create_test_rec("REC-MULTI-02", "INC-M2")

    wf_a.register_recommendation(rec1, "INC-M1")
    # Both A and B were unaware of each other: B registers rec2 with seq=1 as well
    wf_b.register_recommendation(rec2, "INC-M2")

    # When a fresh workflow reads this uncoordinated ledger, sequence discontinuity is detected
    verifier_wf = HumanApprovalWorkflow(
        signing_key=b"piis-recovery-audit-key-32bytes!",
        verifier=recovery_setup["verifier"],
        ledger_path=ledger_path,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        verifier_wf.load_from_ledger()

    assert "audit sequence discontinuity at line 2" in str(exc_info.value).lower()
    # Confirms PIIS architectural constraint: strictly single-process deployment model!
