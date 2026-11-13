"""Unit tests for M5.1 equipment-aware metadata filtering and semantic grounding (FIND-M5-002)."""

from __future__ import annotations

import pytest

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import HypothesisStatus
from piis.knowledge.corpus import build_knowledge_base
from piis.knowledge.models import KnowledgeChunk
from piis.knowledge.sources import SourceType, TrustClassification
from piis.provenance import ProvenanceRecord, SourceType as ProvSourceType
from piis.retrieval.engine import HybridRetrievalEngine
from piis.retrieval.filters import MetadataFilter


@pytest.fixture(scope="module")
def investigation_system():
    registry, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)
    return engine, ret_engine, chunks


def test_metadata_filter_generation_compatibility():
    """Verify MetadataFilter correctly enforces generational compatibility."""
    m_filter = MetadataFilter()

    # 2G vs 5G mismatch
    assert not m_filter._is_generation_compatible("2G_GSM", "5G_NR")
    assert not m_filter._is_generation_compatible("3G_UMTS", "5G_NR")
    assert not m_filter._is_generation_compatible("WIMAX", "5G_NR")

    # 5G vs 5G match
    assert m_filter._is_generation_compatible("5G_NR", "5G_NR")
    assert m_filter._is_generation_compatible(None, "5G_NR")
    assert m_filter._is_generation_compatible("5G_NR", None)


def test_metadata_filter_vendor_compatibility():
    """Verify MetadataFilter enforces vendor isolation."""
    m_filter = MetadataFilter()

    # Proprietary vendor mismatch
    assert not m_filter._is_vendor_compatible("JUNIPER", "CISCO")
    assert not m_filter._is_vendor_compatible("NOKIA", "CISCO")
    assert not m_filter._is_vendor_compatible("CISCO", "JUNIPER")

    # Exact vendor match
    assert m_filter._is_vendor_compatible("CISCO", "CISCO")
    assert m_filter._is_vendor_compatible("JUNIPER", "JUNIPER")

    # Generic vendor match
    assert m_filter._is_vendor_compatible("GENERIC_3GPP", "GENERIC_3GPP")
    assert m_filter._is_vendor_compatible(None, "CISCO")


def test_chunk_filter_drops_incompatible_equipment():
    """Verify that filter_candidates drops chunks with incompatible vendor or tech generation."""
    m_filter = MetadataFilter()
    prov = ProvenanceRecord(
        source_type=ProvSourceType.PUBLIC_REAL,
        source_dataset="test",
        source_record_id="c1",
        transformation_version="1.0.0",
        checksum_sha256="abc",
    )
    chunk = KnowledgeChunk(
        chunk_id="CHK-TEST-01",
        doc_id="SOP-TEST-01",
        source_id="SRC-TEST",
        doc_title="Cisco BGP SOP",
        source_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        network_domain="TRANSPORT",
        technology_generation="OPTICAL_IP_TRANSPORT",
        vendor="CISCO",
        equipment_family="IP_MPLS_ROUTER",
        section_name="Test",
        content="Test content",
        token_count=50,
        checksum="abc",
        provenance=prov,
    )

    candidates = [(chunk, 0.85)]

    # Query asking for Juniper vendor
    surviving, dropped, all_dropped, _ = m_filter.filter_candidates(
        candidates=candidates,
        vendor="JUNIPER",
    )
    assert dropped == 1
    assert all_dropped is True
    assert len(surviving) == 0

    # Query asking for 2G GSM technology
    surviving, dropped, all_dropped, _ = m_filter.filter_candidates(
        candidates=candidates,
        technology_generation="2G_GSM",
    )
    assert dropped == 1
    assert all_dropped is True
    assert len(surviving) == 0


def test_sem_010_legacy_2g_abstains(investigation_system):
    """SEM-010: Legacy 2G GSM incident must abstain to INCONCLUSIVE without recommending 5G runbooks."""
    engine, _, _ = investigation_system
    incident = {
        "incident_id": "INC-SEM-010",
        "title": "GSM 900 MHz TCH congestion and Abis link drop",
        "description": "Base Station Controller reports 2G time slot allocation failure on legacy BTS-881.",
        "network_domain": "RAN",
        "alarm_codes": ["ALM-GSM-TCH-CONG"],
    }
    ctx = engine.investigate(incident=incident)
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert not ctx.sufficiency_report.is_sufficient
    assert any("runbook exists" in d.lower() or "equipment generation" in d.lower() for d in ctx.sufficiency_report.missing_evidence_details)
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_sem_013_juniper_vendor_mismatch_abstains(investigation_system):
    """SEM-013: Juniper JunOS incident must not recommend Cisco CLI commands and must abstain."""
    engine, _, _ = investigation_system
    incident = {
        "incident_id": "INC-SEM-013",
        "title": "Juniper JunOS commit rollback failure on aggregation PE",
        "description": "JunOS 21.4R3 commit check failed on routing instance VRF_5G_INTERNET.",
        "network_domain": "TRANSPORT",
        "alarm_codes": ["ALM-JUNOS-COMMIT-ERR"],
    }
    ctx = engine.investigate(incident=incident)
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_sem_015_nokia_netact_vendor_mismatch_abstains(investigation_system):
    """SEM-015: Nokia NetAct incident must abstain cleanly to INCONCLUSIVE."""
    engine, _, _ = investigation_system
    incident = {
        "incident_id": "INC-SEM-015",
        "title": "Nokia NetAct Northbound CORBA IRP synchronization timeout",
        "description": "Fault Management IRP notification channel broke socket connection to umbrella OSS.",
        "network_domain": "CROSS_DOMAIN",
        "alarm_codes": ["ALM-CORBA-IRP-DROP"],
    }
    ctx = engine.investigate(incident=incident)
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_sem_001_valid_5g_vswr_supported(investigation_system):
    """SEM-001: Genuine 5G NR VSWR incident with matching alarms must be SUPPORTED."""
    engine, _, _ = investigation_system
    incident = {
        "incident_id": "INC-SEM-001",
        "title": "High return loss and antenna VSWR alert",
        "description": "Antenna port return loss degraded below 10 dB on sector 1. Feeder line impedance anomaly.",
        "network_domain": "RAN",
        "network_element_ids": ["gNodeB-101"],
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
    }
    m2_data = {"predicted_category": "RADIO_ACCESS_NETWORK_ISSUE", "category_probability": 0.94}
    m3_data = {"anomalies": [{"network_element_id": "gNodeB-101", "metric_name": "vswr", "fused_score": 0.91}]}

    ctx = engine.investigate(incident=incident, m2_classification=m2_data, m3_network_intelligence=m3_data)
    assert ctx.hypotheses[0].status == HypothesisStatus.SUPPORTED
    assert ctx.sufficiency_report.is_sufficient
    assert ctx.recommendations[0].source_runbook_id == "SOP-RAN-VSWR-001"
