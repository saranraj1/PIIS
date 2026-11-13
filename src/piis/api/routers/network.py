"""Network Intelligence endpoints providing read-only topology, telemetry, alarms, and impact analysis."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Query, status

from piis.api.routers.incidents import get_pipeline
from piis.api.schemas import (
    NetworkAlarmClusterItem,
    NetworkAlarmItem,
    NetworkAlarmsResponse,
    NetworkElementDetailResponse,
    NetworkImpactResponse,
    NetworkLinkItem,
    NetworkNodeItem,
    NetworkOverviewResponse,
    NetworkTelemetryResponse,
    NetworkTopologyResponse,
    TelemetryAnomalyItem,
    TelemetrySeriesItem,
)
from piis.anomaly.pipeline import TelemetryAnomalyPipeline
from piis.auth import (
    AuthenticatedPrincipal,
    Permission,
    require_permissions,
)
from piis.correlation.engine import TemporalAlarmCorrelator
from piis.correlation.models import CorrelatedIncidentCluster
from piis.correlation.topology import TelecomTopologyGraph
from piis.impact.analyzer import NetworkImpactAnalyzer
from piis.pipeline.unified import UnifiedIngestionPipeline

router = APIRouter(prefix="/api/v1/network", tags=["Network Intelligence"])

# Shared Topology Singleton
_topology: Optional[TelecomTopologyGraph] = None


def get_topology() -> TelecomTopologyGraph:
    """Retrieve singleton network topology instance or initialize reference topology."""
    global _topology
    if _topology is None:
        _topology = TelecomTopologyGraph.build_reference_topology()
    return _topology


def set_topology(topology: TelecomTopologyGraph) -> None:
    """Set custom topology instance (used in tests and dynamic loads)."""
    global _topology
    _topology = topology


@router.get(
    "/overview",
    response_model=NetworkOverviewResponse,
    summary="Get Network Observability Overview",
    description="Summarizes monitored network elements by domain, active alarms, correlated clusters, and anomalies.",
)
async def get_network_overview(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkOverviewResponse:
    """Retrieve high-level network observability metrics with explicit provenance."""
    # 1. Elements by domain
    domain_counts: Dict[str, int] = {}
    for node_data in topo._nodes.values():
        dom = str(node_data.get("domain", "UNKNOWN"))
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

    total_elements = len(topo._nodes)

    # 2. Total unique links (avoid double counting undirected pairs)
    unique_links: Set[tuple[str, str]] = set()
    for (u, v) in topo._edges.keys():
        if (v, u) not in unique_links:
            unique_links.add((u, v))
    total_links = len(unique_links)

    # 3. Active alarms count across all elements
    active_alarms_list: List[Dict[str, Any]] = []
    for alarms in pipeline._alarms.values():
        active_alarms_list.extend(alarms)
    active_alarms_count = len(active_alarms_list)

    # 4. Correlate active alarms into clusters
    correlator = TemporalAlarmCorrelator(topology=topo)
    clusters = correlator.correlate(alarms=active_alarms_list) if active_alarms_list else []
    correlated_clusters_count = len(clusters)

    # 5. Detect active anomalies across telemetry
    anomaly_pipeline = TelemetryAnomalyPipeline()
    all_telemetry: List[Dict[str, Any]] = []
    for records in pipeline._telemetry.values():
        all_telemetry.extend(records)
    anomalies = anomaly_pipeline.process_records(all_telemetry) if all_telemetry else []
    active_anomalies_count = len(anomalies)

    now_iso = datetime.now(timezone.utc).isoformat()
    integrity_hash = hashlib.sha256(
        f"{total_elements}_{total_links}_{active_alarms_count}_{now_iso[:10]}".encode()
    ).hexdigest()

    return NetworkOverviewResponse(
        total_elements=total_elements,
        elements_by_domain=domain_counts,
        total_links=total_links,
        active_alarms_count=active_alarms_count,
        correlated_clusters_count=correlated_clusters_count,
        active_anomalies_count=active_anomalies_count,
        last_sync_timestamp=now_iso,
        topology_version="1.0.0-reference",
        epistemic_status="REFERENCE_DATA",
        provenance={
            "source_model": "TelecomTopologyGraph",
            "integrity_hash": integrity_hash,
            "read_only": True,
            "simulated_environment": True,
            "topology_source": "REFERENCE_DATA",
            "live_carrier_infrastructure": False,
        },
    )


@router.get(
    "/topology",
    response_model=NetworkTopologyResponse,
    summary="Get Network Topology Graph",
    description="Retrieve attributed network nodes and directed dependency links, optionally filtered by domain.",
)
async def get_network_topology(
    domain: Optional[str] = Query(default=None, description="Optional domain filter (e.g. RAN, TRANSPORT, 5G_CORE)"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkTopologyResponse:
    """Retrieve full or domain-filtered attributed graph with active alarm and anomaly overlays."""
    # Find nodes with active anomalies
    anomaly_elements: Set[str] = set()
    all_telemetry: List[Dict[str, Any]] = []
    for records in pipeline._telemetry.values():
        all_telemetry.extend(records)
    if all_telemetry:
        anom_pipe = TelemetryAnomalyPipeline()
        for anom in anom_pipe.process_records(all_telemetry):
            anomaly_elements.add(anom.network_element_id)

    nodes: List[NetworkNodeItem] = []
    node_ids: Set[str] = set()

    for node_id, data in topo._nodes.items():
        node_dom = str(data.get("domain", "UNKNOWN"))
        if domain and node_dom.upper() != domain.upper():
            continue

        alarm_count = len(pipeline.get_element_alarms(node_id))
        has_anom = node_id in anomaly_elements

        nodes.append(
            NetworkNodeItem(
                element_id=node_id,
                domain=node_dom,
                element_type=str(data.get("element_type", "UNKNOWN")),
                site_id=data.get("site_id"),
                nominal_subscribers=data.get("nominal_subscribers"),
                active_alarm_count=alarm_count,
                has_anomaly=has_anom,
                epistemic_status="REFERENCE_DATA",
            )
        )
        node_ids.add(node_id)

    # Links
    links: List[NetworkLinkItem] = []
    seen_links: Set[tuple[str, str]] = set()

    for (u, v), edge_data in topo._edges.items():
        # If filtering by domain, include edge only if at least one or both nodes are in the set
        if domain and (u not in node_ids or v not in node_ids):
            continue

        is_dep = edge_data.get("dependency") == "downstream" or v in topo._downstream.get(u, set())
        if is_dep:
            # Directed downstream dependency
            links.append(
                NetworkLinkItem(
                    source=u,
                    target=v,
                    relation=str(edge_data.get("relation", "serves")),
                    is_dependency=True,
                    direction="downstream",
                )
            )
        else:
            # Undirected / bidirectional adjacency
            if (v, u) not in seen_links and (u, v) not in seen_links:
                seen_links.add((u, v))
                links.append(
                    NetworkLinkItem(
                        source=u,
                        target=v,
                        relation=str(edge_data.get("relation", "connected_to")),
                        is_dependency=False,
                        direction="bidirectional",
                    )
                )

    return NetworkTopologyResponse(
        nodes=nodes,
        links=links,
        epistemic_status="COMPUTED_TOPOLOGY",
    )


@router.get(
    "/elements/{element_id}",
    response_model=NetworkElementDetailResponse,
    summary="Get Element Detail",
    description="Retrieve specific network element details, upstream parents, downstream children, and recent alarms.",
)
async def get_element_detail(
    element_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkElementDetailResponse:
    """Retrieve detailed topology and state for a single network element."""
    node = topo.get_node(element_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network element '{element_id}' not found in registered topology.",
            headers={"X-PIIS-Error-Code": "ELEMENT_NOT_FOUND"},
        )

    neighbors = sorted(topo.get_neighbors(element_id))
    upstream = sorted(list(topo._upstream.get(element_id, set())))
    downstream = sorted(list(topo._downstream.get(element_id, set())))
    alarms = pipeline.get_element_alarms(element_id)
    telemetry = pipeline.get_element_telemetry(element_id)

    return NetworkElementDetailResponse(
        element_id=element_id,
        domain=str(node.get("domain", "UNKNOWN")),
        element_type=str(node.get("element_type", "UNKNOWN")),
        site_id=node.get("site_id"),
        nominal_subscribers=node.get("nominal_subscribers"),
        neighbors=neighbors,
        upstream_parents=upstream,
        downstream_children=downstream,
        active_alarms=alarms,
        recent_telemetry_count=len(telemetry),
        epistemic_status="REFERENCE_DATA",
    )


@router.get(
    "/impact",
    response_model=NetworkImpactResponse,
    summary="Quantify Blast Radius and Subscriber Impact",
    description="Compute direct and inferred downstream impact, affected domains, and subscriber risk for an element or incident.",
)
async def get_network_impact(
    element_id: Optional[str] = Query(default=None, description="Target network element ID"),
    incident_id: Optional[str] = Query(default=None, description="Optional incident ID"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkImpactResponse:
    """Evaluate blast radius and service risk using NetworkImpactAnalyzer."""
    if not element_id and not incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either 'element_id' or 'incident_id' parameter.",
            headers={"X-PIIS-Error-Code": "INVALID_QUERY_PARAMETERS"},
        )

    target_elem = element_id
    elements: List[str] = []

    if incident_id:
        inc = pipeline.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
                headers={"X-PIIS-Error-Code": "INCIDENT_NOT_FOUND"},
            )
        elements = inc.get("network_element_ids", [])
        if not elements and inc.get("network_element_id"):
            elements = [str(inc["network_element_id"])]
        if not target_elem and elements:
            target_elem = elements[0]

    if element_id:
        if element_id not in topo._nodes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Network element '{element_id}' not found in registered topology.",
                headers={"X-PIIS-Error-Code": "ELEMENT_NOT_FOUND"},
            )
        if element_id not in elements:
            elements.append(element_id)

    if not elements and target_elem:
        elements = [target_elem]

    # Resolve primary domain
    domains: List[str] = []
    for elem in elements:
        n_data = topo.get_node(elem)
        if n_data and "domain" in n_data:
            domains.append(n_data["domain"])
    if not domains:
        domains = ["RAN"]

    cluster = CorrelatedIncidentCluster(
        cluster_id=f"CLUSTER-IMPACT-{target_elem or 'MULTI'}",
        earliest_timestamp=datetime.now(timezone.utc).isoformat(),
        latest_timestamp=datetime.now(timezone.utc).isoformat(),
        primary_domain=domains[0],
        involved_domains=sorted(list(set(domains))),
        direct_alarm_ids=[],
        telemetry_anomaly_ids=[],
        affected_elements=elements,
    )

    analyzer = NetworkImpactAnalyzer(topology=topo, inferred_hop_depth=2)
    assessment = analyzer.assess_impact(cluster)

    return NetworkImpactResponse(
        target_element=target_elem,
        direct_elements=assessment.direct_elements,
        inferred_elements=assessment.inferred_elements,
        total_element_count=assessment.total_element_count,
        affected_domains=assessment.affected_domains,
        severity_risk_level=assessment.severity_risk_level,
        risk_score=assessment.risk_score,
        estimated_affected_subscribers=assessment.estimated_affected_subscribers,
        subscriber_impact_basis=assessment.subscriber_impact_basis,
        epistemic_status="DERIVED_ESTIMATE",
        provenance=assessment.provenance,
    )


@router.get(
    "/alarms",
    response_model=NetworkAlarmsResponse,
    summary="List Active Network Alarms & Correlated Clusters",
    description="Retrieve ingested alarms and their temporal/topological correlation clusters.",
)
async def get_network_alarms(
    element_id: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkAlarmsResponse:
    """Retrieve active alarms and correlation clusters."""
    # Gather all alarms
    all_alarms: List[Dict[str, Any]] = []
    if element_id:
        all_alarms = pipeline.get_element_alarms(element_id)
    else:
        for alarms in pipeline._alarms.values():
            all_alarms.extend(alarms)

    # Run correlator
    correlator = TemporalAlarmCorrelator(topology=topo)
    raw_clusters = correlator.correlate(alarms=all_alarms) if all_alarms else []

    # Map alarms to cluster IDs
    alarm_to_cluster: Dict[str, str] = {}
    cluster_items: List[NetworkAlarmClusterItem] = []

    for c in raw_clusters:
        for alm_id in c.direct_alarm_ids:
            alarm_to_cluster[alm_id] = c.cluster_id

        rationales = [edge.rationale_text for edge in c.correlation_edges]
        if not rationales and c.root_cause_hypothesis:
            rationales = [c.root_cause_hypothesis]

        if c.correlation_edges:
            mean_conf = round(sum(e.affinity_score for e in c.correlation_edges) / len(c.correlation_edges), 4)
        else:
            mean_conf = 0.85

        cluster_items.append(
            NetworkAlarmClusterItem(
                cluster_id=c.cluster_id,
                dominant_domain=c.primary_domain,
                event_count=len(c.direct_alarm_ids) + len(c.telemetry_anomaly_ids),
                affected_elements=c.affected_elements,
                mean_confidence=mean_conf,
                rationales=rationales,
                epistemic_status="HYPOTHESIS",
            )
        )

    # Filter and format alarms
    alarm_items: List[NetworkAlarmItem] = []
    for a in all_alarms:
        a_id = str(a.get("alarm_id", ""))
        a_ne = str(a.get("network_element_id", ""))
        a_dom = str(a.get("domain") or a.get("network_domain") or "RAN")
        a_sev = str(a.get("severity", "MAJOR")).upper()

        if domain and a_dom.upper() != domain.upper():
            continue
        if severity and a_sev != severity.upper():
            continue

        alarm_items.append(
            NetworkAlarmItem(
                alarm_id=a_id,
                network_element_id=a_ne,
                network_domain=a_dom,
                alarm_code=str(a.get("alarm_code", "UNKNOWN")),
                probable_cause=a.get("probable_cause"),
                severity=a_sev,
                timestamp=str(a.get("timestamp", datetime.now(timezone.utc).isoformat())),
                cluster_id=alarm_to_cluster.get(a_id),
                epistemic_status="OBSERVED_FACT",
            )
        )

    return NetworkAlarmsResponse(
        alarms=alarm_items,
        clusters=cluster_items,
        total_alarms=len(alarm_items),
        total_clusters=len(cluster_items),
    )


@router.get(
    "/telemetry",
    response_model=NetworkTelemetryResponse,
    summary="Get Element Telemetry & Anomaly Detections",
    description="Retrieve raw metric time-series and detected statistical/ML anomaly violations for a network element.",
)
async def get_network_telemetry(
    element_id: str = Query(..., description="Target network element ID"),
    metric_name: Optional[str] = Query(default=None, description="Optional metric filter"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_INCIDENTS)),
    pipeline: UnifiedIngestionPipeline = Depends(get_pipeline),
    topo: TelecomTopologyGraph = Depends(get_topology),
) -> NetworkTelemetryResponse:
    """Retrieve telemetry series and detected anomaly events."""
    if element_id not in topo._nodes and element_id not in pipeline._telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network element '{element_id}' not found in registered topology or telemetry store.",
            headers={"X-PIIS-Error-Code": "ELEMENT_NOT_FOUND"},
        )

    raw_records = pipeline.get_element_telemetry(element_id)

    # Filter by metric_name if specified
    if metric_name:
        filtered = [r for r in raw_records if r.get("metric_name") == metric_name]
    else:
        filtered = raw_records

    # Group into series
    series_map: Dict[str, Dict[str, Any]] = {}
    for r in filtered:
        m_name = str(r.get("metric_name", "unknown_metric"))
        if m_name not in series_map:
            series_map[m_name] = {
                "metric_name": m_name,
                "unit": str(r.get("unit", "")),
                "timestamps": [],
                "values": [],
                "is_imputed": [],
            }
        series_map[m_name]["timestamps"].append(str(r.get("observation_timestamp") or r.get("timestamp", "")))
        series_map[m_name]["values"].append(float(r.get("metric_value", 0.0)))
        series_map[m_name]["is_imputed"].append(bool(r.get("is_imputed", False)))

    series_items = [
        TelemetrySeriesItem(
            metric_name=s["metric_name"],
            unit=s["unit"],
            timestamps=s["timestamps"],
            values=s["values"],
            is_imputed=s["is_imputed"],
        )
        for s in series_map.values()
    ]

    # Run anomaly detection
    anomalies: List[TelemetryAnomalyItem] = []
    if filtered:
        pipe = TelemetryAnomalyPipeline()
        detected = pipe.process_records(filtered)
        for anom in detected:
            for viol in anom.affected_metrics:
                anomalies.append(
                    TelemetryAnomalyItem(
                        anomaly_id=anom.anomaly_id,
                        metric_name=viol.metric_name,
                        timestamp=anom.start_timestamp,
                        observed_value=viol.observed_value,
                        expected_value=viol.expected_value,
                        threshold_value=viol.threshold_value,
                        severity=anom.severity.value,
                        score=anom.anomaly_score,
                        epistemic_status="MODEL_PREDICTION",
                    )
                )

    return NetworkTelemetryResponse(
        element_id=element_id,
        series=series_items,
        anomalies=anomalies,
        epistemic_status="OBSERVED_FACT",
    )
