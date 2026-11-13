"""Unit tests for dense bi-encoder vector index."""

from __future__ import annotations

from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.dense import DenseBiEncoderIndex


def test_dense_index_build_and_query_fallback():
    _, chunks = build_knowledge_base()

    # Test with force_local_fallback=True to guarantee local deterministic behavior
    dense = DenseBiEncoderIndex(dimension=64, force_local_fallback=True)
    dense.build_index(chunks)

    meta = dense.get_metadata()
    assert meta["total_vectors"] == len(chunks)
    assert meta["dimension"] == 64
    assert dense.index_fingerprint != ""

    # Query for optical fiber cut
    results = dense.query("fiber cut optical power broken cable", top_k=3)
    assert len(results) > 0

    top_chunk, score = results[0]
    assert score >= 0.0
    # Optical fiber SOP should score highly
    assert any("FIBER" in c.doc_id for c, _ in results)


def test_dense_index_empty_corpus():
    dense = DenseBiEncoderIndex(dimension=32, force_local_fallback=True)
    dense.build_index([])
    assert dense.query("anything") == []
