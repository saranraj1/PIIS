# PIIS UI-4 — Epistemic Grounding & Safety Audit

**Milestone:** UI-4 — Network Intelligence Workspace  
**Status:** VERIFIED & SEALED  
**Date:** 2026-11-03  
**Authors:** PIIS Safety, Security & Ethics Review Board  

---

## 1. Safety Audit & Non-Negotiable Boundaries

The Production Incident Intelligence System (PIIS — Telecom Edition) is an evidence-grounded incident decision-support platform for NOC operators and telecom reliability engineers.

In accordance with system specifications, this safety audit verifies:
1. **Zero Production Mutation:** PIIS has no connection, credentials, or code paths to execute network changes (no NETCONF `<edit-config>`, no gNMI `Set`, no SSH CLI command issuance, no SNMP `SetRequest`).
2. **Read-Only Enclosure:** All Network Intelligence endpoints (`/api/v1/network/*`) are strictly HTTP `GET`.
3. **No Autonomous Remediation:** Investigation actions and blast radius assessments are strictly recommendations for human review.
4. **No Fabricated Data:** Every topology node, link, alarm, and telemetry sample displayed in the UI originates from authentic registered models or ingested envelopes.

---

## 2. Epistemic Classification Audit

The table below catalogs every data element rendered within the Network Intelligence Workspace, its provenance, and its epistemic tag:

| UI Component | Data Element | Provenance Source | Epistemic Classification | Safety & Grounding Controls |
| :--- | :--- | :--- | :--- | :--- |
| **Network Overview** | Monitored Element Count | `TelecomTopologyGraph._nodes` | `OBSERVED_FACT` | Strictly counts registered nodes; never assumes unpolled hardware. |
| **Network Overview** | Active Alarms Count | `UnifiedIngestionPipeline._alarms` | `OBSERVED_FACT` | Exact count of unacknowledged/active alarms in pipeline memory. |
| **Network Overview** | Correlated Cluster Count | `TemporalAlarmCorrelator.correlate_events()` | `HYPOTHESIS` | Clearly badged as correlated hypothesis clusters; not guaranteed single root causes. |
| **Network Overview** | Anomaly Violations Count | `TelemetryAnomalyPipeline` | `MODEL_PREDICTION` | Tagged as algorithmic anomaly detections based on statistical and ML scoring. |
| **Topology Explorer** | Network Element Node | Registered Topology Node | `OBSERVED_FACT` | Attributes (`site_id`, `element_type`, `domain`) match registered inventory. |
| **Topology Explorer** | Directed Dependency Link | Attributed Topology Edges | `COMPUTED_TOPOLOGY` | Directed link strictly represents modeled service/transport dependency. |
| **Topology Explorer** | Missing / Disconnected Link | Topology Graph Non-Adjacency | `OBSERVED_FACT` | Unconnected nodes are rendered disconnected. No phantom links are invented. |
| **Impact Analysis** | Direct Affected Elements | Alarmed / Investigated Element IDs | `OBSERVED_FACT` | Explicitly lists elements where faults were directly observed. |
| **Impact Analysis** | Inferred Cascading Elements | Directed BFS Downstream Traversal | `DERIVED_ESTIMATE` | Clearly distinguished from direct elements; labeled as inferred cascade. |
| **Impact Analysis** | Estimated Affected Subscribers | Topology Nominal Subscriber Capacity | `DERIVED_ESTIMATE` | Accompanied by mandatory disclaimer: *"Aggregated nominal capacity from registered topology metadata. Not dynamically observed from active UE counters."* |
| **Alarm Intelligence** | Raw Alarms List | Ingested Alarm Envelopes | `OBSERVED_FACT` | Direct timestamps, alarm codes, and probable cause strings from OSS/NMS. |
| **Alarm Intelligence** | Correlation Rationale | `TemporalAlarmCorrelator` | `HYPOTHESIS` | Transparent mathematical rationale showing temporal $\Delta t$, hop distance, domain affinity, and compatibility evaluation. |
| **Telemetry Explorer** | Metric Time Series | Ingested Telemetry Observations | `OBSERVED_FACT` | Raw metric points plotted against observation timestamps. Gaps render as broken lines. |
| **Telemetry Explorer** | Dynamic Thresholds ($\pm 2.5\sigma$) | `StatisticalThresholdDetector` | `MODEL_PREDICTION` | Visualized as upper/lower confidence bounds. |
| **Telemetry Explorer** | Anomaly Markers | `TelemetryAnomaly` Record | `MODEL_PREDICTION` | Explicit markers showing severity and score. |

---

## 3. Epistemic Fallacy Prevention & Hardening

1. **Zero vs Unavailable Discrimination:**
   - Literal zero (e.g., 0 active alarms on a healthy node) is explicitly rendered as `0` with green nominal badge.
   - Missing or unpolled telemetry is explicitly rendered as `"No telemetry ingested for this element"` with an `EmptyState` component.
   - Gaps in telemetry time-series are visually broken, preventing the illusion of steady-state zeros.

2. **No False Certainty in Blast Radius:**
   - Subscriber numbers are never labeled as "current subscribers offline" but rather "Estimated nominal subscriber capacity at risk".
   - Inferred elements are visually distinct (dashed lines, muted badges) from direct alarmed elements.

3. **Causal Compatibility Protection:**
   - The UI surfaces the `AlarmCompatibilityPolicy` justification, showing why alarms were or were not merged into the same cluster.
