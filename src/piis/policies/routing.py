"""Deterministic support-level routing policy engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional
import yaml


class SupportDecision(str, Enum):
    """Canonical support routing decision tiers."""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass(frozen=True)
class RoutingEvidence:
    """Evidence factors evaluated at ticket triage time."""
    known_issue_match: bool = False
    approved_runbook_available: bool = False
    required_permissions_available: bool = False
    advanced_diagnostics_required: bool = False
    specialist_dependency: bool = False
    evidence_sufficient: bool = False
    insufficient_evidence: bool = False

    def is_sufficient(self) -> bool:
        if self.insufficient_evidence:
            return False
        return self.evidence_sufficient


@dataclass
class PolicyRule:
    rule_id: str
    description: str
    decision: SupportDecision
    requires: List[str] = field(default_factory=list)


class PolicyEngine:
    """Configurable policy engine driven by YAML rules."""

    def __init__(
        self,
        policy_version: str = "1.0",
        default_decision: SupportDecision = SupportDecision.HUMAN_REVIEW,
        rules: Optional[List[PolicyRule]] = None,
    ):
        self.policy_version = policy_version
        self.default_decision = default_decision
        self.rules = rules or []

    @classmethod
    def from_yaml(cls, path: Path) -> PolicyEngine:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = []
        for r in data.get("rules", []):
            rules.append(
                PolicyRule(
                    rule_id=r.get("id", "unnamed"),
                    description=r.get("description", ""),
                    decision=SupportDecision(r.get("decision", "HUMAN_REVIEW")),
                    requires=r.get("requires", []),
                )
            )
        return cls(
            policy_version=str(data.get("policy_version", "1.0")),
            default_decision=SupportDecision(data.get("default_decision", "HUMAN_REVIEW")),
            rules=rules,
        )

    def evaluate(self, evidence: RoutingEvidence) -> SupportDecision:
        """Evaluate evidence against ordered policy rules."""
        if not evidence.is_sufficient():
            return SupportDecision.HUMAN_REVIEW

        # Convert evidence dataclass into attribute lookup
        fact_dict = {
            "known_issue_match": evidence.known_issue_match,
            "approved_runbook": evidence.approved_runbook_available,
            "approved_runbook_available": evidence.approved_runbook_available,
            "required_permissions_available": evidence.required_permissions_available,
            "advanced_diagnostics_required": evidence.advanced_diagnostics_required,
            "specialist_dependency": evidence.specialist_dependency,
            "insufficient_evidence": not evidence.is_sufficient(),
        }

        for rule in self.rules:
            if all(fact_dict.get(req, False) for req in rule.requires):
                return rule.decision

        return self.default_decision


def recommend_support_level(evidence: RoutingEvidence) -> SupportDecision:
    """Default conservative routing policy (backward compatible function)."""
    if not evidence.is_sufficient():
        return SupportDecision.HUMAN_REVIEW
    if evidence.specialist_dependency:
        return SupportDecision.L3
    if evidence.advanced_diagnostics_required:
        return SupportDecision.L2
    if (
        evidence.known_issue_match
        and evidence.approved_runbook_available
        and evidence.required_permissions_available
    ):
        return SupportDecision.L1
    return SupportDecision.HUMAN_REVIEW
