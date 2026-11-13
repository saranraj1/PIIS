"""Network impact analyzer evaluating blast radius, cascading risk, and service impact."""

from __future__ import annotations

import hashlib
from typing import List, Optional, Set
from piis.correlation.models import CorrelatedIncidentCluster
from piis.correlation.topology import TelecomTopologyGraph
from piis.impact.models import ImpactAssessment
from piis.provenance import ProvenanceRecord, SourceType


class NetworkImpactAnalyzer:
    """Evaluates blast radius, topological propagation, and service risk for incident clusters."""

    def __init__(
        self,
        topology: Optional[TelecomTopologyGraph] = None,
        inferred_hop_depth: int = 1,
        version: str = "1.0.0",
    ):
        """Initialize network impact analyzer.

        Args:
            topology: Attributed network topology graph.
            inferred_hop_depth: Maximum hops to search for inferred cascading elements.
            version: Analyzer version string.
        """
        self.topology = topology or TelecomTopologyGraph.build_reference_topology()
        self.inferred_hop_depth = inferred_hop_depth
        self.version = version

    def assess_impact(
        self,
        cluster: CorrelatedIncidentCluster,
        source_dataset: str = "PIIS-Network-Intelligence",
        source_type: SourceType = SourceType.DERIVED,
    ) -> ImpactAssessment:
        """Compute blast radius and impact assessment for a correlated incident cluster."""
        direct_elements = sorted(list(set(cluster.affected_elements)))

        # Find inferred cascading downstream elements within k hops not already in direct elements
        inferred_set: Set[str] = set()
        if self.inferred_hop_depth > 0:
            downstream = self.topology.get_downstream_elements(direct_elements, max_depth=self.inferred_hop_depth)
            inferred_set = downstream - set(direct_elements)

        inferred_elements = sorted(list(inferred_set))
        all_elements = direct_elements + inferred_elements

        # Determine all involved domains
        domains_set: Set[str] = set(cluster.involved_domains)
        for elem in all_elements:
            node_data = self.topology.get_node(elem)
            if node_data and "domain" in node_data:
                domains_set.add(node_data["domain"])

        affected_domains = sorted(list(domains_set))

        # Compute composite risk score
        # Base: direct count (0.2 each, max 0.4), inferred count (0.1 each, max 0.2),
        # domain count (0.2 each, max 0.4), 5G Core multiplier (+0.25)
        raw_risk = (
            min(0.40, 0.15 * len(direct_elements))
            + min(0.20, 0.05 * len(inferred_elements))
            + min(0.30, 0.15 * len(affected_domains))
            + (0.25 if "5G_CORE" in affected_domains else 0.0)
        )
        risk_score = round(min(1.0, raw_risk), 4)

        if risk_score >= 0.75:
            severity_risk_level = "CRITICAL"
        elif risk_score >= 0.50:
            severity_risk_level = "MAJOR"
        elif risk_score >= 0.30:
            severity_risk_level = "MODERATE"
        else:
            severity_risk_level = "LOW"

        # Calculate subscriber impact strictly if data exists in topology
        total_subscribers: Optional[int] = None
        has_sub_data = False
        sub_sum = 0

        for elem in all_elements:
            node_data = self.topology.get_node(elem)
            if node_data and node_data.get("nominal_subscribers") is not None:
                has_sub_data = True
                sub_sum += int(node_data["nominal_subscribers"])

        basis_text: Optional[str] = None
        if has_sub_data:
            total_subscribers = sub_sum
            basis_text = (
                f"Aggregated nominal capacity across {len(all_elements)} direct/inferred elements "
                f"from registered topology metadata. Not dynamically observed from active UE counters."
            )

        # Unique assessment ID
        assess_hash = hashlib.sha256(f"{cluster.cluster_id}_{len(all_elements)}_{risk_score}".encode()).hexdigest()[:12]
        assessment_id = f"IMPACT-{assess_hash}"

        prov = ProvenanceRecord(
            source_type=source_type,
            source_dataset=source_dataset,
            source_record_id=assessment_id,
            transformation_version=self.version,
            metadata={
                "cluster_id": cluster.cluster_id,
                "direct_element_count": len(direct_elements),
                "inferred_element_count": len(inferred_elements),
                "total_element_count": len(all_elements),
                "risk_score": risk_score,
                "severity_risk_level": severity_risk_level,
            },
        )

        return ImpactAssessment(
            assessment_id=assessment_id,
            cluster_id=cluster.cluster_id,
            direct_elements=direct_elements,
            inferred_elements=inferred_elements,
            total_element_count=len(all_elements),
            affected_domains=affected_domains,
            domain_count=len(affected_domains),
            severity_risk_level=severity_risk_level,
            risk_score=risk_score,
            estimated_affected_subscribers=total_subscribers,
            subscriber_impact_basis=basis_text,
            epistemic_status="DERIVED_ESTIMATE",
            provenance=prov.to_dict(),
        )

    def assess_batch(
        self,
        clusters: List[CorrelatedIncidentCluster],
        source_dataset: str = "PIIS-Network-Intelligence",
    ) -> List[ImpactAssessment]:
        """Assess impact across multiple incident clusters."""
        return [self.assess_impact(c, source_dataset=source_dataset) for c in clusters]
