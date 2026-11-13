"""Unit tests for IncidentInvestigationEngine: grounding, sufficiency, and hypotheses."""

from piis.knowledge.corpus import build_knowledge_base
from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import (
    ApprovalStatus,
    EvidenceType,
    HypothesisStatus,
    RecommendationRisk,
)
from piis.retrieval.engine import HybridRetrievalEngine


def _build_test_engine() -> IncidentInvestigationEngine:
    docs, chunks = build_knowledge_base()
    ret = HybridRetrievalEngine()
    ret.index_chunks(chunks)
    return IncidentInvestigationEngine(retrieval_engine=ret)


def test_investigation_grounded_vswr_incident():
    engine = _build_test_engine()
    incident = {
        "incident_id": "INC-RAN-001",
        "title": "Severe VSWR degradation and radio link failure on gNodeB-101",
        "description": "Antenna VSWR spike on sector 2 exceeding 2.1:1. High feeder reflected power detected.",
        "network_domain": "RAN",
        "network_element_ids": ["gNodeB-101", "AAU-02"],
        "alarm_codes": ["ALM-RAN-VSWR-HIGH", "0x80040111"],
        "affected_subscribers": 1420,
        "affected_region": "North-Sector-A",
    }
    m2_data = {
        "predicted_category": "RADIO_ACCESS_NETWORK_ISSUE",
        "category_probability": 0.92,
        "predicted_severity": "MAJOR",
        "policy_routing_tier": "L1",
    }
    m3_data = {
        "anomalies": [
            {
                "network_element_id": "gNodeB-101",
                "metric_name": "vswr_ratio",
                "fused_score": 0.88,
                "violations_summary": "vswr_ratio > 2.0 (critical)",
            }
        ],
        "alarm_cluster": {
            "cluster_id": "CLUST-101",
            "dominant_alarm_code": "ALM-RAN-VSWR-HIGH",
            "affected_elements": ["gNodeB-101"],
            "alarm_events": ["ALM-RAN-VSWR-HIGH", "0x80040111"],
        },
        "impact_assessment": {
            "direct_element_count": 1,
            "inferred_element_count": 0,
            "estimated_subscribers_affected": 1420,
        },
    }

    ctx = engine.investigate(incident, m2_classification=m2_data, m3_network_intelligence=m3_data)

    # 1. Verification of Context & Evidence
    assert ctx.incident_id == "INC-RAN-001"
    assert len(ctx.evidence_register) >= 5
    evidence_types = {e.evidence_type for e in ctx.evidence_register}
    assert EvidenceType.TICKET_METADATA in evidence_types
    assert EvidenceType.ML_CLASSIFICATION in evidence_types
    assert EvidenceType.TELEMETRY_ANOMALY in evidence_types
    assert EvidenceType.ALARM_CLUSTER in evidence_types
    assert EvidenceType.APPROVED_RUNBOOK in evidence_types

    # 2. Sufficiency Check
    assert ctx.sufficiency_report.is_sufficient is True
    assert not ctx.sufficiency_report.has_missing_evidence

    # 3. Grounded Hypotheses
    assert len(ctx.hypotheses) >= 1
    primary_hyp = ctx.hypotheses[0]
    assert primary_hyp.status == HypothesisStatus.SUPPORTED
    assert "VSWR" in primary_hyp.description
    assert len(primary_hyp.supporting_evidence_ids) > 0
    assert primary_hyp.confidence_proxy > 0.50

    # 4. Diagnostic Recommendations
    assert len(ctx.recommendations) >= 1
    for rec in ctx.recommendations:
        assert rec.human_approval_required is True
        assert rec.approval_status == ApprovalStatus.PENDING_REVIEW
        assert rec.source_runbook_id == "SOP-RAN-VSWR-001"
        assert len(rec.supporting_evidence_ids) > 0

    # 5. Operator Summary Markdown
    assert "# PIIS Incident Investigation" in ctx.operator_summary_markdown
    assert "READ-ONLY DECISION SUPPORT" in ctx.operator_summary_markdown


def test_investigation_abstains_on_negative_control():
    engine = _build_test_engine()
    incident = {
        "incident_id": "INC-NEG-001",
        "title": "Slight diurnal traffic variation",
        "description": "Routine evening commute traffic dip; nominal operating boundary.",
        "network_domain": "RAN",
        "metadata": {"is_negative_control": True},
    }

    ctx = engine.investigate(incident)

    # Must abstain
    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.sufficiency_report.has_missing_evidence is True
    assert len(ctx.hypotheses) == 1
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert ctx.hypotheses[0].confidence_proxy == 0.0

    # Must only recommend safe human review, zero network changes
    assert len(ctx.recommendations) == 1
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"
    assert ctx.recommendations[0].risk_classification == RecommendationRisk.READ_ONLY_SAFE


def test_investigation_abstains_on_vague_underspecified_ticket():
    engine = _build_test_engine()
    incident = {
        "incident_id": "INC-VAGUE-001",
        "title": "Internet issue",
        "description": "Customer says slow",
        "network_domain": "CROSS_DOMAIN",
    }

    ctx = engine.investigate(incident)

    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_investigation_detects_domain_contradiction():
    engine = _build_test_engine()
    # Ticket claimed TRANSPORT, but text and symptoms are strictly RAN VSWR antenna feeder
    incident = {
        "incident_id": "INC-MISMATCH-001",
        "title": "Antenna VSWR spike on tower feeder",
        "description": "ALM-RAN-VSWR-HIGH on antenna feeder DIN connector.",
        "network_domain": "TRANSPORT",  # Deliberate contradiction
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
    }

    ctx = engine.investigate(incident)
    assert ctx.sufficiency_report.has_contradictions is True
    assert any("Domain mismatch" in c for c in ctx.sufficiency_report.contradiction_details)
