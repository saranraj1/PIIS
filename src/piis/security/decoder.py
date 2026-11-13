"""Bounded recursive decoder for multi-layer encoded and obfuscated payloads.

Remediates DEF-M4-003 by detecting and neutralizing nested URL, Base64, Hex,
and HTML entity encoded prompt injections before LLM or tool-consuming workflows.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
import html
import re
from typing import Dict, List, Set, Tuple
import unicodedata
import urllib.parse

# Unicode confusable homoglyphs mapping Cyrillic, Greek, and other script lookalikes to ASCII
UNICODE_CONFUSABLE_MAP: Dict[str, str] = {
    # Cyrillic small letters
    "\u0430": "a", "\u0431": "b", "\u0432": "v", "\u0433": "g", "\u0434": "d",
    "\u0435": "e", "\u0451": "e", "\u0436": "zh", "\u0437": "z", "\u0438": "i",
    "\u0456": "i", "\u0457": "i", "\u0439": "j", "\u0458": "j", "\u043a": "k",
    "\u043b": "l", "\u043c": "m", "\u043d": "n", "\u043e": "o", "\u043f": "p",
    "\u0440": "p", "\u0441": "c", "\u0442": "t", "\u0443": "y", "\u0444": "f",
    "\u0445": "x", "\u0446": "ts", "\u0447": "ch", "\u0448": "sh", "\u0449": "shch",
    "\u044b": "y", "\u044d": "e", "\u044e": "yu", "\u044f": "ya", "\u0455": "s",
    # Cyrillic capital letters
    "\u0410": "A", "\u0412": "B", "\u0421": "C", "\u0415": "E", "\u041d": "H",
    "\u0406": "I", "\u0408": "J", "\u041a": "K", "\u041c": "M", "\u041e": "O",
    "\u0420": "P", "\u0422": "T", "\u0425": "X", "\u0423": "Y", "\u0405": "S",
    # Greek letters commonly confused with Latin
    "\u03b1": "a", "\u0391": "A", "\u03b2": "b", "\u0392": "B", "\u03b5": "e",
    "\u0395": "E", "\u03b9": "i", "\u0399": "I", "\u03ba": "k", "\u039a": "K",
    "\u03bd": "v", "\u039d": "N", "\u03bf": "o", "\u039f": "O", "\u03c1": "p",
    "\u03a1": "P", "\u03c4": "t", "\u03a4": "T", "\u03c5": "u", "\u03a5": "Y",
    "\u03c7": "x", "\u03a7": "X", "\u0396": "Z", "\u0397": "H", "\u039c": "M",
    # Cherokee lookalikes
    "\u13a0": "D", "\u13a1": "R", "\u13a2": "T", "\u13cd": "W", "\u13ef": "B", "\u13f4": "Y",
    # Tagalog lookalikes
    "\u1700": "a", "\u1701": "i", "\u1702": "u",
    # Armenian lookalikes
    "\u0561": "a", "\u0585": "o", "\u057d": "s",
}

# Regex to strip zero-width, formatting, soft-hyphen, invisible separators, and directional override characters
ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF\u00AD\u180E]")

# Combining diacritics pattern for stacked mark stripping and inspection across all Unicode blocks
COMBINING_MARKS_PATTERN = re.compile(
    r"[\u0300-\u036f\u0483-\u0489\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u0610-\u061a\u064b-\u065f\u0670\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]"
)

# Bidirectional control characters pattern
BIDI_CONTROLS_PATTERN = re.compile(r"[\u200E\u200F\u202A-\u202E\u2066-\u2069]")

# Token / repeated character flood patterns
REPEATED_CHAR_FLOOD_PATTERN = re.compile(r"(\S)\1{49,}")
REPEATED_TOKEN_FLOOD_PATTERN = re.compile(r"((?:\S{1,8}))\1{49,}|(\b\w+\s+)\2{19,}")

# Vietnamese orthography definitions for NFKD decomposed text
VIETNAMESE_VOWELS: Set[str] = set("aAeEiIoOuUyY")
VIET_VOWEL_MODIFIERS: Set[str] = {"\u0302", "\u0306", "\u031b"}  # circumflex, breve, horn
VIET_TONE_MARKS: Set[str] = {"\u0300", "\u0301", "\u0309", "\u0303", "\u0323"}  # grave, acute, hook, tilde, dot below


def is_legitimate_vietnamese_sequence(base_char: str, combining_marks: str) -> bool:
    """Return True if base_char and combining_marks form valid Vietnamese orthography under NFKD."""
    if base_char not in VIETNAMESE_VOWELS:
        return False
    if len(combining_marks) != 2:
        return False
    marks_set = set(combining_marks)
    has_modifier = len(marks_set.intersection(VIET_VOWEL_MODIFIERS)) == 1
    has_tone = len(marks_set.intersection(VIET_TONE_MARKS)) == 1
    return has_modifier and has_tone

# Mathematical alphanumeric symbols pattern
MATH_ALPHANUMERIC_PATTERN = re.compile(r"[\U0001D400-\U0001D7FF]")

# Zero-width / soft-hyphen within word pattern (indicates evasive token-splitting)
ZERO_WIDTH_IN_WORD_PATTERN = re.compile(r"[\w][\u200B-\u200F\u202A-\u202E\uFEFF\u00AD]+[\w]")

# Unusual whitespace characters (non-breaking, narrow, quad/em spaces, ideographic space)
UNUSUAL_WHITESPACE = re.compile(r"[\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]")

# Single space between individual alphanumeric characters (evasive token spacing, e.g. "I g n o r e")
SPACED_LETTER_PATTERN = re.compile(r"(?<=\b\w)\s(?=\w\b)")

# Leetspeak substitution translation map for inspection variants
LEET_TRANSLATION_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

# Malformed encoding patterns
MALFORMED_B64_PATTERN = re.compile(r"[A-Za-z0-9+/]{4,}={3,}|[A-Za-z0-9+/]{2,}={1,2}[A-Za-z0-9+/]+")
MALFORMED_HEX_PATTERN = re.compile(r"\\x(?![0-9a-fA-F]{2})[0-9a-zA-Z]{1,2}")
MALFORMED_URL_PATTERN = re.compile(r"%(?![0-9a-fA-F]{2})[0-9a-zA-Z]{1,2}")
MALFORMED_HTML_PATTERN = re.compile(r"&#x(?![0-9a-fA-F]+;)[0-9a-zA-Z]+;")


@dataclass
class DecodedFragment:
    """Individual decoded substring fragment with encoding type and depth."""
    encoding_type: str
    encoded_snippet: str
    decoded_snippet: str
    depth: int


@dataclass
class DecodingResult:
    """Complete audit record of recursive decoding passes."""
    original_text: str
    final_text: str
    depth_reached: int
    layers: List[str] = field(default_factory=list)
    fragments: List[DecodedFragment] = field(default_factory=list)
    security_flags: List[str] = field(default_factory=list)
    normalized_inspection_variants: List[str] = field(default_factory=list)
    is_nested: bool = False
    is_malformed: bool = False
    has_homoglyphs: bool = False

    def all_text_variants(self) -> List[str]:
        """Return unique text variants across all layers and normalized forms for multi-layer pattern scanning."""
        seen: Set[str] = set()
        variants: List[str] = []
        for text in [self.original_text, self.final_text] + self.layers + self.normalized_inspection_variants:
            if text and text not in seen:
                seen.add(text)
                variants.append(text)
        return variants


class BoundedRecursiveDecoder:
    """Safely and recursively decodes multi-layer encoded text with bounded depth and resource guards."""

    # Regex to find candidate Base64 strings (minimum 8 chars, valid b64 alphabet with padding)
    B64_PATTERN = re.compile(r"(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{8,}={0,2})(?![A-Za-z0-9+/=])")

    # Regex to detect hex escapes like \x61\x62 or 0x61, 0x62
    HEX_ESCAPE_PATTERN = re.compile(r"(?:\\x[0-9a-fA-F]{2})+")
    HEX_LITERAL_PATTERN = re.compile(r"\b0x[0-9a-fA-F]{2}(?:\s*,\s*0x[0-9a-fA-F]{2})+\b")

    def __init__(
        self,
        max_depth: int = 5,
        max_length: int = 50_000,
        min_b64_len: int = 8,
    ):
        """Initialize bounded decoder.

        Args:
            max_depth: Maximum recursion depth to prevent CPU denial of service.
            max_length: Maximum decoded character expansion limit to prevent decompression bombs.
            min_b64_len: Minimum candidate Base64 string length to avoid false positives on words.
        """
        self.max_depth = max_depth
        self.max_length = max_length
        self.min_b64_len = min_b64_len

    def decode(self, text: str) -> DecodingResult:
        """Recursively decode text until quiescence or resource limits are reached."""
        if not text:
            return DecodingResult(original_text="", final_text="", depth_reached=0)

        current_text = text
        layers: List[str] = [current_text]
        all_fragments: List[DecodedFragment] = []
        flags: List[str] = []
        is_nested = False
        is_malformed = False

        # Pre-check: Buffer expansion / size limit guard (DEF-M4-003)
        if len(text) > self.max_length:
            flags.append("EXPANSION_LIMIT_EXCEEDED")
            is_malformed = True
            if REPEATED_CHAR_FLOOD_PATTERN.search(text) or REPEATED_TOKEN_FLOOD_PATTERN.search(text):
                flags.append("TOKEN_FLOOD_DETECTED")
            return DecodingResult(
                original_text=text,
                final_text=text[: self.max_length],
                depth_reached=0,
                security_flags=flags,
                is_malformed=is_malformed,
            )

        # Pre-check: Malformed encoding pattern detection
        if (
            ("=" in text and MALFORMED_B64_PATTERN.search(text))
            or ("\\x" in text and MALFORMED_HEX_PATTERN.search(text))
            or ("%" in text and MALFORMED_URL_PATTERN.search(text))
            or ("&#x" in text and MALFORMED_HTML_PATTERN.search(text))
        ):
            is_malformed = True
            flags.append("MALFORMED_ENCODING_DETECTED")

        if BIDI_CONTROLS_PATTERN.search(text):
            flags.append("BIDI_CONTROL_DETECTED")

        if REPEATED_CHAR_FLOOD_PATTERN.search(text) or REPEATED_TOKEN_FLOOD_PATTERN.search(text):
            flags.append("TOKEN_FLOOD_DETECTED")

        # Pre-check: Unicode homoglyphs and normalization variants
        norm_variants, has_homoglyphs = self.normalize_unicode_variants(text)
        if has_homoglyphs:
            flags.append("UNICODE_HOMOGLYPH_DETECTED")

        for depth in range(1, self.max_depth + 1):
            if len(current_text) > self.max_length:
                flags.append("EXPANSION_LIMIT_EXCEEDED")
                is_malformed = True
                break

            changed = False
            new_text = current_text

            # 1. HTML Entities Decoding (&lt;, &#x2f;, &quot;)
            if "&" in new_text and (";" in new_text):
                try:
                    unescaped_html = html.unescape(new_text)
                    if unescaped_html != new_text:
                        all_fragments.append(
                            DecodedFragment(
                                encoding_type="HTML_ENTITY",
                                encoded_snippet=new_text[:80],
                                decoded_snippet=unescaped_html[:80],
                                depth=depth,
                            )
                        )
                        new_text = unescaped_html
                        changed = True
                except Exception:
                    is_malformed = True
                    flags.append("MALFORMED_HTML_ENTITY")

            # 2. URL Percent-Encoding Decoding (%20, %2f, %2e%2e)
            if not changed and "%" in new_text:
                try:
                    unquoted_url = urllib.parse.unquote(new_text)
                    if unquoted_url != new_text:
                        all_fragments.append(
                            DecodedFragment(
                                encoding_type="URL_PERCENT",
                                encoded_snippet=new_text[:80],
                                decoded_snippet=unquoted_url[:80],
                                depth=depth,
                            )
                        )
                        new_text = unquoted_url
                        changed = True
                except Exception:
                    is_malformed = True
                    flags.append("MALFORMED_URL_ENCODING")

            # 3. Hexadecimal Escape Decoding (\x61\x62\x63)
            if not changed:
                new_text, hex_changed, hex_frags = self._decode_hex_escapes(new_text, depth)
                if hex_changed:
                    changed = True
                    all_fragments.extend(hex_frags)

            # 4. Embedded Base64 Decoding
            if not changed:
                new_text, b64_changed, b64_frags, b64_malformed = self._decode_base64_candidates(
                    new_text, depth
                )
                if b64_changed:
                    changed = True
                    all_fragments.extend(b64_frags)
                if b64_malformed:
                    is_malformed = True
                    flags.append("MALFORMED_BASE64_DETECTED")

            if not changed:
                # Quiescence reached: text did not change in this round
                break

            layers.append(new_text)
            current_text = new_text

            # Check normalized variants for decoded layer
            layer_variants, layer_homo = self.normalize_unicode_variants(new_text)
            for lv in layer_variants:
                if lv not in norm_variants:
                    norm_variants.append(lv)
            if layer_homo:
                has_homoglyphs = True

            if depth > 1:
                is_nested = True

        else:
            # Loop ended without break -> reached max_depth
            flags.append("MAX_DECODING_DEPTH_EXCEEDED")

        if is_nested:
            flags.append("NESTED_ENCODING_DETECTED")

        return DecodingResult(
            original_text=text,
            final_text=current_text,
            depth_reached=len(layers) - 1,
            layers=layers,
            fragments=all_fragments,
            security_flags=flags,
            normalized_inspection_variants=norm_variants,
            is_nested=is_nested,
            is_malformed=is_malformed,
            has_homoglyphs=has_homoglyphs,
        )

    def normalize_unicode_variants(self, text: str) -> Tuple[List[str], bool]:
        """Generate normalized inspection variants without modifying original text.

        Remediates FIND-M5.1-002 and FIND-M5.1-004:
        - Separates Unicode normalization from threat classification.
        - Ordinary NFKD decomposition on European diacritics (ä, ö, ü, é, è, ñ, å) does NOT flag homoglyphs.
        - Detects mixed-script confusables (Cyrillic/Greek lookalikes mixed with Latin letters in words).
        - Detects fullwidth Latin and mathematical alphanumeric symbols.
        - Detects zero-width and soft-hyphen characters placed inside words to evade keyword boundaries.
        - Generates diacritic-stripped variants so stacked combining marks cannot mask malicious commands.
        - Distinguishes legitimate pure non-Latin scripts (Cyrillic, Arabic, Greek, CJK) from injection attacks.
        """
        variants: List[str] = []
        has_homoglyphs = False

        if not text:
            return variants, False

        # 1. Zero-width character & soft-hyphen inspection
        stripped = ZERO_WIDTH_CHARS.sub("", text)
        if stripped != text:
            variants.append(stripped)
            # Only flag as homoglyph/obfuscation if zero-width char is inside an alphanumeric word
            if ZERO_WIDTH_IN_WORD_PATTERN.search(text):
                has_homoglyphs = True
        else:
            stripped = text

        # 1b. Directional override (bidi) safe display inspection variant
        if BIDI_CONTROLS_PATTERN.search(text):
            bidi_escaped = BIDI_CONTROLS_PATTERN.sub("[BIDI_CTRL]", text)
            if bidi_escaped not in variants:
                variants.append(bidi_escaped)
            # Reversal inspection for right-to-left override attacks
            reversed_text = stripped[::-1]
            if reversed_text not in variants:
                variants.append(reversed_text)

        # 1c. Unusual whitespace normalization (non-breaking spaces, ideographic space)
        if UNUSUAL_WHITESPACE.search(stripped):
            ws_normalized = UNUSUAL_WHITESPACE.sub(" ", stripped)
            if ws_normalized not in variants:
                variants.append(ws_normalized)
        else:
            ws_normalized = stripped

        # 1d. Spaced character collapse for inspection (e.g. "I g n o r e" -> "Ignore")
        if SPACED_LETTER_PATTERN.search(ws_normalized):
            unspaced = SPACED_LETTER_PATTERN.sub("", ws_normalized)
            if unspaced not in variants:
                variants.append(unspaced)

        # 1e. Leetspeak substitution decoding for inspection
        deleet = ws_normalized.translate(LEET_TRANSLATION_MAP)
        if deleet != ws_normalized and deleet not in variants:
            variants.append(deleet)

        # 1f. Token / character flood collapsing for inspection
        if REPEATED_CHAR_FLOOD_PATTERN.search(stripped) or REPEATED_TOKEN_FLOOD_PATTERN.search(stripped):
            collapsed = REPEATED_CHAR_FLOOD_PATTERN.sub(r"\1\1\1\1\1\1\1\1\1\1", stripped)
            collapsed = REPEATED_TOKEN_FLOOD_PATTERN.sub(r"\1\1\1\1\1\1\1\1\1\1", collapsed)
            if collapsed not in variants:
                variants.append(collapsed)

        # 2. NFKD Unicode normalization (expands fullwidth, accents, font variants)
        nfkd = unicodedata.normalize("NFKD", stripped)
        if nfkd != stripped and nfkd not in variants:
            variants.append(nfkd)
            # NOTE: NFKD change alone does NOT flag homoglyphs (fixes FIND-M5.1-002)

        # 3. Stacked combining marks inspection & stripping across all Unicode blocks
        diacritic_stripped = COMBINING_MARKS_PATTERN.sub("", nfkd)
        if diacritic_stripped != nfkd and diacritic_stripped not in variants:
            variants.append(diacritic_stripped)
            # Detect stacked combining marks across expanded Unicode blocks, exempting legitimate Vietnamese orthography
            for match in re.finditer(
                r"[a-zA-Z][\u0300-\u036f\u0483-\u0489\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u0610-\u061a\u064b-\u065f\u0670\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]{2,}",
                nfkd,
            ):
                match_str = match.group(0)
                base_char = match_str[0]
                marks = match_str[1:]
                if not is_legitimate_vietnamese_sequence(base_char, marks):
                    has_homoglyphs = True
                    break

        # 4. Fullwidth Latin character detection (A-Z: \uff21-\uff3a, a-z: \uff41-\uff5a)
        if any(("\uff21" <= c <= "\uff3a") or ("\uff41" <= c <= "\uff5a") for c in text):
            has_homoglyphs = True

        # 5. Mathematical alphanumeric symbol detection
        if MATH_ALPHANUMERIC_PATTERN.search(text):
            has_homoglyphs = True

        # 6. Cyrillic / Greek confusable character translation & mixed-script detection
        confusable_translated = []
        confusable_found = False
        for ch in nfkd:
            if ch in UNICODE_CONFUSABLE_MAP:
                confusable_translated.append(UNICODE_CONFUSABLE_MAP[ch])
                confusable_found = True
            else:
                confusable_translated.append(ch)

        if confusable_found:
            trans_str = "".join(confusable_translated)
            if trans_str not in variants:
                variants.append(trans_str)
            if SPACED_LETTER_PATTERN.search(trans_str):
                trans_unspaced = SPACED_LETTER_PATTERN.sub("", trans_str)
                if trans_unspaced not in variants:
                    variants.append(trans_unspaced)
            trans_deleet = trans_str.translate(LEET_TRANSLATION_MAP)
            if trans_deleet != trans_str and trans_deleet not in variants:
                variants.append(trans_deleet)

            # Mixed-script detection: check if individual tokens mix Latin and Cyrillic/Greek confusables
            # or if confusable translation on a token unmasks a sensitive command word
            tokens = re.findall(r"\b[\w\u0400-\u04ff\u0370-\u03ff]+\b", nfkd)
            sensitive_keywords = {
                "ignore", "system", "override", "prompt", "admin", "bypass", "sudo", "eval", "instruction", "developer"
            }

            for tok in tokens:
                has_latin_in_tok = any("a" <= c.lower() <= "z" for c in tok)
                has_confusable_in_tok = any(c in UNICODE_CONFUSABLE_MAP for c in tok)

                if has_latin_in_tok and has_confusable_in_tok:
                    # Token combines Latin letters with Cyrillic/Greek lookalikes (e.g. "рrompt" or "ignоre")
                    has_homoglyphs = True
                    break

                # If token is pure confusable script, check if its translation matches a sensitive keyword
                # in a multilingual or mixed context
                if has_confusable_in_tok and not has_latin_in_tok:
                    trans_tok = "".join(UNICODE_CONFUSABLE_MAP.get(c, c) for c in tok).lower()
                    if trans_tok in sensitive_keywords and any("a" <= c.lower() <= "z" for c in text):
                        has_homoglyphs = True
                        break

        return variants, has_homoglyphs

    def _decode_hex_escapes(self, text: str, depth: int) -> Tuple[str, bool, List[DecodedFragment]]:
        """Find and decode \\xNN hexadecimal escape strings."""
        fragments: List[DecodedFragment] = []
        changed = False

        def replace_hex(match: re.Match) -> str:
            nonlocal changed
            raw = match.group(0)
            try:
                # Strip \x and convert to bytes
                hex_digits = raw.replace("\\x", "")
                decoded_bytes = bytes.fromhex(hex_digits)
                decoded_str = decoded_bytes.decode("utf-8", errors="replace")
                if self._is_mostly_printable(decoded_str):
                    changed = True
                    fragments.append(
                        DecodedFragment(
                            encoding_type="HEX_ESCAPE",
                            encoded_snippet=raw,
                            decoded_snippet=decoded_str,
                            depth=depth,
                        )
                    )
                    return decoded_str
            except Exception:
                pass
            return raw

        result = self.HEX_ESCAPE_PATTERN.sub(replace_hex, text)
        return result, changed, fragments

    def _decode_base64_candidates(
        self, text: str, depth: int
    ) -> Tuple[str, bool, List[DecodedFragment], bool]:
        """Find candidate Base64 substrings and decode them safely if they contain printable text."""
        fragments: List[DecodedFragment] = []
        changed = False
        malformed = False

        def replace_b64(match: re.Match) -> str:
            nonlocal changed, malformed
            candidate = match.group(1)

            # Skip candidate if too short
            if len(candidate) < self.min_b64_len:
                return candidate

            # Base64 padding correction if needed
            pad_needed = (4 - len(candidate) % 4) % 4
            candidate_padded = candidate + ("=" * pad_needed)

            try:
                decoded_bytes = base64.b64decode(candidate_padded, validate=True)
                # Decode to string (UTF-8 or ASCII)
                decoded_str = decoded_bytes.decode("utf-8")
                # Require that decoded text contains printable characters and at least one whitespace, symbol, or word
                if self._is_plausible_plain_text(decoded_str):
                    changed = True
                    fragments.append(
                        DecodedFragment(
                            encoding_type="BASE64",
                            encoded_snippet=candidate,
                            decoded_snippet=decoded_str,
                            depth=depth,
                        )
                    )
                    return decoded_str
            except (binascii.Error, UnicodeDecodeError, ValueError):
                # Check if it was formatted like deliberate base64 with '=' padding
                if "=" in candidate:
                    malformed = True
            return candidate

        result = self.B64_PATTERN.sub(replace_b64, text)
        return result, changed, fragments, malformed

    @staticmethod
    def _is_mostly_printable(s: str) -> bool:
        """Check if string consists almost entirely of printable characters."""
        if not s:
            return False
        printable_count = sum(1 for c in s if c.isprintable() or c in "\r\n\t")
        return (printable_count / len(s)) >= 0.85

    @staticmethod
    def _is_plausible_plain_text(s: str) -> bool:
        """Verify that decoded string looks like human language or command text rather than arbitrary binary."""
        if not s or len(s) < 3:
            return False
        # Disallow strings with null bytes or unprintable control chars
        for ch in s:
            if ord(ch) < 32 and ch not in "\r\n\t":
                return False
        # Must have letters or digits
        has_alphanumeric = any(c.isalnum() for c in s)
        return has_alphanumeric
