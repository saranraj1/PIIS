"""Telecom-aware tokenizer preserving technical acronyms, alarm codes, and 3GPP terms."""

from __future__ import annotations

import re
from typing import List, Set

# Standard English stopwords (excluding telecom collisions like 'up', 'down', 'core', 'on', 'off')
STANDARD_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "could", "did", "do", "does", "doing", "during", "each", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
    "yours", "yourself", "yourselves",
}

# Regex pattern matching telecom tokens in priority order:
# 1. Hex codes: 0x80040111, 0x000F
# 2. Hyphenated / underscored technical identifiers: ALM-RAN-VSWR, LOS_OPTICAL_FAIL
# 3. 3GPP interfaces, versions & element codes: gNodeB, eNodeB, N1, N2, N3, N4, S1-U, Xn-C
# 4. Standard alphabetic words (length >= 2)
TELECOM_TOKEN_REGEX = re.compile(
    r"\b0x[0-9a-fA-F]+\b|"
    r"\b[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b|"
    r"\b[a-zA-Z]+[0-9]+(?:-[a-zA-Z0-9]+)?\b|"
    r"\b[0-9]+[a-zA-Z]+\b|"
    r"\b[A-Za-z]{2,}\b"
)


class TelecomTokenizer:
    """Specialized tokenizer designed for telecom operational text and alarm telemetry."""

    def __init__(self, filter_stopwords: bool = True, lowercase: bool = True):
        self.filter_stopwords = filter_stopwords
        self.lowercase = lowercase

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into preserved telecom symbols and keywords."""
        if not text:
            return []

        raw_matches = TELECOM_TOKEN_REGEX.findall(text)
        tokens: List[str] = []

        for m in raw_matches:
            token = m.strip()
            # If hexadecimal, keep case as lowercase for normalization
            if token.startswith("0x") or token.startswith("0X"):
                token = token.lower()
            elif self.lowercase:
                # Keep uppercase if it's an all-caps acronym or hyphenated alarm code
                # But fold standard words to lowercase
                if "-" in token or "_" in token:
                    token = token.upper()
                elif token.isupper() and len(token) <= 5:
                    # Keep short acronyms uppercase: VSWR, BLER, MCS, RSRP, UPF, AMF
                    pass
                else:
                    token = token.lower()

            if self.filter_stopwords and token.lower() in STANDARD_STOPWORDS:
                continue

            tokens.append(token)

        return tokens
