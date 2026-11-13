"""Hybrid retrieval engine coordinating BM25, dense bi-encoder, RRF, and deterministic fallback."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from piis.knowledge.models import KnowledgeChunk
from piis.retrieval.bm25 import BM25OkapiIndex
from piis.retrieval.contracts import GroundedEvidence, RetrievalQuery, RetrievalResult
from piis.retrieval.dense import DenseBiEncoderIndex
from piis.retrieval.filters import MetadataFilter
from piis.retrieval.fusion import ReciprocalRankFusion
from piis.security.guardrails import RetrievalSecurityGuard

# Curated deterministic SOP rule map for Tier 3 fallback
DETERMINISTIC_SOP_MAP: Dict[str, str] = {
    "ALM-RAN-VSWR-HIGH": "SOP-RAN-VSWR-001",
    "ALM-RAN-VSWR": "SOP-RAN-VSWR-001",
    "VSWR": "SOP-RAN-VSWR-001",
    "ALM-RAN-RLF": "SOP-RAN-HANDOVER-002",
    "RADIO_LINK_FAILURE": "SOP-RAN-HANDOVER-002",
    "ALM-CORE-AMF-REG-FAIL": "SOP-5GC-AMF-001",
    "AMF-REGISTRATION-REJECT": "SOP-5GC-AMF-001",
    "ALM-CORE-UPF-BUFFER-OVERFLOW": "SOP-5GC-UPF-002",
    "UPF-BUFFER-OVERFLOW": "SOP-5GC-UPF-002",
    "ALM-TRANS-OPTICAL-LOS": "SOP-TRANS-FIBER-001",
    "OPTICAL_LOSS_OF_SIGNAL": "SOP-TRANS-FIBER-001",
    "ALM-TRANS-BGP-FLAP": "SOP-TRANS-BGP-002",
    "BGP_SESSION_DOWN": "SOP-TRANS-BGP-002",
    "ALM-SRV-SIP-503": "SOP-IMS-SIP-001",
    "SIP_503_SERVICE_UNAVAILABLE": "SOP-IMS-SIP-001",
}


class HybridRetrievalEngine:
    """Enterprise hybrid retrieval engine providing grounded evidence for operational incidents."""

    def __init__(
        self,
        bm25_index: Optional[BM25OkapiIndex] = None,
        dense_index: Optional[DenseBiEncoderIndex] = None,
        fusion_engine: Optional[ReciprocalRankFusion] = None,
        metadata_filter: Optional[MetadataFilter] = None,
        security_guard: Optional[RetrievalSecurityGuard] = None,
        confidence_threshold: float = 0.35,
        dense_timeout_ms: float = 200.0,
    ):
        self.bm25_index = bm25_index or BM25OkapiIndex()
        self.dense_index = dense_index or DenseBiEncoderIndex()
        self.fusion_engine = fusion_engine or ReciprocalRankFusion()
        self.metadata_filter = metadata_filter or MetadataFilter()
        self.security_guard = security_guard or RetrievalSecurityGuard()
        self.confidence_threshold = confidence_threshold
        self.dense_timeout_ms = dense_timeout_ms

        self._all_chunks: Dict[str, KnowledgeChunk] = {}
        self._sops_by_doc_id: Dict[str, List[KnowledgeChunk]] = {}

    def index_chunks(self, chunks: List[KnowledgeChunk]) -> None:
        """Populate both lexical and dense indices with normalized knowledge chunks."""
        self._all_chunks.clear()
        self._sops_by_doc_id.clear()

        for chunk in chunks:
            self._all_chunks[chunk.chunk_id] = chunk
            self._sops_by_doc_id.setdefault(chunk.doc_id, []).append(chunk)

        # Build lexical BM25 index
        self.bm25_index.build_index(chunks)

        # Build dense bi-encoder index
        self.dense_index.build_index(chunks)

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Execute hybrid search with metadata filtering, fallback ladder, and security guardrails."""
        start_time = time.perf_counter()
        query_id = query.query_id
        timestamp_str = datetime.now(timezone.utc).isoformat()

        # Step 0: Inbound Query Security Inspection & Defanging
        sec_check = self.security_guard.inspect_query(query.query_text)
        effective_query_text = sec_check["neutralized_text"]
        inbound_threats = sec_check["threat_types"]

        # Step 1: Execute Lexical BM25 Search
        bm25_raw = self.bm25_index.query(effective_query_text, top_k=query.top_k * 3)

        # Step 2: Execute Dense Semantic Search (with graceful timeout / exception handling)
        dense_raw: List[Tuple[KnowledgeChunk, float]] = []
        dense_available = True
        dense_error_reason: Optional[str] = None

        dense_t0 = time.perf_counter()
        try:
            dense_raw = self.dense_index.query(effective_query_text, top_k=query.top_k * 3)
            dense_duration_ms = (time.perf_counter() - dense_t0) * 1000.0
            if dense_duration_ms > self.dense_timeout_ms:
                dense_available = False
                dense_error_reason = f"Dense search timeout ({dense_duration_ms:.1f}ms > {self.dense_timeout_ms}ms)"
        except Exception as e:
            dense_available = False
            dense_error_reason = f"Dense search exception: {str(e)}"

        # Step 3: Apply Multi-Attribute Metadata Filtering to both candidate lists
        surviving_bm25, dropped_bm25, all_dropped_bm25, bm25_audit = self.metadata_filter.filter_candidates(
            candidates=bm25_raw,
            target_domain=query.target_domain,
            involved_domains=query.involved_domains,
            allowed_source_types=query.source_type_filter,
            allowed_trust=query.trust_filter,
            subsystem=query.subsystem,
            technology_generation=query.technology_generation,
            vendor=query.vendor,
            equipment_family=query.equipment_family,
        )

        surviving_dense: List[Tuple[KnowledgeChunk, float]] = []
        dropped_dense = 0
        all_dropped_dense = False
        dense_audit: Dict[str, Any] = {}

        if dense_available:
            surviving_dense, dropped_dense, all_dropped_dense, dense_audit = self.metadata_filter.filter_candidates(
                candidates=dense_raw,
                target_domain=query.target_domain,
                involved_domains=query.involved_domains,
                allowed_source_types=query.source_type_filter,
                allowed_trust=query.trust_filter,
                subsystem=query.subsystem,
                technology_generation=query.technology_generation,
                vendor=query.vendor,
                equipment_family=query.equipment_family,
            )

        # Check for Anti-Silent Omission: if filter eliminated 100% of candidates
        filter_dropped_all = (
            (len(bm25_raw) > 0 or len(dense_raw) > 0)
            and len(surviving_bm25) == 0
            and len(surviving_dense) == 0
        )

        if filter_dropped_all:
            return RetrievalResult(
                query_id=query_id,
                executed_at=timestamp_str,
                evidence_items=[],
                total_candidates_evaluated=len(bm25_raw) + len(dense_raw),
                filter_dropped_count=dropped_bm25 + dropped_dense,
                filter_dropped_all=True,
                retrieval_mode_executed="FILTER_DROPPED_ALL",
                confidence_level="NONE",
                audit_trace={
                    "bm25_rejection": bm25_audit.get("rejection_reasons"),
                    "dense_rejection": dense_audit.get("rejection_reasons"),
                    "filter_criteria": {
                        "target_domain": query.target_domain,
                        "source_type_filter": [s.value for s in query.source_type_filter] if query.source_type_filter else None,
                    },
                },
            )

        # Step 4: Tier 1 Hybrid RRF Evaluation
        fused_items: List[Dict[str, Any]] = []
        retrieval_mode = "HYBRID"
        fallback_tier: str = "TIER_1_HYBRID"
        fallback_rationale: Optional[str] = "Hybrid RRF fusion met confidence gate"

        if dense_available and surviving_dense:
            fused_items = self.fusion_engine.fuse(
                bm25_results=surviving_bm25,
                dense_results=surviving_dense,
                top_k=query.top_k,
            )
        else:
            # Tier 2 Fallback: BM25 Only
            retrieval_mode = "BM25_DEGRADED"
            fallback_tier = "TIER_2_BM25_ONLY"
            fallback_rationale = dense_error_reason or "Dense candidates unavailable after filtering"
            # Format BM25 as candidates
            for rank_1b, (chk, score) in enumerate(surviving_bm25[: query.top_k], start=1):
                fused_items.append({
                    "chunk": chk,
                    "fused_score": score,
                    "confidence_proxy": min(1.0, score / 10.0),
                    "calibrated_confidence": min(1.0, score / 10.0),
                    "fused_rank": rank_1b,
                    "raw_bm25_score": score,
                    "raw_dense_score": None,
                })

        # Step 5: Check Confidence Gate -> Fallback to Tier 3 or Tier 4 if under threshold
        max_confidence = max(
            (item.get("confidence_proxy", item.get("calibrated_confidence", 0.0)) for item in fused_items),
            default=0.0,
        )

        if max_confidence < self.confidence_threshold:
            # Attempt Tier 3: Deterministic Approved SOP Map
            matched_sop_id = self._match_deterministic_sop(query)
            if matched_sop_id and matched_sop_id in self._sops_by_doc_id:
                sop_chunks = self._sops_by_doc_id[matched_sop_id]
                retrieval_mode = "DETERMINISTIC_SOP"
                fallback_tier = "TIER_3_DETERMINISTIC_SOP"
                fallback_rationale = (
                    f"Retrieval confidence ({max_confidence:.3f} < {self.confidence_threshold:.3f}). "
                    f"Deterministic alarm match resolved to {matched_sop_id}."
                )
                fused_items = [
                    {
                        "chunk": chk,
                        "fused_score": 1.0,
                        "confidence_proxy": 0.95,
                        "calibrated_confidence": 0.95,
                        "fused_rank": idx + 1,
                        "raw_bm25_score": None,
                        "raw_dense_score": None,
                    }
                    for idx, chk in enumerate(sop_chunks[: query.top_k])
                ]
            else:
                # Tier 4 Floor: Escalate to Human Review
                retrieval_mode = "NO_CONFIDENT_MATCH"
                fallback_tier = "TIER_4_HUMAN_REVIEW"
                fallback_rationale = (
                    f"Retrieval confidence below safety threshold ({max_confidence:.3f} < {self.confidence_threshold:.3f}) "
                    "and zero deterministic SOP rules matched. Abstaining to prevent operational hallucination."
                )
                return RetrievalResult(
                    query_id=query_id,
                    executed_at=timestamp_str,
                    evidence_items=[],
                    total_candidates_evaluated=len(bm25_raw) + len(dense_raw),
                    filter_dropped_count=dropped_bm25 + dropped_dense,
                    filter_dropped_all=False,
                    retrieval_mode_executed="NO_CONFIDENT_MATCH",
                    confidence_level="NONE",
                    audit_trace={
                        "fallback_tier": fallback_tier,
                        "fallback_rationale": fallback_rationale,
                        "max_evaluated_confidence": max_confidence,
                    },
                )

        # Step 6: Construct GroundedEvidence Items and Apply Security Guardrails
        grounded_items: List[GroundedEvidence] = []
        for item in fused_items:
            chunk: KnowledgeChunk = item["chunk"]
            # Scan for adversarial instructions & sandbox
            _, sec_flags = self.security_guard.sandbox_chunk(chunk)

            grounded_items.append(
                GroundedEvidence(
                    query_id=query_id,
                    source_id=chunk.source_id,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    source_title=chunk.doc_title,
                    source_type=chunk.source_type,
                    trust_classification=chunk.trust_classification,
                    doc_version="1.0.0",
                    network_domain=chunk.network_domain,
                    technology_generation=chunk.technology_generation,
                    vendor=chunk.vendor,
                    equipment_family=chunk.equipment_family,
                    section_hierarchy=chunk.heading_hierarchy,
                    original_text=chunk.content,
                    retrieval_method=retrieval_mode,
                    raw_bm25_score=item.get("raw_bm25_score"),
                    raw_dense_score=item.get("raw_dense_score"),
                    fused_score=item["fused_score"],
                    fused_rank=item["fused_rank"],
                    confidence_proxy=item.get("confidence_proxy", item.get("calibrated_confidence", 0.0)),
                    calibrated_confidence=item.get("confidence_proxy", item.get("calibrated_confidence", 0.0)),
                    fallback_tier=fallback_tier,
                    fallback_rationale=fallback_rationale,
                    epistemic_status="HISTORICAL_EVIDENCE",
                    provenance=chunk.provenance,
                    security_flags=sec_flags,
                )
            )

        # Determine confidence level
        conf_level = "HIGH" if max_confidence >= 0.65 else ("MEDIUM" if max_confidence >= 0.40 else "LOW")
        primary_doc = grounded_items[0].doc_id if grounded_items else None
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return RetrievalResult(
            query_id=query_id,
            executed_at=timestamp_str,
            evidence_items=grounded_items,
            total_candidates_evaluated=len(bm25_raw) + len(dense_raw),
            filter_dropped_count=dropped_bm25 + dropped_dense,
            filter_dropped_all=False,
            retrieval_mode_executed=retrieval_mode,
            primary_runbook_id=primary_doc,
            confidence_level=conf_level,
            audit_trace={
                "elapsed_ms": round(elapsed_ms, 2),
                "fallback_tier": fallback_tier,
                "fallback_rationale": fallback_rationale,
                "inbound_threats_detected": inbound_threats,
                "bm25_candidates_count": len(surviving_bm25),
                "dense_candidates_count": len(surviving_dense),
                "dense_available": dense_available,
            },
        )

    def _match_deterministic_sop(self, query: RetrievalQuery) -> Optional[str]:
        """Check for exact alarm code or error keyword mapping in approved SOP table with metadata compatibility."""
        cand_sop_id = None
        # 1. Check explicit alarm codes
        for code in query.alarm_codes:
            code_upper = code.upper().strip()
            if code_upper in DETERMINISTIC_SOP_MAP:
                cand_sop_id = DETERMINISTIC_SOP_MAP[code_upper]
                break

        # 2. Check query text for exact keywords
        if not cand_sop_id:
            query_upper = query.query_text.upper()
            for key, sop_id in DETERMINISTIC_SOP_MAP.items():
                if key in query_upper:
                    cand_sop_id = sop_id
                    break

        if not cand_sop_id or cand_sop_id not in self._sops_by_doc_id:
            return None

        # Verify that candidate SOP chunks satisfy query metadata constraints
        sop_chunks = self._sops_by_doc_id[cand_sop_id]
        for chk in sop_chunks:
            passed, _ = self.metadata_filter.evaluate_chunk(
                chunk=chk,
                target_domain=query.target_domain,
                involved_domains=query.involved_domains,
                allowed_source_types=query.source_type_filter,
                allowed_trust=query.trust_filter,
                subsystem=query.subsystem,
                technology_generation=query.technology_generation,
                vendor=query.vendor,
                equipment_family=query.equipment_family,
            )
            if passed:
                return cand_sop_id

        return None
