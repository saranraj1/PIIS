"""Unit tests for Reciprocal Rank Fusion."""

from __future__ import annotations

from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.fusion import ReciprocalRankFusion


def test_reciprocal_rank_fusion_combines_rankings():
    _, chunks = build_knowledge_base()
    c1, c2, c3 = chunks[0], chunks[1], chunks[2]

    # BM25 ranks: c1 (rank 1), c2 (rank 2)
    bm25_res = [(c1, 10.5), (c2, 8.2)]
    # Dense ranks: c2 (rank 1), c3 (rank 2)
    dense_res = [(c2, 0.95), (c3, 0.88)]

    rrf = ReciprocalRankFusion(k=60, weight_bm25=0.5, weight_dense=0.5)
    fused = rrf.fuse(bm25_res, dense_res, top_k=3)

    assert len(fused) == 3
    # c2 appears in both lists, so its reciprocal rank sum is higher:
    # c2 score = 0.5/(60+2) + 0.5/(60+1) = 0.5/62 + 0.5/61 ~= 0.00806 + 0.00819 = 0.01625
    # c1 score = 0.5/(60+1) ~= 0.00819
    # c3 score = 0.5/(60+2) ~= 0.00806
    top_chunk = fused[0]["chunk"]
    assert top_chunk.chunk_id == c2.chunk_id
    assert fused[0]["fused_rank"] == 1
    assert fused[0]["calibrated_confidence"] > 0.0
