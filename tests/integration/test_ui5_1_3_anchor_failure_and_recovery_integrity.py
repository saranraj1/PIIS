"""Checkpoint Anchor Failure Semantics & Recovery Integrity Verification Tests for Milestone UI-5.1.3.

Verifies:
1. Task 1: Anchor Persisted, Then Exception:
   - Anchor file write succeeds, but an exception occurs before record_checkpoint returns.
   - Compensating disk rollback excises the unanchored entry from the ledger.
   - Ledger remains at sequence N, anchor at sequence N+1.
   - Same-process retry triggers external anchor fork detection and fails closed without duplicate sequences.
   - Fresh-process restart detects ledger rollback against anchor and fails closed on boot.
2. Task 2: Four-State Anchor/Ledger Parity Matrix:
   - State 1: Matching valid ledger and anchor -> normal boot.
   - State 2: Ledger ahead of anchor -> fails closed with CRITICAL ANCHOR DESYNCHRONIZATION.
   - State 3: Anchor ahead of ledger -> fails closed with CRITICAL ROLLBACK.
   - State 4: Matching sequence but differing entry hash -> fails closed with CRITICAL TAMPERING / FORK.
   - State 5: Corrupted anchor file -> fails closed with CRITICAL ANCHOR INTEGRITY ERROR.
3. Task 3: Monotonic Anchor Non-Rollback Invariant:
   - Anchor rejects retroactive sequence rollback proposals with LedgerRollbackDetectedError.
4. Task 4: Fresh Evidence Binding Security Checks:
   - Attempt A: Cross-incident investigation reuse -> HTTP 400 ("Investigation incident mismatch").
   - Attempt B: Stale investigation (>3600s) -> HTTP 400 ("Linked investigation evidence is stale").
   - Attempt C: Insufficient or missing evidence -> HTTP 400 ("Evidence is insufficient").
   - Attempt D: Recommendation ID mismatch -> HTTP 400 ("Investigation recommendation mismatch").
   - Attempt E: Valid, fresh, sufficient evidence -> HTTP 200 (APPROVED with cryptographic receipt).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from piis.api.app import app
from piis.api.routers.incidents import get_pipeline, get_workflow
from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
    LedgerRollbackDetectedError,
    canonical_json_dumps,
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
def workflow_setup(tmp_path: Path):
    """Setup isolated workflow with real tempfile JSONL ledger and checkpoint anchor."""
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "ui5_1_3_audit_ledger.jsonl"
    anchor_path = tmp_path / "ui5_1_3_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    workflow = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
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
    rec_id: str = "REC-UI513-001",
    incident_id: str = "INC-UI513-100",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=f"Diagnostic action for {rec_id}",
        reason="Testing UI-5.1.3 checkpoint anchor failure and recovery semantics",
        supporting_evidence_ids=["EVID-RAN-001"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1: Feeder Sweep",
        expected_observation="VSWR reflection < 1.3",
        risk_classification=risk,
        human_approval_required=True,
    )


# ==============================================================================
# TASK 1: ANCHOR PERSISTED, THEN EXCEPTION
# ==============================================================================

def test_anchor_persisted_then_exception_compensating_rollback_and_fail_closed(workflow_setup):
    """Anchor file write succeeds, but an exception occurs before record_checkpoint returns.

    Verifies:
    1. Disk ledger compensating rollback excises the unanchored entry back to pre-write state.
    2. Ledger on disk remains at sequence 1, while anchor on disk is at sequence 2.
    3. In-memory audit trail remains at 1 entry and recommendation reverts to PENDING_REVIEW.
    4. Same-process retry triggers external anchor fork detection and fails closed.
    5. Fresh-process restart detects ledger rollback against anchor and fails closed.
    """
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    token = workflow_setup["auth"].mint_dev_token("OP-UI513-01", role=ApplicationRole.NOC_L2)
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-TASK1-01", "INC-T1-01")
    wf.register_recommendation(rec, "INC-T1-01")

    # Baseline: Sequence 1 (SUBMITTED) written to ledger and anchor
    assert len(ledger_path.read_text(encoding="utf-8").strip().splitlines()) == 1
    chk1 = anchor.get_latest_checkpoint()
    assert chk1 is not None
    assert chk1["sequence_number"] == 1

    # Save original record_checkpoint method
    real_record_checkpoint = anchor.record_checkpoint

    def faulty_record_checkpoint(*args, **kwargs):
        # 1. Execute the real persistent write to the anchor file
        real_record_checkpoint(*args, **kwargs)
        # 2. Simulate post-persistence failure (e.g. secondary acknowledgment or network socket crash)
        raise RuntimeError("Simulated post-persistence exception in record_checkpoint")

    anchor.record_checkpoint = faulty_record_checkpoint

    # Attempt approval under post-persistence exception
    with pytest.raises(RuntimeError, match="Simulated post-persistence exception"):
        wf.approve_recommendation(
            "REC-TASK1-01",
            token,
            "INC-T1-01",
            "Approval under simulated post-persistence failure",
        )

    # 1. Ledger on disk: Compensating rollback excised sequence 2! Only sequence 1 remains
    ledger_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger_lines) == 1, "Ledger was not cleanly truncated back to sequence 1"

    # 2. Anchor on disk: Persistence succeeded before the exception, so anchor is at sequence 2!
    chk2 = anchor.get_latest_checkpoint()
    assert chk2 is not None
    assert chk2["sequence_number"] == 2
    assert len(chk2["entry_sha256"]) == 64

    # 3. In-memory state: Audit trail is length 1; recommendation reverted to PENDING_REVIEW
    assert len(wf.get_audit_trail()) == 1
    current_rec = wf.get_recommendation("REC-TASK1-01")
    assert current_rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert current_rec.reviewed_by is None

    # Restore normal record_checkpoint for restart / retry testing
    anchor.record_checkpoint = real_record_checkpoint

    # 4. Fresh-process restart BEFORE retry: Booting from disk must fail closed immediately
    # Because ledger has seq 1 but anchor has seq 2, verify_ledger_head detects CRITICAL ROLLBACK!
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK"):
        restarted_wf.load_from_ledger()

    # 5. Same-process retry: Operator attempts to re-approve
    # The workflow attempts sequence 2. A new timestamp generates a different entry hash (H2).
    # The anchor on disk already has sequence 2 with H1.
    # The fork guard in record_checkpoint MUST raise LedgerRollbackDetectedError ("External anchor fork detected").
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor fork detected"):
        wf.approve_recommendation(
            "REC-TASK1-01",
            token,
            "INC-T1-01",
            "Same-process retry after transient post-persistence exception",
        )

    # Disk ledger remains strictly at sequence 1 (compensating rollback excised the retry line)
    ledger_lines_after_retry = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger_lines_after_retry) == 1

    # Anchor on disk remains intact at sequence 2 with H1 - never overwritten or erased!
    chk_retry = anchor.get_latest_checkpoint()
    assert chk_retry["sequence_number"] == 2
    assert chk_retry["entry_sha256"] == chk2["entry_sha256"]

    # In-memory recommendation remains rolled back to PENDING_REVIEW
    assert wf.get_recommendation("REC-TASK1-01").approval_status == ApprovalStatus.PENDING_REVIEW

    # In-memory audit trail remains at 1 entry
    assert len(wf.get_audit_trail()) == 1

    # 6. Fresh-process restart AFTER retry: Still fails closed because anchor is at seq 2 and ledger is at seq 1
    fresh_after_retry_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK"):
        fresh_after_retry_wf.load_from_ledger()


# ==============================================================================
# TASK 2: FOUR-STATE ANCHOR/LEDGER PARITY MATRIX
# ==============================================================================

def test_parity_matrix_state_1_matching_valid_ledger_and_anchor(workflow_setup):
    """State 1: Ledger and anchor match sequences and entry hashes perfectly -> boot succeeds."""
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    token = workflow_setup["auth"].mint_dev_token("OP-UI513-02", role=ApplicationRole.NOC_L2)
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-PARITY-01", "INC-PAR-01")
    wf.register_recommendation(rec, "INC-PAR-01")
    wf.approve_recommendation("REC-PARITY-01", token, "INC-PAR-01", "Valid approval")

    # Both ledger and anchor are at sequence 2
    latest_entry = wf.get_audit_trail()[-1]
    assert latest_entry.sequence_number == 2

    # verify_ledger_head succeeds
    valid, err = anchor.verify_ledger_head(latest_entry)
    assert valid is True
    assert err is None

    # Restart succeeds
    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    loaded = fresh_wf.load_from_ledger()
    assert loaded == 2


def test_parity_matrix_state_2_ledger_ahead_of_anchor(workflow_setup):
    """State 2: Ledger is ahead of anchor (e.g. unanchored appends) -> fails closed with CRITICAL ANCHOR DESYNCHRONIZATION."""
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    token = workflow_setup["auth"].mint_dev_token("OP-UI513-03", role=ApplicationRole.NOC_L2)
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor_path: Path = workflow_setup["anchor_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-PARITY-02", "INC-PAR-02")
    wf.register_recommendation(rec, "INC-PAR-02")
    wf.approve_recommendation("REC-PARITY-02", token, "INC-PAR-02", "Valid approval")

    # Manually overwrite anchor with sequence 1
    anchor_path.write_text(
        canonical_json_dumps({
            "audit_id": "AUD-0001",
            "sequence_number": 1,
            "entry_sha256": "a" * 64,
            "hmac_signature": "sig-01",
            "timestamp_utc": "2026-11-03T12:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    latest_entry = wf.get_audit_trail()[-1]
    assert latest_entry.sequence_number == 2

    valid, err = anchor.verify_ledger_head(latest_entry)
    assert valid is False
    assert "CRITICAL ANCHOR DESYNCHRONIZATION" in err

    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ANCHOR DESYNCHRONIZATION"):
        fresh_wf.load_from_ledger()


def test_parity_matrix_state_3_anchor_ahead_of_ledger(workflow_setup):
    """State 3: Anchor is ahead of ledger (e.g. restored older snapshot) -> fails closed with CRITICAL ROLLBACK."""
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor_path: Path = workflow_setup["anchor_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-PARITY-03", "INC-PAR-03")
    wf.register_recommendation(rec, "INC-PAR-03")

    # Ledger is at sequence 1. Forge anchor at sequence 5.
    anchor_path.write_text(
        canonical_json_dumps({
            "audit_id": "AUD-0005",
            "sequence_number": 5,
            "entry_sha256": "b" * 64,
            "hmac_signature": "sig-05",
            "timestamp_utc": "2026-11-03T12:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    latest_entry = wf.get_audit_trail()[-1]
    assert latest_entry.sequence_number == 1

    valid, err = anchor.verify_ledger_head(latest_entry)
    assert valid is False
    assert "CRITICAL ROLLBACK" in err

    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ROLLBACK"):
        fresh_wf.load_from_ledger()


def test_parity_matrix_state_4_matching_sequence_differing_hash(workflow_setup):
    """State 4: Matching sequence but differing SHA-256 hash -> fails closed with CRITICAL TAMPERING / FORK."""
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor_path: Path = workflow_setup["anchor_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-PARITY-04", "INC-PAR-04")
    wf.register_recommendation(rec, "INC-PAR-04")

    latest_entry = wf.get_audit_trail()[-1]
    assert latest_entry.sequence_number == 1

    # Overwrite anchor with same sequence 1, but completely different hash
    forged_hash = "f" * 64
    anchor_path.write_text(
        canonical_json_dumps({
            "audit_id": "AUD-0001",
            "sequence_number": 1,
            "entry_sha256": forged_hash,
            "hmac_signature": "sig-forged",
            "timestamp_utc": "2026-11-03T12:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    valid, err = anchor.verify_ledger_head(latest_entry)
    assert valid is False
    assert "CRITICAL TAMPERING / FORK" in err

    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL TAMPERING / FORK"):
        fresh_wf.load_from_ledger()


def test_parity_matrix_state_5_corrupted_anchor_file(workflow_setup):
    """State 5: Corrupted or unparseable anchor file -> fails closed with CRITICAL ANCHOR INTEGRITY ERROR."""
    wf: HumanApprovalWorkflow = workflow_setup["workflow"]
    ledger_path: Path = workflow_setup["ledger_path"]
    anchor_path: Path = workflow_setup["anchor_path"]
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    rec = _create_test_rec("REC-PARITY-05", "INC-PAR-05")
    wf.register_recommendation(rec, "INC-PAR-05")

    latest_entry = wf.get_audit_trail()[-1]

    # Corrupt anchor file with invalid JSON garbage
    anchor_path.write_text("<<<CORRUPT_NON_JSON_DATA_BUFFER>>>\n", encoding="utf-8")

    valid, err = anchor.verify_ledger_head(latest_entry)
    assert valid is False
    assert "CRITICAL ANCHOR INTEGRITY ERROR" in err

    fresh_wf = HumanApprovalWorkflow(
        signing_key=b"piis-ui5-1-3-test-secret-key-32b!",
        verifier=workflow_setup["verifier"],
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    with pytest.raises(LedgerRollbackDetectedError, match="CRITICAL ANCHOR INTEGRITY ERROR"):
        fresh_wf.load_from_ledger()


# ==============================================================================
# TASK 3: MONOTONIC ANCHOR NON-ROLLBACK INVARIANT
# ==============================================================================

def test_monotonic_anchor_rejects_backward_synchronization(workflow_setup):
    """External trust anchor cannot be synchronized backward under any circumstances."""
    anchor: FileBasedCheckpointAnchor = workflow_setup["anchor"]

    # Initial checkpoint at sequence 10
    anchor.record_checkpoint(
        audit_id="AUD-0010",
        sequence_number=10,
        entry_sha256="1" * 64,
        hmac_signature="sig-10",
        timestamp_utc="2026-11-03T12:00:00Z",
    )
    assert anchor.get_latest_checkpoint()["sequence_number"] == 10

    # Attempt to record sequence 9 (backward rollback proposal)
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor monotonic violation"):
        anchor.record_checkpoint(
            audit_id="AUD-0009",
            sequence_number=9,
            entry_sha256="9" * 64,
            hmac_signature="sig-09",
            timestamp_utc="2026-11-03T11:59:00Z",
        )

    # Anchor remains securely at sequence 10
    assert anchor.get_latest_checkpoint()["sequence_number"] == 10


# ==============================================================================
# TASK 4: FRESH EVIDENCE BINDING SECURITY CHECKS (FASTAPI ROUTER)
# ==============================================================================

@pytest.fixture
def api_test_env(tmp_path: Path):
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "api_test_ledger.jsonl"
    anchor_path = tmp_path / "api_test_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    wf = HumanApprovalWorkflow(
        signing_key=b"piis-evidence-binding-secret-key-32b!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    pipeline = UnifiedIngestionPipeline()

    app.dependency_overrides[get_workflow] = lambda: wf
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    client = TestClient(app)
    operator_token = auth_mgr.mint_dev_token("OP-REVIEWER-99", role=ApplicationRole.NOC_L2)
    headers = {"Authorization": f"Bearer {operator_token}"}

    yield {
        "client": client,
        "headers": headers,
        "workflow": wf,
        "pipeline": pipeline,
    }

    app.dependency_overrides.clear()


def test_evidence_binding_attempt_a_incident_id_mismatch(api_test_env):
    """Attempt A: Reusing active investigation from INC-MISMATCH-999 for INC-TARGET-100 fails closed."""
    client: TestClient = api_test_env["client"]
    headers = api_test_env["headers"]
    wf: HumanApprovalWorkflow = api_test_env["workflow"]
    pipeline: UnifiedIngestionPipeline = api_test_env["pipeline"]

    rec = _create_test_rec("REC-BIND-A", "INC-TARGET-100")
    wf.register_recommendation(rec, "INC-TARGET-100")

    # Cached investigation is bound to INC-MISMATCH-999 instead of INC-TARGET-100
    with pipeline._lock:
        pipeline._investigations["INC-TARGET-100"] = InvestigationContext(
            incident_id="INC-MISMATCH-999",  # Cross-incident reuse attack
            title="Mismatched Investigation Context",
            network_domain="RAN",
            created_at=datetime.now(timezone.utc).isoformat(),
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="test-telemetry",
                source_record_id="REC-A",
            ),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=True,
                has_contradictions=False,
                has_missing_evidence=False,
                missing_evidence_details=[],
            ),
        )

    res = client.post(
        "/api/v1/incidents/INC-TARGET-100/reviews",
        json={
            "recommendation_id": "REC-BIND-A",
            "decision": "APPROVED",
            "review_notes": "Attempting cross-incident evidence reuse",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "Investigation incident mismatch" in res.json()["detail"]


def test_evidence_binding_attempt_b_stale_investigation(api_test_env):
    """Attempt B: Reusing investigation evidence older than 3600 seconds fails closed."""
    client: TestClient = api_test_env["client"]
    headers = api_test_env["headers"]
    wf: HumanApprovalWorkflow = api_test_env["workflow"]
    pipeline: UnifiedIngestionPipeline = api_test_env["pipeline"]

    rec = _create_test_rec("REC-BIND-B", "INC-STALE-200")
    wf.register_recommendation(rec, "INC-STALE-200")

    stale_timestamp = (datetime.now(timezone.utc) - timedelta(seconds=3601)).isoformat()
    with pipeline._lock:
        pipeline._investigations["INC-STALE-200"] = InvestigationContext(
            incident_id="INC-STALE-200",
            title="Stale Investigation Context",
            network_domain="RAN",
            created_at=stale_timestamp,
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="test-telemetry",
                source_record_id="REC-B",
            ),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=True,
                has_contradictions=False,
                has_missing_evidence=False,
                missing_evidence_details=[],
            ),
        )

    res = client.post(
        "/api/v1/incidents/INC-STALE-200/reviews",
        json={
            "recommendation_id": "REC-BIND-B",
            "decision": "APPROVED",
            "review_notes": "Attempting approval with stale telemetry",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "Linked investigation evidence is stale" in res.json()["detail"]


def test_evidence_binding_attempt_c_insufficient_or_missing_evidence(api_test_env):
    """Attempt C: Approving recommendation with is_sufficient=False fails closed."""
    client: TestClient = api_test_env["client"]
    headers = api_test_env["headers"]
    wf: HumanApprovalWorkflow = api_test_env["workflow"]
    pipeline: UnifiedIngestionPipeline = api_test_env["pipeline"]

    rec = _create_test_rec("REC-BIND-C", "INC-INSUFF-300")
    wf.register_recommendation(rec, "INC-INSUFF-300")

    with pipeline._lock:
        pipeline._investigations["INC-INSUFF-300"] = InvestigationContext(
            incident_id="INC-INSUFF-300",
            title="Insufficient Evidence Context",
            network_domain="RAN",
            created_at=datetime.now(timezone.utc).isoformat(),
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="test-telemetry",
                source_record_id="REC-C",
            ),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=False,
                has_contradictions=False,
                has_missing_evidence=True,
                missing_evidence_details=["VSWR metric missing"],
            ),
        )

    res = client.post(
        "/api/v1/incidents/INC-INSUFF-300/reviews",
        json={
            "recommendation_id": "REC-BIND-C",
            "decision": "APPROVED",
            "review_notes": "Attempting approval without sufficient telemetry",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "Evidence is insufficient" in res.json()["detail"]


def test_evidence_binding_attempt_d_recommendation_id_mismatch(api_test_env):
    """Attempt D: Investigation does not contain requested recommendation -> fails closed."""
    client: TestClient = api_test_env["client"]
    headers = api_test_env["headers"]
    wf: HumanApprovalWorkflow = api_test_env["workflow"]
    pipeline: UnifiedIngestionPipeline = api_test_env["pipeline"]

    rec_target = _create_test_rec("REC-TARGET-01", "INC-REC-400")
    rec_other = _create_test_rec("REC-OTHER-99", "INC-REC-400")
    wf.register_recommendation(rec_target, "INC-REC-400")

    with pipeline._lock:
        pipeline._investigations["INC-REC-400"] = InvestigationContext(
            incident_id="INC-REC-400",
            title="Investigation without target recommendation",
            network_domain="RAN",
            created_at=datetime.now(timezone.utc).isoformat(),
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="test-telemetry",
                source_record_id="REC-D",
            ),
            recommendations=[rec_other],  # Only REC-OTHER-99 is in this investigation
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=True,
                has_contradictions=False,
                has_missing_evidence=False,
                missing_evidence_details=[],
            ),
        )

    res = client.post(
        "/api/v1/incidents/INC-REC-400/reviews",
        json={
            "recommendation_id": "REC-TARGET-01",
            "decision": "APPROVED",
            "review_notes": "Attempting approval for unlisted recommendation",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "Investigation recommendation mismatch" in res.json()["detail"]


def test_evidence_binding_attempt_e_valid_fresh_evidence_succeeds(api_test_env):
    """Attempt E: Fresh, sufficient investigation matching incident and recommendation -> succeeds with receipt."""
    client: TestClient = api_test_env["client"]
    headers = api_test_env["headers"]
    wf: HumanApprovalWorkflow = api_test_env["workflow"]
    pipeline: UnifiedIngestionPipeline = api_test_env["pipeline"]

    rec = _create_test_rec("REC-VALID-01", "INC-VALID-500")
    wf.register_recommendation(rec, "INC-VALID-500")

    with pipeline._lock:
        pipeline._investigations["INC-VALID-500"] = InvestigationContext(
            incident_id="INC-VALID-500",
            title="Valid Active Investigation Context",
            network_domain="RAN",
            created_at=datetime.now(timezone.utc).isoformat(),
            provenance=ProvenanceRecord(
                source_type=SourceType.OPERATOR_INTERNAL,
                source_dataset="live-telemetry",
                source_record_id="REC-VALID-500",
            ),
            recommendations=[rec],
            sufficiency_report=EvidenceSufficiencyReport(
                is_sufficient=True,
                has_contradictions=False,
                has_missing_evidence=False,
                missing_evidence_details=[],
            ),
        )

    res = client.post(
        "/api/v1/incidents/INC-VALID-500/reviews",
        json={
            "recommendation_id": "REC-VALID-01",
            "decision": "APPROVED",
            "review_notes": "Fresh, valid evidence verified by NOC_L2 operator",
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation_id"] == "REC-VALID-01"
    assert data["decision"] == "APPROVED"
    assert data["status"] == "RECORDED_IN_AUDIT_CHAIN"
    assert data["ledger_sequence"] == 2
    assert data["audit_entry_hash"] != "UNKNOWN_HASH"
    assert data["receipt_id"].startswith("RCPT-")

    # Verify audit trail contains the matching cryptographic receipt
    latest_entry = wf.get_audit_trail()[-1]
    assert latest_entry.sequence_number == 2
    assert latest_entry.audit_id == "AUD-0002"
    assert latest_entry.entry_sha256 == data["audit_entry_hash"]
    assert latest_entry.hmac_signature is not None
    assert latest_entry.action == "APPROVED"
