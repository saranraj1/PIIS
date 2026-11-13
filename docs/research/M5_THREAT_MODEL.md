# Milestone 5 — Threat Model & Security Specification

**System:** PIIS Milestone 5 (Incident Investigation & Decision Support)  
**Security Focus:** Indirect Prompt Injection, Encoded Payloads, Tool Escape, Operational Hallucination & Epistemic Integrity  
**Frameworks:** STRIDE, MITRE ATLAS (Adversarial Threat Landscape for AI Systems), OWASP Top 10 for LLM Applications  
**Date:** 2026-11-01  
**Status:** Security Baseline Locked  

---

## 1. Threat Landscape & Security Posture

Telecom operational environments represent high-consequence critical infrastructure. Malicious actors, rogue automated scripts, or compromised monitoring agents may inject adversarial payloads into:
1. Incident ticket titles, descriptions, and user notes.
2. Ingested network alarms and syslog messages.
3. Synthetic or third-party historical knowledge repositories.
4. Operator feedback strings.

In PIIS Milestone 5, the primary security objective is to prevent **adversarial instruction hijacking**, **unauthorized command generation**, and **operational hallucinations** while maintaining complete epistemic separation between data evidence and execution authority.

---

## 2. Attack Surface Analysis

```
[Inbound Attack Vectors]
       │
       ├──► Vector 1: Malicious Ticket Content (Direct Prompt Injection)
       │    └── Attacker crafts ticket description containing override directives.
       │
       ├──► Vector 2: Encoded & Nested Payloads (Evasion Attacks - DEF-M4-003)
       │    └── Attacker encodes malicious instructions in Base64, URL hex, or nested wrappers.
       │
       ├──► Vector 3: Poisoned Knowledge Chunk (Indirect Prompt Injection)
       │    └── Attacker plants malicious runbook section containing hidden system prompts.
       │
       ├──► Vector 4: Exfiltration via Error Traces / SSRF
       │    └── Injected payload requests telemetry from AWS metadata (169.254.169.254) or internal webhook.
       │
       └──► Vector 5: Unsupported Recommendation Hijacking
            └── System is tricked into proposing a destructive network change (e.g. reload router chassis).
```

---

## 3. Threat Matrix (STRIDE Classification)

| Threat ID | STRIDE Category | Threat Description | Attack Vector / Scenario | Potential Impact | M5 Mitigation Controls |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **THR-001** | **Spoofing** | Fake System Directives | Injected text uses `<system>`, `[system instruction]`, or role spoofing to trick LLM/parsers. | Model ignores safety boundaries and treats data as system instructions. | Multi-pattern regex detection, tag neutralization (`[NEUTRALIZED_FAKE_SYSTEM_PROMPT]`), structural XML sandboxing. |
| **THR-002** | **Tampering** | Indirect Knowledge Poisoning | Runbook or historical ticket contains instructions to bypass safety policy. | System adopts malicious troubleshooting procedures. | Strict trust classification (`HIGH_TRUST_APPROVED` whitelist), SHA-256 chunk integrity verification. |
| **THR-003** | **Repudiation** | Unaudited Human Decisions | An engineer executes an unapproved or modified command without logging. | Inability to establish incident root cause or trace who authorized actions. | Immutable `AuditTrailRecord` with SHA-256 state signatures and mandatory operator ID. |
| **THR-004** | **Information Disclosure** | Cloud SSRF & Key Exfiltration | Ticket prompts system to curl internal metadata IP (`http://169.254.169.254`) or paste API keys. | Leakage of AWS/GCP IAM credentials or internal telecom topology secrets. | Regex neutralization of curl/wget/webhook patterns, no outbound HTTP execution capabilities in M5. |
| **THR-005** | **Denial of Service** | Recursive Decoding Exhaustion (Zip-Bomb style) | Highly nested Base64 or URL encoding designed to cause exponential memory/CPU usage. | Crash of investigation engine, blocking NOC operations during severe outage. | Strict bounded decoding ($d_{\max} = 5$, $L_{\max} = 50,000$ chars). Malformed strings handled safely without crashes. |
| **THR-006** | **Elevation of Privilege** | Autonomous Command Execution | System is tricked into proposing active bash commands (`rm -rf /`, `reboot -f`). | Catastrophic network outage, element destruction, or unauthorized system mutation. | **Strict Read-Only Invariant**. $100\%$ of recommendations require human approval; zero tool execution capabilities. |

---

## 4. Deep Dive: Defense Against Encoded & Nested Payloads (DEF-M4-003)

### 4.1. The Vulnerability in Milestone 4
Milestone 4 audit finding `DEF-M4-003` demonstrated that while regex scanning catches plaintext patterns (`rm -rf /`, `ignore previous instructions`), it was blind to encoded variants:
- Example: `cm0gLXJmIC8=` (Base64 for `rm -rf /`)
- Example: `%69%67%6e%6f%72%65%20%70%72%65%76%69%6f%75%73` (URL encoded `ignore previous`)
- Example: Nested: `JTI1NjklMjU2NyUyNTZl...` (Double URL-encoded Base64)

### 4.2. Bounded Recursive Decoding Specification
The `BoundedRecursiveDecoder` enforces strict boundary conditions:
1. **Depth Boundary:** At most 5 recursive iterations. If a payload requires $>5$ decoding steps, decoding halts, an alert flag `MAX_DECODING_DEPTH_EXCEEDED` is set, and the intermediate layers are inspected.
2. **Expansion Boundary:** At most 50,000 output characters. If decoded output grows beyond this threshold, decoding aborts with flag `DECODING_EXPANSION_LIMIT_EXCEEDED`.
3. **Multi-Codec Support:**
   - URL percent-encoding (`urllib.parse.unquote`).
   - Base64 encoding (standard RFC 4648, URL-safe RFC 4648, and unpadded strings).
   - Hexadecimal escape sequences (`\xNN`, `0xNN`).
   - HTML entities (`html.unescape`).
4. **Resilience:** Malformed Base64 (invalid padding, non-alphabet characters) does not raise exceptions; the decoder catches `binascii.Error` and continues.
5. **Audit Artifact:** All decoded intermediate layers and detected candidate strings are preserved in `DecodingTrace` for forensic inspection.

---

## 5. Epistemic Safety & Operational Hallucination Defense

In a telecom network, an inaccurate recommendation is as dangerous as malicious injection:
1. **Zero Hallucinated Runbooks:**
   - Every recommendation must trace directly to a verified `doc_id` registered in `KnowledgeSourceRegistry`.
   - The synthesizer is cryptographically restricted to citing passages that exist in the indexed corpus.
2. **Anti-Silent Omission:**
   - When metadata filters drop all candidate runbooks (e.g. unknown technology domain), the engine sets `filter_dropped_all = True` and alerts the operator.
3. **Unsupported Hypothesis Suppression:**
   - A hypothesis cannot be emitted without at least one valid supporting `evidence_id`.
   - Hypotheses with conflicting evidence must explicitly list all contradicting evidence IDs.
4. **Safety Abstention Floor:**
   - When retrieval returns `NO_CONFIDENT_MATCH` or `TIER_4_HUMAN_REVIEW`, the engine is forbidden from inventing intermediate guesses. It must immediately output an `INCONCLUSIVE` hypothesis requesting human specialist dispatch.

---

## 6. Verification and Red-Teaming Test Cases

The test suite in `tests/unit/test_m5_adversarial.py` must programmatically verify that:
- Plaintext direct injection is neutralized.
- Base64-encoded destructive commands are decoded, identified, and neutralized.
- Double-URL-encoded fake system directives are decoded and neutralized.
- Payloads exceeding recursion limits halt gracefully without CPU spinning.
- Malformed Base64 strings do not crash the engine.
- Retrieved passages containing script tags or markdown exploits are defanged.
- No recommendation can be approved without a non-empty `operator_id`.

---
*PIIS Milestone 5 Threat Model Locked on 2026-11-01.*
