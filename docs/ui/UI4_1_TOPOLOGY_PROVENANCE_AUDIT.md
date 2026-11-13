# UI-4.1 Topology Provenance & Structural Grounding Audit

**Milestone:** UI-4.1 — Network Intelligence Evidence Grounding & Independent Verification  
**Module:** Network Topology & Provenance Engine  
**Status:** AUDITED & ACCEPTED  
**Date:** 2026-11-03  
**Auditor / Engineering Role:** Antigravity Engineering Agent  
**Operational Scope:** Strictly Read-Only Decision Support (Zero Network Mutation)  

---

## 1. Executive Summary & Core Classification

This audit examines the exact origin, edge derivations, hierarchy representations, and epistemic labeling of every network topology node and dependency link within PIIS. 

### Key Audit Finding
The PIIS topology is **not live carrier production infrastructure**. It is a **deterministic reference topology** based on 3GPP 5G Service-Based Architecture (SBA) and IP transport standards, instantiated via `TelecomTopologyGraph.build_reference_topology()`. 

To prevent operators or auditors from mistaking reference models for live carrier telemetry, all overview and element endpoints now emit `epistemic_status: "REFERENCE_DATA"` and explicit provenance flags (`simulated_environment: True`, `live_carrier_infrastructure: False`, `topology_source: "REFERENCE_DATA"`), mirrored by the frontend `[REFERENCE DATA]` tag.

---

## 2. Source-by-Source Node Inventory Classification

Every node registered in PIIS topology was audited against its physical, logical, or synthetic origin:

| Node ID | Domain | Element Type | Source Classification | Authoritative Origin | Nominal Subscribers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`AMF-CORE-01`** | `5G_CORE` | `AMF` | **REFERENCE DATA** | 3GPP TS 23.501 reference core model | 100,000 |
| **`SMF-CORE-01`** | `5G_CORE` | `SMF` | **REFERENCE DATA** | 3GPP TS 23.501 reference core model | 100,000 |
| **`UPF-CORE-PRIMARY`** | `5G_CORE` | `UPF` | **REFERENCE DATA** | 3GPP TS 23.501 reference core model | 50,000 |
| **`UPF-CORE-SECONDARY`** | `5G_CORE` | `UPF` | **REFERENCE DATA** | 3GPP TS 23.501 reference core model | 50,000 |
| **`IMS-CORE-01`** | `SERVICE` | `IMS` | **REFERENCE DATA** | VoNR/IMS reference service model | 80,000 |
| **`RTR-IPMPLS-AGG01`** | `TRANSPORT` | `ROUTER` | **REFERENCE DATA** | Optical/IP aggregation router model | None (No mapping) |
| **`RTR-IPMPLS-AGG02`** | `TRANSPORT` | `ROUTER` | **REFERENCE DATA** | Optical/IP aggregation router model | None (No mapping) |
| **`SW-ACCESS-SITE01`** | `TRANSPORT` | `SWITCH` | **REFERENCE DATA** | Cell-site gateway access switch model | None (No mapping) |
| **`SW-ACCESS-SITE02`** | `TRANSPORT` | `SWITCH` | **REFERENCE DATA** | Cell-site gateway access switch model | None (No mapping) |
| **`GNB-TESTBED-5G-01`** | `RAN` | `GNB` | **REFERENCE DATA** | 5G NR gNodeB reference base station | 5,000 |
| **`CELL-101`** | `RAN` | `CELL` | **REFERENCE DATA** | Macro sector cell (Site 01) | 1,500 |
| **`CELL-102`** | `RAN` | `CELL` | **REFERENCE DATA** | Macro sector cell (Site 01) | 1,500 |
| **`CELL-103`** | `RAN` | `CELL` | **REFERENCE DATA** | Macro sector cell (Site 01) | 2,000 |
| **`GNB-SITE02-01`** | `RAN` | `GNB` | **REFERENCE DATA** | 5G NR gNodeB reference base station | 4,000 |
| **`CELL-201`** | `RAN` | `CELL` | **REFERENCE DATA** | Macro sector cell (Site 02) | 1,200 |
| **`CELL-202`** | `RAN` | `CELL` | **REFERENCE DATA** | Macro sector cell (Site 02) | 1,400 |
| **`CELL-A81B-C`** | `RAN` | `CELL` | **REFERENCE DATA** | Micro sector cell (Site 02) | 1,400 |

**Classification Summary:**
- **OBSERVED INVENTORY:** 0 nodes (No live carrier CMDB auto-discovery).
- **REFERENCE DATA:** 17 nodes (Standardized reference models).
- **SYNTHETIC FIXTURE:** 0 nodes (No random or ungrounded mock names).
- **UNKNOWN:** 0 nodes (All 17 nodes have explicit domain, site, and element type).

---

## 3. Dependency Edge Provenance & Directionality

Edges in `TelecomTopologyGraph` are divided into **directed downstream dependencies** and **bidirectional adjacencies**:

| Edge (Source $\rightarrow$ Target) | Link Relation | Directionality | Provenance / Standard Interface |
| :--- | :--- | :--- | :--- |
| `AMF-CORE-01` $\leftrightarrow$ `SMF-CORE-01` | `n11_control` | Bidirectional | 3GPP N11 interface between AMF and SMF |
| `SMF-CORE-01` $\rightarrow$ `UPF-CORE-PRIMARY` | `n4_session` | **Downstream Dependency** | 3GPP N4 session establishment interface |
| `UPF-CORE-PRIMARY` $\leftrightarrow$ `IMS-CORE-01` | `n6_data` | Bidirectional | 3GPP N6 user-plane interface to Data Network/IMS |
| `UPF-CORE-PRIMARY` $\rightarrow$ `RTR-IPMPLS-AGG01` | `n3_interface` | **Downstream Dependency** | 3GPP N3 user plane encapsulation interface |
| `UPF-CORE-SECONDARY` $\rightarrow$ `RTR-IPMPLS-AGG02` | `n3_interface` | **Downstream Dependency** | 3GPP N3 user plane encapsulation interface |
| `RTR-IPMPLS-AGG01` $\rightarrow$ `SW-ACCESS-SITE01` | `backhaul_fiber` | **Downstream Dependency** | Optical transport backhaul link |
| `RTR-IPMPLS-AGG02` $\rightarrow$ `SW-ACCESS-SITE02` | `backhaul_fiber` | **Downstream Dependency** | Optical transport backhaul link |
| `SW-ACCESS-SITE01` $\rightarrow$ `GNB-TESTBED-5G-01` | `fronthaul` | **Downstream Dependency** | Fronthaul ethernet interface to radio site |
| `GNB-TESTBED-5G-01` $\rightarrow$ `CELL-101` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |
| `GNB-TESTBED-5G-01` $\rightarrow$ `CELL-102` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |
| `GNB-TESTBED-5G-01` $\rightarrow$ `CELL-103` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |
| `SW-ACCESS-SITE02` $\rightarrow$ `GNB-SITE02-01` | `fronthaul` | **Downstream Dependency** | Fronthaul ethernet interface to radio site |
| `GNB-SITE02-01` $\rightarrow$ `CELL-201` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |
| `GNB-SITE02-01` $\rightarrow$ `CELL-202` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |
| `GNB-SITE02-01` $\rightarrow$ `CELL-A81B-C` | `serves_cell` | **Downstream Dependency** | Base station sector radio carrier |

### Directionality Derivation Verification
1. **Derived from Underlying Model:** In `src/piis/correlation/topology.py`, `add_dependency(parent, child)` explicitly populates `self._downstream[parent].add(child)` and `self._upstream[child].add(parent)`.
2. **Backend API Exposition:** `src/piis/api/routers/network.py` maps these edges to `NetworkLinkItem(direction="downstream", is_dependency=True)`.
3. **Frontend Rendering:** `NetworkTopologyExplorer.tsx` reads `link.direction` and `link.is_dependency` directly. Downstream edges are rendered with solid directional arrows (`markerEnd="url(#arrow-downstream)"`), while peer links are rendered with dashed lines without arrowheads.
4. **No Frontend Invented Hierarchy:** The visual tiers (Tier 0 Core $\rightarrow$ Tier 1 Transport $\rightarrow$ Tier 2 gNodeB $\rightarrow$ Tier 3 Cells) strictly map to backend node domain and element type attributes. The frontend does not fabricate or rearrange any topological dependencies.

---

## 4. Unknown & Missing Relationship Handling

- **Disconnected / Isolated Nodes:** If an element is ingested in telemetry or alarms that is not present in `TelecomTopologyGraph._nodes`, the API returns structured 404 error `ELEMENT_NOT_FOUND`.
- **Missing Peer Links:** The graph does not assume cross-site or mesh connectivity unless explicitly declared in `_edges`.
- **Unknown Subscriber Mapping:** Transport elements (`RTR-*`, `SW-*`) have `nominal_subscribers=None`, which is strictly preserved and never defaulted to 0.

---

## 5. Audit Verdict

| Audit Dimension | Classification | Result |
| :--- | :--- | :--- |
| Node Provenance | REFERENCE DATA | **PASS** (Explicitly labeled) |
| Edge Provenance | COMPUTED RELATIONSHIP / REFERENCE DATA | **PASS** (Grounded in 3GPP models) |
| Directionality Derivation | Direct Model Mapping | **PASS** (Model-driven) |
| Carrier Infrastructure Representation | Not Live Carrier NOC | **PASS** (Safely qualified) |
