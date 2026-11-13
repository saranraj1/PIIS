"""Telecom network topology graph and spatial adjacency engine.

Represents hierarchical and peer connections across RAN, Transport, Core, and Service domains.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple


class TelecomTopologyGraph:
    """Attributed graph representing physical, logical, and service relationships in telecom networks."""

    def __init__(self):
        """Initialize empty topology graph with both physical adjacency and directed dependencies."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._adjacency: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}  # Parent -> Dependent Children
        self._upstream: Dict[str, Set[str]] = {}    # Child -> Infrastructure Parents
        self._edges: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def add_node(
        self,
        node_id: str,
        domain: str = "RAN",
        element_type: str = "CELL",
        site_id: Optional[str] = None,
        nominal_subscribers: Optional[int] = None,
        **attrs: Any,
    ) -> None:
        """Register a network element node in the topology."""
        self._nodes[node_id] = {
            "domain": domain,
            "element_type": element_type,
            "site_id": site_id or node_id.split("-")[0],
            "nominal_subscribers": nominal_subscribers,
            **attrs,
        }
        if node_id not in self._adjacency:
            self._adjacency[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()
        if node_id not in self._upstream:
            self._upstream[node_id] = set()

    def add_edge(
        self,
        node_u: str,
        node_v: str,
        relation: str = "connected_to",
        bidirectional: bool = True,
        is_dependency: bool = False,
        parent: Optional[str] = None,
        **attrs: Any,
    ) -> None:
        """Register a link or dependency between two network elements."""
        # Auto-create nodes if not pre-registered
        if node_u not in self._nodes:
            self.add_node(node_u)
        if node_v not in self._nodes:
            self.add_node(node_v)

        self._adjacency[node_u].add(node_v)
        self._edges[(node_u, node_v)] = {"relation": relation, **attrs}

        if bidirectional:
            self._adjacency[node_v].add(node_u)
            self._edges[(node_v, node_u)] = {"relation": relation, **attrs}

        # Track directed dependencies if specified
        if is_dependency:
            parent_node = parent or node_u
            child_node = node_v if parent_node == node_u else node_u
            self.add_dependency(parent_node, child_node, relation=relation)

    def add_dependency(self, parent_u: str, child_v: str, relation: str = "serves") -> None:
        """Explicitly declare that parent_u is upstream infrastructure for downstream child_v."""
        if parent_u not in self._nodes:
            self.add_node(parent_u)
        if child_v not in self._nodes:
            self.add_node(child_v)

        self._downstream[parent_u].add(child_v)
        self._upstream[child_v].add(parent_u)
        # Also ensure undirected adjacency is populated
        self._adjacency[parent_u].add(child_v)
        self._adjacency[child_v].add(parent_u)
        self._edges[(parent_u, child_v)] = {"relation": relation, "dependency": "downstream"}
        self._edges[(child_v, parent_u)] = {"relation": relation, "dependency": "upstream"}

    def get_downstream_elements(self, node_ids: List[str], max_depth: int = 1) -> Set[str]:
        """Traverse ONLY downstream dependencies to determine blast radius on dependent nodes."""
        result: Set[str] = set()
        for root in node_ids:
            if root not in self._downstream:
                continue
            visited = {root}
            queue: deque[Tuple[str, int]] = deque([(root, 0)])
            while queue:
                current, dist = queue.popleft()
                if 0 < dist <= max_depth:
                    result.add(current)
                if dist < max_depth:
                    for child in self._downstream.get(current, set()):
                        if child not in visited:
                            visited.add(child)
                            queue.append((child, dist + 1))
        return result

    def get_upstream_elements(self, node_ids: List[str], max_depth: int = 1) -> Set[str]:
        """Traverse ONLY upstream dependencies to identify potential parent infrastructure root causes."""
        result: Set[str] = set()
        for root in node_ids:
            if root not in self._upstream:
                continue
            visited = {root}
            queue: deque[Tuple[str, int]] = deque([(root, 0)])
            while queue:
                current, dist = queue.popleft()
                if 0 < dist <= max_depth:
                    result.add(current)
                if dist < max_depth:
                    for parent in self._upstream.get(current, set()):
                        if parent not in visited:
                            visited.add(parent)
                            queue.append((parent, dist + 1))
        return result

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve node attributes."""
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> List[str]:
        """Return direct topological neighbors of an element."""
        return list(self._adjacency.get(node_id, set()))

    def shortest_path_distance(self, node_u: str, node_v: str) -> Optional[int]:
        """Compute the shortest path hop distance between two network elements using BFS."""
        if node_u == node_v:
            return 0
        if node_u not in self._adjacency or node_v not in self._adjacency:
            return None

        visited = {node_u}
        queue: deque[Tuple[str, int]] = deque([(node_u, 0)])

        while queue:
            current, dist = queue.popleft()
            for neighbor in self._adjacency[current]:
                if neighbor == node_v:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return None

    def get_k_hop_neighbors(self, node_ids: List[str], k: int = 1) -> Set[str]:
        """Retrieve all network elements within k hops of a target set."""
        result: Set[str] = set()
        for root in node_ids:
            if root not in self._adjacency:
                continue
            visited = {root}
            queue: deque[Tuple[str, int]] = deque([(root, 0)])
            while queue:
                current, dist = queue.popleft()
                if 0 < dist <= k:
                    result.add(current)
                if dist < k:
                    for neighbor in self._adjacency[current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, dist + 1))
        return result

    @classmethod
    def build_reference_topology(cls) -> TelecomTopologyGraph:
        """Create a standard multi-domain reference topology for testing and benchmarking."""
        topo = cls()

        # Core Domain Elements
        topo.add_node("AMF-CORE-01", domain="5G_CORE", element_type="AMF", nominal_subscribers=100000)
        topo.add_node("SMF-CORE-01", domain="5G_CORE", element_type="SMF", nominal_subscribers=100000)
        topo.add_node("UPF-CORE-PRIMARY", domain="5G_CORE", element_type="UPF", nominal_subscribers=50000)
        topo.add_node("UPF-CORE-SECONDARY", domain="5G_CORE", element_type="UPF", nominal_subscribers=50000)
        topo.add_node("IMS-CORE-01", domain="SERVICE", element_type="IMS", nominal_subscribers=80000)

        # Core Links
        topo.add_edge("AMF-CORE-01", "SMF-CORE-01", relation="n11_control", bidirectional=True)
        topo.add_dependency("SMF-CORE-01", "UPF-CORE-PRIMARY", relation="n4_session")
        topo.add_edge("UPF-CORE-PRIMARY", "IMS-CORE-01", relation="n6_data", bidirectional=True)

        # Transport Domain Elements
        topo.add_node("RTR-IPMPLS-AGG01", domain="TRANSPORT", element_type="ROUTER")
        topo.add_node("RTR-IPMPLS-AGG02", domain="TRANSPORT", element_type="ROUTER")
        topo.add_node("SW-ACCESS-SITE01", domain="TRANSPORT", element_type="SWITCH")
        topo.add_node("SW-ACCESS-SITE02", domain="TRANSPORT", element_type="SWITCH")

        # Transport Links & Downstream Hierarchical Dependencies
        topo.add_dependency("UPF-CORE-PRIMARY", "RTR-IPMPLS-AGG01", relation="n3_interface")
        topo.add_dependency("UPF-CORE-SECONDARY", "RTR-IPMPLS-AGG02", relation="n3_interface")
        topo.add_dependency("RTR-IPMPLS-AGG01", "SW-ACCESS-SITE01", relation="backhaul_fiber")
        topo.add_dependency("RTR-IPMPLS-AGG02", "SW-ACCESS-SITE02", relation="backhaul_fiber")

        # RAN Domain — Site 01
        topo.add_node("GNB-TESTBED-5G-01", domain="RAN", element_type="GNB", site_id="SITE01", nominal_subscribers=5000)
        topo.add_node("CELL-101", domain="RAN", element_type="CELL", site_id="SITE01", nominal_subscribers=1500)
        topo.add_node("CELL-102", domain="RAN", element_type="CELL", site_id="SITE01", nominal_subscribers=1500)
        topo.add_node("CELL-103", domain="RAN", element_type="CELL", site_id="SITE01", nominal_subscribers=2000)

        topo.add_dependency("SW-ACCESS-SITE01", "GNB-TESTBED-5G-01", relation="fronthaul")
        topo.add_dependency("GNB-TESTBED-5G-01", "CELL-101", relation="serves_cell")
        topo.add_dependency("GNB-TESTBED-5G-01", "CELL-102", relation="serves_cell")
        topo.add_dependency("GNB-TESTBED-5G-01", "CELL-103", relation="serves_cell")

        # RAN Domain — Site 02
        topo.add_node("GNB-SITE02-01", domain="RAN", element_type="GNB", site_id="SITE02", nominal_subscribers=4000)
        topo.add_node("CELL-201", domain="RAN", element_type="CELL", site_id="SITE02", nominal_subscribers=1200)
        topo.add_node("CELL-202", domain="RAN", element_type="CELL", site_id="SITE02", nominal_subscribers=1400)
        topo.add_node("CELL-A81B-C", domain="RAN", element_type="CELL", site_id="SITE02", nominal_subscribers=1400)

        topo.add_dependency("SW-ACCESS-SITE02", "GNB-SITE02-01", relation="fronthaul")
        topo.add_dependency("GNB-SITE02-01", "CELL-201", relation="serves_cell")
        topo.add_dependency("GNB-SITE02-01", "CELL-202", relation="serves_cell")
        topo.add_dependency("GNB-SITE02-01", "CELL-A81B-C", relation="serves_cell")

        # Operational Ingested Incident Elements
        topo.add_node("GNB-RAN-701", domain="RAN", element_type="GNB", site_id="SITE04", nominal_subscribers=1420)
        topo.add_dependency("SW-ACCESS-SITE01", "GNB-RAN-701", relation="fronthaul")

        topo.add_node("UPF-CORE-01", domain="5G_CORE", element_type="UPF", site_id="DC01", nominal_subscribers=45000)
        topo.add_dependency("SMF-CORE-01", "UPF-CORE-01", relation="n4_session")

        topo.add_node("DWDM-MUC-04", domain="TRANSPORT", element_type="TRANSPONDER", site_id="MUC01", nominal_subscribers=22000)
        topo.add_dependency("RTR-IPMPLS-AGG01", "DWDM-MUC-04", relation="optical_link")

        return topo
