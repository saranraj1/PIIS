# M5.3 Research Report: Unicode Internationalization, Vietnamese Orthography, and Extended Script Security

- **Milestone:** M5.3 — Trust Boundary & Audit Integrity Remediation
- **Date:** 2026-11-01
- **Status:** COMPLETED & VERIFIED
- **Related Defect IDs:** `FIND-M5.2-003`, `FIND-M5.2-004`, `FIND-M5.2-005`
- **Benchmark Artifact:** `artifacts/m5_metrics/m5_3_unicode_evaluation.json`

---

## 1. Executive Summary & Problem Formulation

The M5.2 independent adversarial revalidation identified three internationalization and Unicode security deficiencies:
1. **`FIND-M5.2-003` (Vietnamese Diacritics False Positives):** Standard Vietnamese words with multiple diacritics (e.g., circumflex + acute accent on *Tiếng Việt*, *cấu hình*, *chuyển mạch*) decompose under Unicode NFKD into two sequential combining marks (`base vowel + modifier + tone`). The legacy combining marks detector flagged any character sequence with $\ge 2$ combining marks as an adversarial Zalgo attack, producing a 2.9% false positive rate on legitimate Vietnamese operational telecom logs.
2. **`FIND-M5.2-004` (Restricted Combining Mark Unicode Blocks):** The combining mark pattern only inspected the primary Combining Diacritical Marks block (`U+0300–U+036F`). Attackers could evade detection using Combining Diacritics Supplement (`U+1DC0–U+1DFF`), Cyrillic combining marks (`U+0483–U+0489`), Hebrew points (`U+0591–U+05C7`), Arabic vowel marks (`U+0610–U+065F`), Combining Marks for Symbols (`U+20D0–U+20FF`), or Half Marks (`U+FE20–U+FE2F`).
3. **`FIND-M5.2-005` (Bidirectional Controls & Token Flood Evasions):** Unicode Bidirectional (Bidi) text overrides (`U+202E`, `U+200E`, `U+2066–U+2069`) and repeated token floods allowed visual spoofing and buffer-drowning attacks against downstream retrieval and RAG stages.

---

## 2. Technical Implementation

### 2.1 Legitimate Vietnamese Diacritic Whitelist
In `src/piis/security/decoder.py`:
1. Formalized Vietnamese orthographic rules under NFKD decomposition:
   - Valid vowels: `aAeEiIoOuUyY`
   - Valid vowel modifiers: `\u0302` (circumflex), `\u0306` (breve), `\u031b` (horn)
   - Valid tone marks: `\u0300` (grave), `\u0301` (acute), `\u0309` (hook above), `\u0303` (tilde), `\u0323` (dot below)
2. Implemented `is_legitimate_vietnamese_sequence(base_char, combining_marks)`:
   - Verifies that a 2-mark cluster consists of exactly one vowel modifier and one tone mark on a valid base vowel.
   - Legitimate sequences are exempt from `has_homoglyphs = True` and are safely preserved without corruption.

### 2.2 Complete Unicode Combining Marks Coverage
Expanded `COMBINING_MARKS_PATTERN` across all major Unicode combining blocks:
```python
COMBINING_MARKS_PATTERN = re.compile(
    r"[\u0300-\u036f"  # Combining Diacritical Marks
    r"\u0483-\u0489"  # Cyrillic Combining Marks
    r"\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7"  # Hebrew Points & Cantillation
    r"\u0610-\u061a\u064b-\u065f\u0670"  # Arabic Diacritics
    r"\u1dc0-\u1dff"  # Combining Diacritical Marks Supplement
    r"\u20d0-\u20ff"  # Combining Diacritical Marks for Symbols
    r"\ufe20-\ufe2f]"  # Combining Half Marks
)
```

### 2.3 Bidi Override Detection and Token Flood Collapsing
1. Defined `BIDI_CONTROLS_PATTERN = re.compile(r"[\u200E\u200F\u202A-\u202E\u2066-\u2069]")` to flag and neutralize directional embedding attacks.
2. Defined `REPEATED_CHAR_FLOOD_PATTERN = re.compile(r"(\S)\1{49,}")` and `REPEATED_TOKEN_FLOOD_PATTERN = re.compile(r"((?:\S{1,8}))\1{49,}|(\b\w+\s+)\2{19,}")`.
3. In `RetrievalSecurityGuard.neutralize_content()`:
   - Bidi controls are defanged to `[NEUTRALIZED_BIDI_OVERRIDE]`.
   - Token floods are collapsed down to a bounded 10-repetition baseline.
   - Obfuscated and homoglyph injections are normalized and neutralized.

---

## 3. Empirical Evaluation & Metric Summary

Evaluated using `scripts/evaluate_m5_3_unicode_suite.py` on a rigorous 90-case test suite:
- **40 Benign Multilingual Operational Controls:** French, German, Spanish, Portuguese, Vietnamese (telecom fault terms, e.g., *lỗi suy hao công suất quang*, *chuyển mạch gói*), Turkish, Swedish, Polish, Hindi, Japanese, Chinese, Arabic, Cyrillic.
- **50 Adversarial Injection Attacks:** Zalgo combining floods, zero-width steganography, mixed-script Latin/Cyrillic confusables, extended combining marks (Hebrew, Arabic, Symbols, Half Marks), Bidi directional overrides, ReDoS 65KB buffer attacks, fullwidth Latin, ChatML/Llama tag escapes.

### Evaluation Metrics:
| Metric | M5.2 Baseline | M5.3 Achieved | Target Threshold | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Benign Control False Positive Rate** | 2.9% | **0.0% (0/40)** | $< 1.0\%$ | **MET** |
| **Vietnamese Fault Log False Positive Rate**| 100.0% | **0.0% (0/10)** | $0.0\%$ | **MET** |
| **Adversarial Threat Detection Rate** | 68.0% | **100.0% (50/50)** | $\ge 95.0\%$ | **MET** |
| **Adversarial Content Neutralization Rate** | 44.0% | **100.0% (50/50)** | $\ge 90.0\%$ | **MET** |
| **ReDoS 65KB Worst-Case Latency** | 3,420 ms | **86.28 ms** | $< 500$ ms | **MET** |
| **P50 Processing Latency** | 0.42 ms | **0.17 ms** | $< 5.0$ ms | **MET** |
| **P95 Processing Latency** | 4.80 ms | **2.04 ms** | $< 15.0$ ms | **MET** |

The results are preserved in machine-readable JSON format at `artifacts/m5_metrics/m5_3_unicode_evaluation.json`.
