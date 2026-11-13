"""Anchor Immutability, Fork Prevention & Final Integrity Closure Tests for Milestone UI-5.1.4.

Verifies:
Task 1: Anchor Immutability & Fork Prevention (10 Required Tests):
  1. test_record_checkpoint_same_sequence_same_digest_idempotent_success
  2. test_record_checkpoint_same_sequence_different_digest_rejected_as_fork
  3. test_record_checkpoint_lower_sequence_different_digest_rejected_as_monotonic_violation
  4. test_record_checkpoint_higher_sequence_valid_transition_accepted
  5. test_record_checkpoint_higher_sequence_invalid_transition_gap_rejected
  6. test_anchor_persisted_then_caller_exception_compensating_rollback_preserves_anchor
  7. test_same_process_retry_after_post_persistence_exception_fails_closed
  8. test_fresh_process_restart_after_post_persistence_exception_fails_closed
  9. test_direct_overwrite_original_anchor_digest_after_failed_tx_rejected
  10. test_failed_attempt_and_retry_produce_zero_receipts

Task 3: Evidence Freshness & Clock-Skew Rejection (8 Required Tests):
  1. test_freshness_valid_recent_investigation_succeeds
  2. test_freshness_exactly_at_freshness_boundary_succeeds
  3. test_freshness_just_beyond_freshness_boundary_fails_stale
  4. test_freshness_future_within_allowed_skew_succeeds
  5. test_freshness_future_beyond_allowed_skew_fails
  6. test_freshness_naive_datetime_rejected
  7. test_freshness_non_utc_timezone_normalized_correctly
  8. test_freshness_missing_timestamp_rejected
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from piis.api.app import app
from piis.api.routers.incidents import (
    CLOCK_SKEW_TOLERANCE_SECONDS,
    EVIDENCE_MAX_AGE_SECONDS,
    get_pipeline,
    get_workflow,
)
from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
    LedgerRollbackDetectedError,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    EvidenceSufficiencyReport,
    InvestigationContext,
    RecommendationRisk,
)
from piis.pipeline.unified import UnifiedIngestionPipeline
from piis.provenance import ProvenanceRecord, SourceType


@pytest.fixture
def isolated_workflow_env(tmp_path: Path):
    """Setup isolated workflow with real tempfile JSONL ledger and local checkpoint anchor."""
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "ui5_1_4_ledger.jsonl"
    anchor_path = tmp_path / "ui5_1_4_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    workflow = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-4-secret-key-32bytes!",
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
    rec_id: str = "REC-UI514-001",
    incident_id: str = "INC-UI514-100",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=f"Diagnostic action for {rec_id}",
        reason="Testing UI-5.1.4 anchor immutability and freshness bounds",
        supporting_evidence_ids=["EVID-RAN-514"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1: Feeder Sweep",
        expected_observation="VSWR reflection < 1.3",
        risk_classification=risk,
        human_approval_required=True,
    )


# ==============================================================================
# TASK 1: ANCHOR IMMUTABILITY & FORK PREVENTION (10 REQUIRED TESTS)
# ==============================================================================

def test_1_record_checkpoint_same_sequence_same_digest_idempotent_success(isolated_workflow_env):
    """1. Same sequence, same digest: idempotent success (no error, remains unchanged)."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="a" * 64,
        hmac_signature="sig-01",
        timestamp_utc="2026-11-04T04:00:00Z",
    )
    chk1 = anchor.get_latest_checkpoint()
    assert chk1["sequence_number"] == 1
    assert chk1["entry_sha256"] == "a" * 64

    # Idempotent re-recording with exact same digest succeeds
    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="a" * 64,
        hmac_signature="sig-01",
        timestamp_utc="2026-11-04T04:00:00Z",
    )
    chk2 = anchor.get_latest_checkpoint()
    assert chk2["sequence_number"] == 1
    assert chk2["entry_sha256"] == "a" * 64


def test_2_record_checkpoint_same_sequence_different_digest_rejected_as_fork(isolated_workflow_env):
    """2. Same sequence, different digest: rejected as checkpoint fork / tampering violation."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="a" * 64,
        hmac_signature="sig-01",
        timestamp_utc="2026-11-04T04:00:00Z",
    )

    with pytest.raises(LedgerRollbackDetectedError, match="External anchor fork detected"):
        anchor.record_checkpoint(
            audit_id="AUD-0001",
            sequence_number=1,
            entry_sha256="b" * 64,  # Differing hash at sequence 1
            hmac_signature="sig-01-tampered",
            timestamp_utc="2026-11-04T04:00:05Z",
        )

    # Digest remains original 'a'*64; never overwritten
    assert anchor.get_latest_checkpoint()["entry_sha256"] == "a" * 64


def test_3_record_checkpoint_lower_sequence_different_digest_rejected_as_monotonic_violation(isolated_workflow_env):
    """3. Lower sequence, different digest: rejected as monotonic rollback violation."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    anchor.record_checkpoint(
        audit_id="AUD-0005",
        sequence_number=5,
        entry_sha256="5" * 64,
        hmac_signature="sig-05",
        timestamp_utc="2026-11-04T04:00:00Z",
    )

    with pytest.raises(LedgerRollbackDetectedError, match="External anchor monotonic violation"):
        anchor.record_checkpoint(
            audit_id="AUD-0004",
            sequence_number=4,
            entry_sha256="4" * 64,
            hmac_signature="sig-04",
            timestamp_utc="2026-11-04T03:59:00Z",
        )

    assert anchor.get_latest_checkpoint()["sequence_number"] == 5


def test_4_record_checkpoint_higher_sequence_valid_transition_accepted(isolated_workflow_env):
    """4. Higher sequence with valid transition (sequence == existing + 1): accepted."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="1" * 64,
        hmac_signature="sig-01",
        timestamp_utc="2026-11-04T04:00:00Z",
    )
    # Valid transition to sequence 2
    anchor.record_checkpoint(
        audit_id="AUD-0002",
        sequence_number=2,
        entry_sha256="2" * 64,
        hmac_signature="sig-02",
        timestamp_utc="2026-11-04T04:01:00Z",
    )
    chk = anchor.get_latest_checkpoint()
    assert chk["sequence_number"] == 2
    assert chk["entry_sha256"] == "2" * 64


def test_5_record_checkpoint_higher_sequence_invalid_transition_gap_rejected(isolated_workflow_env):
    """5. Higher sequence with invalid transition (sequence gap > existing + 1): rejected."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    anchor.record_checkpoint(
        audit_id="AUD-0001",
        sequence_number=1,
        entry_sha256="1" * 64,
        hmac_signature="sig-01",
        timestamp_utc="2026-11-04T04:00:00Z",
    )

    # Attempt sequence 3 when anchor is at sequence 1 (skipping sequence 2)
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor sequence gap"):
        anchor.record_checkpoint(
            audit_id="AUD-0003",
            sequence_number=3,
            entry_sha256="3" * 64,
            hmac_signature="sig-03",
            timestamp_utc="2026-11-04T04:02:00Z",
        )

    assert anchor.get_latest_checkpoint()["sequence_number"] == 1


def test_6_anchor_persisted_then_caller_exception_compensating_rollback_preserves_anchor(isolated_workflow_env):
    """6. Anchor persisted, then caller exception:
    - Ledger truncated back to sequence 1.
    - Anchor remains at sequence 2 with original digest H1.
    - In-memory recommendation reverts to PENDING_REVIEW.
    - In-memory audit trail remains length 1.
    """
    wf: HumanApprovalWorkflow = isolated_workflow_env["workflow"]
    token = isolated_workflow_env["auth"].mint_dev_token("OP-UI514-01", role=ApplicationRole.NOC_L2)
    ledger_path: Path = isolated_workflow_env["ledger_path"]
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    rec = _create_rec("REC-T6-01", "INC-T6-01")
    wf.register_recommendation(rec, "INC-T6-01")

    # Baseline: sequence 1 in ledger and anchor
    assert len(ledger_path.read_text(encoding="utf-8").strip().splitlines()) == 1
    assert anchor.get_latest_checkpoint()["sequence_number"] == 1

    real_record_checkpoint = anchor.record_checkpoint

    def faulty_record_checkpoint(*args, **kwargs):
        real_record_checkpoint(*args, **kwargs)
        raise RuntimeError("Simulated post-persistence exception")

    anchor.record_checkpoint = faulty_record_checkpoint

    with pytest.raises(RuntimeError, match="Simulated post-persistence exception"):
        wf.approve_recommendation("REC-T6-01", token, "INC-T6-01", "Approve attempt 1")

    # Ledger truncated back to line 1
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    # Anchor holds sequence 2 with digest H1
    chk2 = anchor.get_latest_checkpoint()
    assert chk2["sequence_number"] == 2
    assert len(chk2["entry_sha256"]) == 64

    # In-memory recommendation reverted
    assert wf.get_recommendation("REC-T6-01").approval_status == ApprovalStatus.PENDING_REVIEW
    assert len(wf.get_audit_trail()) == 1


def test_7_same_process_retry_after_post_persistence_exception_fails_closed(isolated_workflow_env):
    """7. Same-process retry after post-persistence exception:
    The retry attempts sequence 2 with digest H2. Anchor has sequence 2 with H1.
    MUST fail closed with LedgerRollbackDetectedError ('External anchor fork detected').
    """
    wf: HumanApprovalWorkflow = isolated_workflow_env["workflow"]
    token = isolated_workflow_env["auth"].mint_dev_token("OP-UI514-02", role=ApplicationRole.NOC_L2)
    ledger_path: Path = isolated_workflow_env["ledger_path"]
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    rec = _create_rec("REC-T7-01", "INC-T7-01")
    wf.register_recommendation(rec, "INC-T7-01")

    real_record_checkpoint = anchor.record_checkpoint

    def faulty_record_checkpoint(*args, **kwargs):
        real_record_checkpoint(*args, **kwargs)
        raise RuntimeError("Transient post-persistence error")

    anchor.record_checkpoint = faulty_record_checkpoint

    with pytest.raises(RuntimeError, match="Transient post-persistence error"):
        wf.approve_recommendation("REC-T7-01", token, "INC-T7-01", "Attempt 1")

    anchor.record_checkpoint = real_record_checkpoint
    original_h1 = anchor.get_latest_checkpoint()["entry_sha256"]

    # Retry in same process: attempt to approve again
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor fork detected"):
        wf.approve_recommendation("REC-T7-01", token, "INC-T7-01", "Retry attempt 2")

    # Ledger remains at sequence 1 (compensating rollback excised retry entry)
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    # Anchor remains at sequence 2 with original H1 (NEVER overwritten or erased!)
    assert anchor.get_latest_checkpoint()["sequence_number"] == 2
    assert anchor.get_latest_checkpoint()["entry_sha256"] == original_h1

    # Recommendation remains PENDING_REVIEW
    assert wf.get_recommendation("REC-T7-01").approval_status == ApprovalStatus.PENDING_REVIEW


def test_8_fresh_process_restart_after_post_persistence_exception_fails_closed(isolated_workflow_env):
    """8. Fresh-process restart after post-persistence exception fails closed with CRITICAL ROLLBACK."""
    wf: HumanApprovalWorkflow = isolated_workflow_env["workflow"]
    token = isolated_workflow_env["auth"].mint_dev_token("OP-UI514-03", role=ApplicationRole.NOC_L2)
    ledger_path: Path = isolated_workflow_env["ledger_path"]
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    rec = _create_rec("REC-T8-01", "INC-T8-01")
    wf.register_recommendation(rec, "INC-T8-01")

    real_record_checkpoint = anchor.record_checkpoint

    def faulty_record_checkpoint(*args, **kwargs):
        real_record_checkpoint(*args, **kwargs)
        raise RuntimeError("Post-persistence fault")

    anchor.record_checkpoint = faulty_record_checkpoint

    with pytest.raises(RuntimeError):
        wf.approve_recommendation("REC-T8-01", token, "INC-T8-01", "Crash simulation")

    # Restart fresh workflow from disk
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-4-secret-key-32bytes!",
        verifier=isolated_workflow_env["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK"):
        restarted_wf.load_from_ledger()


def test_9_direct_overwrite_original_anchor_digest_after_failed_tx_rejected(isolated_workflow_env):
    """9. Attempt to overwrite the original anchor digest directly after a failed transaction is rejected."""
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    # Sequence 1 recorded
    anchor.record_checkpoint("AUD-0001", 1, "h1" * 32, "sig1", "2026-11-04T04:00:00Z")
    # Sequence 2 recorded (H2_original)
    anchor.record_checkpoint("AUD-0002", 2, "h2_original" * 5 + "1234", "sig2", "2026-11-04T04:01:00Z")

    # Attempt to overwrite sequence 2 with conflicting digest
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor fork detected"):
        anchor.record_checkpoint(
            "AUD-0002",
            2,
            "h2_conflicting" * 4 + "12345678",
            "sig2_bad",
            "2026-11-04T04:02:00Z",
        )

    # Value is unchanged
    assert anchor.get_latest_checkpoint()["entry_sha256"] == "h2_original" * 5 + "1234"


def test_10_failed_attempt_and_retry_produce_zero_receipts(isolated_workflow_env):
    """10. Verify that failed attempt and failed retry produce NO receipts to caller."""
    wf: HumanApprovalWorkflow = isolated_workflow_env["workflow"]
    token = isolated_workflow_env["auth"].mint_dev_token("OP-UI514-04", role=ApplicationRole.NOC_L2)
    anchor: FileBasedCheckpointAnchor = isolated_workflow_env["anchor"]

    rec = _create_rec("REC-T10-01", "INC-T10-01")
    wf.register_recommendation(rec, "INC-T10-01")

    # Injected post-persistence fault
    real_record = anchor.record_checkpoint

    def post_err(*args, **kwargs):
        real_record(*args, **kwargs)
        raise RuntimeError("Post-persistence fault")

    anchor.record_checkpoint = post_err

    # Attempt 1: raises exception; no return value / receipt
    with pytest.raises(RuntimeError):
        wf.approve_recommendation("REC-T10-01", token, "INC-T10-01", "Notes")

    anchor.record_checkpoint = real_record

    # Attempt 2 (retry): raises LedgerRollbackDetectedError; no receipt
    with pytest.raises(LedgerRollbackDetectedError):
        wf.approve_recommendation("REC-T10-01", token, "INC-T10-01", "Retry notes")

    # Recommendation was NEVER approved
    current_rec = wf.get_recommendation("REC-T10-01")
    assert current_rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert current_rec.reviewed_by is None
    assert current_rec.review_timestamp is None


# ==============================================================================
# TASK 3: EVIDENCE FRESHNESS & CLOCK-SKEW REJECTION (8 REQUIRED TESTS)
# ==============================================================================

@pytest.fixture
def freshness_api_env(tmp_path: Path):
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "freshness_ledger.jsonl"
    anchor_path = tmp_path / "freshness_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    wf = HumanApprovalWorkflow(
        signing_key=b"piis-freshness-test-key-32bytes!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    pipeline = UnifiedIngestionPipeline()

    app.dependency_overrides[get_workflow] = lambda: wf
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    client = TestClient(app)
    operator_token = auth_mgr.mint_dev_token("OP-FRESH-01", role=ApplicationRole.NOC_L2)
    headers = {"Authorization": f"Bearer {operator_token}"}

    yield {
        "client": client,
        "headers": headers,
        "workflow": wf,
        "pipeline": pipeline,
    }

    app.dependency_overrides.clear()


def test_freshness_1_valid_recent_investigation_succeeds(freshness_api_env):
    """1. Valid recent investigation (e.g. 10s old) succeeds."""
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F1", "INC-F1")
    wf.register_recommendation(rec, "INC-F1")

    now = datetime.now(timezone.utc)
    ts = (now - timedelta(seconds=10)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F1"] = InvestigationContext(
            incident_id="INC-F1",
            title="Valid Investigation",
            network_domain="RAN",
            created_at=ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F1"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    res = client.post("/api/v1/incidents/INC-F1/reviews", json={"recommendation_id": "REC-F1", "decision": "APPROVED", "review_notes": "Valid recent"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["decision"] == "APPROVED"


def test_freshness_2_exactly_at_freshness_boundary_succeeds(freshness_api_env):
    """2. Investigation timestamp exactly at the freshness boundary (age == 3600.0s) succeeds."""
    from unittest.mock import patch
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F2", "INC-F2")
    wf.register_recommendation(rec, "INC-F2")

    fixed_now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    ts = (fixed_now - timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F2"] = InvestigationContext(
            incident_id="INC-F2",
            title="Boundary Investigation",
            network_domain="RAN",
            created_at=ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F2"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    with patch("piis.api.routers.incidents.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        res = client.post("/api/v1/incidents/INC-F2/reviews", json={"recommendation_id": "REC-F2", "decision": "APPROVED", "review_notes": "Exact boundary"}, headers=headers)

    assert res.status_code == 200
    assert res.json()["decision"] == "APPROVED"


def test_freshness_3_just_beyond_freshness_boundary_fails_stale(freshness_api_env):
    """3. Investigation timestamp just beyond freshness boundary (3601s old) fails with stale error."""
    from unittest.mock import patch
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F3", "INC-F3")
    wf.register_recommendation(rec, "INC-F3")

    fixed_now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    ts = (fixed_now - timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS + 1.0)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F3"] = InvestigationContext(
            incident_id="INC-F3",
            title="Stale Investigation",
            network_domain="RAN",
            created_at=ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F3"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    with patch("piis.api.routers.incidents.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        res = client.post("/api/v1/incidents/INC-F3/reviews", json={"recommendation_id": "REC-F3", "decision": "APPROVED", "review_notes": "Stale attempt"}, headers=headers)

    assert res.status_code == 400
    assert "Linked investigation evidence is stale" in res.json()["detail"]


def test_freshness_4_future_within_allowed_skew_succeeds(freshness_api_env):
    """4. Investigation timestamp slightly in the future within allowed skew (30s ahead, <= 60s) succeeds."""
    from unittest.mock import patch
    assert CLOCK_SKEW_TOLERANCE_SECONDS == 60.0
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F4", "INC-F4")
    wf.register_recommendation(rec, "INC-F4")

    fixed_now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    # 30 seconds into the future (within 60s skew tolerance)
    ts = (fixed_now + timedelta(seconds=30)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F4"] = InvestigationContext(
            incident_id="INC-F4",
            title="Skew Tolerated Investigation",
            network_domain="RAN",
            created_at=ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F4"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    with patch("piis.api.routers.incidents.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        res = client.post("/api/v1/incidents/INC-F4/reviews", json={"recommendation_id": "REC-F4", "decision": "APPROVED", "review_notes": "Minor skew tolerated"}, headers=headers)

    assert res.status_code == 200
    assert res.json()["decision"] == "APPROVED"


def test_freshness_5_future_beyond_allowed_skew_fails(freshness_api_env):
    """5. Investigation timestamp beyond allowed clock skew (120s ahead, > 60s) fails."""
    from unittest.mock import patch
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F5", "INC-F5")
    wf.register_recommendation(rec, "INC-F5")

    fixed_now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    # 120 seconds into the future (> 60s skew tolerance)
    ts = (fixed_now + timedelta(seconds=120)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F5"] = InvestigationContext(
            incident_id="INC-F5",
            title="Future Dated Investigation",
            network_domain="RAN",
            created_at=ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F5"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    with patch("piis.api.routers.incidents.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        res = client.post("/api/v1/incidents/INC-F5/reviews", json={"recommendation_id": "REC-F5", "decision": "APPROVED", "review_notes": "Future dated attempt"}, headers=headers)

    assert res.status_code == 400
    assert "future-dated beyond allowed clock skew" in res.json()["detail"]


def test_freshness_6_naive_datetime_rejected(freshness_api_env):
    """6. Naive datetime timestamp (lacking timezone information) is rejected."""
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F6", "INC-F6")
    wf.register_recommendation(rec, "INC-F6")

    # Timezone-naive ISO format: e.g. "2026-11-04T04:00:00"
    naive_ts = "2026-11-04T04:00:00"

    with pipeline._lock:
        pipeline._investigations["INC-F6"] = InvestigationContext(
            incident_id="INC-F6",
            title="Naive TS Investigation",
            network_domain="RAN",
            created_at=naive_ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F6"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    res = client.post("/api/v1/incidents/INC-F6/reviews", json={"recommendation_id": "REC-F6", "decision": "APPROVED", "review_notes": "Naive TS"}, headers=headers)
    assert res.status_code == 400
    assert "timezone-naive" in res.json()["detail"]


def test_freshness_7_non_utc_timezone_normalized_correctly(freshness_api_env):
    """7. Non-UTC timezone (e.g. Asia/Kolkata +05:30) is normalized accurately to UTC."""
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F7", "INC-F7")
    wf.register_recommendation(rec, "INC-F7")

    # Current time represented in +05:30 timezone offset
    ist = timezone(timedelta(hours=5, minutes=30))
    ist_ts = (datetime.now(ist) - timedelta(seconds=15)).isoformat()

    with pipeline._lock:
        pipeline._investigations["INC-F7"] = InvestigationContext(
            incident_id="INC-F7",
            title="Non-UTC TS Investigation",
            network_domain="RAN",
            created_at=ist_ts,
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F7"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    res = client.post("/api/v1/incidents/INC-F7/reviews", json={"recommendation_id": "REC-F7", "decision": "APPROVED", "review_notes": "IST TS"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["decision"] == "APPROVED"


def test_freshness_8_missing_timestamp_rejected(freshness_api_env):
    """8. Missing timestamp (empty or None) is rejected as missing mandatory created_at."""
    client: TestClient = freshness_api_env["client"]
    headers = freshness_api_env["headers"]
    wf: HumanApprovalWorkflow = freshness_api_env["workflow"]
    pipeline: UnifiedIngestionPipeline = freshness_api_env["pipeline"]

    rec = _create_rec("REC-F8", "INC-F8")
    wf.register_recommendation(rec, "INC-F8")

    with pipeline._lock:
        # Pydantic schema expects a string for created_at, so test with empty string ""
        pipeline._investigations["INC-F8"] = InvestigationContext(
            incident_id="INC-F8",
            title="Missing TS Investigation",
            network_domain="RAN",
            created_at="",  # Empty timestamp
            provenance=ProvenanceRecord(source_type=SourceType.OPERATOR_INTERNAL, source_dataset="live-telem", source_record_id="F8"),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(is_sufficient=True, has_contradictions=False, has_missing_evidence=False, missing_evidence_details=[]),
        )

    res = client.post("/api/v1/incidents/INC-F8/reviews", json={"recommendation_id": "REC-F8", "decision": "APPROVED", "review_notes": "Missing TS"}, headers=headers)
    assert res.status_code == 400
    assert "missing mandatory created_at timestamp" in res.json()["detail"]
