"""Natural language evidence extractor for support-level policy routing.

Decoupled from synthetic scenario IDs and generator internals.
Extracts operational routing facts strictly from prediction-time text and metadata.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from piis.policies.routing import RoutingEvidence


class NaturalLanguageEvidenceExtractor:
    """Extracts policy evidence facts from incident text without scenario ID shortcuts."""

    # Regex patterns for operational indicators
    SOP_PATTERN = re.compile(r"\b(SOP-[A-Z0-9-]+|runbook|standard operating procedure)\b", re.IGNORECASE)
    ADVANCED_DIAG_PATTERN = re.compile(
        r"\b(vswr|otdr|spectrum analyzer|packet capture|dpdk|optical power|attenuation|framing errors|physical RF)\b",
        re.IGNORECASE,
    )
    SPECIALIST_PATTERN = re.compile(
        r"\b(vendor|third-party|specialist|fiber splice|cable replacement|firmware patch|hardware chassis)\b",
        re.IGNORECASE,
    )
    NEGATIVE_PATTERN = re.compile(
        r"\b(nominal|diurnal|routine|transient|below threshold|self-clearing|normal boundary|normal operating)\b",
        re.IGNORECASE,
    )

    def extract_evidence(self, incident: Dict[str, Any]) -> RoutingEvidence:
        """Extract policy evidence facts from ticket text and prediction-time attributes."""
        title = str(incident.get("title") or "")
        desc = str(incident.get("description") or "")
        meta = incident.get("metadata") or {}
        combined_text = f"{title}. {desc}"

        # 1. Negative control or insufficient evidence check
        is_negative = bool(
            meta.get("is_negative_control")
            or meta.get("negative_control")
            or self.NEGATIVE_PATTERN.search(combined_text)
        )
        if is_negative:
            return RoutingEvidence(
                evidence_sufficient=False,
                insufficient_evidence=True,
            )

        # 2. Extract operational flags from text and metadata
        has_runbook = bool(meta.get("runbook_available") or self.SOP_PATTERN.search(combined_text))
        requires_specialist = bool(meta.get("requires_specialist") or self.SPECIALIST_PATTERN.search(combined_text))
        requires_advanced = bool(meta.get("requires_advanced_diag") or self.ADVANCED_DIAG_PATTERN.search(combined_text))

        # Operational precedence: Specialist (L3) > Advanced Diagnostics (L2) > Standard L1 SOP
        return RoutingEvidence(
            known_issue_match=has_runbook and not requires_advanced and not requires_specialist,
            approved_runbook_available=has_runbook and not requires_advanced and not requires_specialist,
            required_permissions_available=has_runbook and not requires_advanced and not requires_specialist,
            advanced_diagnostics_required=requires_advanced and not requires_specialist,
            specialist_dependency=requires_specialist,
            evidence_sufficient=True,
            insufficient_evidence=False,
        )
