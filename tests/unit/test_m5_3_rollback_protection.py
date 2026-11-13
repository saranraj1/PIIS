"""Unit and adversarial tests for M5.3 Workstream 4: External Monotonic Rollback Protection.

Validates:
1. Full snapshot rollback detection: restoring an earlier valid ledger snapshot is detected.
2. Ledger truncation detection: removing the tail entries triggers LedgerRollbackDetectedError.
3. Ledger deletion and recreation: resetting ledger with new genesis is detected.
4. Checkpoint substitution / fork detection: altering head entry hash at same sequence is detected.
5. Monotonic sequence enforcement: anchor rejects non-monotonic sequence regressions.
6. Legitimate sequential advancement: anchor advances monotonically without error.
"""

import pytest

from piis.investigation.approval import (
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
    LedgerRollbackDetectedError,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_rec(rec_id: str) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description=f"Action procedure for {rec_id}",
        reason="Verification of hardware link",
        supporting_evidence_ids=["EVID-01"],
        source_runbook_id="SOP-TRANS-FIBER-001",
        source_section="Section 1",
        expected_observation="Nominal",
        risk_classification=RecommendationRisk.READ_ONLY_SAFE,
        human_approval_required=True,
    )


def test_full_snapshot_rollback_detected(tmp_path):
    """Verify that replacing the ledger with an earlier valid backup snapshot is detected."""
    ledger_path = tmp_path / "production_ledger.jsonl"
    anchor_path = tmp_path / "external_anchor.json"
    backup_path = tmp_path / "backup_snapshot.jsonl"

    anchor = FileBasedCheckpointAnchor(anchor_path)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)

    # 1. Create first 2 entries
    rec1 = _sample_rec("REC-ROLL-01")
    wf.register_recommendation(rec1, "INC-01")
    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-ROLL-01", tok, "INC-01", "Approved step 1")

    # Take backup of 2-entry snapshot
    backup_path.write_bytes(ledger_path.read_bytes())

    # 2. Add 2 more entries (now 4 total entries)
    rec2 = _sample_rec("REC-ROLL-02")
    wf.register_recommendation(rec2, "INC-02")
    wf.approve_recommendation("REC-ROLL-02", tok, "INC-02", "Approved step 2")

    assert len(wf.get_audit_trail()) == 4
    latest_cp = anchor.get_latest_checkpoint()
    assert latest_cp["sequence_number"] == 4

    # 3. Attacker restores the 2-entry backup snapshot!
    ledger_path.write_bytes(backup_path.read_bytes())

    # 4. Restarting process and restoring from rolled-back ledger must raise LedgerRollbackDetectedError
    wf_restart = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK: Ledger sequence 2 is older than external anchor sequence 4"):
        wf_restart.load_from_ledger()


def test_ledger_truncation_detected(tmp_path):
    """Verify that deleting tail entries from the ledger is detected by external anchor."""
    ledger_path = tmp_path / "trunc_ledger.jsonl"
    anchor_path = tmp_path / "trunc_anchor.json"

    anchor = FileBasedCheckpointAnchor(anchor_path)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)

    rec = _sample_rec("REC-TRUNC-01")
    wf.register_recommendation(rec, "INC-TRUNC-01")
    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-TRUNC-01", tok, "INC-TRUNC-01", "Approved")

    assert anchor.get_latest_checkpoint()["sequence_number"] == 2

    # Truncate line 2 (remove the approval entry)
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    ledger_path.write_text(lines[0] + "\n", encoding="utf-8")

    wf_restart = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK: Ledger sequence 1 is older than external anchor sequence 2"):
        wf_restart.load_from_ledger()


def test_ledger_deletion_and_recreation_detected(tmp_path):
    """Verify that deleting the ledger and creating a fresh 1-entry genesis is detected."""
    ledger_path = tmp_path / "deleted_ledger.jsonl"
    anchor_path = tmp_path / "deleted_anchor.json"

    anchor = FileBasedCheckpointAnchor(anchor_path)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)

    rec = _sample_rec("REC-DEL-01")
    wf.register_recommendation(rec, "INC-DEL-01")
    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-DEL-01", tok, "INC-DEL-01", "Approved")

    assert anchor.get_latest_checkpoint()["sequence_number"] == 2

    # Delete ledger completely
    ledger_path.unlink()

    # Empty ledger check
    wf_restart = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)
    # Target path does not exist -> load_from_ledger returns 0, verify_audit_trail will fail head check
    assert wf_restart.load_from_ledger() == 0

    valid, errors = wf_restart.verify_audit_trail()
    assert valid is True  # empty trail in memory

    # Now create new ledger starting at seq=1
    wf_new = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)
    rec_new = _sample_rec("REC-NEW-01")
    # Registration writes seq=1, but anchor is at seq=2 -> monotonic violation
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor monotonic violation"):
        wf_new.register_recommendation(rec_new, "INC-NEW-01")


def test_checkpoint_substitution_detected(tmp_path):
    """Verify that mutating the head entry at the same sequence number is detected."""
    ledger_path = tmp_path / "subst_ledger.jsonl"
    anchor_path = tmp_path / "subst_anchor.json"

    anchor = FileBasedCheckpointAnchor(anchor_path)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)

    rec = _sample_rec("REC-SUBST-01")
    wf.register_recommendation(rec, "INC-SUBST-01")

    # 1. Programmatic mutation without administrative override is blocked at write time (UI-5.1.4)
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor fork detected"):
        anchor.record_checkpoint(
            audit_id="AUD-0001",
            sequence_number=1,
            entry_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            hmac_signature="sig",
            timestamp_utc="2026-11-01T12:00:00Z",
        )

    # 2. External physical disk tampering / administrative override simulation
    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        hmac_signature="sig",
        timestamp_utc="2026-11-01T12:00:00Z",
        force_override=True,
    )

    wf_restart = HumanApprovalWorkflow(ledger_path=ledger_path, verifier=verifier, checkpoint_anchor=anchor)
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL TAMPERING / FORK: Ledger sequence matches anchor"):
        wf_restart.load_from_ledger()
