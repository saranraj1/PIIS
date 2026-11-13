# UI-4.1 Network Impact & Subscriber Estimate Grounding Audit

**Milestone:** UI-4.1 — Network Intelligence Evidence Grounding & Independent Verification  
**Module:** Network Impact Analyzer & Blast Radius Evaluation  
**Status:** AUDITED & ACCEPTED  
**Date:** 2026-11-03  
**Auditor / Engineering Role:** Antigravity Engineering Agent  
**Operational Scope:** Strictly Read-Only Decision Support  

---

## 1. Executive Summary & Verification Objective

This audit investigates the end-to-end algorithmic calculation and visual representation of blast radius, cascading element inference, risk scoring, and subscriber impact within PIIS.

### Key Audit Mandate
- Direct impact must follow verified topology edges.
- Cascading impact must follow valid directed downstream paths.
- Cycles and disconnected graphs must be handled safely without infinite recursion.
- Subscriber counts must be grounded in actual data; unsupported subscriber counts must NOT be invented.
- Unknown subscriber impact must be unambiguously distinguishable from zero subscriber impact.
- Derived estimates must NOT be promoted to observed facts.

---

## 2. Topological Traversal & Cycle Safety Verification

### 2.1 Direct vs. Cascading Traversal
The traversal engine is implemented in `TelecomTopologyGraph.get_downstream_elements()` (`src/piis/correlation/topology.py`):
```python
def get_downstream_elements(self, node_ids: List[str], max_depth: int = 1) -> Set[str]:
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
```

### Traversal Invariants Verified:
1. **Downstream-Only Flow:** The queue traverses strictly `self._downstream`, ensuring that service-impacting failures only cascade along dependency edges (e.g., UPF $\rightarrow$ Aggregation Router $\rightarrow$ Access Switch $\rightarrow$ gNodeB $\rightarrow$ Cell). Upstream infrastructure parents are never mistakenly included in cascading blast radius.
2. **Cycle Prevention:** `visited = {root}` tracks visited nodes and `if child not in visited:` guarantees that cyclic graphs terminate with bounded runtime $O(V + E)$ and zero risk of infinite loops.
3. **Disconnected Nodes:** If a root node has no downstream dependencies (e.g. a leaf sector `CELL-101`), `get_downstream_elements` returns `set()` cleanly.
4. **Depth Bounding:** Controlled by `max_depth` parameter (default `inferred_hop_depth=2` in `/api/v1/network/impact`).

---

## 3. Subscriber Count Grounding & Limitation Disclosure

### 3.1 Grounding vs. Illusion Audit
A critical telecom failure mode is displaying a precise, animated subscriber count that has no basis in live network counters. The PIIS implementation was audited against this failure mode:

1. **Source of Subscriber Figures:**
   - Counts are aggregated strictly from the `nominal_subscribers` attribute registered in the reference topology graph.
   - For example: `GNB-TESTBED-5G-01` (5,000 nominal) + `CELL-101` (1,500) + `CELL-102` (1,500) + `CELL-103` (2,000) = **10,000 subscribers**.
   - These are **engineering nominal design capacities**, NOT real-time dynamically connected User Equipment (UE) counts.
2. **Distinguishing Unknown from Zero:**
   - In `NetworkImpactAnalyzer.assess_impact()` (`src/piis/impact/analyzer.py`):
     - If elements in the blast radius have NO `nominal_subscribers` registered (e.g. transport switches or IP routers), `has_sub_data` is `False`.
     - When `has_sub_data == False`: `estimated_affected_subscribers` is strictly `None`, and `subscriber_impact_basis` is `None`.
     - If an element explicitly registers `nominal_subscribers = 0` (e.g., an unallocated spare cell), `estimated_affected_subscribers` is `0`, and basis text notes `0 registered capacity`.
3. **Frontend Representation (`NetworkImpactCard.tsx`):**
   - When `estimated_affected_subscribers === null`:
     - Value displayed: **`NOT AVAILABLE (UNKNOWN)`**.
     - Subtitle displayed: **`No subscriber mapping registered`**.
     - Limitation notice displayed: **`[UNKNOWN] Epistemic Limitation Notice: Direct subscriber-to-element mapping is not monitored for this element type. Subscriber impact is not available.`**
   - When `estimated_affected_subscribers === 0`:
     - Value displayed: **`0`**.
     - Subtitle displayed: **`Zero nominal capacity modeled`**.
   - When `estimated_affected_subscribers > 0`:
     - Value displayed: e.g. **`10,000`**.
     - Subtitle displayed: **`Nominal Topology Capacity`**.
     - Epistemic notice displayed: **`[DERIVED ESTIMATE] Epistemic Grounding Notice: Aggregated nominal capacity across N direct/inferred elements from registered topology metadata. Not dynamically observed from active UE counters.`**

---

## 4. Epistemic Separation Verification

The audit verified that derived estimates are never represented as observed empirical facts:
- Backend `NetworkImpactResponse` schema explicitly specifies `epistemic_status: str = "DERIVED_ESTIMATE"`.
- `EpistemicBadge.tsx` implements a dedicated badge:
  - **Label:** `[DERIVED ESTIMATE]`
  - **Aria Role:** `Statistically or topologically derived estimation (not directly observed)`
  - **Style Class:** `bg-amber-500/15 text-amber-300 border-amber-500/30`
  - **Icon:** `≈`
- Direct affected elements carry `[OBSERVED FACT]`, while inferred cascading elements carry `[DERIVED ESTIMATE]`.

---

## 5. Audit Verdict

| Impact Dimension | Requirement | Implementation Status | Verdict |
| :--- | :--- | :--- | :--- |
| **Topological Path** | Strict downstream traversal | Verified via BFS with depth limit | **PASS** |
| **Cycle Safety** | Terminate on circular dependencies | Verified via `visited` set guard | **PASS** |
| **Subscriber Count** | Grounded in registered topology | Aggregated nominal metadata only | **PASS** |
| **Unknown Distinction** | Distinguishable from 0 | `None` renders `NOT AVAILABLE (UNKNOWN)` | **PASS** |
| **Grounding Notice** | Explicit limitation disclosure | Rendered in both API and UI card | **PASS** |
| **Epistemic Label** | No promotion to observed fact | `[DERIVED ESTIMATE]` with `≈` icon | **PASS** |
