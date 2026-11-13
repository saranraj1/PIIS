"""Reciprocal Rank Fusion (RRF) for combining lexical and dense retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from piis.knowledge.models import KnowledgeChunk


class ReciprocalRankFusion:
    """Fuses multi-modal search rankings without requiring score normalization calibration."""

    def __init__(
        self,
        k: int = 60,
        weight_bm25: float = 0.5,
        weight_dense: float = 0.5,
    ):
        self.k = k
        self.weight_bm25 = weight_bm25
        self.weight_dense = weight_dense

    def fuse(
        self,
        bm25_results: List[Tuple[KnowledgeChunk, float]],
        dense_results: List[Tuple[KnowledgeChunk, float]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Combine ranked lists using RRF formula: sum(w / (k + rank))."""
        chunk_map: Dict[str, KnowledgeChunk] = {}
        rrf_scores: Dict[str, float] = {}
        raw_bm25: Dict[str, float] = {}
        raw_dense: Dict[str, float] = {}
        ranks_bm25: Dict[str, int] = {}
        ranks_dense: Dict[str, int] = {}

        # 1. Process BM25 rankings
        for rank_1b, (chunk, score) in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            raw_bm25[cid] = score
            ranks_bm25[cid] = rank_1b
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (self.weight_bm25 / (self.k + rank_1b))

        # 2. Process Dense rankings
        for rank_1b, (chunk, score) in enumerate(dense_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            raw_dense[cid] = score
            ranks_dense[cid] = rank_1b
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (self.weight_dense / (self.k + rank_1b))

        if not rrf_scores:
            return []

        # 3. Sort descending by RRF score, deterministic tie-breaking by chunk_id
        sorted_candidates = sorted(
            rrf_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        max_possible_rrf = (self.weight_bm25 + self.weight_dense) / (self.k + 1)

        fused_output: List[Dict[str, Any]] = []
        for fused_rank, (cid, score) in enumerate(sorted_candidates[:top_k], start=1):
            rrf_rank_ratio = score / max_possible_rrf
            bm25_val = raw_bm25.get(cid)
            dense_val = raw_dense.get(cid)

            # Quality modulation incorporating both rank fusion and raw relevance strength
            if bm25_val is not None and dense_val is not None:
                qual_bm25 = min(1.0, bm25_val / 5.0)
                qual_dense = min(1.0, dense_val / 0.5)
                quality_factor = 0.5 * qual_bm25 + 0.5 * qual_dense
                conf_proxy = rrf_rank_ratio * quality_factor
            elif bm25_val is not None:
                qual_bm25 = min(1.0, bm25_val / 5.0)
                conf_proxy = rrf_rank_ratio * qual_bm25 * 0.75
            elif dense_val is not None:
                qual_dense = min(1.0, dense_val / 0.5)
                conf_proxy = rrf_rank_ratio * qual_dense * 0.75
            else:
                conf_proxy = rrf_rank_ratio * 0.5

            conf_proxy = min(1.0, max(0.0, conf_proxy))

            fused_output.append({
                "chunk": chunk_map[cid],
                "fused_score": round(score, 6),
                "confidence_proxy": round(conf_proxy, 4),
                "calibrated_confidence": round(conf_proxy, 4),  # Deprecated alias
                "fused_rank": fused_rank,
                "raw_bm25_score": raw_bm25.get(cid),
                "raw_dense_score": raw_dense.get(cid),
                "bm25_rank": ranks_bm25.get(cid),
                "dense_rank": ranks_dense.get(cid),
            })

        return fused_output
