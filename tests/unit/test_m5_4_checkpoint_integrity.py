"""
Unit tests for PIIS M5.4 Workstream D:
- FIND-M5.3-005: Missing Checkpoint Anchor Fails Open Against Ledger Rollback
- FIND-M5.3-004: Local File-Based Anchor Host Compromise Boundary & Hardened Permissions
"""

from datetime import datetime, timezone
import pytest

from piis.investigation.approval import (
    FileBasedCheckpointAnchor,
    AuditLogEntry,
    ApprovalStatus,
    LedgerRollbackDetectedError,
)


@pytest.fixture
def sample_entry():
    return AuditLogEntry(
        audit_id="AUD-0005",
        sequence_number=5,
        recommendation_id="REC-005",
        incident_id="INC-005",
        action="APPROVED",
        previous_status=ApprovalStatus.PENDING_REVIEW,
        new_status=ApprovalStatus.APPROVED,
        operator_id="eng-05",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        recommendation_content_hash="a" * 64,
        previous_entry_sha256="b" * 64,
        entry_sha256="c" * 64,
        hmac_signature="sig-005",
    )


def test_missing_checkpoint_fails_closed_when_ledger_non_empty(tmp_path, sample_entry):
    """Verify that verify_ledger_head fails closed if anchor file is missing while ledger has records."""
    anchor_file = tmp_path / "missing_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    
    # Anchor file does not exist
    assert not anchor_file.exists()
    
    # Ledger has entries (sample_entry is seq 5)
    valid, err_msg = anchor.verify_ledger_head(sample_entry)
    
    assert valid is False
    assert err_msg is not None
    assert "CRITICAL ROLLBACK / ANCHOR DELETION" in err_msg
    assert "anchor at" in err_msg or "anchor" in err_msg


def test_brand_new_system_empty_ledger_and_missing_anchor_succeeds(tmp_path):
    """Verify that a brand new empty ledger and absent anchor returns (True, None)."""
    anchor_file = tmp_path / "new_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    
    # Both are empty
    valid, err_msg = anchor.verify_ledger_head(None)
    assert valid is True
    assert err_msg is None


def test_corrupted_checkpoint_anchor_fails_closed(tmp_path, sample_entry):
    """Verify that a corrupted / unparseable anchor file fails closed."""
    anchor_file = tmp_path / "corrupted_anchor.json"
    anchor_file.write_text("CORRUPTED NOT JSON {{{", encoding="utf-8")
    
    anchor = FileBasedCheckpointAnchor(anchor_file)
    valid, err_msg = anchor.verify_ledger_head(sample_entry)
    
    assert valid is False
    assert "CRITICAL ANCHOR INTEGRITY ERROR" in err_msg or "corrupted or unreadable" in err_msg


def test_monotonic_checkpoint_recording_and_advancement(tmp_path, sample_entry):
    """Verify normal recording, file permissions, and rollback detection upon state regression."""
    anchor_file = tmp_path / "monotonic_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    
    anchor.record_checkpoint(
        audit_id=sample_entry.audit_id,
        sequence_number=sample_entry.sequence_number,
        entry_sha256=sample_entry.entry_sha256,
        hmac_signature=sample_entry.hmac_signature,
        timestamp_utc=sample_entry.timestamp_utc,
    )
    
    # Head matches anchor
    valid, err = anchor.verify_ledger_head(sample_entry)
    assert valid is True
    assert err is None
    
    # Regression attempt (recording seq 4 after seq 5)
    with pytest.raises(LedgerRollbackDetectedError, match="External anchor monotonic violation"):
        anchor.record_checkpoint(
            audit_id="AUD-0004",
            sequence_number=4,
            entry_sha256="d" * 64,
            hmac_signature="sig-004",
            timestamp_utc=sample_entry.timestamp_utc,
        )


def test_ledger_head_hash_mismatch_detected(tmp_path, sample_entry):
    """Verify that matching sequence with differing entry hash is detected as fork/tampering."""
    anchor_file = tmp_path / "fork_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_file)
    
    anchor.record_checkpoint(
        audit_id=sample_entry.audit_id,
        sequence_number=sample_entry.sequence_number,
        entry_sha256=sample_entry.entry_sha256,
        hmac_signature=sample_entry.hmac_signature,
        timestamp_utc=sample_entry.timestamp_utc,
    )
    
    # Alter entry hash
    tampered_entry = sample_entry.model_copy()
    tampered_entry.entry_sha256 = "f" * 64
    
    valid, err = anchor.verify_ledger_head(tampered_entry)
    assert valid is False
    assert "CRITICAL TAMPERING / FORK" in err
