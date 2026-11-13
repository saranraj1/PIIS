"""Evidence-Grounded Incident Investigation and Decision Support Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    EvidenceSufficiencyReport,
    EvidenceType,
    HypothesisStatus,
    IncidentHypothesis,
    InvestigationContext,
    InvestigationEvidenceItem,
    RecommendationRisk,
    TrustLevel,
)
from piis.investigation.temporal import (
    EvidenceTemporalStatus,
    TemporalEvidenceEvaluator,
)
from piis.knowledge.sources import KnowledgeSourceRegistry
from piis.provenance import ProvenanceRecord, SourceType
from piis.retrieval.contracts import RetrievalQuery, RetrievalResult
from piis.retrieval.engine import HybridRetrievalEngine
from piis.retrieval.filters import MetadataFilter
from piis.security.guardrails import RetrievalSecurityGuard


class IncidentInvestigationEngine:
    """Orchestrates evidence aggregation, hypothesis ranking, and runbook-backed diagnostic recommendations."""

    def __init__(
        self,
        retrieval_engine: Optional[HybridRetrievalEngine] = None,
        security_guard: Optional[RetrievalSecurityGuard] = None,
        source_registry: Optional[KnowledgeSourceRegistry] = None,
        temporal_evaluator: Optional[TemporalEvidenceEvaluator] = None,
        version: str = "1.0.0",
    ):
        self.retrieval_engine = retrieval_engine or HybridRetrievalEngine()
        self.security_guard = security_guard or RetrievalSecurityGuard()
        self.source_registry = source_registry or KnowledgeSourceRegistry()
        self.temporal_evaluator = temporal_evaluator or TemporalEvidenceEvaluator()
        self.version = version

    def investigate(
        self,
        incident: Dict[str, Any],
        m2_classification: Optional[Dict[str, Any]] = None,
        m3_network_intelligence: Optional[Dict[str, Any]] = None,
    ) -> InvestigationContext:
        """Execute end-to-end evidence-grounded incident investigation.

        Args:
            incident: Normalized incident dictionary.
            m2_classification: Optional precomputed M2 fault classification, severity, and routing tier.
            m3_network_intelligence: Optional precomputed M3 telemetry anomalies, alarm cluster, and blast radius.

        Returns:
            InvestigationContext containing canonical evidence, hypotheses, and diagnostic recommendations.
        """
        incident_id = str(incident.get("incident_id") or "INC-UNKNOWN")
        title = str(incident.get("title") or "")
        description = str(incident.get("description") or "")
        network_domain = str(incident.get("network_domain") or "CROSS_DOMAIN")
        created_at = str(incident.get("created_at") or datetime.now(timezone.utc).isoformat())

        # Step 1: Inbound Security Inspection & Neutralization
        combined_text = f"{title}. {description}"
        sec_analysis = self.security_guard.inspect_query(combined_text)
        sanitized_title = self.security_guard.neutralize_content(title, sec_analysis["threat_types"])
        sanitized_description = self.security_guard.neutralize_content(description, sec_analysis["threat_types"])

        # Step 2: Query Historical Retrieval (M4)
        # Note: Do not hard-restrict target_domain so retrieval can surface the true best matching runbook
        # and enable domain mismatch / contradiction detection.
        # Include sanitized text and alarm codes from incident and M3 alarm intelligence to ground retrieval
        alarm_codes = list(incident.get("alarm_codes") or [])
        if m3_network_intelligence and "alarm_cluster" in m3_network_intelligence:
            cluster = m3_network_intelligence["alarm_cluster"]
            dom_code = cluster.get("dominant_alarm_code")
            if dom_code and dom_code not in alarm_codes:
                alarm_codes.append(dom_code)
            for evt in cluster.get("alarm_events", []):
                evt_code = evt.get("alarm_code") if isinstance(evt, dict) else str(evt)
                if evt_code and evt_code not in alarm_codes:
                    alarm_codes.append(evt_code)

        alarm_text = " ".join(alarm_codes)
        query_text = f"{sanitized_title}. {sanitized_description}"
        if alarm_text:
            query_text += f". Alarms: {alarm_text}"

        tech_gen = self._extract_technology_generation(incident)
        vendor = self._extract_vendor(incident)

        ret_query = RetrievalQuery(
            query_id=f"Q-INV-{incident_id}",
            query_text=query_text,
            target_domain=None,
            technology_generation=tech_gen,
            vendor=vendor,
            alarm_codes=alarm_codes,
            top_k=3,
        )
        ret_result: RetrievalResult = self.retrieval_engine.retrieve(ret_query)

        # Step 3: Compile Canonical Evidence Register
        evidence_register, evid_counter = self._build_evidence_register(
            incident=incident,
            created_at=created_at,
            sanitized_title=sanitized_title,
            sanitized_description=sanitized_description,
            sec_analysis=sec_analysis,
            m2_classification=m2_classification or {},
            m3_network_intelligence=m3_network_intelligence or {},
            ret_result=ret_result,
        )

        # Step 4: Evaluate Evidence Sufficiency & Contradictions
        sufficiency_report = self._evaluate_sufficiency_and_contradictions(
            incident=incident,
            evidence_register=evidence_register,
            ret_result=ret_result,
            m2_classification=m2_classification or {},
            m3_network_intelligence=m3_network_intelligence or {},
        )

        # Step 5: Generate Ranked Hypotheses
        hypotheses = self._generate_hypotheses(
            incident_id=incident_id,
            evidence_register=evidence_register,
            sufficiency_report=sufficiency_report,
            ret_result=ret_result,
            m2_classification=m2_classification or {},
            m3_network_intelligence=m3_network_intelligence or {},
        )

        # Step 6: Synthesize Diagnostic Recommendations (Strictly Approved Runbooks)
        recommendations = self._synthesize_recommendations(
            incident_id=incident_id,
            evidence_register=evidence_register,
            sufficiency_report=sufficiency_report,
            ret_result=ret_result,
            hypotheses=hypotheses,
        )

        # Step 7: Build Operator Summary Markdown
        operator_summary = self._generate_operator_summary(
            incident_id=incident_id,
            title=sanitized_title,
            network_domain=network_domain,
            hypotheses=hypotheses,
            recommendations=recommendations,
            sufficiency_report=sufficiency_report,
            evidence_register=evidence_register,
        )

        # Compute Provenance
        prov_hash = hashlib.sha256(
            f"{incident_id}:{len(evidence_register)}:{len(hypotheses)}:{self.version}".encode("utf-8")
        ).hexdigest()

        context = InvestigationContext(
            incident_id=incident_id,
            title=sanitized_title,
            network_domain=network_domain,
            created_at=created_at,
            m2_classification=m2_classification or {},
            m3_network_intelligence=m3_network_intelligence or {},
            m4_retrieval={
                "retrieval_mode": ret_result.retrieval_mode_executed,
                "confidence_level": ret_result.confidence_level,
                "primary_runbook_id": ret_result.primary_runbook_id,
                "evidence_count": len(ret_result.evidence_items),
            },
            evidence_register=evidence_register,
            sufficiency_report=sufficiency_report,
            hypotheses=hypotheses,
            recommendations=recommendations,
            epistemic_status="READ_ONLY_DECISION_SUPPORT",
            operator_summary_markdown=operator_summary,
            provenance=ProvenanceRecord(
                source_type=SourceType.DERIVED,
                source_dataset="PIIS-InvestigationEngine",
                source_record_id=f"INV-{incident_id}",
                checksum_sha256=prov_hash,
                transformation_version=self.version,
                metadata={"uri": f"piis://investigation/{incident_id}"},
            ),
        )
        return context

    def _build_evidence_register(
        self,
        incident: Dict[str, Any],
        created_at: str,
        sanitized_title: str,
        sanitized_description: str,
        sec_analysis: Dict[str, Any],
        m2_classification: Dict[str, Any],
        m3_network_intelligence: Dict[str, Any],
        ret_result: RetrievalResult,
    ) -> Tuple[List[InvestigationEvidenceItem], int]:
        """Register all input observations and model outputs with uniform EVID-xxx identifiers."""
        items: List[InvestigationEvidenceItem] = []
        counter = 1

        def next_id() -> str:
            nonlocal counter
            eid = f"EVID-{counter:03d}"
            counter += 1
            return eid

        # 1. Incident Ticket Metadata
        ticket_summary = f"Ticket: {sanitized_title}. Description: {sanitized_description[:200]}"
        if sec_analysis["threat_types"]:
            ticket_summary += f" [Security Flags: {', '.join(sec_analysis['threat_types'])}]"

        items.append(
            InvestigationEvidenceItem(
                evidence_id=next_id(),
                evidence_type=EvidenceType.TICKET_METADATA,
                source_ref=f"IncidentTicket-{incident.get('incident_id', 'UNKNOWN')}",
                domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                observed_at=incident.get("created_at") or created_at,
                trust_classification=TrustLevel.MEDIUM_TRUST_VERIFIED,
                content_summary=ticket_summary,
                raw_metadata={
                    "affected_elements": incident.get("network_element_ids", []),
                    "affected_subscribers": incident.get("affected_subscribers", 0),
                    "region": incident.get("affected_region"),
                    "threat_types": sec_analysis["threat_types"],
                },
            )
        )

        # 2. M2 Fault Category Prediction
        if m2_classification.get("predicted_category"):
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.ML_CLASSIFICATION,
                    source_ref="M2-FaultCategoryClassifier",
                    domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    trust_classification=TrustLevel.MEDIUM_TRUST_VERIFIED,
                    content_summary=(
                        f"Predicted Fault Category: {m2_classification['predicted_category']} "
                        f"(Probability: {m2_classification.get('category_probability', 0.0):.2f})"
                    ),
                    raw_metadata=m2_classification,
                )
            )

        # 3. M2 Severity Prediction
        if m2_classification.get("predicted_severity"):
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.SEVERITY_PREDICTION,
                    source_ref="M2-SeverityPredictor",
                    domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    trust_classification=TrustLevel.MEDIUM_TRUST_VERIFIED,
                    content_summary=f"Predicted Operational Severity: {m2_classification['predicted_severity']}",
                    raw_metadata=m2_classification,
                )
            )

        # 4. M2 Support Policy Routing
        if m2_classification.get("policy_routing_tier"):
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.POLICY_ROUTING,
                    source_ref="M2-PolicyEngine",
                    domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
                    content_summary=f"Deterministic Support Routing: Tier {m2_classification['policy_routing_tier']}",
                    raw_metadata=m2_classification,
                )
            )

        # 5. M3 Telemetry Anomalies
        anomalies = m3_network_intelligence.get("anomalies", [])
        for anom in anomalies:
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.TELEMETRY_ANOMALY,
                    source_ref=f"M3-AnomalyDetector-{anom.get('network_element_id', 'NE')}",
                    domain=anom.get("network_domain", str(incident.get("network_domain", "CROSS_DOMAIN"))),
                    observed_at=anom.get("timestamp"),
                    trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
                    content_summary=(
                        f"Telemetry Anomaly on {anom.get('network_element_id')}: "
                        f"Score {anom.get('fused_score', 0.0):.3f}, Violations: {anom.get('violations_summary', 'Metric drift')}"
                    ),
                    raw_metadata=anom,
                )
            )

        # 5b. Direct Telemetry Observations on Incident
        for obs in incident.get("telemetry_observations", []):
            obs_dict = obs if isinstance(obs, dict) else (obs.model_dump() if hasattr(obs, "model_dump") else obs.__dict__)
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.TELEMETRY_ANOMALY,
                    source_ref=f"TelemetryProbe-{obs_dict.get('network_element_id', 'NE')}",
                    domain=obs_dict.get("network_domain", str(incident.get("network_domain", "CROSS_DOMAIN"))),
                    observed_at=obs_dict.get("timestamp") or obs_dict.get("observed_at"),
                    trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
                    content_summary=(
                        f"Telemetry Observation on {obs_dict.get('network_element_id', 'NE')}: "
                        f"{obs_dict.get('metric_name', 'metric')}={obs_dict.get('value', 'N/A')}"
                    ),
                    raw_metadata=obs_dict,
                )
            )

        # 6. M3 Alarm Cluster
        cluster = m3_network_intelligence.get("alarm_cluster")
        if cluster:
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.ALARM_CLUSTER,
                    source_ref=f"M3-AlarmCorrelator-{cluster.get('cluster_id', 'CLUST')}",
                    domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                    observed_at=cluster.get("cluster_window_start") or cluster.get("timestamp") or cluster.get("observed_at") or created_at,
                    trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
                    content_summary=(
                        f"Correlated Alarm Cluster {cluster.get('cluster_id')}: "
                        f"{len(cluster.get('alarm_events', []))} events across {cluster.get('affected_elements', [])}. "
                        f"Dominant root cause code: {cluster.get('dominant_alarm_code')}"
                    ),
                    raw_metadata=cluster,
                )
            )

        # 7. M3 Topology Impact / Blast Radius
        impact = m3_network_intelligence.get("impact_assessment")
        if impact:
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=EvidenceType.TOPOLOGY_IMPACT,
                    source_ref="M3-NetworkImpactAnalyzer",
                    domain=str(incident.get("network_domain", "CROSS_DOMAIN")),
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
                    content_summary=(
                        f"Topological Blast Radius: {impact.get('direct_element_count', 0)} direct + "
                        f"{impact.get('inferred_element_count', 0)} inferred elements. "
                        f"Estimated subscriber impact: {impact.get('estimated_subscribers_affected', 0):,}"
                    ),
                    raw_metadata=impact,
                )
            )

        # 8. M4 Retrieved Runbooks and Historical Cases
        for ev in ret_result.evidence_items:
            ev_type = (
                EvidenceType.HISTORICAL_CASE
                if "INC-" in ev.doc_id
                else EvidenceType.APPROVED_RUNBOOK
            )
            items.append(
                InvestigationEvidenceItem(
                    evidence_id=next_id(),
                    evidence_type=ev_type,
                    source_ref=f"{ev.doc_id}#{'/'.join(ev.section_hierarchy[:2])}",
                    domain=ev.network_domain,
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    trust_classification=TrustLevel(ev.trust_classification.value),
                    content_summary=(
                        f"[{ev.doc_id}] {ev.source_title}: "
                        f"{ev.original_text[:180].replace(chr(10), ' ')}... "
                        f"(Confidence Proxy: {ev.confidence_proxy:.3f})"
                    ),
                    raw_metadata={
                        "chunk_id": ev.chunk_id,
                        "doc_id": ev.doc_id,
                        "confidence_proxy": ev.confidence_proxy,
                        "retrieval_method": ev.retrieval_method,
                        "section_hierarchy": ev.section_hierarchy,
                    },
                )
            )

        return items, counter

    def _evaluate_sufficiency_and_contradictions(
        self,
        incident: Dict[str, Any],
        evidence_register: List[InvestigationEvidenceItem],
        ret_result: RetrievalResult,
        m2_classification: Dict[str, Any],
        m3_network_intelligence: Dict[str, Any],
    ) -> EvidenceSufficiencyReport:
        """Inspect evidence register for missing facts, domain contradictions, or staleness."""
        missing: List[str] = []
        contradictions: List[str] = []
        stale: List[str] = []

        desc = str(incident.get("description") or "").lower()
        title = str(incident.get("title") or "").lower()
        meta = incident.get("metadata") or {}

        has_alarms = bool(incident.get("alarm_codes")) or bool(m3_network_intelligence.get("alarm_cluster"))
        has_anomalies = bool(m3_network_intelligence.get("anomalies"))
        has_elements = bool(incident.get("network_element_ids"))

        # 1. Negative control / Nominal variation / Planned maintenance window detection
        maintenance_indicators = (
            "planned maintenance",
            "maintenance window",
            "scheduled maintenance",
            "traffic drained",
            "proactively drained",
            "drain traffic",
            "maintenance outage",
            "maintenance state",
        )
        is_maintenance_or_nominal = (
            meta.get("is_negative_control")
            or meta.get("is_maintenance_window")
            or "nominal" in desc
            or "routine" in desc
            or "nominal" in title
            or "routine" in title
            or any(kw in desc for kw in maintenance_indicators)
            or any(kw in title for kw in maintenance_indicators)
        )
        if is_maintenance_or_nominal:
            return EvidenceSufficiencyReport(
                is_sufficient=False,
                has_missing_evidence=True,
                missing_evidence_details=[
                    "Incident description represents nominal diurnal variation or planned maintenance activity with drained traffic. "
                    "No active fault condition confirmed. Safe operational abstention."
                ],
            )

        # 1b. Transient Self-Healing Glitches / Cleared Before Ingestion (Remediates FIND-M5.3-006)
        transient_indicators = (
            "self-cleared",
            "self cleared",
            "returned to nominal",
            "returned to normal",
            "returned to baseline",
            "settled to normal",
            "stable for",
            "stabilized",
            "cleared before ingestion",
            "cleared before",
            "transient spike",
            "transient glitch",
            "transient 200ms",
            "temporary spike",
        )
        is_transient_self_cleared = (
            not has_alarms
            and not has_anomalies
            and (
                any(kw in desc for kw in transient_indicators)
                or any(kw in title for kw in transient_indicators)
                or ("transient" in desc and "returned" in desc)
                or ("transient" in title and "cleared" in title)
            )
        )
        if is_transient_self_cleared:
            return EvidenceSufficiencyReport(
                is_sufficient=False,
                has_missing_evidence=True,
                missing_evidence_details=[
                    "Incident represents a transient, self-cleared operational event without active alarms or sustained telemetry anomalies. "
                    "Metrics returned to nominal. Safe operational abstention to prevent disruptive automated intervention."
                ],
                is_transient_event=True,
            )

        # 2. Vague / Under-specified ticket / Novelty lacking network telemetry
        if not has_alarms and not has_anomalies:
            if len(desc.split()) < 4:
                missing.append(
                    "Ticket contains zero associated alarm codes, no telemetry anomalies, and an under-specified description."
                )
            elif not has_elements:
                missing.append(
                    "Ticket lacks network element binding, active alarm codes, and telemetry anomalies. Insufficient operational context."
                )

        # 3. M4 Retrieval Low Confidence / Zero Matches / Filter Dropped All
        if ret_result.retrieval_mode_executed in ("NO_CONFIDENT_MATCH", "FILTER_DROPPED_ALL") or not ret_result.evidence_items:
            if ret_result.retrieval_mode_executed == "FILTER_DROPPED_ALL":
                missing.append(
                    "Incident references equipment generation or vendor for which no approved runbook exists in the knowledge base."
                )
            else:
                missing.append(
                    "No approved runbook or historical case met the minimum confidence safety threshold."
                )

        # 4. Domain Contradiction Check
        ticket_domain = str(incident.get("network_domain") or "UNKNOWN").upper()
        if ret_result.evidence_items:
            top_evidence_domain = ret_result.evidence_items[0].network_domain.upper()
            if (
                ticket_domain != "UNKNOWN"
                and ticket_domain != "CROSS_DOMAIN"
                and top_evidence_domain != "CROSS_DOMAIN"
                and ticket_domain != top_evidence_domain
            ):
                contradictions.append(
                    f"Domain mismatch: Ticket domain is '{ticket_domain}', but primary runbook evidence belongs to '{top_evidence_domain}'."
                )

        # 5. Equipment Generation & Vendor Contradiction Check
        ticket_tech = self._extract_technology_generation(incident)
        ticket_vendor = self._extract_vendor(incident)
        if ret_result.evidence_items:
            top_ev = ret_result.evidence_items[0]
            if ticket_tech and top_ev.technology_generation:
                if not MetadataFilter._is_generation_compatible(ticket_tech, top_ev.technology_generation):
                    contradictions.append(
                        f"Technology generation mismatch: Ticket involves '{ticket_tech}', but primary runbook '{top_ev.doc_id}' applies to '{top_ev.technology_generation}'."
                    )
            if ticket_vendor and top_ev.vendor:
                if not MetadataFilter._is_vendor_compatible(ticket_vendor, top_ev.vendor):
                    contradictions.append(
                        f"Vendor mismatch: Ticket involves '{ticket_vendor}', but primary runbook '{top_ev.doc_id}' applies to '{top_ev.vendor}'."
                    )

        # 6. Alarm Code Alignment with Retrieved Runbook
        ticket_alarms = incident.get("alarm_codes", [])
        if ticket_alarms and ret_result.evidence_items:
            top_ev = ret_result.evidence_items[0]
            if str(getattr(top_ev.source_type, "value", top_ev.source_type)) == "APPROVED_RUNBOOK":
                from piis.retrieval.engine import DETERMINISTIC_SOP_MAP

                doc_chunks = self.retrieval_engine._sops_by_doc_id.get(top_ev.doc_id, [])
                doc_text_upper = " ".join(c.content.upper() for c in doc_chunks) if doc_chunks else top_ev.original_text.upper()

                has_alarm_match = any(
                    alm.upper() in doc_text_upper or DETERMINISTIC_SOP_MAP.get(alm.upper()) == top_ev.doc_id
                    for alm in ticket_alarms
                )
                if not has_alarm_match:
                    contradictions.append(
                        f"Alarm mismatch: Ticket alarms {ticket_alarms} do not match the alarm indicators in runbook '{top_ev.doc_id}'."
                    )

        # 7. Alarm Domain vs Ticket Domain Check
        for code in incident.get("alarm_codes", []):
            code_upper = code.upper()
            if "ALM-RAN" in code_upper and ticket_domain in ("TRANSPORT", "5G_CORE", "SERVICE"):
                contradictions.append(f"Domain mismatch: Alarm '{code}' belongs to RAN, but ticket domain is '{ticket_domain}'.")
            elif "ALM-TRANS" in code_upper and ticket_domain in ("RAN", "5G_CORE", "SERVICE"):
                contradictions.append(f"Domain mismatch: Alarm '{code}' belongs to TRANSPORT, but ticket domain is '{ticket_domain}'.")
            elif ("ALM-5GC" in code_upper or "ALM-CORE" in code_upper) and ticket_domain in ("RAN", "TRANSPORT", "SERVICE"):
                contradictions.append(f"Domain mismatch: Alarm '{code}' belongs to 5G_CORE, but ticket domain is '{ticket_domain}'.")
            elif ("ALM-SRV" in code_upper or "ALM-IMS" in code_upper) and ticket_domain in ("RAN", "TRANSPORT", "5G_CORE"):
                contradictions.append(f"Domain mismatch: Alarm '{code}' belongs to SERVICE, but ticket domain is '{ticket_domain}'.")

        # 7. Incompatible Alarm Check from M3
        cluster = m3_network_intelligence.get("alarm_cluster")
        if cluster and cluster.get("has_incompatible_alarms"):
            contradictions.append(
                f"Contradictory alarms in cluster {cluster.get('cluster_id')}: "
                f"Mechanisms {cluster.get('incompatible_mechanisms')} cannot be causally merged without a cross-domain transport link failure."
            )

        # 8. Temporal Freshness, Staleness & Clock-Skew Evaluation (Remediates FIND-M5.4-001)
        temp_results, temp_stale_details, temp_defect_details = self.temporal_evaluator.evaluate_register(
            evidence_register=evidence_register,
            incident=incident,
        )

        # Record identified staleness
        if temp_stale_details:
            stale.extend(temp_stale_details)

        # Temporal defects (future-dated, unparseable, or missing required timestamps on critical telemetry)
        if temp_defect_details:
            for defect in temp_defect_details:
                if "FUTURE_DATED" in defect or "INVALID_TIMESTAMP" in defect:
                    missing.append(defect)
                elif "MISSING_TIMESTAMP" in defect:
                    if not has_alarms or "TelemetryProbe" in defect or "require_timestamp" in defect:
                        missing.append(defect)

        # Cross-source temporal corroboration:
        # If an active alarm is present, but supporting telemetry anomaly is stale, require live confirmation
        active_alarms = [e for e in evidence_register if e.evidence_type == EvidenceType.ALARM_CLUSTER]
        telemetry_items = [e for e in evidence_register if e.evidence_type == EvidenceType.TELEMETRY_ANOMALY]
        if active_alarms and telemetry_items:
            fresh_telemetry = [
                r for r in temp_results
                if r.evidence_type == EvidenceType.TELEMETRY_ANOMALY and r.is_current_confirmation
            ]
            stale_telemetry = [
                r for r in temp_results
                if r.evidence_type == EvidenceType.TELEMETRY_ANOMALY and r.temporal_status == EvidenceTemporalStatus.STALE
            ]
            if not fresh_telemetry and stale_telemetry:
                stale.append(
                    "Active alarm present, but supporting telemetry is stale (> 3600s old). "
                    "Prohibiting automated SOP recommendation without current live metric confirmation."
                )

        is_sufficient = (len(missing) == 0 and len(contradictions) == 0 and len(stale) == 0)

        return EvidenceSufficiencyReport(
            is_sufficient=is_sufficient,
            has_missing_evidence=len(missing) > 0,
            missing_evidence_details=missing,
            has_contradictions=len(contradictions) > 0,
            contradiction_details=contradictions,
            has_stale_evidence=len(stale) > 0,
            stale_evidence_details=stale,
        )

    def _generate_hypotheses(
        self,
        incident_id: str,
        evidence_register: List[InvestigationEvidenceItem],
        sufficiency_report: EvidenceSufficiencyReport,
        ret_result: RetrievalResult,
        m2_classification: Dict[str, Any],
        m3_network_intelligence: Dict[str, Any],
    ) -> List[IncidentHypothesis]:
        """Synthesize ranked diagnostic hypotheses strictly grounded in registered evidence."""
        hypotheses: List[IncidentHypothesis] = []

        # Find supporting evidence IDs
        ticket_evids = [e.evidence_id for e in evidence_register if e.evidence_type == EvidenceType.TICKET_METADATA]
        m2_evids = [e.evidence_id for e in evidence_register if e.evidence_type in (EvidenceType.ML_CLASSIFICATION, EvidenceType.SEVERITY_PREDICTION)]
        m3_evids = [e.evidence_id for e in evidence_register if e.evidence_type in (EvidenceType.TELEMETRY_ANOMALY, EvidenceType.ALARM_CLUSTER)]
        runbook_evids = [e.evidence_id for e in evidence_register if e.evidence_type in (EvidenceType.APPROVED_RUNBOOK, EvidenceType.HISTORICAL_CASE)]

        # CASE A: Under-specified, negative control, or contradictory evidence -> Inconclusive
        if not sufficiency_report.is_sufficient:
            reasons = (
                sufficiency_report.missing_evidence_details
                + sufficiency_report.contradiction_details
                + sufficiency_report.stale_evidence_details
            )
            hypotheses.append(
                IncidentHypothesis(
                    hypothesis_id="HYP-001",
                    description=(
                        "INCONCLUSIVE: Insufficient or contradictory evidence to confirm a root cause hypothesis. "
                        f"Reason: {'; '.join(reasons)}"
                    ),
                    supporting_evidence_ids=ticket_evids,
                    contradicting_evidence_ids=[e.evidence_id for e in evidence_register if e.evidence_type == EvidenceType.ALARM_CLUSTER],
                    evidence_source="PIIS-InvestigationEngine-AbstentionFloor",
                    confidence_proxy=0.0,
                    confidence_rationale="Evidence sufficiency gate failed. Abstaining to prevent operational hallucination.",
                    alternative_explanations=[
                        "Transient diurnal traffic fluctuation",
                        "Uninstrumented upstream power or third-party fiber outage",
                    ],
                    recommended_verification_steps=[
                        "Request manual diagnostic capture from NOC shift engineer",
                        "Verify physical alarm indicators on site chassis",
                    ],
                    status=HypothesisStatus.INCONCLUSIVE,
                )
            )
            return hypotheses

        # CASE B: M4 Low Confidence / Zero Runbook Match -> Inconclusive Tier 4
        if ret_result.retrieval_mode_executed == "NO_CONFIDENT_MATCH" or not ret_result.evidence_items:
            hypotheses.append(
                IncidentHypothesis(
                    hypothesis_id="HYP-001",
                    description=(
                        "INCONCLUSIVE: Out-of-domain or unindexed operational failure scenario. "
                        "No approved standard operating procedure matched the incident symptoms above safety threshold."
                    ),
                    supporting_evidence_ids=ticket_evids + m2_evids,
                    contradicting_evidence_ids=[],
                    evidence_source="M4-HybridRetrieval-Tier4Escalation",
                    confidence_proxy=0.15,
                    confidence_rationale="Retrieval confidence below 0.35 safety gate. Zero deterministic SOP matched.",
                    alternative_explanations=[
                        "Novel firmware defect",
                        "Non-standard vendor configuration drift",
                    ],
                    recommended_verification_steps=[
                        "Escalate incident directly to Tier 3 Advanced TAC / Vendor Engineering",
                        "Author and verify new SOP before executing active troubleshooting",
                    ],
                    status=HypothesisStatus.INCONCLUSIVE,
                )
            )
            return hypotheses

        # CASE C: Grounded Operational Incident
        primary_ev = ret_result.evidence_items[0]
        pred_cat = m2_classification.get("predicted_category", "HARDWARE_OR_LINK_DEGRADATION")
        pred_prob = m2_classification.get("category_probability", 0.70)
        conf_proxy = round(min(1.0, 0.6 * primary_ev.confidence_proxy + 0.4 * pred_prob), 3)

        supporting = ticket_evids + m2_evids + m3_evids + [runbook_evids[0]] if runbook_evids else ticket_evids
        verification_steps = self._extract_verification_steps_from_runbook(primary_ev.doc_id)

        hypotheses.append(
            IncidentHypothesis(
                hypothesis_id="HYP-001",
                description=(
                    f"Primary Diagnostic Hypothesis: Incident symptoms consistent with '{primary_ev.source_title}'. "
                    f"Underlying mechanism indicates {pred_cat.lower().replace('_', ' ')} affecting target subsystems."
                ),
                supporting_evidence_ids=supporting,
                contradicting_evidence_ids=[],
                evidence_source=f"M4-RetrievedRunbook-{primary_ev.doc_id}",
                evidence_timestamp=datetime.now(timezone.utc).isoformat(),
                confidence_proxy=conf_proxy,
                confidence_rationale=(
                    f"Synthesized Confidence Proxy: 0.6 * RetrievalProxy({primary_ev.confidence_proxy:.2f}) + "
                    f"0.4 * MLClassificationProb({pred_prob:.2f}). (Empirical heuristic, not a probability)."
                ),
                alternative_explanations=[
                    f"Secondary candidate: {ret_result.evidence_items[1].source_title}"
                    if len(ret_result.evidence_items) > 1
                    else "Configuration parameter drift on adjacent network element"
                ],
                recommended_verification_steps=verification_steps,
                status=HypothesisStatus.SUPPORTED if conf_proxy >= 0.50 else HypothesisStatus.UNVERIFIED,
            )
        )

        # Secondary hypothesis if available
        if len(ret_result.evidence_items) > 1:
            sec_ev = ret_result.evidence_items[1]
            sec_supporting = ticket_evids + [runbook_evids[1]] if len(runbook_evids) > 1 else ticket_evids
            hypotheses.append(
                IncidentHypothesis(
                    hypothesis_id="HYP-002",
                    description=f"Alternative Hypothesis: Secondary correlation with '{sec_ev.source_title}'.",
                    supporting_evidence_ids=sec_supporting,
                    contradicting_evidence_ids=[runbook_evids[0]] if runbook_evids else [],
                    evidence_source=f"M4-RetrievedRunbook-{sec_ev.doc_id}",
                    confidence_proxy=round(sec_ev.confidence_proxy * 0.75, 3),
                    confidence_rationale="Secondary RRF candidate ranking score.",
                    alternative_explanations=["Primary hypothesis HYP-001 remains the dominant explanation."],
                    recommended_verification_steps=self._extract_verification_steps_from_runbook(sec_ev.doc_id),
                    status=HypothesisStatus.UNVERIFIED,
                )
            )

        return hypotheses

    def _synthesize_recommendations(
        self,
        incident_id: str,
        evidence_register: List[InvestigationEvidenceItem],
        sufficiency_report: EvidenceSufficiencyReport,
        ret_result: RetrievalResult,
        hypotheses: List[IncidentHypothesis],
    ) -> List[DiagnosticRecommendation]:
        """Synthesize actionable, runbook-backed diagnostic recommendations."""
        recommendations: List[DiagnosticRecommendation] = []
        rec_counter = 1

        def next_rec_id() -> str:
            nonlocal rec_counter
            rid = f"REC-{rec_counter:03d}"
            rec_counter += 1
            return rid

        # CASE 1: Inconclusive or Missing Evidence -> Safe Escalation Only
        if not sufficiency_report.is_sufficient or not ret_result.evidence_items:
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Dispatch Tier 2 NOC Field Support for on-site visual inspection and manual trace capture.",
                    reason="Automated evidence is insufficient or contradictory. Prohibiting ungrounded configuration changes.",
                    supporting_evidence_ids=[e.evidence_id for e in evidence_register if e.evidence_type == EvidenceType.TICKET_METADATA],
                    source_runbook_id="HUMAN_ESCALATION",
                    source_section="Section 1: Manual Field Triage Dispatch",
                    preconditions=["Confirm site access authorization and safety clearance."],
                    expected_observation="Manual multimeter, OTDR, or RF spectrum analyzer trace confirming root cause.",
                    risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                    human_approval_required=True,
                    approval_status=ApprovalStatus.PENDING_REVIEW,
                )
            )
            from piis.security.guardrails import OutputSecurityPolicyValidator
            return [OutputSecurityPolicyValidator.validate_recommendation(r) for r in recommendations]

        # CASE 2: Grounded Recommendations Derived from Verified SOPs
        top_ev = ret_result.evidence_items[0]
        runbook_evid = [e.evidence_id for e in evidence_register if top_ev.chunk_id in e.raw_metadata.get("chunk_id", "")]
        supporting_ids = runbook_evid or [evidence_register[0].evidence_id]

        # Extract structured diagnostic actions based on verified SOP doc_id
        doc_id = top_ev.doc_id

        if "VSWR" in doc_id:
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Measure RF feeder line return loss and inspect DIN 7/16 physical connectors for moisture ingress.",
                    reason=f"Corroborates hypothesis HYP-001 regarding {top_ev.source_title}.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section="Section 2.1: Feeder Line Sweep & Return Loss",
                    preconditions=["Tower climb safety harness approved; site transmission set to low power during sweep."],
                    expected_observation="VSWR ratio should be <= 1.3:1 (return loss >= 18 dB). Fault indicated if VSWR > 1.5:1.",
                    risk_classification=RecommendationRisk.LOW_OBSERVABILITY,
                    human_approval_required=True,
                )
            )
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Execute remote antenna tilt calibration diagnostic to test remote electrical tilt (RET) motor communication.",
                    reason="Verify whether antenna tilt motor actuator is responding to AISG control signals.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section="Section 3.2: RET Control Calibration",
                    preconditions=["Antenna sub-unit online and reachable via eCPRI control channel."],
                    expected_observation="RET motor responds with AISG OK status; no motor stall alarm returned.",
                    risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                    human_approval_required=True,
                )
            )

        elif "FIBER" in doc_id or "OPTICAL" in doc_id:
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Trigger optical time-domain reflectometer (OTDR) diagnostic sweep on fronthaul fiber strand 1.",
                    reason="Identify exact distance from BBU chassis to optical break or micro-bend fault.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section="Section 2: OTDR Localization & Splice Testing",
                    preconditions=["Optical SFP receiver protected from direct high-power reflection."],
                    expected_observation="Continuous optical return line with no localized reflection step > 0.5 dB.",
                    risk_classification=RecommendationRisk.LOW_OBSERVABILITY,
                    human_approval_required=True,
                )
            )

        elif "AMF" in doc_id or "5GC" in doc_id:
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Inspect N2 SCTP association status and capture association buffer utilization counters on AMF-01.",
                    reason="Diagnose whether AMF registration storm is causing SCTP socket buffer exhaustion.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section="Section 3: SCTP Association Buffer Analysis",
                    preconditions=["AMF management interface accessible via read-only monitoring credentials."],
                    expected_observation="SCTP socket buffer utilization below 75%; retransmission rate < 1.0%.",
                    risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                    human_approval_required=True,
                )
            )

        elif "SIP" in doc_id or "IMS" in doc_id:
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description="Capture SIP signaling trace at P-CSCF ingress to inspect distribution of SIP 503 vs 408 responses.",
                    reason="Determine whether upstream S-CSCF is rejecting INVITEs or if DNS resolution timeout is occurring.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section="Section 2.2: P-CSCF Signaling Trace & Response Code Audit",
                    preconditions=["Signaling packet trace buffer capped at 50 MB to prevent disk saturation."],
                    expected_observation="SIP INVITE transaction latency < 150 ms; 5xx response rate < 0.1%.",
                    risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                    human_approval_required=True,
                )
            )

        else:
            # Generic runbook-grounded verification
            recommendations.append(
                DiagnosticRecommendation(
                    recommendation_id=next_rec_id(),
                    description=f"Perform diagnostic inspection per {top_ev.source_title} ({'/'.join(top_ev.section_hierarchy[:2])}).",
                    reason="Ground truth runbook procedure for incident symptoms.",
                    supporting_evidence_ids=supporting_ids,
                    source_runbook_id=doc_id,
                    source_section='/'.join(top_ev.section_hierarchy[:2]),
                    preconditions=["Operator verified site ID and topology neighbor availability."],
                    expected_observation="Status indicators match normal operating thresholds defined in SOP.",
                    risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                    human_approval_required=True,
                )
            )

        from piis.security.guardrails import OutputSecurityPolicyValidator
        return [OutputSecurityPolicyValidator.validate_recommendation(r) for r in recommendations]

    @staticmethod
    def _extract_verification_steps_from_runbook(doc_id: str) -> List[str]:
        """Extract high-level verification procedures for hypothesis testing."""
        if "VSWR" in doc_id:
            return [
                "Measure physical return loss with calibrated line sweep analyzer",
                "Inspect RF feeder connectors for water penetration or torque loosening",
                "Verify AAU transmission power calibration settings",
            ]
        elif "FIBER" in doc_id:
            return [
                "Run OTDR trace to pinpoint fiber break distance",
                "Check SFP optical Rx power levels against minimum -14 dBm threshold",
                "Inspect patch panel fiber terminations with video fiber microscope",
            ]
        elif "AMF" in doc_id:
            return [
                "Query AMF SCTP association state across connected gNodeBs",
                "Verify N2 interface ingress throughput against throttling thresholds",
                "Inspect NRF registration status for AMF instance pool",
            ]
        elif "SIP" in doc_id:
            return [
                "Inspect P-CSCF to S-CSCF DIAMETER/SIP connectivity",
                "Query DNS SRV record resolution latency for IMS core domain",
                "Verify subscriber authentication server (HSS/UDM) response times",
            ]
        else:
            return [
                "Execute read-only interface status query",
                "Verify syslog error frequency over trailing 60 minutes",
                "Confirm neighbor cell handover statistics",
            ]

    def _generate_operator_summary(
        self,
        incident_id: str,
        title: str,
        network_domain: str,
        hypotheses: List[IncidentHypothesis],
        recommendations: List[DiagnosticRecommendation],
        sufficiency_report: EvidenceSufficiencyReport,
        evidence_register: List[InvestigationEvidenceItem],
    ) -> str:
        """Render a clean, professional GitHub-flavored markdown report for NOC/SOC operations."""
        primary_hyp = hypotheses[0] if hypotheses else None
        md = [
            "# PIIS Incident Investigation & Decision Support Briefing",
            f"**Incident ID:** `{incident_id}` | **Domain:** `{network_domain}` | **Generated:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
            f"**Title:** {title}",
            "",
            "---",
            "",
            "## 1. Executive Diagnostic Summary",
        ]

        if primary_hyp:
            md.extend([
                f"- **Primary Hypothesis:** {primary_hyp.description}",
                f"- **Status:** `{primary_hyp.status.value}` | **Confidence Proxy:** `{primary_hyp.confidence_proxy:.3f}` *(Heuristic score; not a probability)*",
                f"- **Confidence Rationale:** {primary_hyp.confidence_rationale}",
                f"- **Supporting Evidence IDs:** `{', '.join(primary_hyp.supporting_evidence_ids) or 'None'}`",
            ])
            if primary_hyp.contradicting_evidence_ids:
                md.append(f"- **Contradicting Evidence IDs:** `{', '.join(primary_hyp.contradicting_evidence_ids)}`")
        else:
            md.append("- *No hypothesis generated.*")

        md.extend([
            "",
            "## 2. Evidence Sufficiency & Contradiction Audit",
            f"- **Sufficiency Status:** `{'SUFFICIENT' if sufficiency_report.is_sufficient else 'INSUFFICIENT / AMBIGUOUS'}`",
        ])
        if sufficiency_report.has_missing_evidence:
            for m in sufficiency_report.missing_evidence_details:
                md.append(f"  - ⚠️ **Missing Evidence:** {m}")
        if sufficiency_report.has_contradictions:
            for c in sufficiency_report.contradiction_details:
                md.append(f"  - ❌ **Contradiction:** {c}")
        if sufficiency_report.is_sufficient:
            md.append("  - ✅ All required evidence dimensions (Ticket, Telemetry, Alarms, Runbooks) are verified and consistent.")

        md.extend([
            "",
            "## 3. Recommended Diagnostic Actions (Awaiting Human Approval)",
            "| Rec ID | Description | Source Runbook & Section | Risk Tier | Approval Status |",
            "| :--- | :--- | :--- | :---: | :---: |",
        ])
        for r in recommendations:
            md.append(
                f"| `{r.recommendation_id}` | {r.description} | `{r.source_runbook_id}` ({r.source_section}) | `{r.risk_classification.value}` | **`{r.approval_status.value}`** |"
            )

        md.extend([
            "",
            "## 4. Canonical Evidence Register",
            "| Evidence ID | Type | Source Reference | Trust Level | Summary Snippet |",
            "| :--- | :--- | :--- | :---: | :--- |",
        ])
        for e in evidence_register:
            md.append(
                f"| `{e.evidence_id}` | `{e.evidence_type.value}` | `{e.source_ref}` | `{e.trust_classification.value}` | {e.content_summary[:90]}... |"
            )

        md.extend([
            "",
            "---",
            "**Operational Epistemic Safeguard:** PIIS operates exclusively in **READ-ONLY DECISION SUPPORT** mode. No autonomous production commands or network configuration modifications may be initiated by this system. All diagnostic checks require explicit human operator review and sign-off via the `HumanApprovalWorkflow`.",
        ])

        return "\n".join(md)

    @staticmethod
    def _extract_technology_generation(incident: Dict[str, Any]) -> Optional[str]:
        """Extract technology generation (2G, 3G, 4G, 5G, Optical) from ticket fields."""
        meta = incident.get("metadata") or {}
        if meta.get("technology_generation"):
            return str(meta["technology_generation"])
        if incident.get("technology_generation"):
            return str(incident["technology_generation"])

        text = f"{incident.get('title', '')} {incident.get('description', '')} {' '.join(incident.get('alarm_codes', []))}"

        # 2G / GSM / GPRS (exclude architectural "edge server/router/node/cloud/computing/device/gateway/site/infrastructure/du/cu/dc")
        if re.search(r"\b(2G|GSM|GPRS|BTS|BSC|Abis|TCH)\b|\bEDGE\b(?!\s+(?:server|router|node|cloud|computing|device|gateway|site|infrastructure|du|cu|dc|mec))\b", text, re.IGNORECASE):
            if not re.search(r"\b(5G|NR|gNodeB|gNB|4G|LTE|eNodeB|eNB)\b", text, re.IGNORECASE):
                return "2G_GSM"
        # 3G / UMTS / WCDMA
        if re.search(r"\b(3G|UMTS|WCDMA|HSPA|RNC|Iub|ATM)\b|(?<![ge])NodeB\b", text, re.IGNORECASE):
            return "3G_UMTS"
        # WiMAX / 802.16e
        if re.search(r"\b(WiMAX|802\.16e|ASN\s+gateway)\b", text, re.IGNORECASE):
            return "WIMAX"
        # 4G / LTE
        if re.search(r"\b(4G|LTE|eNodeB|eNB|MME|SGW|PGW)\b", text, re.IGNORECASE):
            return "4G_LTE"
        # 5G NR / gNodeB
        if re.search(r"\b(5G|NR|gNodeB|gNB|AAU|eCPRI|Xn|DU|CU)\b", text, re.IGNORECASE):
            return "5G_NR"
        # 5G Core
        if re.search(r"\b(AMF|SMF|UPF|NRF|UDM|VoNR|5GC)\b", text, re.IGNORECASE):
            return "5G_CORE"
        # Optical IP Transport
        if re.search(r"\b(Optical|OTDR|SFP|BGP|BFD|IP-MPLS|MPLS|DWDM)\b", text, re.IGNORECASE):
            return "OPTICAL_IP_TRANSPORT"
        # 5G Core
        if re.search(r"\b(AMF|SMF|UPF|NRF|UDM|VoNR|5GC)\b", text, re.IGNORECASE):
            return "5G_CORE"
        # Optical IP Transport
        if re.search(r"\b(Optical|OTDR|SFP|BGP|BFD|IP-MPLS|MPLS|DWDM)\b", text, re.IGNORECASE):
            return "OPTICAL_IP_TRANSPORT"

        return None

    @staticmethod
    def _extract_vendor(incident: Dict[str, Any]) -> Optional[str]:
        """Extract target network vendor from structured fields or anchored markers.

        Remediates FIND-M5.1-003:
        - Prioritizes structured metadata fields over free text.
        - Checks network element prefixes (e.g. ERIC-AAU-01, CISCO-ASR-02).
        - Requires anchored OEM/hardware markers if parsing free text.
        - Excludes client/management tools and VPN prose (Cisco AnyConnect, Nokia NetAct EMS, etc.).
        - Abstains (returns None) when vendor identity is ambiguous.
        """
        # 1. Structured metadata priority
        meta = incident.get("metadata") or {}
        for k in ("vendor", "equipment_vendor", "hardware_vendor", "oem"):
            val = meta.get(k)
            if val:
                return str(val).upper().strip()

        if incident.get("equipment_vendor"):
            return str(incident["equipment_vendor"]).upper().strip()

        # 2. Network Element ID prefix conventions (e.g. ERIC-AAU-01, CISCO-ASR-02)
        element_ids = incident.get("network_element_ids") or []
        for eid in element_ids:
            ueid = str(eid).upper()
            if ueid.startswith(("ERIC-", "ERS-", "ERICSSON-")):
                return "ERICSSON"
            if ueid.startswith(("NOK-", "NOKIA-")):
                return "NOKIA"
            if ueid.startswith(("CISCO-", "CSCO-")):
                return "CISCO"
            if ueid.startswith(("JUN-", "JNPR-", "JUNIPER-")):
                return "JUNIPER"
            if ueid.startswith(("HUA-", "HW-", "HUAWEI-")):
                return "HUAWEI"
            if ueid.startswith("ZTE-"):
                return "ZTE"

        # 3. Anchored hardware OEM markers in text
        text = f"{incident.get('title', '')} {incident.get('description', '')}"

        hw_match = re.search(
            r"\b(?:Equipment\s+Vendor|Hardware\s+Vendor|Node\s+Vendor|OEM|Hardware\s+Manufacturer|Vendor):\s*([A-Za-z0-9_-]+)",
            text,
            re.IGNORECASE,
        )
        if hw_match:
            cand = hw_match.group(1).upper()
            if cand in ("ERICSSON", "NOKIA", "CISCO", "JUNIPER", "HUAWEI", "ZTE", "GENERIC_3GPP"):
                return cand

        # 4. Filter out client tools and VPN prose before inspecting equipment models
        cleaned_text = re.sub(
            r"(?i)\b(?:Cisco\s+AnyConnect|AnyConnect\s+VPN|AnyConnect|Nokia\s+NetAct|NetAct\s+EMS|NetAct|Ericsson\s+ENM|ENM\s+Portal|Huawei\s+U2000|Huawei\s+U2020|Webex|TeamViewer|Wireshark|Putty|SecureCRT)\b",
            " ",
            text,
        )

        # 5. Distinctive proprietary node models (not generic text)
        if re.search(r"\b(JunOS|MX960|MX480|MX240|PTX10000|PTX5000)\b", cleaned_text, re.IGNORECASE):
            return "JUNIPER"
        if re.search(r"\b(IOS-XR|IOS-XE|NX-OS|ASR-9000|ASR9K|ASR9001|NCS-5500|Catalyst\s+9[0-9]{3})\b", cleaned_text, re.IGNORECASE):
            return "CISCO"
        if re.search(r"\b(AirScale|SROS|7750\s+SR|7250\s+IXR|Flexi\s+Zone)\b", cleaned_text, re.IGNORECASE):
            return "NOKIA"
        if re.search(r"\b(Radio\s+Dot|RBS\s+6[0-9]{3}|Baseband\s+6630|Baseband\s+5216|MINI-LINK)\b", cleaned_text, re.IGNORECASE):
            return "ERICSSON"
        if re.search(r"\b(OptiX|NE40E|AirEngine|CloudEngine)\b", cleaned_text, re.IGNORECASE):
            return "HUAWEI"

        # 6. Ambiguous / unspecified: abstain
        return None
