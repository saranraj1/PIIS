"""
Unit tests for PIIS M5.4 Workstream C:
- FIND-M5.3-003: RFC 8785 JSON Canonicalization Scheme (JCS) Compliance
"""

import pytest

from piis.investigation.approval import (
    canonical_json_dumps,
    AuditLogEntry,
    ApprovalStatus,
)


def test_rfc8785_utf16_code_unit_sorting():
    """Verify that object keys are sorted lexicographically by UTF-16 code units."""
    # Test varying key orders
    d1 = {"b": 1, "a": 2, "c": 3}
    assert canonical_json_dumps(d1) == '{"a":2,"b":1,"c":3}'

    # Supplementary characters (surrogate pairs in UTF-16) vs BMP
    d2 = {"\u20ac": "euro", "a": "ascii", "z": "last_ascii"}
    assert canonical_json_dumps(d2) == '{"a":"ascii","z":"last_ascii","\u20ac":"euro"}'


def test_rfc8785_unicode_raw_utf8_preservation():
    """Verify that non-ASCII Unicode characters are NOT escaped to \\uXXXX sequences."""
    telecom_data = {
        "station": "München_Core_01",
        "region": "北京",
        "indicator": "VSWR ≥ 1.5",
        "symbol": "λ = 1550nm",
    }
    serialized = canonical_json_dumps(telecom_data)
    
    # Must contain literal characters
    assert "München_Core_01" in serialized
    assert "北京" in serialized
    assert "≥" in serialized
    assert "λ" in serialized

    # Must NOT contain escaped unicode
    assert "\\u00fc" not in serialized
    assert "\\u5317" not in serialized
    assert "\\u2265" not in serialized
    assert "\\u03bb" not in serialized


def test_rfc8785_control_character_escaping():
    """Verify that control characters U+0000..U+001F, quote, and backslash are strictly escaped."""
    data = {
        "text": 'Line1\nLine2\tTabbed\\Backslash"Quoted"\r\b\f',
        "null_byte": "null\u0000byte",
        "unit_separator": "unit\u001fsep",
    }
    serialized = canonical_json_dumps(data)
    
    assert '\\"' in serialized
    assert '\\\\' in serialized
    assert '\\n' in serialized
    assert '\\t' in serialized
    assert '\\r' in serialized
    assert '\\b' in serialized
    assert '\\f' in serialized
    assert '\\u0000' in serialized
    assert '\\u001f' in serialized


def test_rfc8785_number_and_float_normalization():
    """Verify that negative zero, float integers, and IEEE 754 numbers format per RFC 8785 Section 3.2.2.3."""
    # Negative zero must normalize to 0
    assert canonical_json_dumps(-0.0) == "0"
    assert canonical_json_dumps(0.0) == "0"
    assert canonical_json_dumps({"val": -0.0}) == '{"val":0}'

    # Integer floats must serialize as integers without .0
    assert canonical_json_dumps(100.0) == "100"
    assert canonical_json_dumps(-42.0) == "-42"

    # Standard floats
    assert canonical_json_dumps(1.5) == "1.5"
    assert canonical_json_dumps(0.00001) == "0.00001"

    # NaN and Infinity must be rejected
    with pytest.raises(ValueError, match="Invalid RFC 8785 float"):
        canonical_json_dumps(float("nan"))

    with pytest.raises(ValueError, match="Invalid RFC 8785 float"):
        canonical_json_dumps(float("inf"))

    with pytest.raises(ValueError, match="Invalid RFC 8785 float"):
        canonical_json_dumps(float("-inf"))


def test_audit_log_entry_canonical_hash_stability_with_unicode():
    """Verify that AuditLogEntry computes deterministic canonical hash with Unicode text in notes."""
    entry = AuditLogEntry(
        audit_id="AUD-UNICODE-01",
        sequence_number=1,
        schema_version="2.0",
        recommendation_id="REC-UNI-01",
        incident_id="INC-UNI-01",
        action="APPROVED",
        previous_status=ApprovalStatus.PENDING_REVIEW,
        new_status=ApprovalStatus.APPROVED,
        operator_id="eng-münchen",
        reviewer_role="NOC_TIER_2",
        timestamp_utc="2026-11-01T12:00:00Z",
        recommendation_content_hash="a" * 64,
        previous_entry_sha256="0" * 64,
        entry_sha256="",
        notes="Geprüft und bestätigt: VSWR ≥ 1.5 auf Funkzelle München-Ost",
    )
    
    hash1 = entry.compute_canonical_hash()
    hash2 = entry.compute_canonical_hash()
    assert hash1 == hash2
    assert len(hash1) == 64
    
    # Verify that raw UTF-8 serialized payload is used
    serialized = entry.get_canonical_serialized()
    assert "München-Ost" in serialized
    assert "≥" in serialized
    assert "\\u00fc" not in serialized
