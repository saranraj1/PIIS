"""Unit and adversarial tests for M5.3 Workstream 3: Audit Ledger Canonicalization & Migration.

Validates:
1. Complete canonical payload covering every security-relevant field including operator notes.
2. Direct mutation of the 'notes' field in persistent JSONL is strictly detected and rejected.
3. Deletion, truncation, or Unicode alteration in notes invalidates entry_sha256 and HMAC.
4. Schema versioning: legacy v1.0 entries load cleanly without breaking historical records,
   marking notes_cryptographically_covered=False.
5. Migration utility migrate_ledger_v1_to_v2():
   - Preserves historical entries and original hashes.
   - Appends a signed MIGRATION_CHECKPOINT entry under v2.0 schema.
   - Distinguishes historical guarantees from post-migration guarantees.
"""

import json
import unicodedata

import pytest

from piis.investigation.approval import (
    AuditLogEntry,
    AuditTrailDiscontinuityError,
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
    migrate_ledger_v1_to_v2,
)
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_rec(rec_id: str = "REC-LEDGER-01") -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Run loopback diagnostic on core interface GigabitEthernet0/0/1",
        reason="Test interface line status and bit errors",
        supporting_evidence_ids=["EVID-01"],
        source_runbook_id="SOP-TRANS-BGP-002",
        source_section="Section 3",
        expected_observation="Line status UP, zero errors",
        risk_classification=RecommendationRisk.READ_ONLY_SAFE,
        human_approval_required=True,
    )


def test_notes_field_included_in_canonical_payload():
    """Verify that AuditLogEntry v2.0 includes 'notes' in get_canonical_payload()."""
    entry = AuditLogEntry(
        audit_id="AUD-0001",
        sequence_number=1,
        schema_version="2.0",
        recommendation_id="REC-01",
        incident_id="INC-01",
        action="APPROVED",
        previous_status=ApprovalStatus.PENDING_REVIEW,
        new_status=ApprovalStatus.APPROVED,
        operator_id="op_alice",
        reviewer_role="NOC_TIER_2",
        authorization_scope="NOC_TIER_2",
        principal_type="HUMAN",
        timestamp_utc="2026-11-01T12:00:00Z",
        recommendation_content_hash="abc123hash",
        previous_entry_sha256="GENESIS_CHECKPOINT",
        entry_sha256="",
        notes="Verified optical power is nominal; proceed with check.",
        notes_cryptographically_covered=True,
    )
    payload = entry.get_canonical_payload()
    assert "notes" in payload
    assert payload["notes"] == "Verified optical power is nominal; proceed with check."
    assert payload["schema_version"] == "2.0"
    assert payload["principal_type"] == "HUMAN"
    assert payload["authorization_scope"] == "NOC_TIER_2"


def test_tampering_with_notes_field_in_jsonl_is_rejected(tmp_path):
    """Verify that mutating the notes field in JSONL ledger file is detected during load_from_ledger."""
    ledger_file = tmp_path / "tampered_notes_ledger.jsonl"
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)

    rec = _sample_rec("REC-NOTE-01")
    wf.register_recommendation(rec, "INC-NOTE-01")

    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-NOTE-01", tok, "INC-NOTE-01", notes="Original operator justification notes")

    # Tamper with the notes field in line 2 of the JSONL file
    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    entry2_dict = json.loads(lines[1])
    assert entry2_dict["notes"] == "Original operator justification notes"

    # Attacker alters the notes field in place
    entry2_dict["notes"] = "MALICIOUS ALTERATION: Approved unauthorized command execution"
    lines[1] = json.dumps(entry2_dict)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Restoring from tampered ledger must raise AuditTrailDiscontinuityError
    restoration_wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)
    with pytest.raises(AuditTrailDiscontinuityError, match="Tampered record digest|Invalid HMAC signature"):
        restoration_wf.load_from_ledger()


def test_deleting_notes_field_in_jsonl_is_rejected(tmp_path):
    """Verify that deleting the notes field from a v2.0 entry is detected."""
    ledger_file = tmp_path / "deleted_notes_ledger.jsonl"
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)

    rec = _sample_rec("REC-NOTE-02")
    wf.register_recommendation(rec, "INC-NOTE-02")

    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-NOTE-02", tok, "INC-NOTE-02", notes="Crucial justification note")

    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    entry2_dict = json.loads(lines[1])
    entry2_dict["notes"] = ""  # Deleting note content
    lines[1] = json.dumps(entry2_dict)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    restoration_wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)
    with pytest.raises(AuditTrailDiscontinuityError, match="Tampered record digest|Invalid HMAC signature"):
        restoration_wf.load_from_ledger()


def test_unicode_normalization_alteration_in_notes_rejected(tmp_path):
    """Verify that altering Unicode normalization of notes (e.g. NFC to NFD) invalidates signature."""
    ledger_file = tmp_path / "unicode_notes_ledger.jsonl"
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)

    rec = _sample_rec("REC-NOTE-03")
    wf.register_recommendation(rec, "INC-NOTE-03")

    # Note contains precomposed NFC character é (\u00e9)
    note_nfc = "Vérifié par l'opérateur"
    tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    wf.approve_recommendation("REC-NOTE-03", tok, "INC-NOTE-03", notes=note_nfc)

    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    entry2_dict = json.loads(lines[1])

    # Convert notes to NFD decomposed form (e + \u0301)
    note_nfd = unicodedata.normalize("NFD", note_nfc)
    assert note_nfd != note_nfc
    entry2_dict["notes"] = note_nfd
    lines[1] = json.dumps(entry2_dict)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    restoration_wf = HumanApprovalWorkflow(ledger_path=ledger_file, verifier=verifier)
    with pytest.raises(AuditTrailDiscontinuityError, match="Tampered record digest|Invalid HMAC signature"):
        restoration_wf.load_from_ledger()


def test_legacy_v1_ledger_backwards_compatibility(tmp_path):
    """Verify that historical v1.0 entries load cleanly without breaking, noting notes_cryptographically_covered=False."""
    legacy_file = tmp_path / "legacy_v1_ledger.jsonl"
    key = b"PIIS_TEST_HMAC_SIGNING_KEY_32_BYTES_MINIMUM!"

    # Construct synthetic v1.0 entry where notes was not in canonical hash
    canonical_payload_v1 = {
        "action": "SUBMITTED",
        "audit_id": "AUD-0001",
        "incident_id": "INC-LEGACY-01",
        "new_status": "PENDING_REVIEW",
        "operator_id": "SYSTEM",
        "previous_entry_sha256": "GENESIS_CHECKPOINT",
        "previous_status": "PENDING_REVIEW",
        "recommendation_content_hash": "dummy_content_hash",
        "recommendation_id": "REC-LEGACY-01",
        "reviewer_auth_hash": "auth_hash",
        "reviewer_role": "SYSTEM",
        "sequence_number": 1,
        "timestamp_utc": "2026-10-31T10:00:00Z",
    }
    from piis.investigation.approval import canonical_json_dumps
    import hashlib
    import hmac

    serialized_v1 = canonical_json_dumps(canonical_payload_v1)
    entry_hash_v1 = hashlib.sha256(serialized_v1.encode("utf-8")).hexdigest()
    hmac_sig_v1 = hmac.new(key, serialized_v1.encode("utf-8"), hashlib.sha256).hexdigest()

    v1_entry = {
        "audit_id": "AUD-0001",
        "sequence_number": 1,
        "schema_version": "1.0",
        "recommendation_id": "REC-LEGACY-01",
        "incident_id": "INC-LEGACY-01",
        "action": "SUBMITTED",
        "previous_status": "PENDING_REVIEW",
        "new_status": "PENDING_REVIEW",
        "operator_id": "SYSTEM",
        "reviewer_role": "SYSTEM",
        "reviewer_auth_hash": "auth_hash",
        "key_id": "piis-audit-key-2026-v1",
        "timestamp_utc": "2026-10-31T10:00:00Z",
        "recommendation_content_hash": "dummy_content_hash",
        "previous_entry_sha256": "GENESIS_CHECKPOINT",
        "entry_sha256": entry_hash_v1,
        "hmac_signature": hmac_sig_v1,
        "notes": "Historical unauthenticated note",
        "notes_cryptographically_covered": False,
        "state_sha256": entry_hash_v1,
    }
    legacy_file.write_text(json.dumps(v1_entry) + "\n", encoding="utf-8")

    # Load legacy ledger into workflow
    wf = HumanApprovalWorkflow(ledger_path=legacy_file, signing_key=key)
    count = wf.load_from_ledger()
    assert count == 1
    trail = wf.get_audit_trail()
    assert trail[0].schema_version == "1.0"
    assert trail[0].notes_cryptographically_covered is False
    assert trail[0].notes == "Historical unauthenticated note"

    # Integrity verification succeeds for v1.0
    valid, errors = wf.verify_audit_trail()
    assert valid is True
    assert len(errors) == 0


def test_migrate_ledger_v1_to_v2_creates_checkpoint(tmp_path):
    """Verify that migrate_ledger_v1_to_v2 appends a signed checkpoint and preserves historical hashes."""
    input_ledger = tmp_path / "pre_migration_ledger.jsonl"
    output_ledger = tmp_path / "post_migration_ledger.jsonl"
    key = b"PIIS_TEST_HMAC_SIGNING_KEY_32_BYTES_MINIMUM!"

    # Create v1.0 entry
    from piis.investigation.approval import canonical_json_dumps
    import hashlib
    import hmac

    canonical_payload_v1 = {
        "action": "SUBMITTED",
        "audit_id": "AUD-0001",
        "incident_id": "INC-01",
        "new_status": "PENDING_REVIEW",
        "operator_id": "SYSTEM",
        "previous_entry_sha256": "GENESIS_CHECKPOINT",
        "previous_status": "PENDING_REVIEW",
        "recommendation_content_hash": "hash1",
        "recommendation_id": "REC-01",
        "reviewer_auth_hash": "auth1",
        "reviewer_role": "SYSTEM",
        "sequence_number": 1,
        "timestamp_utc": "2026-10-31T10:00:00Z",
    }
    serialized_v1 = canonical_json_dumps(canonical_payload_v1)
    entry_hash_v1 = hashlib.sha256(serialized_v1.encode("utf-8")).hexdigest()
    hmac_sig_v1 = hmac.new(key, serialized_v1.encode("utf-8"), hashlib.sha256).hexdigest()

    v1_entry = {
        "audit_id": "AUD-0001",
        "sequence_number": 1,
        "schema_version": "1.0",
        "recommendation_id": "REC-01",
        "incident_id": "INC-01",
        "action": "SUBMITTED",
        "previous_status": "PENDING_REVIEW",
        "new_status": "PENDING_REVIEW",
        "operator_id": "SYSTEM",
        "reviewer_role": "SYSTEM",
        "reviewer_auth_hash": "auth1",
        "key_id": "piis-audit-key-2026-v1",
        "timestamp_utc": "2026-10-31T10:00:00Z",
        "recommendation_content_hash": "hash1",
        "previous_entry_sha256": "GENESIS_CHECKPOINT",
        "entry_sha256": entry_hash_v1,
        "hmac_signature": hmac_sig_v1,
        "notes": "Original v1 note",
        "notes_cryptographically_covered": False,
    }
    input_ledger.write_text(json.dumps(v1_entry) + "\n", encoding="utf-8")

    # Run migration
    summary = migrate_ledger_v1_to_v2(input_ledger, output_ledger, signing_key=key)
    assert summary["migrated_entries_count"] == 1
    assert summary["historical_notes_covered"] is False
    assert summary["new_schema_version"] == "2.0"

    # Verify that post-migration ledger restores cleanly with 2 entries
    wf = HumanApprovalWorkflow(ledger_path=output_ledger, signing_key=key)
    count = wf.load_from_ledger()
    assert count == 2

    trail = wf.get_audit_trail()
    assert trail[0].schema_version == "1.0"
    assert trail[0].notes_cryptographically_covered is False
    assert trail[1].schema_version == "2.0"
    assert trail[1].action == "MIGRATION_CHECKPOINT"
    assert trail[1].notes_cryptographically_covered is True
    assert "MIGRATION NOTICE" in trail[1].notes

    valid, errors = wf.verify_audit_trail()
    assert valid is True
    assert len(errors) == 0
