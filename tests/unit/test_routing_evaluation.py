"""Unit tests for deterministic support routing evidence extraction and policy execution."""

from pathlib import Path
from piis.policies.routing import PolicyEngine, SupportDecision
from scripts.evaluate_routing import extract_routing_evidence


def test_routing_evidence_negative_control_abstention():
    negative_incident = {
        "incident_id": "SYN-INC-S00-NC-42-001",
        "title": "Nominal traffic variation",
        "description": "Routine diurnal pattern",
        "scenario_family_id": "S00",
        "metadata": {"negative_control": True},
    }

    evidence = extract_routing_evidence(negative_incident)
    assert evidence.insufficient_evidence is True
    assert evidence.evidence_sufficient is False

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.HUMAN_REVIEW


def test_routing_evidence_l1_runbook():
    l1_incident = {
        "incident_id": "SYN-INC-S03-42-001",
        "title": "Severe downlink PRB saturation",
        "description": "PRB utilization exceeding 98%",
        "support_level_rationale": "Standard load-balancing SOP-RAN-CONGEST applies via automated OSS portal.",
        "scenario_family_id": "S03",
        "metadata": {"runbook_available": "SOP-RAN-CONGEST-01"},
    }

    evidence = extract_routing_evidence(l1_incident)
    assert evidence.known_issue_match is True
    assert evidence.approved_runbook_available is True
    assert evidence.required_permissions_available is True
    assert evidence.advanced_diagnostics_required is False

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.L1


def test_routing_evidence_l2_advanced():
    l2_incident = {
        "incident_id": "SYN-INC-S01-42-001",
        "title": "Severe downlink signal attenuation",
        "description": "Sector reports progressive radio link degradation.",
        "support_level_rationale": "Requires physical RF antenna feeder line inspection and VSWR measurement.",
        "scenario_family_id": "S01",
        "metadata": {},
    }

    evidence = extract_routing_evidence(l2_incident)
    assert evidence.advanced_diagnostics_required is True

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.L2
