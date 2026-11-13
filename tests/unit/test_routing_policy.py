from pathlib import Path
from piis.policies.routing import (
    PolicyEngine,
    RoutingEvidence,
    SupportDecision,
    recommend_support_level,
)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "routing_policy.example.yaml"


def test_insufficient_evidence_abstains():
    assert recommend_support_level(RoutingEvidence()) == SupportDecision.HUMAN_REVIEW


def test_known_runbook_case_can_be_l1():
    evidence = RoutingEvidence(
        known_issue_match=True,
        approved_runbook_available=True,
        required_permissions_available=True,
        evidence_sufficient=True,
    )
    assert recommend_support_level(evidence) == SupportDecision.L1


def test_advanced_diagnostics_routes_l2():
    evidence = RoutingEvidence(
        advanced_diagnostics_required=True,
        evidence_sufficient=True,
    )
    assert recommend_support_level(evidence) == SupportDecision.L2


def test_specialist_dependency_routes_l3():
    evidence = RoutingEvidence(
        specialist_dependency=True,
        evidence_sufficient=True,
    )
    assert recommend_support_level(evidence) == SupportDecision.L3


def test_policy_engine_yaml_loading():
    assert CONFIG_PATH.exists()
    engine = PolicyEngine.from_yaml(CONFIG_PATH)

    assert engine.default_decision == SupportDecision.HUMAN_REVIEW
    assert len(engine.rules) > 0

    # Test L1 rule via engine
    l1_evidence = RoutingEvidence(
        known_issue_match=True,
        approved_runbook_available=True,
        required_permissions_available=True,
        evidence_sufficient=True,
    )
    assert engine.evaluate(l1_evidence) == SupportDecision.L1

    # Test L2 rule via engine
    l2_evidence = RoutingEvidence(
        advanced_diagnostics_required=True,
        evidence_sufficient=True,
    )
    assert engine.evaluate(l2_evidence) == SupportDecision.L2

    # Test abstention on insufficient evidence
    empty_evidence = RoutingEvidence(evidence_sufficient=False)
    assert engine.evaluate(empty_evidence) == SupportDecision.HUMAN_REVIEW
