"""RAG security guardrails: prompt injection detection, data sandboxing, and command neutralization."""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

from piis.knowledge.models import KnowledgeChunk
from piis.security.decoder import BoundedRecursiveDecoder, DecodingResult

# Pattern definitions for malicious instructions embedded in tickets or unvetted text
THREAT_PATTERNS = [
    (
        "HTML_TAG_ESCAPE_DETECTED",
        re.compile(
            r"(?i)(?:</operational_evidence>|<script[\s>]|</script>|<iframe[\s>]|<object[\s>]|javascript:)"
        ),
    ),
    (
        "DIRECT_PROMPT_INJECTION",
        re.compile(
            r"(?i)\b(?:"
            r"ignore\s+(?:all\s+)?(?:previous|prior|safety|standard|the\s+alarm|diagnostic|metadata|token|audit)?(?:\s+instructions|\s+prompts|\s+rules|\s+sops|\s+limits|\s+filters|\s+checks|\s+register)?|"
            r"disregard\s+(?:all\s+)?(?:prior\s+prompts|system\s+(?:guidelines|rules|instructions|constraints)|standard\s+triage|contradictory\s+evidence|audit\s+signature)|"
            r"override\s+(?:all\s+)?(?:safety|system|security|approval)\s*(?:rules|constraints|policies|checks|guidelines)?|"
            r"forget\s+(?:all\s+)?(?:previous|prior|system|safety)\s*(?:instructions|invariants|prompts|rules|constraints)|"
            r"cancel\s+(?:all\s+)?(?:safety|human\s+gatekeeper)\s*(?:validations|checks|requirements?)?|"
            r"auto-resolve\s+ticket(?:\s+and\s+dismiss(?:\s+warnings)?)?|"
            r"emergency\s+root\s+override|"
            r"safety\s+test\s+mode(?:\s+active)?|"
            r"unrestricted_engineer(?:\s+mode)?|"
            r"system\s+maintenance\s+update.*pre-approved|"
            r"you\s+are\s+now\s+(?:a|an)?\s*[a-zA-Z0-9_\-\s]+|"
            r"system\s+(?:override|directive)|"
            r"developer\s+mode\s+enabled|"
            r"drop\s+all\s+guardrails"
            r")\b"
        ),
    ),
    (
        "PRIVILEGE_ESCALATION",
        re.compile(
            r"(?i)\b(?:grant\s+(?:all\s+|full\s+)?access|"
            r"escalate\s+privileges|"
            r"bypass\s+(?:security\s+|safety\s+)?policy|"
            r"disable\s+(?:all\s+)?guardrails?|"
            r"sudo\s+mode)\b"
        ),
    ),
    (
        "FAKE_AUTHORITY_INJECTION",
        re.compile(
            r"(?i)\b(?:per\s+(?:cto|vp|director|lead|senior|architect|security\s+officer|liaison|governance|authority)\s+(?:directive|order|mandate|decree|waiver|clause|protocol|exemption|clearance)|"
            r"authorized\s+(?:immediate\s+)?bypass|"
            r"emergency\s+(?:override|order|waiver|alert|clause)|"
            r"special\s+operations\s+authorization|"
            r"pre-approved\s+(?:by\s+(?:the\s+)?cto|emergency|change))\b"
        ),
    ),
    (
        "APPROVAL_BYPASS_INJECTION",
        re.compile(
            r"(?i)\b(?:bypass\s+(?:human\s+)?approval|"
            r"skip\s+(?:human\s+)?review|"
            r"set\s+approval_status\s+to\s+approved|"
            r"approval_status\s*:\s*approved|"
            r"human_approval_required\s*:\s*false|"
            r"auto-sign|"
            r"auto-execute|"
            r"pre-approved\s+by\s+system|"
            r"transition\s+(?:recommendation\s+)?directly\s+to\s+approved|"
            r"skip\s+pending_review)\b"
        ),
    ),
    (
        "PROMPT_EXTRACTION_INJECTION",
        re.compile(
            r"(?i)\b(?:"
            r"print\s+(?:your\s+)?(?:entire\s+|hidden\s+|complete\s+)?(?:system\s+prompt|initial\s+instructions|system\s+directives)|"
            r"output\s+(?:all\s+|the\s+|full\s+)?(?:hidden\s+|secret\s+)?(?:system\s+directives|system\s+instructions|developer\s+(?:mode|prompt|instructions)|signing\s+hmac|secret\s+signing)|"
            r"repeat\s+your\s+initial\s+developer\s+instructions\s+verbatim|"
            r"repeat\s+.*starting\s+from|"
            r"starting\s+from\s+['\"]?you\s+are|"
            r"what\s+are\s+the\s+exact\s+(?:secret\s+)?rules\s+and\s+criteria|"
            r"display\s+(?:the\s+secret\s+hmac|all\s+internal\s+configuration\s+variables(?:,\s*api\s+keys)?)|"
            r"what\s+are\s+the\s+secret\s+tokens|"
            r"echo\s+the\s+hidden\s+system\s+instructions|"
            r"translate\s+your\s+system\s+prompt|"
            r"summarize\s+every\s+directive\s+in\s+your\s+base\s+prompt|"
            r"provide\s+a\s+full\s+dump\s+of\s+your\s+runtime(?:\s+environment)?|"
            r"tell\s+me\s+your\s+initial\s+prompt\s+word-by-word|"
            r"echo\s+the\s+internal\s+oidc|"
            r"reveal\s+(?:the\s+)?(?:system-level|hidden\s+safety)|"
            r"dump\s+the\s+memory\s+context|"
            r"leak\s+(?:the\s+)?private\s+keys"
            r")\b"
        ),
    ),
    (
        "CROSS_LANGUAGE_INJECTION",
        re.compile(
            r"(?i)(?:"
            r"yönetici\s+emri|yonetici\s+emri|"
            r"insan\s+onay[ıi]n[ıi]\s+atlay[ıi]n|insan\s+onay[ıi]n[ıi]\s+derhal\s+atla|"
            r"güvenlik\s+filtrelerini\s+devre\s+dışı\s+bırakın|guvenlik\s+filtrelerini|"
            r"tüm\s+güvenlik\s+kontrollerini\s+atla|tum\s+guvenlik\s+kontrollerini|"
            r"acil\s+(?:durum|bakim).*(?:iptal|onayla|yetki)|"
            r"sistem\s+talimati.*(?:unutun|onaylayin)|"
            r"i-override\s+ang\s+sistema|"
            r"laktawan\s+ang\s+pag-apruba|"
            r"huwag\s+pansinin\s+ang\s+nakaraang|"
            r"पिछल[ेा]\s+सभी\s+नियमों\s+को\s+अनदेखा|"
            r"मानव\s+अनुमोदन\s+को\s+बायपास|"
            r"तत्काल\s+पुनः\s+आरंभ|"
            r"पूर्वीच्या\s+सर्व\s+सूचना\s+दुर्लक्षित|"
            r"পূর্ববর্তী\s+সমস্ত\s+নির্দেশাবলী\s+বাতিল|"
            r"игнорируйте\s+инструкции|отмените\s+все\s+предыдущие\s+инструкции|"
            r"пропустить\s+утверждение\s+оператором|утвердите\s+действие\s+немедленно|"
            r"выполните\s+команду\s+оболочки|удалить\s+журнал\s+аудита|"
            r"忽略(?:之前|所有)?(?:的)?(?:系统)?指令|"
            r"自动批准.*无需(?:人工)?(?:审核|审批)|"
            r"执行(?:终端)?(?:系统)?(?:shell)?命令|"
            r"重启所有基站|"
            r"anulación\s+de\s+emergencia|anulacion\s+de\s+emergencia|"
            r"omita\s+la\s+aprobación\s+humana|omita\s+la\s+aprobacion\s+humana|"
            r"apruebe\s+el\s+sop|"
            r"ignora\s+todas\s+las\s+reglas\s+anteriores|"
            r"تجاوز\s+فوري|تجاهل\s+جميع\s+(?:التعليمات|القيود|القواعد)|"
            r"دون\s+موافقة\s+بشرية|أمر\s+النظام.*أمر\s+القذيفة|"
            r"bỏ\s+qua\s+mọi\s+quy\s+tắc\s+trước\s+đó|"
            r"notfall-überschreibung|notfall\s+ueberschreibung|"
            r"alle\s+vorherigen\s+sicherheitsregeln\s+ignorieren|alle\s+sicherheitsregeln\s+ignorieren|"
            r"ignorez\s+toutes\s+les\s+instructions\s+préalables|"
            r"desative\s+todas\s+as\s+proteções\s+e\s+autorize"
            r")"
        ),
    ),
    (
        "DATA_TEMPLATE_AND_EXFIL_INJECTION",
        re.compile(
            r"(?i)(?:"
            r"!\[[^\]]*\]\((?:https?:)?//[^\)]+\)|"
            r"<img[\s>][^>]*src\s*=\s*['\"]https?://|"
            r"\$\{jndi:|"
            r"\{\{system\.|"
            r"\$\{[A-Za-z0-9_]+\}|"
            r"<!\[CDATA\[.*(?:ignore|reboot|system|approve).*\]\]>"
            r")"
        ),
    ),
    (
        "DESTRUCTIVE_COMMAND_INJECTION",
        re.compile(
            r"(?i)(?:\brm\s+-rf(?:\s+[/~]|\s+\S+)|"
            r"\bformat\s+[a-z]:|"
            r"\bdrop\s+database\b|"
            r"\bdrop\s+table\b|"
            r"\breboot\s+(?:-f|--force)\b|"
            r"\bshutdown\s+-h\s+now\b|"
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:)"
        ),
    ),
    (
        "FAKE_SYSTEM_PROMPT",
        re.compile(
            r"(?i)(?:<system>|\[system\s+instruction\]|"
            r"\[(?:developer|system|admin)\s+(?:note|instruction|directive|prompt|mode)[^\]]*\]|"
            r"system\s+prompt\s*:|"
            r"###\s+system\s+directive|"
            r"<!--\s*system\s*:?|"
            r"<<SYS>>|"
            r"role:\s*system|"
            r"<\|im_start\|>|"
            r"<\|im_end\|>|"
            r"\[INST\]|"
            r"\[/INST\])"
        ),
    ),
    (
        "TOOL_CALL_INJECTION",
        re.compile(
            r"(?i)(?:"
            r"<\s*/?\s*(?:tool[\s_]*call|function[\s_]*calls?|tool[\s_]*response|tool[\s_]*use|mcp_call)[^>]*>|"
            r"call_tool\s*:|"
            r"['\"]?action['\"]\s*:\s*['\"]run_command['\"]|"
            r"invoke\s+tool\s+['\"][a-zA-Z0-9_-]+['\"]|"
            r"system\s*\(\s*['\"](?:curl|wget|sh|bash|rm)"
            r")"
        ),
    ),
    (
        "COMMAND_EXFILTRATION",
        re.compile(
            r"(?i)\b(?:curl\s+https?://|"
            r"wget\s+https?://|"
            r"webhook\s+https?://|"
            r"nc\s+-e|"
            r"powershell\s+-[eE]nc(?:odedCommand)?)\b"
        ),
    ),
]


class RetrievalSecurityGuard:
    """Enforces non-executability, instruction neutralization, and structural sandboxing on retrieved text."""

    def __init__(
        self,
        sanitize_dangerous_patterns: bool = True,
        decoder: Optional[BoundedRecursiveDecoder] = None,
    ):
        self.sanitize_dangerous_patterns = sanitize_dangerous_patterns
        self.decoder = decoder or BoundedRecursiveDecoder(max_depth=5, max_length=50_000)

    def scan_content(self, text: str) -> List[str]:
        """Scan text across raw and all recursively decoded layers for threat tags."""
        if not text:
            return []

        detected_flags: List[str] = []

        # 1. Direct scan on raw text
        for tag, pattern in THREAT_PATTERNS:
            if pattern.search(text) and tag not in detected_flags:
                detected_flags.append(tag)

        # 2. Bounded recursive decoding pass (DEF-M4-003)
        dec_res: DecodingResult = self.decoder.decode(text)

        # Check for abnormal encoding and resource flags
        if dec_res.is_nested and "NESTED_ENCODING_DETECTED" not in detected_flags:
            detected_flags.append("NESTED_ENCODING_DETECTED")
        if dec_res.is_malformed and "MALFORMED_ENCODING_DETECTED" not in detected_flags:
            detected_flags.append("MALFORMED_ENCODING_DETECTED")
        if dec_res.has_homoglyphs and "UNICODE_HOMOGLYPH_DETECTED" not in detected_flags:
            detected_flags.append("UNICODE_HOMOGLYPH_DETECTED")
        if "EXPANSION_LIMIT_EXCEEDED" in dec_res.security_flags and "BUFFER_EXPANSION_LIMIT_EXCEEDED" not in detected_flags:
            detected_flags.append("BUFFER_EXPANSION_LIMIT_EXCEEDED")
        if "BIDI_CONTROL_DETECTED" in dec_res.security_flags and "BIDI_CONTROL_DETECTED" not in detected_flags:
            detected_flags.append("BIDI_CONTROL_DETECTED")
        if "TOKEN_FLOOD_DETECTED" in dec_res.security_flags and "TOKEN_FLOOD_DETECTED" not in detected_flags:
            detected_flags.append("TOKEN_FLOOD_DETECTED")

        # 3. Scan all decoded layers and fragments
        encoded_threat_found = False
        for variant in dec_res.all_text_variants():
            for tag, pattern in THREAT_PATTERNS:
                if pattern.search(variant):
                    if tag not in detected_flags:
                        detected_flags.append(tag)
                    if variant != text:
                        encoded_threat_found = True

        if encoded_threat_found and "ENCODED_PAYLOAD_DETECTED" not in detected_flags:
            detected_flags.append("ENCODED_PAYLOAD_DETECTED")

        return detected_flags

    def inspect_query(self, query_text: str) -> Dict[str, Any]:
        """Inspect query text for malicious prompt injection patterns and return analysis."""
        threat_flags = self.scan_content(query_text)
        is_safe = len(threat_flags) == 0
        neutralized = self.neutralize_content(query_text, threat_flags)
        return {
            "is_safe": is_safe,
            "threat_types": threat_flags,
            "neutralized_text": neutralized,
        }

    def neutralize_content(self, text: str, detected_flags: List[str]) -> str:
        """Neutralize executable instructions and encoded payloads while preserving diagnostics."""
        if not detected_flags or not text:
            return text

        neutralized = text

        # 0. Token flood collapsing & buffer expansion guard
        if "TOKEN_FLOOD_DETECTED" in detected_flags or "BUFFER_EXPANSION_LIMIT_EXCEEDED" in detected_flags:
            from piis.security.decoder import REPEATED_CHAR_FLOOD_PATTERN, REPEATED_TOKEN_FLOOD_PATTERN, ZERO_WIDTH_CHARS
            neutralized = ZERO_WIDTH_CHARS.sub("", neutralized)
            neutralized = REPEATED_CHAR_FLOOD_PATTERN.sub(r"\1\1\1\1\1\1\1\1\1\1", neutralized)
            neutralized = REPEATED_TOKEN_FLOOD_PATTERN.sub(r"\1\1\1\1\1\1\1\1\1\1", neutralized)

        # 0b. Bidi directional control stripping
        if "BIDI_CONTROL_DETECTED" in detected_flags:
            from piis.security.decoder import BIDI_CONTROLS_PATTERN
            neutralized = BIDI_CONTROLS_PATTERN.sub("[NEUTRALIZED_BIDI_OVERRIDE]", neutralized)

        # 0c. Unicode homoglyph and obfuscation neutralization
        if "UNICODE_HOMOGLYPH_DETECTED" in detected_flags:
            from piis.security.decoder import (
                COMBINING_MARKS_PATTERN,
                UNICODE_CONFUSABLE_MAP,
                ZERO_WIDTH_CHARS,
            )
            # Remove zero-width characters and soft hyphens
            if ZERO_WIDTH_CHARS.search(neutralized):
                neutralized = ZERO_WIDTH_CHARS.sub("", neutralized)
            # Normalize combining marks that are not legitimate
            if COMBINING_MARKS_PATTERN.search(neutralized):
                neutralized = COMBINING_MARKS_PATTERN.sub("", neutralized)
            # Normalize fullwidth characters to standard Latin
            neutralized = unicodedata.normalize("NFKD", neutralized)
            # Replace confusables
            neutralized = "".join(UNICODE_CONFUSABLE_MAP.get(c, c) for c in neutralized)

        if "BUFFER_EXPANSION_LIMIT_EXCEEDED" in detected_flags or len(neutralized) > self.decoder.max_length:
            neutralized = neutralized[: self.decoder.max_length] + " [TRUNCATED_MAX_LENGTH]"

        # 1. Neutralize HTML tag escapes
        if "HTML_TAG_ESCAPE_DETECTED" in detected_flags or "</operational_evidence>" in neutralized:
            neutralized = (
                neutralized.replace("</operational_evidence>", "[NEUTRALIZED_TAG_ESCAPE]")
                .replace("<script>", "&lt;script&gt;")
                .replace("</script>", "&lt;/script&gt;")
            )

        # 2. Neutralize malformed encodings
        if "MALFORMED_ENCODING_DETECTED" in detected_flags:
            from piis.security.decoder import (
                MALFORMED_B64_PATTERN,
                MALFORMED_HEX_PATTERN,
                MALFORMED_HTML_PATTERN,
                MALFORMED_URL_PATTERN,
            )
            if "=" in neutralized:
                neutralized = MALFORMED_B64_PATTERN.sub("[NEUTRALIZED_MALFORMED_BASE64]", neutralized)
            if "\\x" in neutralized:
                neutralized = MALFORMED_HEX_PATTERN.sub("[NEUTRALIZED_MALFORMED_HEX]", neutralized)
            if "%" in neutralized:
                neutralized = MALFORMED_URL_PATTERN.sub("[NEUTRALIZED_MALFORMED_URL]", neutralized)
            if "&#x" in neutralized:
                neutralized = MALFORMED_HTML_PATTERN.sub("[NEUTRALIZED_MALFORMED_HTML]", neutralized)

        # 3. Neutralize identified encoded fragments if any
        dec_res = self.decoder.decode(text)
        for fragment in dec_res.fragments:
            for tag, pattern in THREAT_PATTERNS:
                if pattern.search(fragment.decoded_snippet):
                    # Replace encoded snippet in raw text
                    replacement = f"[NEUTRALIZED_ENCODED_{tag}]"
                    if fragment.encoded_snippet in neutralized:
                        neutralized = neutralized.replace(fragment.encoded_snippet, replacement)

        # 4. Handle nested or layered encoding where intermediate fragment forms may differ from raw text
        if "NESTED_ENCODING_DETECTED" in detected_flags or "ENCODED_PAYLOAD_DETECTED" in detected_flags:
            for tag, pattern in THREAT_PATTERNS:
                if pattern.search(dec_res.final_text):
                    replacement = f"[NEUTRALIZED_ENCODED_{tag}]"
                    if "%" in neutralized:
                        neutralized = re.sub(r"(?:%[0-9a-fA-F]{2})+[^ \t\r\n]*", replacement, neutralized)
                    for fragment in dec_res.fragments:
                        if fragment.encoded_snippet in neutralized:
                            neutralized = neutralized.replace(fragment.encoded_snippet, replacement)

        # 5. Neutralize plaintext threat patterns
        for tag, pattern in THREAT_PATTERNS:
            def replace_with_redacted(_match):
                return f"[NEUTRALIZED_{tag}]"

            neutralized = pattern.sub(replace_with_redacted, neutralized)

        # 6. Neutralize Unicode homoglyph and obfuscated variant injections
        for variant in dec_res.normalized_inspection_variants:
            for tag, pattern in THREAT_PATTERNS:
                if pattern.search(variant):
                    if f"[NEUTRALIZED_{tag}]" not in neutralized and f"[NEUTRALIZED_ENCODED_{tag}]" not in neutralized:
                        neutralized = f"[NEUTRALIZED_OBFUSCATED_{tag}]"
                        break
            if neutralized.startswith("[NEUTRALIZED_OBFUSCATED_"):
                break

        # 7. Defang active HTML/markdown, ChatML, and tool injection syntax
        neutralized = (
            neutralized.replace("<script>", "&lt;script&gt;")
            .replace("</script>", "&lt;/script&gt;")
            .replace("</operational_evidence>", "&lt;/operational_evidence&gt;")
            .replace("<|im_start|>", "[NEUTRALIZED_CHATML_START]")
            .replace("<|im_end|>", "[NEUTRALIZED_CHATML_END]")
        )
        neutralized = re.sub(
            r"(?i)<\s*/?\s*(?:tool[\s_]*call|function[\s_]*calls?|tool[\s_]*response|tool[\s_]*use)[^>]*>",
            "[NEUTRALIZED_TOOL_CALL]",
            neutralized,
        )
        # Defang active markdown image exfiltration: ![alt](url) -> [NEUTRALIZED_MARKDOWN_EXFIL]
        neutralized = re.sub(r"!\[[^\]]*\]\((?:https?:)?//[^\)]+\)", "[NEUTRALIZED_MARKDOWN_EXFIL]", neutralized)
        # Defang template syntax ${...} and {{...}} -> [NEUTRALIZED_TEMPLATE_SYNTAX]
        neutralized = re.sub(r"\$\{jndi:[^\}]+\}", "[NEUTRALIZED_JNDI_INJECTION]", neutralized)
        neutralized = re.sub(r"\{\{system\.[^\}]+\}\}", "[NEUTRALIZED_TEMPLATE_SYNTAX]", neutralized)
        neutralized = re.sub(r"\$\{[A-Za-z0-9_]+\}", "[NEUTRALIZED_VARIABLE_INTERPOLATION]", neutralized)
        return neutralized

    def sandbox_chunk(self, chunk: KnowledgeChunk) -> Tuple[str, List[str]]:
        """Wrap knowledge chunk in an explicit non-executable data container with security metadata."""
        flags = self.scan_content(chunk.content)
        sanitized_content = self.neutralize_content(chunk.content, flags) if flags else chunk.content

        # Strict structural sandboxing
        sandboxed_xml = (
            f'<operational_evidence id="{chunk.chunk_id}" doc="{chunk.doc_id}" domain="{chunk.network_domain}">\n'
            f'<section>{html.escape(chunk.section_name)}</section>\n'
            f'<content>\n{sanitized_content}\n</content>\n'
            f'</operational_evidence>'
        )

        return sandboxed_xml, flags


# Allowed read-only operational tools for M5 decision support
ALLOWED_READ_ONLY_TOOLS: Set[str] = {
    "retrieve_telemetry",
    "query_alarm_cluster",
    "get_topology_neighbors",
    "get_downstream_blast_radius",
    "search_historical_sops",
    "get_incident_record",
    "generate_hypotheses",
    "generate_recommendations",
    "submit_human_review",
}

# Explicitly prohibited mutative or command execution tools
PROHIBITED_MUTATIVE_TOOLS: Set[str] = {
    "execute_bash_command",
    "ssh_connect",
    "modify_element_config",
    "restart_network_element",
    "close_ticket",
    "send_customer_notification",
    "post_production_api_mutation",
    "drop_database_table",
}


class ToolExecutionGuard:
    """Enforces read-only safety boundary and blocks any autonomous mutation or command execution."""

    def __init__(self, allowed_tools: Set[str] = ALLOWED_READ_ONLY_TOOLS):
        self.allowed_tools = allowed_tools

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool is in strictly allowed read-only whitelist."""
        return tool_name in self.allowed_tools

    def validate_tool_invocation(self, tool_name: str, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate tool invocation against read-only policy.

        Returns:
            Tuple of (is_authorized, reason_string).
        """
        if tool_name in PROHIBITED_MUTATIVE_TOOLS:
            return False, f"CRITICAL: Tool '{tool_name}' is explicitly prohibited by M5 Read-Only Policy."

        if tool_name not in self.allowed_tools:
            return False, f"DENIED: Tool '{tool_name}' is not in M5 read-only allowlist."

        # Parameter safety checks: reject dangerous command strings or code execution primitives
        param_str = str(parameters).lower()
        dangerous_primitives = ["rm -rf", "drop database", "reboot -f", "shutdown", "__import__", "subprocess", "os.system"]
        for dang in dangerous_primitives:
            if dang in param_str:
                return False, f"DENIED: Dangerous parameter primitive '{dang}' detected in tool arguments."

        return True, "AUTHORIZED: Read-only tool permitted."

    def sandbox_tool_output(self, tool_name: str, output_data: Any) -> str:
        """Encapsulate tool output in an explicit non-executable data container."""
        out_str = html.escape(str(output_data))
        return (
            f'<tool_data tool="{tool_name}" trust="DATA_ONLY">\n'
            f'{out_str}\n'
            f'</tool_data>'
        )


class OutputSecurityPolicyValidator:
    """Enforces application-level policy invariants on synthesized diagnostic recommendations."""

    @staticmethod
    def validate_recommendation(rec: Any) -> Any:
        """Enforces that consequential actions always require authenticated human approval and cannot be auto-executed."""
        from piis.investigation.schemas import ApprovalStatus, RecommendationRisk

        # 1. Force human approval required
        rec.human_approval_required = True

        # 2. Force approval status to PENDING_REVIEW unless cryptographically signed by reviewer
        if getattr(rec, "approval_status", None) not in (
            ApprovalStatus.PENDING_REVIEW,
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.MODIFIED,
        ):
            rec.approval_status = ApprovalStatus.PENDING_REVIEW

        # An un-reviewed recommendation MUST be PENDING_REVIEW
        if not getattr(rec, "reviewed_by", None) and rec.approval_status != ApprovalStatus.PENDING_REVIEW:
            rec.approval_status = ApprovalStatus.PENDING_REVIEW

        # 3. Maximum allowed autonomous risk tier is READ_ONLY_SAFE
        if getattr(rec, "risk_classification", None) not in (
            RecommendationRisk.READ_ONLY_SAFE,
            RecommendationRisk.LOW_OBSERVABILITY,
        ):
            rec.risk_classification = RecommendationRisk.READ_ONLY_SAFE

        return rec
