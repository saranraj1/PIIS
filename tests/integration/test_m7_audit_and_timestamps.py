"""Milestone M7-B & M7-C: Integration Verification for Audit Integrity, Storage & Timestamps.

Exercises:
1. Durable append-only audit records & restart recovery.
2. Hash-chain integrity & content tamper detection.
3. Record deletion detection.
4. Record reordering detection.
5. Monotonic checkpoint anchor rollback & truncation detection.
6. Concurrent multi-threaded approval writers.
7. Key provider abstraction (LocalDevKeyProvider vs ExternalKMSProvider fail-closed).
8. Trusted timestamp authority abstraction (LocalUtc, LocalDev simulated TSA, RFC 3161).
"""

from __future__ import annotations

import concurrent.futures
import json
import pytest

from piis.audit import (
    ExternalKMSProvider,
    LocalDevKeyProvider,
    LocalDevTimestampProvider,
    LocalUtcTimestampProvider,
    ProductionTrustViolationError,
    RFC3161TimestampProvider,
)
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


def _create_sample_rec(rec_id: str = "REC-M7-001", incident_id: str = "INC-M7-100") -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Reset optical transponder on CSR-99",
        reason="Bit error rate exceeds 1e-4",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-OPTICAL-001",
        source_section="Section 3: Optical Reset",
        expected_observation="Bit error rate drops below 1e-9",
        risk_classification=RecommendationRisk.READ_ONLY_SAFE,
        human_approval_required=True,
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )


def test_audit_durability_and_restart_recovery(tmp_path):
    """Test 1: Audit records persist to append-only JSONL and restore cleanly across restart."""
    ledger_file = tmp_path / "audit_ledger.jsonl"
    anchor_file = tmp_path / "checkpoint_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"0" * 32

    # Phase 1: Initialize workflow and record approvals
    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    rec1 = _create_sample_rec("REC-001", "INC-001")
    workflow.register_recommendation(rec1, "INC-001")
    tok = verifier.mint_token(operator_id="OP-NOC-1", role="NOC_TIER_2")
    workflow.approve_recommendation("REC-001", tok, "INC-001", notes="Verified optical health")

    rec2 = _create_sample_rec("REC-002", "INC-002")
    workflow.register_recommendation(rec2, "INC-002")
    workflow.reject_recommendation("REC-002", tok, "INC-002", reason="False alarm on feeder")

    assert len(workflow.get_audit_trail()) == 4  # 2 SUBMITTED + 2 DECISIONS
    is_valid, err = workflow.verify_audit_trail()
    assert is_valid, f"Verification failed: {err}"

    # Phase 2: Simulate process restart - re-instantiate from same ledger & anchor
    restarted_workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    loaded_count = restarted_workflow.load_from_ledger()
    assert loaded_count == 4
    assert len(restarted_workflow.get_audit_trail()) == 4
    is_valid_after_restart, err_restart = restarted_workflow.verify_audit_trail()
    assert is_valid_after_restart, f"Restart verification failed: {err_restart}"


def test_audit_hash_chain_tamper_detection(tmp_path):
    """Test 2: Modifying an audit entry on disk breaks the hash chain and is detected."""
    ledger_file = tmp_path / "tamper_ledger.jsonl"
    anchor_file = tmp_path / "tamper_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"1" * 32

    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    rec = _create_sample_rec("REC-TAMPER", "INC-TAMPER")
    workflow.register_recommendation(rec, "INC-TAMPER")
    tok = verifier.mint_token(operator_id="OP-HONEST", role="NOC_TIER_2")
    workflow.approve_recommendation("REC-TAMPER", tok, "INC-TAMPER", notes="Legitimate approval")

    # Read ledger lines and tamper with the second entry notes
    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    entry2 = json.loads(lines[1])
    entry2["notes"] = "MALICIOUS MUTATION: Injected unauthorized instruction"
    lines[1] = json.dumps(entry2)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reloading from disk must fail closed immediately on tamper detection
    tampered_workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        tampered_workflow.load_from_ledger()
    assert "Tampered record digest" in str(exc_info.value) or "discontinuity" in str(exc_info.value).lower()

    # In-memory verification must also catch in-memory tampering
    workflow._audit_trail[1].notes = "IN_MEMORY_TAMPER"
    is_valid, errs = workflow.verify_audit_trail()
    assert not is_valid
    err_msg = " ".join(errs).lower()
    assert "hash" in err_msg or "signature" in err_msg or "mismatch" in err_msg


def test_audit_record_deletion_detection(tmp_path):
    """Test 3: Deleting an intermediate record breaks the hash pointers and sequence order."""
    ledger_file = tmp_path / "deletion_ledger.jsonl"
    anchor_file = tmp_path / "deletion_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"2" * 32

    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    rec1 = _create_sample_rec("REC-DEL-1", "INC-1")
    rec2 = _create_sample_rec("REC-DEL-2", "INC-2")
    workflow.register_recommendation(rec1, "INC-1")
    workflow.register_recommendation(rec2, "INC-2")
    tok = verifier.mint_token(operator_id="OP-1", role="NOC_TIER_2")
    workflow.approve_recommendation("REC-DEL-1", tok, "INC-1")

    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    # Delete the intermediate registration record (index 1)
    tampered_lines = [lines[0], lines[2]]
    ledger_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")

    wf = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        wf.load_from_ledger()
    assert "discontinuity" in str(exc_info.value).lower() or "sequence" in str(exc_info.value).lower() or "broken" in str(exc_info.value).lower()


def test_audit_record_reordering_detection(tmp_path):
    """Test 4: Swapping / reordering audit entries is caught by sequence and hash pointer checks."""
    ledger_file = tmp_path / "reorder_ledger.jsonl"
    anchor_file = tmp_path / "reorder_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"3" * 32

    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    rec1 = _create_sample_rec("REC-ORD-1", "INC-1")
    rec2 = _create_sample_rec("REC-ORD-2", "INC-2")
    workflow.register_recommendation(rec1, "INC-1")
    workflow.register_recommendation(rec2, "INC-2")

    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    # Swap line 0 and line 1
    swapped = [lines[1], lines[0]]
    ledger_file.write_text("\n".join(swapped) + "\n", encoding="utf-8")

    wf = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        wf.load_from_ledger()
    assert "discontinuity" in str(exc_info.value).lower() or "sequence" in str(exc_info.value).lower() or "broken" in str(exc_info.value).lower()


def test_checkpoint_anchor_rollback_detection(tmp_path):
    """Test 5: Restoring an older ledger snapshot when checkpoint anchor has advanced is rejected."""
    ledger_file = tmp_path / "rollback_ledger.jsonl"
    anchor_file = tmp_path / "rollback_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"4" * 32

    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    rec1 = _create_sample_rec("REC-RB-1", "INC-1")
    workflow.register_recommendation(rec1, "INC-1")
    tok = verifier.mint_token(operator_id="OP-1", role="NOC_TIER_2")
    workflow.approve_recommendation("REC-RB-1", tok, "INC-1")

    # Save backup of ledger at sequence 2
    backup_lines = ledger_file.read_text(encoding="utf-8")

    # Add more decisions advancing anchor to sequence 4
    rec2 = _create_sample_rec("REC-RB-2", "INC-2")
    workflow.register_recommendation(rec2, "INC-2")
    workflow.reject_recommendation("REC-RB-2", tok, "INC-2", reason="Not justified")

    # Now restore older backup of ledger file (sequence 2) while anchor remains at sequence 4
    ledger_file.write_text(backup_lines, encoding="utf-8")

    wf_rollback = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )
    with pytest.raises(LedgerRollbackDetectedError) as exc_info:
        wf_rollback.load_from_ledger()
    assert "ROLLBACK" in str(exc_info.value)


def test_concurrent_writer_thread_safety(tmp_path):
    """Test 6: Multiple concurrent threads recording decisions cause zero sequence corruption or loss."""
    ledger_file = tmp_path / "concurrent_ledger.jsonl"
    anchor_file = tmp_path / "concurrent_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    key = b"5" * 32

    workflow = HumanApprovalWorkflow(
        signing_key=key,
        ledger_path=ledger_file,
        checkpoint_anchor=anchor,
        verifier=verifier,
    )

    num_threads = 6
    recs_per_thread = 2
    total_recs = num_threads * recs_per_thread

    # Register recommendations first
    for i in range(total_recs):
        workflow.register_recommendation(
            _create_sample_rec(f"REC-CONC-{i}", f"INC-CONC-{i}"),
            f"INC-CONC-{i}",
        )

    def worker_decision(start_idx: int):
        tok = verifier.mint_token(operator_id=f"OP-CONC-{start_idx}", role="NOC_TIER_2")
        for j in range(recs_per_thread):
            idx = start_idx * recs_per_thread + j
            workflow.approve_recommendation(f"REC-CONC-{idx}", tok, f"INC-CONC-{idx}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_decision, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Total entries: total_recs registrations + total_recs approvals
    trail = workflow.get_audit_trail()
    assert len(trail) == total_recs * 2

    # Verify all sequence numbers are strictly monotonic: 1..2*total_recs
    seqs = [e.sequence_number for e in trail]
    assert seqs == list(range(1, total_recs * 2 + 1))

    is_valid, err = workflow.verify_audit_trail()
    assert is_valid, f"Concurrent audit trail invalid: {err}"


def test_key_provider_abstraction_and_production_fail_closed():
    """Test 7: LocalDevKeyProvider warns in dev and fails closed in production; ExternalKMSProvider interface."""
    # 7a. LocalDevKeyProvider warns in development
    with pytest.warns(UserWarning, match="LocalDevKeyProvider in use: Not suitable for production"):
        dev_key_prov = LocalDevKeyProvider(environment="development")
    assert len(dev_key_prov.get_signing_key()) >= 32
    kid1 = dev_key_prov.get_key_id()
    kid2, _ = dev_key_prov.rotate_key()
    assert kid1 != kid2

    # 7b. LocalDevKeyProvider fails closed in production
    with pytest.raises(ProductionTrustViolationError, match="cannot be initialized in production"):
        LocalDevKeyProvider(environment="production")

    # 7c. ExternalKMSProvider rejects test ARN in production
    with pytest.raises(ProductionTrustViolationError, match="Invalid KMS Key ARN for production"):
        ExternalKMSProvider(key_arn="arn:aws:kms:test:key-123", environment="production")

    # 7d. ExternalKMSProvider accepts valid production ARN interface
    kms_prov = ExternalKMSProvider(
        key_arn="arn:aws:kms:us-east-1:123456789012:key/prod-audit-signing-key",
        environment="development",
    )
    assert kms_prov.get_key_id().startswith("kms-")
    assert len(kms_prov.get_signing_key()) == 32


def test_timestamp_authority_abstraction():
    """Test 8: Separation of LocalUtcTimestampProvider, LocalDevTimestampProvider, and RFC3161TimestampProvider."""
    sample_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # 8a. LocalUtcTimestampProvider provides standard ISO-8601 UTC timestamp with explicit unnotarized disclaimer
    utc_prov = LocalUtcTimestampProvider()
    token_utc = utc_prov.generate_timestamp_token(sample_hash)
    assert token_utc["tsa_type"] == "LOCAL_UTC_CLOCK"
    assert token_utc["is_cryptographic_tsa"] is False
    assert "Standard UTC timestamp" in token_utc["disclaimer"]
    assert utc_prov.verify_timestamp_token(token_utc, sample_hash)

    # 8b. LocalDevTimestampProvider generates HMAC-backed simulated token, fails in production
    dev_tsa = LocalDevTimestampProvider(environment="development")
    token_dev = dev_tsa.generate_timestamp_token(sample_hash)
    assert token_dev["tsa_type"] == "LOCAL_DEV_SIMULATED"
    assert dev_tsa.verify_timestamp_token(token_dev, sample_hash)
    assert not dev_tsa.verify_timestamp_token(token_dev, "wrong_hash")

    with pytest.raises(ProductionTrustViolationError, match="cannot be used in production"):
        LocalDevTimestampProvider(environment="production")

    # 8c. RFC3161TimestampProvider client interface
    rfc_tsa = RFC3161TimestampProvider(tsa_url="https://timestamp.sectigo.com", environment="development")
    token_rfc = rfc_tsa.generate_timestamp_token(sample_hash)
    assert token_rfc["tsa_type"] == "RFC_3161_COMPLIANT"
    assert token_rfc["status"] == "GRANTED"
    assert rfc_tsa.verify_timestamp_token(token_rfc, sample_hash)

    # Insecure HTTP fails in production
    with pytest.raises(ProductionTrustViolationError, match="must use HTTPS"):
        RFC3161TimestampProvider(tsa_url="http://insecure-tsa.internal", environment="production")
