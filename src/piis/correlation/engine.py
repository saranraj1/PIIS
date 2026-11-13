"""Temporal and topology-aware correlation engine for telecom alarms and anomalies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from piis.anomaly.models import TelemetryAnomaly
from piis.correlation.models import CorrelatedIncidentCluster, CorrelationRationale
from piis.correlation.topology import TelecomTopologyGraph
from piis.provenance import ProvenanceRecord, SourceType


# Domain coupling affinity matrix
DOMAIN_AFFINITY: Dict[Tuple[str, str], float] = {
    ("RAN", "RAN"): 1.0,
    ("5G_CORE", "5G_CORE"): 1.0,
    ("TRANSPORT", "TRANSPORT"): 1.0,
    ("SERVICE", "SERVICE"): 1.0,
    ("RAN", "TRANSPORT"): 0.80,
    ("TRANSPORT", "RAN"): 0.80,
    ("TRANSPORT", "5G_CORE"): 0.75,
    ("5G_CORE", "TRANSPORT"): 0.75,
    ("RAN", "5G_CORE"): 0.65,
    ("5G_CORE", "RAN"): 0.65,
    ("SERVICE", "5G_CORE"): 0.70,
    ("5G_CORE", "SERVICE"): 0.70,
    ("SERVICE", "RAN"): 0.50,
    ("RAN", "SERVICE"): 0.50,
}


class AlarmCompatibilityPolicy:
    """Evaluates causal semantic compatibility between alarm codes to prevent false merges."""

    # Categorization regex/prefixes
    CATEGORY_MAPPINGS = [
        ("RF_HARDWARE", ["VSWR", "RF-UNIT", "FEEDER", "PIM-HIGH", "ANTENNA"]),
        ("RADIO_CAPACITY", ["PRB", "HO-EXC", "RRC-REJ", "CELL-DEG", "CELL-UNAVAILABLE", "CARRIER-DOWN", "RESTART", "REBOOT", "RESET"]),
        ("POWER_FACILITY", ["PWR", "BATT", "MAINS", "ENCL-TEMP", "RECTIFIER"]),
        ("TRANSPORT_LINK", ["TX", "LOS", "OPTICAL", "FIBER", "SCTP", "CRC-ERR", "SYNC-LOSS", "MTU"]),
        ("CORE_USER_PLANE", ["5GC", "UPF", "SMF", "AMF", "N4", "DNN", "BUFFER-OVERFLOW", "IP-POOL"]),
        ("SERVICE_APPLICATION", ["SRV", "DNS", "SIP", "TLS-CERT", "HTTP-503"]),
        ("SOFTWARE_LICENSE", ["LIC", "LICENSE", "FIRMWARE", "SW-CRASH"]),
    ]

    # Explicitly incompatible pairs of local fault mechanisms
    INCOMPATIBLE_PAIRS = {
        frozenset(["RF_HARDWARE", "SOFTWARE_LICENSE"]),
        frozenset(["RF_HARDWARE", "SERVICE_APPLICATION"]),
        frozenset(["SOFTWARE_LICENSE", "TRANSPORT_LINK"]),
        frozenset(["SOFTWARE_LICENSE", "CORE_USER_PLANE"]),
        frozenset(["RF_HARDWARE", "CORE_USER_PLANE"]),
    }

    def classify_code(self, code: str) -> str:
        """Classify alarm code or summary into functional causal category."""
        upper_code = code.upper()
        for cat, keywords in self.CATEGORY_MAPPINGS:
            if any(kw in upper_code for kw in keywords):
                return cat
        return "UNKNOWN"

    def evaluate(self, event_a: NormalizedEvent, event_b: NormalizedEvent) -> Tuple[float, str]:
        """Evaluate compatibility score in [0.0, 1.0] and return justification rationale."""
        # Telemetry anomalies default to compatible with their respective domain
        if event_a.event_type == "TELEMETRY_ANOMALY" or event_b.event_type == "TELEMETRY_ANOMALY":
            return 1.0, "Telemetry anomaly compatible with operational domain alarms."

        # Extract alarm codes from raw records
        code_a = str(event_a.raw_record.get("alarm_code") or event_a.summary)
        code_b = str(event_b.raw_record.get("alarm_code") or event_b.summary)

        cat_a = self.classify_code(code_a)
        cat_b = self.classify_code(code_b)

        # 1. Unknown alarm semantics: express uncertainty with conservative 0.70 weight
        if cat_a == "UNKNOWN" or cat_b == "UNKNOWN":
            return 0.70, f"Uncertain semantic compatibility (codes: {code_a} [{cat_a}] <-> {code_b} [{cat_b}])."

        # 2. Incompatible categories: mutually exclusive local mechanisms
        pair_key = frozenset([cat_a, cat_b])
        if pair_key in self.INCOMPATIBLE_PAIRS:
            return 0.0, f"Incompatible fault categories ({cat_a} <-> {cat_b}) on same or adjacent nodes."

        # 3. Compatible categories
        if cat_a == cat_b:
            return 1.0, f"Shared fault category ({cat_a})."

        return 0.90, f"Causally compatible cascading categories ({cat_a} <-> {cat_b})."


@dataclass(frozen=True)
class NormalizedEvent:
    """Standardized event envelope for alarms and telemetry anomalies."""
    event_id: str
    event_type: str  # ALARM or TELEMETRY_ANOMALY
    timestamp_dt: datetime
    timestamp_iso: str
    network_element_id: str
    network_domain: str
    severity: str
    summary: str
    raw_record: Dict[str, Any]


class TemporalAlarmCorrelator:
    """Correlates telecom alarms and telemetry anomalies across time, topology, and domains."""

    def __init__(
        self,
        topology: Optional[TelecomTopologyGraph] = None,
        compatibility_policy: Optional[AlarmCompatibilityPolicy] = None,
        time_window_seconds: float = 900.0,  # 15 minutes
        correlation_threshold: float = 0.55,
        max_hops: int = 3,
        lambda_topo: float = 0.5,
        weight_time: float = 0.40,
        weight_topo: float = 0.40,
        weight_domain: float = 0.20,
        version: str = "1.0.0",
    ):
        """Initialize correlation engine.

        Args:
            topology: Network topology graph.
            compatibility_policy: Causal semantic compatibility policy.
            time_window_seconds: Maximum time difference for temporal proximity.
            correlation_threshold: Minimum composite affinity to form an edge.
            max_hops: Maximum graph distance allowed for topological correlation.
            lambda_topo: Exponential spatial decay factor.
            weight_time: Weight for temporal proximity.
            weight_topo: Weight for topological proximity.
            weight_domain: Weight for cross-domain coupling.
            version: Engine version string.
        """
        self.topology = topology or TelecomTopologyGraph.build_reference_topology()
        self.compatibility_policy = compatibility_policy or AlarmCompatibilityPolicy()
        self.time_window_seconds = time_window_seconds
        self.correlation_threshold = correlation_threshold
        self.max_hops = max_hops
        self.lambda_topo = lambda_topo
        self.weight_time = weight_time
        self.weight_topo = weight_topo
        self.weight_domain = weight_domain
        self.version = version

    def _normalize_alarm(self, alarm: Dict[str, Any]) -> NormalizedEvent:
        """Convert alarm record to NormalizedEvent."""
        raw_ts = str(alarm.get("timestamp") or "")
        dt = pd.to_datetime(raw_ts, utc=True).to_pydatetime()
        return NormalizedEvent(
            event_id=str(alarm.get("alarm_id") or f"ALM-{hashlib.sha256(raw_ts.encode()).hexdigest()[:8]}"),
            event_type="ALARM",
            timestamp_dt=dt,
            timestamp_iso=dt.isoformat(),
            network_element_id=str(alarm.get("network_element_id") or "UNKNOWN_NE"),
            network_domain=str(alarm.get("network_domain") or "RAN"),
            severity=str(alarm.get("severity") or "MAJOR"),
            summary=f"Alarm {alarm.get('alarm_code', 'UNKNOWN')}: {alarm.get('probable_cause', '')}",
            raw_record=alarm,
        )

    def _normalize_anomaly(self, anomaly: TelemetryAnomaly | Dict[str, Any]) -> NormalizedEvent:
        """Convert TelemetryAnomaly to NormalizedEvent."""
        if isinstance(anomaly, TelemetryAnomaly):
            data = anomaly.model_dump()
        else:
            data = dict(anomaly)

        raw_ts = str(data.get("start_timestamp") or data.get("timestamp") or "")
        dt = pd.to_datetime(raw_ts, utc=True).to_pydatetime()
        metrics = data.get("affected_metrics") or []
        m_names = [m.get("metric_name") if isinstance(m, dict) else m.metric_name for m in metrics]

        return NormalizedEvent(
            event_id=str(data.get("anomaly_id") or f"ANOM-{hashlib.sha256(raw_ts.encode()).hexdigest()[:8]}"),
            event_type="TELEMETRY_ANOMALY",
            timestamp_dt=dt,
            timestamp_iso=dt.isoformat(),
            network_element_id=str(data.get("network_element_id") or "UNKNOWN_NE"),
            network_domain=str(data.get("network_domain") or "RAN"),
            severity=str(data.get("severity") or "WARNING"),
            summary=f"Telemetry Anomaly (score={data.get('anomaly_score', 0.0)}): violating {', '.join(m_names)}",
            raw_record=data,
        )

    def compute_pairwise_affinity(
        self,
        event_a: NormalizedEvent,
        event_b: NormalizedEvent,
    ) -> Tuple[float, Optional[CorrelationRationale]]:
        """Compute composite affinity and auditable rationale between two events."""
        # 1. Temporal Proximity
        dt_seconds = abs((event_a.timestamp_dt - event_b.timestamp_dt).total_seconds())
        if dt_seconds > self.time_window_seconds:
            return 0.0, None

        time_affinity = 1.0 - (dt_seconds / self.time_window_seconds)

        # 2. Topological Proximity
        ne_a = event_a.network_element_id
        ne_b = event_b.network_element_id
        hop_dist = self.topology.shortest_path_distance(ne_a, ne_b)

        if hop_dist is None or hop_dist > self.max_hops:
            # Elements are disconnected or too distant in network topology
            topo_affinity = 0.0
        else:
            topo_affinity = math.exp(-self.lambda_topo * hop_dist)

        # If topology indicates disjoint nodes (topo_affinity == 0.0) and elements differ,
        # suppress correlation to prevent false correlations across unrelated physical towers/sites
        if ne_a != ne_b and topo_affinity == 0.0:
            return 0.0, None

        # 3. Cross-Domain Coupling
        domain_pair = (event_a.network_domain, event_b.network_domain)
        domain_affinity = DOMAIN_AFFINITY.get(domain_pair, 0.40)

        # 4. Semantic Alarm Compatibility Guardrail
        comp_score, comp_rationale = self.compatibility_policy.evaluate(event_a, event_b)
        if comp_score <= 0.0:
            # Explicitly incompatible causal categories -> suppress false merge
            return 0.0, None

        # Composite Weighted Affinity modulated by causal compatibility
        base_affinity = (
            self.weight_time * time_affinity
            + self.weight_topo * topo_affinity
            + self.weight_domain * domain_affinity
        )
        composite = base_affinity * comp_score

        if composite >= self.correlation_threshold:
            rel_text = "same element" if ne_a == ne_b else f"hop distance {hop_dist}"
            rationale_text = (
                f"{event_a.event_type} on {ne_a} and {event_b.event_type} on {ne_b} "
                f"occurred {dt_seconds:.1f}s apart with {rel_text}. "
                f"Cross-domain affinity ({event_a.network_domain} <-> {event_b.network_domain}): {domain_affinity:.2f}. "
                f"Semantic compatibility ({comp_score:.2f}): {comp_rationale} "
                f"Composite affinity: {composite:.3f} >= {self.correlation_threshold:.2f}."
            )
            rationale = CorrelationRationale(
                event_id_a=event_a.event_id,
                event_id_b=event_b.event_id,
                time_delta_seconds=round(dt_seconds, 2),
                hop_distance=hop_dist,
                topology_relation=rel_text,
                affinity_score=round(composite, 4),
                rationale_text=rationale_text,
            )
            return composite, rationale

        return 0.0, None

    def correlate(
        self,
        alarms: List[Dict[str, Any]],
        anomalies: Optional[List[TelemetryAnomaly | Dict[str, Any]]] = None,
        source_dataset: str = "PIIS-Operational-Stream",
        source_type: SourceType = SourceType.DERIVED,
    ) -> List[CorrelatedIncidentCluster]:
        """Correlate alarms and anomalies into candidate incident clusters."""
        events: List[NormalizedEvent] = []
        for alm in alarms:
            events.append(self._normalize_alarm(alm))
        for anom in anomalies or []:
            events.append(self._normalize_anomaly(anom))

        if not events:
            return []

        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp_dt)

        n = len(events)
        adj: Dict[int, List[int]] = {i: [] for i in range(n)}
        rationales_by_pair: Dict[Tuple[int, int], CorrelationRationale] = {}

        # Build correlation graph
        for i in range(n):
            for j in range(i + 1, n):
                score, rationale = self.compute_pairwise_affinity(events[i], events[j])
                if score >= self.correlation_threshold and rationale is not None:
                    adj[i].append(j)
                    adj[j].append(i)
                    rationales_by_pair[(i, j)] = rationale

        # Find connected components (candidate clusters)
        visited: Set[int] = set()
        clusters: List[CorrelatedIncidentCluster] = []

        for root in range(n):
            if root in visited:
                continue

            comp: List[int] = []
            queue = [root]
            visited.add(root)

            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            comp_events = [events[idx] for idx in comp]
            comp_alarm_ids = [e.event_id for e in comp_events if e.event_type == "ALARM"]
            comp_anom_ids = [e.event_id for e in comp_events if e.event_type == "TELEMETRY_ANOMALY"]
            comp_elements = sorted(list(set(e.network_element_id for e in comp_events)))
            comp_domains = sorted(list(set(e.network_domain for e in comp_events)))

            # Collect rationales within this component
            comp_rationales: List[CorrelationRationale] = []
            for i in comp:
                for j in comp:
                    if i < j and (i, j) in rationales_by_pair:
                        comp_rationales.append(rationales_by_pair[(i, j)])

            earliest = min(e.timestamp_iso for e in comp_events)
            latest = max(e.timestamp_iso for e in comp_events)

            # Determine primary domain
            primary_domain = comp_domains[0]
            if len(comp_domains) > 1:
                # Prioritize upstream domains: TRANSPORT > 5G_CORE > RAN
                for d in ["TRANSPORT", "5G_CORE", "RAN", "SERVICE"]:
                    if d in comp_domains:
                        primary_domain = d
                        break

            # Deterministic cluster ID incorporating sorted event IDs
            cluster_hash = hashlib.sha256(
                f"{earliest}_{comp_elements}_{sorted(comp_alarm_ids)}_{sorted(comp_anom_ids)}".encode()
            ).hexdigest()[:12]
            cluster_id = f"CLUST-{primary_domain}-{cluster_hash}"

            # Root cause hypothesis based on earliest root node
            first_event = comp_events[0]
            hypothesis = (
                f"Candidate root event: {first_event.summary} on element {first_event.network_element_id} "
                f"at {first_event.timestamp_iso}. Downstream correlated impact across {len(comp_elements)} elements."
            )

            prov = ProvenanceRecord(
                source_type=source_type,
                source_dataset=source_dataset,
                source_record_id=cluster_id,
                transformation_version=self.version,
                metadata={
                    "event_count": len(comp_events),
                    "alarm_count": len(comp_alarm_ids),
                    "anomaly_count": len(comp_anom_ids),
                    "element_count": len(comp_elements),
                    "correlation_threshold": self.correlation_threshold,
                    "time_window_seconds": self.time_window_seconds,
                },
            )

            clusters.append(
                CorrelatedIncidentCluster(
                    cluster_id=cluster_id,
                    earliest_timestamp=earliest,
                    latest_timestamp=latest,
                    primary_domain=primary_domain,
                    involved_domains=comp_domains,
                    direct_alarm_ids=comp_alarm_ids,
                    telemetry_anomaly_ids=comp_anom_ids,
                    affected_elements=comp_elements,
                    correlation_edges=comp_rationales,
                    root_cause_hypothesis=hypothesis,
                    epistemic_status="HYPOTHESIS",
                    provenance=prov.to_dict(),
                )
            )

        return clusters
