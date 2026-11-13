"""Multi-attribute metadata filtering with anti-silent omission safeguards."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from piis.knowledge.models import KnowledgeChunk
from piis.knowledge.sources import SourceType, TrustClassification


class MetadataFilter:
    """Evaluates chunk metadata against query constraints."""

    def __init__(self, allow_cross_domain_when_unspecified: bool = True):
        self.allow_cross_domain = allow_cross_domain_when_unspecified

    @staticmethod
    def _is_generation_compatible(target_gen: Optional[str], chunk_gen: Optional[str]) -> bool:
        """Check if technology generation of chunk is compatible with query."""
        if not target_gen:
            return True
        if not chunk_gen:
            # If query specifically targets legacy generations (2G, 3G, WiMAX), reject unannotated or generic chunks
            t_gen_upper = target_gen.upper()
            if any(legacy in t_gen_upper for legacy in ("2G", "GSM", "3G", "UMTS", "WIMAX")):
                return False
            return True

        t_gen = target_gen.upper().strip()
        c_gen = chunk_gen.upper().strip()

        if t_gen in ("MULTI_GEN", "ANY") or c_gen in ("MULTI_GEN", "ANY"):
            return True

        # Check for legacy vs modern generational mismatches
        if ("2G" in t_gen or "GSM" in t_gen) and not ("2G" in c_gen or "GSM" in c_gen):
            return False
        if ("3G" in t_gen or "UMTS" in t_gen) and not ("3G" in c_gen or "UMTS" in c_gen):
            return False
        if ("4G" in t_gen or "LTE" in t_gen) and not ("4G" in c_gen or "LTE" in c_gen):
            return False
        if ("5G" in t_gen or "NR" in t_gen) and ("2G" in c_gen or "3G" in c_gen):
            return False
        if "WIMAX" in t_gen and "WIMAX" not in c_gen:
            return False

        # If target is specific legacy and does not match chunk
        if any(leg in t_gen for leg in ("2G", "3G", "WIMAX")) and t_gen != c_gen:
            return False

        return True

    @staticmethod
    def _is_vendor_compatible(target_vendor: Optional[str], chunk_vendor: Optional[str]) -> bool:
        """Check if vendor specification of chunk is compatible with query.

        Remediates FIND-M5.1-003:
        - A genuinely vendor-neutral 3GPP runbook (GENERIC_3GPP, MULTI_VENDOR) is compatible
          with specific vendor incidents (e.g. ERICSSON, NOKIA) when technology matches.
        - Vendor-specific runbooks (e.g. CISCO, JUNIPER) are NOT vendor-neutral and must not match
          incompatible proprietary vendor incidents or queries requesting vendor-neutral procedures.
        - Missing metadata does not silently become proof of compatibility.
        """
        if not chunk_vendor:
            # Missing chunk vendor metadata: cannot assume compatibility
            return False

        c_vend = chunk_vendor.upper().strip()

        # If query has no vendor constraint, allow any chunk
        if not target_vendor:
            return True

        t_vend = target_vendor.upper().strip()

        # If chunk is genuinely vendor-neutral, it is compatible with vendor-tagged incidents
        if c_vend in ("GENERIC_3GPP", "MULTI_VENDOR", "ANY"):
            return True

        # If query explicitly requests vendor-neutral procedures, vendor-specific runbooks do not match
        if t_vend in ("GENERIC_3GPP", "MULTI_VENDOR", "ANY"):
            return False

        # Both are proprietary vendors: must match strictly
        return t_vend == c_vend

    def evaluate_chunk(
        self,
        chunk: KnowledgeChunk,
        target_domain: Optional[str] = None,
        involved_domains: Optional[List[str]] = None,
        allowed_source_types: Optional[List[SourceType]] = None,
        allowed_trust: Optional[List[TrustClassification]] = None,
        subsystem: Optional[str] = None,
        technology_generation: Optional[str] = None,
        vendor: Optional[str] = None,
        equipment_family: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a chunk satisfies all active filter criteria."""
        # 1. Domain constraint check
        if target_domain:
            allowed_domains = [target_domain.upper()]
            if involved_domains:
                allowed_domains.extend([d.upper() for d in involved_domains])

            chunk_dom = chunk.network_domain.upper()
            if chunk_dom not in allowed_domains:
                return False, f"Domain mismatch (expected {allowed_domains}, got {chunk_dom})"

        # 2. Source type constraint
        if allowed_source_types:
            if chunk.source_type not in allowed_source_types:
                return False, f"SourceType mismatch (expected {allowed_source_types}, got {chunk.source_type})"

        # 3. Trust classification constraint
        if allowed_trust:
            if chunk.trust_classification not in allowed_trust:
                return False, f"Trust mismatch (expected {allowed_trust}, got {chunk.trust_classification})"

        # 4. Target subsystem constraint
        if subsystem:
            subsystem_upper = subsystem.upper()
            chunk_subs = [s.upper() for s in chunk.target_subsystems]
            if chunk_subs and subsystem_upper not in chunk_subs:
                return False, f"Subsystem mismatch (expected {subsystem_upper}, got {chunk_subs})"

        # 5. Technology Generation constraint check
        if technology_generation:
            if not self._is_generation_compatible(technology_generation, chunk.technology_generation):
                return False, f"Technology generation mismatch (expected {technology_generation}, got {chunk.technology_generation})"

        # 6. Vendor constraint check
        if vendor:
            if not self._is_vendor_compatible(vendor, chunk.vendor):
                return False, f"Vendor mismatch (expected {vendor}, got {chunk.vendor})"

        # 7. Equipment Family constraint check
        if equipment_family and chunk.equipment_family:
            if equipment_family.upper() != chunk.equipment_family.upper():
                return False, f"Equipment family mismatch (expected {equipment_family}, got {chunk.equipment_family})"

        return True, None

    def filter_candidates(
        self,
        candidates: List[Tuple[KnowledgeChunk, float]],
        target_domain: Optional[str] = None,
        involved_domains: Optional[List[str]] = None,
        allowed_source_types: Optional[List[SourceType]] = None,
        allowed_trust: Optional[List[TrustClassification]] = None,
        subsystem: Optional[str] = None,
        technology_generation: Optional[str] = None,
        vendor: Optional[str] = None,
        equipment_family: Optional[str] = None,
    ) -> Tuple[List[Tuple[KnowledgeChunk, float]], int, bool, Dict[str, Any]]:
        """Filter a ranked candidate list and return (surviving_list, dropped_count, all_dropped, audit_meta)."""
        surviving: List[Tuple[KnowledgeChunk, float]] = []
        dropped_count = 0
        rejection_reasons: Dict[str, int] = {}

        for chunk, score in candidates:
            passed, reason = self.evaluate_chunk(
                chunk=chunk,
                target_domain=target_domain,
                involved_domains=involved_domains,
                allowed_source_types=allowed_source_types,
                allowed_trust=allowed_trust,
                subsystem=subsystem,
                technology_generation=technology_generation,
                vendor=vendor,
                equipment_family=equipment_family,
            )
            if passed:
                surviving.append((chunk, score))
            else:
                dropped_count += 1
                r_key = reason or "unknown_rejection"
                rejection_reasons[r_key] = rejection_reasons.get(r_key, 0) + 1

        all_dropped = (len(candidates) > 0 and len(surviving) == 0)

        audit_meta = {
            "initial_candidates": len(candidates),
            "surviving_candidates": len(surviving),
            "dropped_count": dropped_count,
            "filter_dropped_all": all_dropped,
            "rejection_reasons": rejection_reasons,
        }

        return surviving, dropped_count, all_dropped, audit_meta
