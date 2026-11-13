"""
Unit tests for PIIS Runbook Negative Coverage & Safe Operational Abstention.
Validates Workstream C:
- Legacy 2G GSM incidents abstain safely when no approved SOP exists.
- Cross-domain contradictions (RAN vs TRANSPORT) abstain to prevent ungrounded actions.
- Transient network fluctuations abstain safely to prevent disruptive automation.
- Underspecified tickets lacking telemetry and alarms abstain to human triage.
"""

from datetime import datetime, timezone
import pytest

from piis.knowledge.corpus import build_knowledge_base
from piis.retrieval.engine import HybridRetrievalEngine
from piis.investigation.engine import IncidentInvestigationEngine


@pytest.fixture(scope="module")
def investigation_engine():
    reg, chunks = build_knowledge_base()
    ret = HybridRetrievalEngine(confidence_threshold=0.35)
    ret.index_chunks(chunks)
    return IncidentInvestigationEngine(retrieval_engine=ret)


def test_legacy_2g_gsm_safely_abstains(investigation_engine):
    """Verify that a legacy 2G GSM incident safely abstains because no approved 2G SOP exists."""
    now = datetime.now(timezone.utc)
    incident = {
        "incident_id": "INC-TEST-2G-001",
        "title": "Legacy 2G GSM BTS TRX Board Defect",
        "description": "Base Station Transceiver TRX-04 hardware fault. Equipment is legacy 2G GSM.",
        "element_id": "BTS-2G-SITE-99",
        "network_domain": "RAN",
        "created_at": now.isoformat(),
        "alarm_codes": ["ALM-RAN-VSWR-HIGH"],
    }
    ctx = investigation_engine.investigate(incident)
    assert not ctx.sufficiency_report.is_sufficient
    assert any("no approved runbook exists" in d for d in ctx.sufficiency_report.missing_evidence_details)
    assert len(ctx.recommendations) == 1
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"
    assert ctx.recommendations[0].human_approval_required is True


def test_cross_domain_contradiction_safely_abstains(investigation_engine):
    """Verify that domain mismatch between ticket domain and retrieved evidence triggers safe abstention."""
    now = datetime.now(timezone.utc)
    incident = {
        "incident_id": "INC-TEST-XDOM-001",
        "title": "NTP Clock Skew and Drift on Transmission Gateway",
        "description": "PTP clock sync failure on edge router gateway. Jitter exceeds boundary.",
        "element_id": "EDGE-RTR-01",
        "network_domain": "RAN",  # Ticket marked as RAN, but symptom is Transport PTP/NTP
        "created_at": now.isoformat(),
    }
    ctx = investigation_engine.investigate(incident)
    # Primary evidence retrieved is INC-TELTS-SYNC-0001 (TRANSPORT), creating a domain contradiction
    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.sufficiency_report.has_contradictions is True
    assert any("Domain mismatch" in c for c in ctx.sufficiency_report.contradiction_details)
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_transient_alarm_cleared_safely_abstains(investigation_engine):
    """Verify that transient events cleared in telemetry trigger safe abstention."""
    now = datetime.now(timezone.utc)
    incident = {
        "incident_id": "INC-TEST-TRANS-001",
        "title": "Transient Microwave Link Rain Fade Settled",
        "description": "Heavy monsoon downpour caused brief 4 dB fade, but signal returned to baseline 15m ago. Settled.",
        "element_id": "MW-LINK-01",
        "network_domain": "TRANSPORT",
        "created_at": now.isoformat(),
    }
    m3_intel = {
        "correlations": [{
            "alarm_id": "ALM-MW-01",
            "severity": "MINOR",
            "status": "CLEARED",
            "duration_ms": 120,
        }]
    }
    ctx = investigation_engine.investigate(incident, m3_network_intelligence=m3_intel)
    assert not ctx.sufficiency_report.is_sufficient
    assert ctx.sufficiency_report.is_transient_event is True
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"


def test_underspecified_ticket_safely_abstains(investigation_engine):
    """Verify that underspecified tickets without telemetry or alarms safely escalate to NOC."""
    now = datetime.now(timezone.utc)
    incident = {
        "incident_id": "INC-TEST-VAGUE-001",
        "title": "System slow",
        "description": "Cell slow",
        "created_at": now.isoformat(),
        "network_domain": "RAN",
    }
    ctx = investigation_engine.investigate(incident)
    assert not ctx.sufficiency_report.is_sufficient
    assert any("Ticket contains zero associated alarm codes" in d for d in ctx.sufficiency_report.missing_evidence_details)
    assert ctx.recommendations[0].source_runbook_id == "HUMAN_ESCALATION"
