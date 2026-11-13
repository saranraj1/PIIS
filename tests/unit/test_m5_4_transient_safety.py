"""
Unit tests for PIIS M5.4 Workstream E:
- FIND-M5.3-006: Transient Telemetry & Recommendation Safety
"""

import pytest

from piis.investigation.engine import IncidentInvestigationEngine
from piis.investigation.schemas import HypothesisStatus
from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine


@pytest.fixture(scope="module")
def investigation_engine():
    docs, chunks = build_knowledge_base()
    retrieval_engine = HybridRetrievalEngine()
    retrieval_engine.index_chunks(chunks)
    return IncidentInvestigationEngine(retrieval_engine=retrieval_engine)


def test_transient_200ms_cpu_spike_abstains_safely(investigation_engine):
    """Verify ABS-08: 200ms self-cleared CPU spike without alarms safely abstains to INCONCLUSIVE."""
    incident = {
        "incident_id": "INC-ABS-08-TEST",
        "title": "Transient 200ms CPU spike self-cleared",
        "description": "SMF processor spiked to 92% for 200 milliseconds during routing reload, then returned to 14%.",
        "alarm_codes": [],
        "network_domain": "5G_CORE",
        "network_element_ids": ["SMF-CORE-01"],
    }
    
    ctx = investigation_engine.investigate(incident=incident, m2_classification={}, m3_network_intelligence={})
    
    assert ctx.sufficiency_report.is_sufficient is False
    assert ctx.sufficiency_report.is_transient_event is True
    assert len(ctx.sufficiency_report.missing_evidence_details) > 0
    assert "transient, self-cleared operational event" in ctx.sufficiency_report.missing_evidence_details[0]

    # Verify top hypothesis
    assert len(ctx.hypotheses) > 0
    top_hyp = ctx.hypotheses[0]
    assert top_hyp.status == HypothesisStatus.INCONCLUSIVE
    assert "INCONCLUSIVE" in top_hyp.description

    # Verify recommendation routes to safe human escalation
    assert len(ctx.recommendations) > 0
    rec = ctx.recommendations[0]
    assert rec.source_runbook_id == "HUMAN_ESCALATION"
    assert rec.human_approval_required is True


def test_transient_cleared_before_ingestion_abstains(investigation_engine):
    """Verify that incidents explicitly noting cleared faults without active alarms abstain."""
    incident = {
        "incident_id": "INC-TRANSIENT-02",
        "title": "Temporary packet discard returned to nominal",
        "description": "Short-lived buffer spike on UPF card cleared before ingestion. Telemetry returned to normal baseline.",
        "alarm_codes": [],
        "network_domain": "5G_CORE",
        "network_element_ids": ["UPF-CORE-02"],
    }
    
    ctx = investigation_engine.investigate(incident=incident, m2_classification={}, m3_network_intelligence={})
    assert ctx.sufficiency_report.is_sufficient is False
    assert ctx.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_sustained_fault_with_active_alarm_does_not_falsely_abstain(investigation_engine):
    """Verify that an ongoing sustained fault with active alarms is NOT misclassified as transient."""
    incident = {
        "incident_id": "INC-SUSTAINED-01",
        "title": "Severe antenna return loss high",
        "description": "ALM-RAN-VSWR-HIGH on sector 3. Previously intermittent spike has now become persistent and sustained.",
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
        "network_domain": "RAN",
        "network_element_ids": ["gNodeB-M54-01"],
    }
    
    m2 = {"predicted_category": "HARDWARE_OR_LINK_DEGRADATION", "category_probability": 0.94}
    m3 = {"anomalies": [{"network_element_id": "gNodeB-M54-01", "metric_name": "vswr", "fused_score": 0.92}]}
    
    ctx = investigation_engine.investigate(incident=incident, m2_classification=m2, m3_network_intelligence=m3)
    
    assert ctx.sufficiency_report.is_transient_event is False
    assert ctx.sufficiency_report.is_sufficient is True
    assert ctx.hypotheses[0].status == HypothesisStatus.SUPPORTED
    assert ctx.recommendations[0].source_runbook_id == "SOP-RAN-VSWR-001"
