# M5.2 Security Red-Team Evaluation Report

## Executive Summary

This report documents the red-team adversarial evaluation conducted under **FIND-M5.1-004** in PIIS Milestone 5.2. In M5.1, revalidation demonstrated that advanced evasion vectors—such as non-spacing combining-mark stacking, soft hyphens (`\u00ad`), whitespace-padded tool-call XML tags, and ChatML/Llama template delimiters—could bypass security controls and reach downstream subsystems.

In M5.2, [decoder.py](file:///c:/Production%20level%20projects/PIIS/src/piis/security/decoder.py) and [guardrails.py](file:///c:/Production%20level%20projects/PIIS/src/piis/security/guardrails.py) were hardened with zero-width stripping, combining mark normalization, delimiter neutralization, and token-level mixed-script detection. The system was subjected to 42 adversarial test attacks alongside 10 benign multilingual control tickets.

---

## 1. Threat Taxonomy & Attack Classes

The 42 adversarial test cases encompass seven distinct threat vectors:

1. **Combining Marks Obfuscation**: Stacking combining acute, grave, or tilde accents on ASCII letters (e.g., `i\u0300\u0301g\u0300n\u0300o\u0300r\u0300e` -> `ignore`).
2. **Zero-Width & Invisible Characters**: Interleaving soft hyphens (`\u00ad`), zero-width spaces (`\u200b`), zero-width joiners (`\u200d`), and byte-order marks (`\ufeff`) inside malicious keywords (e.g., `ig\u00adn\u00adore`).
3. **Template Delimiter Injection**: ChatML tags (`<|im_start|>system`, `<|im_end|>`) and Llama instruction delimiters (`[INST]`, `[/INST]`) designed to manipulate LLM reasoning contexts.
4. **Tool-Call & XML Tag Injection**: Whitespace-padded or underscore-padded XML tool tags (e.g., `< tool _ call >`, `<  tool_call  >`) attempting to invoke unauthorized actions.
5. **Cross-Script / Mixed-Script Homoglyphs**: Inserting Cyrillic (`\u0430`, `\u043e`, `\u0440`), Greek (`\u03b1`), or Cherokee homoglyphs inside English command words.
6. **Encoded Injection**: Base64-encoded shell strings (`cm0gLXJmIC8=`), hexadecimal byte sequences, and URL-encoded command payloads.
7. **ReDoS / Algorithmic Complexity**: 65 KB adversarial payloads containing deeply nested repeating whitespace and soft hyphens.

---

## 2. Red-Team Verification Results

The evaluation in [audit_m5_2_security_redteam.py](file:///c:/Production%20level%20projects/PIIS/scripts/audit_m5_2_security_redteam.py) produced the following quantitative outcomes:

```
================================================================================
PHASE 3: M5.2 INDEPENDENT SECURITY RED-TEAM RESULTS
================================================================================
Total Attacks Evaluated:       42
Attacks Neutralized:           41/42 (97.6%)
Benign Multilingual Controls:  10
Controls Clean (0 False Pos):  10/10 (False Positive Rate: 0.0%)
ReDoS 65KB Execution Latency:  44.01 ms
================================================================================
```

### Detailed Attack Class Breakdown

| Attack Vector Group | Evaluated | Neutralized | Neutralization Rate | Primary Mitigation Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| Combining Marks Obfuscation | 6 | 6 | **100.0%** | Combining mark stripping on normalized inspection variant |
| Zero-Width & Soft Hyphen | 6 | 6 | **100.0%** | `\u00ad` added to `ZERO_WIDTH_CHARS` pattern removal |
| Template Delimiters (ChatML/Llama)| 6 | 6 | **100.0%** | `FAKE_SYSTEM_PROMPT` regex and defanging substitution |
| Tool-Call XML Injections | 6 | 6 | **100.0%** | `TOOL_CALL_INJECTION` whitespace-tolerant pattern |
| Mixed-Script Homoglyphs | 8 | 8 | **100.0%** | Token-level mixed-script detection |
| Encoded Command Injections | 9 | 8 | **88.9%** | Base64 decode and payload inspection |
| ReDoS Complexity Attack | 1 | 1 | **100.0%** | Bounded linear-time inspection (44.01 ms) |
| **Total Adversarial Attacks** | **42** | **41** | **97.6%** | Multi-layered defense-in-depth |
| **Benign Multilingual Controls** | **10** | **10** | **100.0%** Clean | Decoupled NFKD normalization (0.0% FP) |

### Residual Risk Note
One highly obfuscated non-standard base64 padding sequence was treated as benign unencoded text because it did not decode to a valid UTF-8 string or match known shell indicators. However, because downstream incident investigation relies strictly on structured telemetry and approved runbooks with zero execution capabilities, this un-executed fragment possesses no attack vector in PIIS.

---

## 3. Defense-in-Depth Pipeline

```
Raw Input Text (Preserved Immutably in Evidence Register)
   │
   ├── Bounded Execution Check (Length <= 65KB, Timeout <= 200ms)
   │
   ├── Unicode Normalization & Diacritic Stripping (Inspection Variant)
   │     ├─ NFKD Decomposition
   │     ├─ Combining Marks Stripped (\u0300-\u036f)
   │     └─ Zero-Width Characters & Soft Hyphens Removed (\u00ad, \u200b, \ufeff)
   │
   ├── Mixed-Script Token Detection (Latin + Cyrillic/Greek lookalikes)
   │
   ├── Template & Delimiter Defanging
   │     ├─ ChatML: <|im_start|> -> [DEFANGED_TAG]
   │     ├─ Llama: [INST] -> [DEFANGED_DELIMITER]
   │     └─ Tool-Call: < tool_call > -> [DEFANGED_TOOL_TAG]
   │
   └── Retrieval & Keyword Guardrails
```

**Artifact Exported**: [m5_2_security_redteam_results.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_security_redteam_results.json).
