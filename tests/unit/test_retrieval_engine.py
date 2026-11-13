"""End-to-end unit and integration tests for HybridRetrievalEngine and fallback ladder."""

from __future__ import annotations

from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.bm25 import BM25OkapiIndex
from piis.retrieval.contracts import RetrievalQuery
from piis.retrieval.dense import DenseBiEncoderIndex
from piis.retrieval.engine import HybridRetrievalEngine
from piis.retrieval.filters import MetadataFilter
from piis.retrieval.fusion import ReciprocalRankFusion
from piis.security.guardrails import RetrievalSecurityGuard


def _create_engine() -> HybridRetrievalEngine:
    _, chunks = build_knowledge_base()
    bm25 = BM25OkapiIndex()
    # Force local deterministic dense fallback for fast, isolated test suite
    dense = DenseBiEncoderIndex(dimension=64, force_local_fallback=True)
    fusion = ReciprocalRankFusion(k=60)
    filt = MetadataFilter()
    guard = RetrievalSecurityGuard()

    engine = HybridRetrievalEngine(
        bm25_index=bm25,
        dense_index=dense,
        fusion_engine=fusion,
        metadata_filter=filt,
        security_guard=guard,
        confidence_threshold=0.35,
    )
    engine.index_chunks(chunks)
    return engine


def test_hybrid_retrieval_nominal_exact_alarm():
    engine = _create_engine()
    query = RetrievalQuery(
        query_id="Q-TEST-001",
        query_text="ALM-RAN-VSWR-HIGH antenna port return loss degradation",
        target_domain="RAN",
        top_k=3,
    )
    result = engine.retrieve(query)

    assert len(result.evidence_items) > 0
    assert result.retrieval_mode_executed == "HYBRID"
    assert result.primary_runbook_id == "SOP-RAN-VSWR-001"
    top_ev = result.evidence_items[0]
    assert top_ev.doc_id == "SOP-RAN-VSWR-001"
    assert top_ev.provenance is not None
    assert top_ev.provenance.source_record_id != ""


def test_hybrid_retrieval_tier_2_bm25_fallback():
    engine = _create_engine()
    # Simulate dense outage by setting dense_timeout_ms to 0.0
    engine.dense_timeout_ms = -1.0

    query = RetrievalQuery(
        query_id="Q-TEST-002",
        query_text="ALM-TRANS-OPTICAL-LOS loss of signal fiber break",
        target_domain="TRANSPORT",
        top_k=3,
    )
    result = engine.retrieve(query)

    assert len(result.evidence_items) > 0
    assert result.retrieval_mode_executed == "BM25_DEGRADED"
    assert any("TIER_2" in str(item.fallback_tier) for item in result.evidence_items)
    assert result.primary_runbook_id == "SOP-TRANS-FIBER-001"


def test_hybrid_retrieval_tier_3_deterministic_sop_mapping():
    engine = _create_engine()

    # Query with exact alarm code but obscure text that causes low retrieval score
    query = RetrievalQuery(
        query_id="Q-TEST-003",
        query_text="xyz non-matching obscure text",
        alarm_codes=["ALM-RAN-VSWR-HIGH"],
        top_k=3,
    )
    result = engine.retrieve(query)

    assert len(result.evidence_items) > 0
    assert result.retrieval_mode_executed == "DETERMINISTIC_SOP"
    assert result.primary_runbook_id == "SOP-RAN-VSWR-001"
    assert result.evidence_items[0].fallback_tier == "TIER_3_DETERMINISTIC_SOP"


def test_hybrid_retrieval_tier_4_human_review_abstention():
    engine = _create_engine()

    # Query about completely unknown technology not in corpus (e.g. quantum crypto key distribution)
    query = RetrievalQuery(
        query_id="Q-TEST-004",
        query_text="quantum cryptography qubit entanglement decoherence teleportation protocol",
        top_k=3,
    )
    result = engine.retrieve(query)

    # Must abstain rather than hallucinating an unrelated RAN SOP
    assert len(result.evidence_items) == 0
    assert result.retrieval_mode_executed == "NO_CONFIDENT_MATCH"
    assert result.confidence_level == "NONE"
    assert "TIER_4_HUMAN_REVIEW" in result.audit_trace["fallback_tier"]


def test_hybrid_retrieval_filter_dropped_all():
    engine = _create_engine()

    # Search for an alarm but set domain filter to completely wrong domain
    query = RetrievalQuery(
        query_id="Q-TEST-005",
        query_text="ALM-RAN-VSWR-HIGH",
        target_domain="SATELLITE_ORBITAL",  # Non-existent domain
        top_k=3,
    )
    result = engine.retrieve(query)

    assert len(result.evidence_items) == 0
    assert result.filter_dropped_all is True
    assert result.retrieval_mode_executed == "FILTER_DROPPED_ALL"
