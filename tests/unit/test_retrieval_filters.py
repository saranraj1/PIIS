"""Unit tests for metadata filtering and anti-silent-omission safeguards."""

from __future__ import annotations

from piis.knowledge.corpus import build_knowledge_base
from piis.knowledge.sources import TrustClassification
from piis.retrieval.filters import MetadataFilter


def test_metadata_filter_domain_isolation():
    _, chunks = build_knowledge_base()
    ran_chunk = next(c for c in chunks if c.network_domain == "RAN")
    core_chunk = next(c for c in chunks if c.network_domain == "5G_CORE")

    candidates = [(ran_chunk, 5.0), (core_chunk, 4.8)]
    filt = MetadataFilter()

    # Filter for RAN only
    surviving, dropped, all_dropped, audit = filt.filter_candidates(
        candidates,
        target_domain="RAN",
    )
    assert len(surviving) == 1
    assert surviving[0][0].network_domain == "RAN"
    assert dropped == 1
    assert all_dropped is False


def test_metadata_filter_anti_silent_omission():
    _, chunks = build_knowledge_base()
    ran_chunk = next(c for c in chunks if c.network_domain == "RAN")
    candidates = [(ran_chunk, 5.0)]

    filt = MetadataFilter()
    # Filter for non-existent domain: should report all_dropped=True rather than returning wrong data
    surviving, dropped, all_dropped, audit = filt.filter_candidates(
        candidates,
        target_domain="SATELLITE_ORBITAL",
    )
    assert len(surviving) == 0
    assert dropped == 1
    assert all_dropped is True
    assert audit["filter_dropped_all"] is True


def test_metadata_filter_trust_classification():
    _, chunks = build_knowledge_base()
    sop_chunk = next(c for c in chunks if c.trust_classification == TrustClassification.HIGH_TRUST_APPROVED)
    candidates = [(sop_chunk, 3.0)]

    filt = MetadataFilter()
    # Filter for BENCHMARK_ONLY: HIGH_TRUST_APPROVED should be excluded
    surviving, dropped, all_dropped, _ = filt.filter_candidates(
        candidates,
        allowed_trust=[TrustClassification.BENCHMARK_ONLY],
    )
    assert len(surviving) == 0
    assert all_dropped is True
