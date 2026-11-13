"""Unit tests for M2.1 natural language evidence extraction and policy routing."""

from pathlib import Path
from piis.policies.evidence import NaturalLanguageEvidenceExtractor
from piis.policies.routing import PolicyEngine, SupportDecision


def test_natural_language_evidence_extractor_l1_sop():
    extractor = NaturalLanguageEvidenceExtractor()
    incident = {
        "title": "Dispatch ticket for node GNB-102",
        "description": "Technician observed degraded load. Runbook SOP-RAN-102 executed via desk portal.",
        "metadata": {"runbook_available": True},
    }

    evidence = extractor.extract_evidence(incident)
    assert evidence.approved_runbook_available is True
    assert evidence.advanced_diagnostics_required is False
    assert evidence.specialist_dependency is False

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.L1


def test_natural_language_evidence_extractor_l2_advanced():
    extractor = NaturalLanguageEvidenceExtractor()
    incident = {
        "title": "Antenna line impedance degradation",
        "description": "VSWR measurement exceeded 2.5 on sector 2. Physical RF inspection required.",
        "metadata": {"requires_advanced_diag": True},
    }

    evidence = extractor.extract_evidence(incident)
    assert evidence.advanced_diagnostics_required is True

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.L2


def test_natural_language_evidence_extractor_l3_vendor():
    extractor = NaturalLanguageEvidenceExtractor()
    incident = {
        "title": "Optical fiber trunk failure",
        "description": "Physical fiber cable sever on rail line. Cable splice team and vendor TAC required.",
        "metadata": {"requires_specialist": True},
    }

    evidence = extractor.extract_evidence(incident)
    assert evidence.specialist_dependency is True

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.L3


def test_natural_language_evidence_extractor_negative_abstention():
    extractor = NaturalLanguageEvidenceExtractor()
    incident = {
        "title": "Nominal traffic fluctuation",
        "description": "Routine diurnal envelope observed. No threshold violation.",
        "metadata": {"is_negative_control": True},
    }

    evidence = extractor.extract_evidence(incident)
    assert evidence.insufficient_evidence is True

    engine = PolicyEngine.from_yaml(Path("configs/routing_policy.example.yaml"))
    decision = engine.evaluate(evidence)
    assert decision == SupportDecision.HUMAN_REVIEW
