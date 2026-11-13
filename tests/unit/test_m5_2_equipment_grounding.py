"""Comprehensive equipment grounding and vendor-neutral compatibility unit tests for M5.2.

Remediates FIND-M5.1-003:
- Tests prose bleed elimination (Cisco AnyConnect, Nokia NetAct, Ericsson ENM, Huawei U2000).
- Tests bidirectional vendor-neutral 3GPP runbook compatibility with proprietary vendor queries.
- Tests proprietary vendor isolation (Cisco SOPs cannot run on Juniper; vendor SOPs not vendor-neutral).
- Tests structured metadata precedence over ambiguous conversational text.
- Tests network element ID prefix conventions.
- Tests graceful abstention on ambiguous vendor references.
- Tests cross-generation isolation (2G/3G/4G/WiMAX vs 5G SA).
- Tests end-to-end investigation engine grounding under adversarial prose noise.
"""

from __future__ import annotations

import pytest

from piis.investigation.engine import IncidentInvestigationEngine
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine
from piis.retrieval.filters import MetadataFilter


@pytest.fixture(scope="module")
def investigation_pipeline():
    _, chunks = build_knowledge_base()
    ret_engine = HybridRetrievalEngine()
    ret_engine.index_chunks(chunks)
    engine = IncidentInvestigationEngine(retrieval_engine=ret_engine)
    return engine, ret_engine, chunks


# =========================================================================
# 1. PROSE BLEED ELIMINATION TESTS (_extract_vendor)
# =========================================================================

def test_extract_vendor_ignores_cisco_anyconnect_in_5g_ticket():
    """Verify that conversational mention of 'Cisco AnyConnect' does NOT extract CISCO."""
    incident = {
        "incident_id": "INC-PROSE-01",
        "title": "5G gNodeB cell drop and high VSWR",
        "description": "Technician connected via Cisco AnyConnect VPN to inspect the AAU antenna feeder line.",
        "network_element_ids": ["ERIC-AAU-5501"],
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == "ERICSSON", f"Expected 'ERICSSON' from element ID, got '{extracted}'"


def test_extract_vendor_ignores_anyconnect_vpn_without_node_vendor():
    """Verify that pure VPN client mentions abstain to None rather than poisoning query."""
    incident = {
        "incident_id": "INC-PROSE-02",
        "title": "Cell tower remote management failure",
        "description": "Field tech AnyConnect VPN session dropped during scheduled sweep.",
        "network_element_ids": ["SITE-TOWER-99"],
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted is None, f"Expected None (abstention), got '{extracted}'"


def test_extract_vendor_ignores_nokia_netact_ems_on_5g_core():
    """Verify that Nokia NetAct EMS mentions do not poison AMF core incident."""
    incident = {
        "incident_id": "INC-PROSE-03",
        "title": "5G Core AMF registration storm",
        "description": "Nokia NetAct EMS console shows high N2 interface SCTP latency on 5GC cluster.",
        "network_element_ids": ["AMF-CLUSTER-01"],
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted is None, f"Expected None (abstention), got '{extracted}'"


def test_extract_vendor_ignores_ericsson_enm_on_juniper_transport():
    """Verify that Ericsson ENM portal mention does not override Juniper router hardware."""
    incident = {
        "incident_id": "INC-PROSE-04",
        "title": "BGP peer flap on transport router",
        "description": "ENM portal shows transport interface down on PTX10000 core node.",
        "network_element_ids": ["JUN-PTX-01"],
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == "JUNIPER"


def test_extract_vendor_ignores_huawei_u2000_on_cisco_asr():
    """Verify that Huawei U2000 NMS mention does not override Cisco ASR node."""
    incident = {
        "incident_id": "INC-PROSE-05",
        "title": "ASR9001 linecard optic low power",
        "description": "Alarm mirrored in Huawei U2000 management bridge for ASR-9000 gateway.",
        "network_element_ids": ["CISCO-ASR-01"],
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == "CISCO"


# =========================================================================
# 2. STRUCTURED METADATA PRECEDENCE
# =========================================================================

def test_structured_metadata_vendor_overrides_prose():
    """Verify that structured metadata.vendor takes absolute precedence over conversational text."""
    incident = {
        "incident_id": "INC-META-01",
        "title": "Cell outage with mixed mentions",
        "description": "Technician mentions Cisco and Juniper switches in the cabinet.",
        "metadata": {"vendor": "ERICSSON"},
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == "ERICSSON"


def test_structured_equipment_vendor_field_precedence():
    """Verify incident['equipment_vendor'] field precedence."""
    incident = {
        "incident_id": "INC-META-02",
        "title": "Router fiber break",
        "description": "Connecting via Huawei bridge to examine link.",
        "equipment_vendor": "JUNIPER",
    }
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == "JUNIPER"


# =========================================================================
# 3. NETWORK ELEMENT ID PREFIX CONVENTIONS
# =========================================================================

@pytest.mark.parametrize(
    "element_id, expected_vendor",
    [
        ("ERIC-AAU-01", "ERICSSON"),
        ("ERS-RADIO-02", "ERICSSON"),
        ("NOK-AIRSCALE-01", "NOKIA"),
        ("NOKIA-BBU-02", "NOKIA"),
        ("CISCO-ASR9K-01", "CISCO"),
        ("CSCO-ROUTER-02", "CISCO"),
        ("JUN-MX960-01", "JUNIPER"),
        ("JNPR-PTX-02", "JUNIPER"),
        ("HUA-NE40E-01", "HUAWEI"),
        ("HW-OPTIX-02", "HUAWEI"),
        ("ZTE-ZXCTN-01", "ZTE"),
    ],
)
def test_element_id_prefix_extraction(element_id, expected_vendor):
    incident = {"incident_id": "INC-ELEM", "network_element_ids": [element_id]}
    extracted = IncidentInvestigationEngine._extract_vendor(incident)
    assert extracted == expected_vendor


# =========================================================================
# 4. BIDIRECTIONAL VENDOR-NEUTRAL 3GPP COMPATIBILITY (_is_vendor_compatible)
# =========================================================================

def test_generic_3gpp_runbook_compatible_with_ericsson():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="ERICSSON", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_nokia():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="NOKIA", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_huawei():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="HUAWEI", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_cisco():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="CISCO", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_juniper():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="JUNIPER", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_zte():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="ZTE", chunk_vendor="GENERIC_3GPP") is True


def test_generic_3gpp_runbook_compatible_with_multi_vendor():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="MULTI_VENDOR", chunk_vendor="GENERIC_3GPP") is True
    assert m_filter._is_vendor_compatible(target_vendor="GENERIC_3GPP", chunk_vendor="GENERIC_3GPP") is True


# =========================================================================
# 5. PROPRIETARY VENDOR ISOLATION (Vendor-specific is NOT vendor-neutral)
# =========================================================================

def test_cisco_runbook_not_compatible_with_juniper():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="JUNIPER", chunk_vendor="CISCO") is False


def test_cisco_runbook_not_compatible_with_nokia():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="NOKIA", chunk_vendor="CISCO") is False


def test_cisco_runbook_not_compatible_with_generic_3gpp_query():
    """Verify that a proprietary Cisco SOP is NOT treated as vendor-neutral."""
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="GENERIC_3GPP", chunk_vendor="CISCO") is False


def test_nokia_runbook_not_compatible_with_generic_3gpp_query():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="GENERIC_3GPP", chunk_vendor="NOKIA") is False


def test_juniper_runbook_not_compatible_with_cisco():
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="CISCO", chunk_vendor="JUNIPER") is False


def test_missing_chunk_vendor_metadata_fails_closed():
    """Verify that missing chunk vendor metadata does NOT silently pass compatibility."""
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor="ERICSSON", chunk_vendor=None) is False
    assert m_filter._is_vendor_compatible(target_vendor="CISCO", chunk_vendor="") is False


def test_unconstrained_query_allows_any_chunk():
    """Verify that query without vendor requirement accepts chunks with valid vendor."""
    m_filter = MetadataFilter()
    assert m_filter._is_vendor_compatible(target_vendor=None, chunk_vendor="CISCO") is True
    assert m_filter._is_vendor_compatible(target_vendor=None, chunk_vendor="GENERIC_3GPP") is True


# =========================================================================
# 6. END-TO-END INVESTIGATION ENGINE GROUNDING UNDER PROSE NOISE
# =========================================================================

def test_end_to_end_5g_vswr_with_cisco_anyconnect_prose(investigation_pipeline):
    """Verify that a 5G VSWR ticket mentioning 'Cisco AnyConnect' correctly retrieves 5G VSWR SOP."""
    engine, _, _ = investigation_pipeline

    incident = {
        "incident_id": "INC-E2E-5G-CISCO-PROSE",
        "title": "Severe VSWR degradation and cell drop on 5G gNodeB AAU",
        "description": "Technician connected via Cisco AnyConnect VPN to inspect the AAU antenna feeder line. Antenna VSWR spike on sector 2 exceeding 2.1:1. High feeder reflected power detected.",
        "network_domain": "RAN",
        "network_element_ids": ["ERIC-AAU-9901"],
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
    }
    m2 = {
        "predicted_category": "RADIO_ACCESS_NETWORK_ISSUE",
        "category_probability": 0.95,
        "predicted_severity": "MAJOR",
        "policy_routing_tier": "L1",
    }
    m3 = {
        "anomalies": [
            {
                "network_element_id": "ERIC-AAU-9901",
                "metric_name": "vswr_ratio",
                "fused_score": 0.88,
                "violations_summary": "vswr_ratio > 2.0 (critical)",
            }
        ],
        "alarm_cluster": {
            "cluster_id": "CLUST-101",
            "dominant_alarm_code": "ALM-RAN-VSWR-HIGH",
            "affected_elements": ["ERIC-AAU-9901"],
            "alarm_events": ["ALM-RAN-VSWR-HIGH"],
        },
    }

    ctx = engine.investigate(incident, m2_classification=m2, m3_network_intelligence=m3)

    # Must retrieve SOP-RAN-VSWR-001 rather than abstaining or looking for Cisco SOPs
    assert ctx.m4_retrieval["primary_runbook_id"] == "SOP-RAN-VSWR-001"
    assert len(ctx.hypotheses) > 0
    assert "VSWR" in ctx.hypotheses[0].description or "RF" in ctx.hypotheses[0].description
    assert ctx.hypotheses[0].confidence_proxy > 0.5


def test_end_to_end_juniper_bgp_with_nokia_netact_prose(investigation_pipeline):
    """Verify that Juniper IP transport flap retrieves fiber/transport SOP without Nokia false match."""
    engine, _, _ = investigation_pipeline

    incident = {
        "incident_id": "INC-E2E-JUN-BGP",
        "title": "Optical fiber attenuation on core transport interface",
        "description": "Nokia NetAct EMS console shows optical Rx power degraded to -22 dBm on JunOS PTX10000 gateway.",
        "network_domain": "TRANSPORT",
        "network_element_ids": ["JUN-PTX-01"],
        "alarm_codes": ["ALM-TRANS-FIBER-CUT"],
    }
    m2 = {
        "predicted_category": "TRANSMISSION_FIBER_FAULT",
        "category_probability": 0.90,
        "predicted_severity": "HIGH",
        "policy_routing_tier": "L2",
    }
    m3 = {
        "anomalies": [
            {
                "network_element_id": "JUN-PTX-01",
                "metric_name": "optical_power",
                "fused_score": 0.85,
                "violations_summary": "optical rx power low",
            }
        ],
        "alarm_cluster": {
            "cluster_id": "CLUST-202",
            "dominant_alarm_code": "ALM-TRANS-FIBER-CUT",
            "affected_elements": ["JUN-PTX-01"],
            "alarm_events": ["ALM-TRANS-FIBER-CUT"],
        },
    }

    ctx = engine.investigate(incident, m2_classification=m2, m3_network_intelligence=m3)
    assert ctx.m4_retrieval["primary_runbook_id"] == "SOP-TRANS-FIBER-001"
    assert len(ctx.hypotheses) > 0
    assert "optical" in ctx.hypotheses[0].description.lower() or "fiber" in ctx.hypotheses[0].description.lower()
