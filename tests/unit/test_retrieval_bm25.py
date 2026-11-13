"""Unit tests for lexical BM25 Okapi index."""

from __future__ import annotations

from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.bm25 import BM25OkapiIndex


def test_bm25_exact_alarm_code_ranking():
    _, chunks = build_knowledge_base()
    index = BM25OkapiIndex()
    index.build_index(chunks)

    assert index.total_chunks == len(chunks)

    # Search for specific alarm
    results = index.query("ALM-RAN-VSWR-HIGH", top_k=3)
    assert len(results) > 0
    top_chunk, score = results[0]

    assert top_chunk.doc_id == "SOP-RAN-VSWR-001"
    assert score > 0.0


def test_bm25_empty_query_and_corpus():
    index = BM25OkapiIndex()
    index.build_index([])
    assert index.query("test query") == []

    _, chunks = build_knowledge_base()
    index.build_index(chunks)
    assert index.query("") == []
    assert index.query("   ") == []
