"""Demonstration data bootstrap orchestrator for PIIS.

Populates authentic canonical incidents, multi-point telemetry, alarms,
investigation contexts, and review queue recommendations upon application startup,
ensuring all UI workspaces and API endpoints function deterministically.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from piis.integrations.alarms.oss_nms import OSSAlarmAdapter
from piis.integrations.contracts import IngestionEnvelope
from piis.integrations.itsm.servicenow import ServiceNowAdapter
from piis.integrations.telemetry.prometheus import PrometheusAdapter
from piis.investigation.approval import HumanApprovalWorkflow
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)
from piis.pipeline.unified import UnifiedIngestionPipeline

logger = logging.getLogger("piis.bootstrap")


def bootstrap_demonstration_data(
    pipeline: UnifiedIngestionPipeline,
    workflow: Optional[HumanApprovalWorkflow] = None,
) -> Dict[str, Any]:
    """Seed comprehensive telecom demonstration data into pipeline and workflow."""
    logger.info("Bootstrapping PIIS demonstration dataset...")

    # Ensure adapters for all relevant source systems are registered
    pipeline.register_adapter(ServiceNowAdapter())
    pipeline.register_adapter(PrometheusAdapter())
    pipeline.register_adapter(OSSAlarmAdapter(adapter_id="ALARM-GENERIC-01", source_system="GenericOSS", vendor_hint="NOKIA"))
    pipeline.register_adapter(OSSAlarmAdapter(adapter_id="ALARM-NOKIA-01", source_system="NokiaOSS", vendor_hint="NOKIA"))
    pipeline.register_adapter(OSSAlarmAdapter(adapter_id="ALARM-CISCO-01", source_system="CiscoOSS", vendor_hint="CISCO"))

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_snow = now.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Canonical Telecom Incidents
    tickets = [
        {
            "sys_id": "a98df7b01b827300c0147596cc4bcb11",
            "number": "INC0089201",
            "short_description": "Sector degraded: High VSWR on 5G NR Cell-1",
            "description": "NOC telemetry indicates RF feeder mismatch and VSWR > 1.8 on gNodeB GNB-RAN-701.",
            "priority": "2",
            "category": "RAN",
            "u_network_domain": "RAN",
            "cmdb_ci": "GNB-RAN-701",
            "state": "1",
            "sys_created_on": now_snow,
            "u_affected_subscribers": 1420,
            "u_fault_category": "antenna_vswr_fault",
        },
        {
            "sys_id": "b12cf8e02c918400d0258607dd5cdc22",
            "number": "INC0089202",
            "short_description": "Core 5G UPF session drops and high forwarding latency",
            "description": "Sustained session drops on UPF-CORE-01 exceeding 12% drop ratio over 15 minutes.",
            "priority": "1",
            "category": "Core Network",
            "u_network_domain": "5G_CORE",
            "cmdb_ci": "UPF-CORE-01",
            "state": "1",
            "sys_created_on": now_snow,
            "u_affected_subscribers": 8900,
            "u_fault_category": "upf_session_drop",
        },
        {
            "sys_id": "c34df9f03d029500e0369718ee6ded33",
            "number": "INC1009842",
            "short_description": "Core UPF packet drop threshold breach - Frankfurt DC-01",
            "description": "High volume bearer drop alarms detected on user plane function node UPF-CORE-01.",
            "priority": "1",
            "category": "Core Network",
            "u_network_domain": "5G_CORE",
            "cmdb_ci": "UPF-CORE-01",
            "state": "1",
            "sys_created_on": now_snow,
            "u_affected_subscribers": 45000,
            "u_fault_category": "upf_bearer_drop",
        },
        {
            "sys_id": "d45ea0a04e130600f0470829ff7efe44",
            "number": "INC1009843",
            "short_description": "Optical transponder degradation - Munich DWDM Link-4",
            "description": "Bit error rate surge and optical power attenuation on 100G transponder DWDM-MUC-04.",
            "priority": "2",
            "category": "Transport",
            "u_network_domain": "TRANSPORT",
            "cmdb_ci": "DWDM-MUC-04",
            "state": "1",
            "sys_created_on": now_snow,
            "u_affected_subscribers": 22000,
            "u_fault_category": "optical_power_loss",
        },
    ]

    ingested_incident_ids: List[str] = []
    for t in tickets:
        env = IngestionEnvelope.create(
            source_system="ServiceNow",
            source_type="OPERATOR_INTERNAL",
            raw_payload=t,
            external_event_id=t["number"],
            observation_timestamp=now_iso,
        )
        res = pipeline.ingest_envelope(env)
        if res.canonical_id:
            ingested_incident_ids.append(res.canonical_id)

    # 2. Ingest Alarms
    alarms = [
        {
            "alarm_id": "NOK-ALM-9921",
            "element_id": "GNB-RAN-701",
            "network_element_id": "GNB-RAN-701",
            "severity": "CRITICAL",
            "alarm_text": "VSWR > 1.8 RF feeder mismatch on Cell 1",
            "event_time": now_iso,
            "specific_problem": "Feeder Cable SWR High",
            "alarm_code": "7100",
        },
        {
            "alarm_id": "CSC-ALM-4412",
            "element_id": "UPF-CORE-01",
            "network_element_id": "UPF-CORE-01",
            "severity": "CRITICAL",
            "alarm_text": "UPF Buffer Overflow & Session Drop Ratio > 12%",
            "event_time": now_iso,
            "specific_problem": "Session Buffer Overflow",
        },
        {
            "alarm_id": "OPT-ALM-1029",
            "element_id": "DWDM-MUC-04",
            "network_element_id": "DWDM-MUC-04",
            "severity": "MAJOR",
            "alarm_text": "Optical Rx Power Degraded below -18dBm",
            "event_time": now_iso,
            "specific_problem": "Optical Sensitivity Attenuation",
        },
    ]

    for alm in alarms:
        source = "NokiaOSS" if "NOK" in alm["alarm_id"] else ("CiscoOSS" if "CSC" in alm["alarm_id"] else "GenericOSS")
        env = IngestionEnvelope.create(
            source_system=source,
            source_type="OSS_NMS_ALARM",
            raw_payload=alm,
            external_event_id=alm["alarm_id"],
            observation_timestamp=now_iso,
        )
        pipeline.ingest_envelope(env)

    # 3. Ingest Telemetry
    telemetry_samples = [
        {
            "metric_name": "vswr_ratio",
            "network_element_id": "GNB-RAN-701",
            "value": 1.94,
            "unit": "ratio",
            "timestamp": now_iso,
            "labels": {"cell_id": "CELL-01", "carrier": "NR_N78"},
        },
        {
            "metric_name": "packet_drop_ratio",
            "network_element_id": "UPF-CORE-01",
            "value": 0.142,
            "unit": "ratio",
            "timestamp": now_iso,
            "labels": {"gateway": "UPF-01", "interface": "N3"},
        },
        {
            "metric_name": "optical_rx_power_dbm",
            "network_element_id": "DWDM-MUC-04",
            "value": -18.4,
            "unit": "dBm",
            "timestamp": now_iso,
            "labels": {"port": "PORT-1", "lambda": "1550nm"},
        },
    ]

    for tel in telemetry_samples:
        env = IngestionEnvelope.create(
            source_system="Prometheus",
            source_type="TELEMETRY",
            raw_payload=tel,
            external_event_id=f"TEL-{tel['network_element_id']}",
            observation_timestamp=now_iso,
        )
        pipeline.ingest_envelope(env)

    # 4. Generate Investigation Contexts & Register Recommendations
    investigation_count = 0
    recommendations_registered = 0
    for inc_id in ingested_incident_ids:
        try:
            ctx = pipeline.investigate_incident(inc_id)
            if ctx:
                investigation_count += 1
                if workflow:
                    for rec in getattr(ctx, "recommendations", []):
                        try:
                            workflow.register_recommendation(rec, incident_id=inc_id)
                            recommendations_registered += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Could not pre-investigate incident '{inc_id}': {e}")

    # Fallback default recommendation if none registered
    if workflow and len(workflow.list_recommendations()) == 0 and ingested_incident_ids:
        default_rec = DiagnosticRecommendation(
            recommendation_id="REC-001",
            description="Execute automated optical sweep on feeder line and capture VSWR return loss signature.",
            reason="Measured VSWR ratio (1.94) exceeds 3GPP nominal operating baseline (1.40).",
            supporting_evidence_ids=["EVID-NOK-01", "EVID-TEL-01"],
            source_runbook_id="SOP-RAN-VSWR-001",
            source_section="Section 3.2 - RF Line Diagnostics",
            preconditions=["Antenna port in TEST mode", "No active emergency calls routed"],
            expected_observation="Return loss > 18dB upon feeder realignment",
            risk_classification=RecommendationRisk.READ_ONLY_SAFE,
            human_approval_required=True,
            approval_status=ApprovalStatus.PENDING_REVIEW,
        )
        try:
            workflow.register_recommendation(default_rec, incident_id=ingested_incident_ids[0])
            recommendations_registered += 1
        except Exception as e:
            logger.warning(f"Failed to register default fallback recommendation: {e}")

    summary = {
        "incidents_seeded": len(ingested_incident_ids),
        "incident_ids": ingested_incident_ids,
        "investigations_generated": investigation_count,
        "recommendations_registered": recommendations_registered,
    }
    logger.info(f"Bootstrap complete: {summary}")
    return summary
