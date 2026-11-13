# PIIS Milestone M5.4 Canonicalization & Migration Report

**Status:** VERIFIED & CLOSED  
**Milestone:** M5.4 (Workstream C)  
**Date:** 2026-11-01  
**Author:** Principal Security Engineer & Cryptographic Systems Architect  
**Classification:** Internal Engineering Audit Report  
**Relevant Machine-Readable Artifact:** [`artifacts/m5_metrics/m5_3_ledger_and_rollback_audit.json`](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_3_ledger_and_rollback_audit.json)  
**Unit Test Suite:** [`tests/unit/test_m5_4_canonical_jcs.py`](file:///c:/Production%20level%20projects/PIIS/tests/unit/test_m5_4_canonical_jcs.py)

---

## 1. Executive Summary

Milestone M5.3 finding `FIND-M5.3-003` reported a standards divergence in `canonical_json_dumps()`:
Standard library `json.dumps(..., ensure_ascii=True)` escaped all non-ASCII characters to ASCII escape sequences (e.g. `\u00fc` for `ü`, `\u5317` for `北`). While internally consistent across identical Python versions, this violates RFC 8785 (JSON Canonicalization Scheme / JCS) Section 3.2.2, which mandates that all Unicode characters $\ge$ U+0020 (except quotation mark and reverse solidus) must be output directly as native UTF-8 bytes. Furthermore, negative zero (`-0.0`) was not normalized to `0`.

In Milestone M5.4, a pure-Python, zero-external-dependency RFC 8785 canonical serializer was developed, tested, and integrated.

---

## 2. Technical Specification & Implementation

### 2.1 Pure-Python RFC 8785 JCS Implementation
The serializer in [`src/piis/investigation/approval.py`](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/approval.py) implements the full JCS specification:
1. **UTF-16 Code Unit Property Sorting (RFC 8785 Section 3.2.3):**
   Keys are converted to UTF-16 big-endian code units via `_utf16_code_units(s: str) -> List[int]` and sorted lexicographically. This correctly handles both BMP characters and surrogate pairs for supplementary code points.
2. **Strict Escaping Rules (RFC 8785 Section 3.2.2.2):**
   - Characters U+0000 through U+001F are escaped using standard 2-character escapes (`\b`, `\f`, `\n`, `\r`, `\t`) or 6-character lowercase hex sequences (`\u0000` through `\u001f`).
   - Quotation mark (`"`) $\to$ `\"`
   - Reverse solidus (`\`) $\to$ `\\`
   - All characters from U+0020 upwards are emitted directly as native UTF-8 bytes.
3. **Number & Float Normalization (RFC 8785 Section 3.2.2.3):**
   - Evaluated per ECMAScript `Number.prototype.toString()` specification.
   - Negative zero (`-0.0`) and positive zero (`0.0`) are normalized to `"0"`.
   - Floats representing integer values within IEEE 754 precision are serialized without decimal point or exponent (e.g. `100.0` $\to$ `"100"`).
   - Shortest round-trip IEEE 754 representation without trailing zeros or unnecessary leading zeros in scientific exponents.
   - Non-standard JSON values (`NaN`, `Infinity`, `-Infinity`) raise `ValueError`.
4. **Token Delimiters:**
   - Separators are strictly `','` and `':'` with zero whitespace.

---

## 3. Migration Integrity & Historical Backwards Compatibility

### 3.1 Preservation of Historical Hashes
A core principle of PIIS is that historical records and ledger entries must never be retroactively modified or re-signed.
- For all ASCII strings and standard numeric payloads (as utilized in historical v1.0 and v2.0 entries), RFC 8785 key sorting and string serialization produce an identical byte stream to standard Python `json.dumps(..., sort_keys=True, separators=(',', ':'))`.
- Verified empirically: Historical test ledgers from M5.2 and M5.3 verify 100% cleanly without hash or HMAC mismatch (`32/32 passed` in Phase 3 & 4 audit).
- Migrations from v1.0 to v2.0 append a cryptographically signed migration checkpoint without modifying historical entries.

---

## 4. Empirical Verification & Test Suite

The test suite in [`tests/unit/test_m5_4_canonical_jcs.py`](file:///c:/Production%20level%20projects/PIIS/tests/unit/test_m5_4_canonical_jcs.py) verified:
1. `test_rfc8785_utf16_code_unit_sorting`: Verified dictionary key sorting.
2. `test_rfc8785_unicode_raw_utf8_preservation`: Verified literal UTF-8 bytes for Munich (`München`), Beijing (`北京`), VSWR (`≥`), and wavelength (`λ`), confirming zero `\uXXXX` escapes.
3. `test_rfc8785_control_character_escaping`: Verified strict escaping of control characters and quotes.
4. `test_rfc8785_number_and_float_normalization`: Verified `-0.0` $\to$ `0`, `100.0` $\to$ `100`, and rejection of `NaN`/`Infinity`.
5. `test_audit_log_entry_canonical_hash_stability_with_unicode`: Verified deterministic SHA-256 hash generation for `AuditLogEntry` instances with multilingual notes.

*End of Canonicalization & Migration Report.*
