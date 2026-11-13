# PIIS UI-4 — Backend API Capability & Topology Audit Matrix

**Milestone:** UI-4 — Network Intelligence Workspace  
**Status:** AUDITED & SPECIFIED  
**Date:** 2026-11-03  
**Authors:** PIIS Architecture & Core Engineering Team  
**Scope:** Backend Capability Mapping, Data Grounding, and REST Surface for Network Intelligence  

---

## 1. Executive Summary

This document establishes the authoritative capability and data-grounding audit for the **Network Intelligence Workspace (UI-4)**. In strict alignment with the locked architectural principle:

$$\text{EXISTING TELECOM WORKFLOW} + \text{PIIS} = \text{ADDITIONAL OBSERVABILITY, INTEGRITY AND PROVENANCE}$$

The Network Intelligence Workspace operates strictly in **read-only, recommendation-only** mode. It executes zero live network mutating commands, zero autonomous network remediation, zero uncontrolled topology discovery, and zero fabricated telemetry or topology illusions.

---

## 2. Backend Capability Audit Matrix

| Capability Area | Existing Backend Module | Existing API Route | Data Availability & Grounding | Gap & UI-4 Remedy |
| :--- | :--- | :--- | :--- | :--- |
| **Topology Model & Traversal** | `TelecomTopologyGraph` in `src/piis/correlation/topology.py` | None | Fully modeled in-memory directed graph with multi-domain nodes (`RAN`, `TRANSPORT`, `5G_CORE`, `SERVICE`), explicit parent $\to$ child dependencies, hop distances, and `build_reference_topology()`. | Expose `GET /api/v1/network/topology` and `GET /api/v1/network/elements/{element_id}` to provide nodes, links, and directed dependencies to the UI. |
| **Network Impact & Blast Radius** | `NetworkImpactAnalyzer` in `src/piis/impact/analyzer.py` | None | Calculates direct elements, inferred downstream cascade via topology traversal, affected domains, composite risk score, and nominal subscriber capacity. Epistemic status: `DERIVED_ESTIMATE`. | Expose `GET /api/v1/network/impact` parameterized by `element_id` or `incident_id` with full provenance and basis text. |
| **Alarm Aggregation & Correlation** | `TemporalAlarmCorrelator` & `AlarmCompatibilityPolicy` in `src/piis/correlation/engine.py`; `UnifiedIngestionPipeline` in `src/piis/pipeline/unified.py` | Ingestion only (`POST /api/v1/alarms/ingest`) | Alarms stored by `network_element_id` in canonical pipeline store. Correlator produces `CorrelatedIncidentCluster` with rationales and compatibility scoring. | Expose `GET /api/v1/network/alarms` with filtering by element, domain, severity, and correlation cluster membership. |
| **Telemetry & Anomaly Stream** | `TelemetryAnomalyPipeline` in `src/piis/anomaly/pipeline.py`; `StatisticalThresholdDetector`; `IsolationForestDetector` | Ingestion only (`POST /api/v1/telemetry/ingest`) | Raw telemetry time series indexed by `network_element_id`. Pipeline generates `TelemetryAnomaly` with k-sigma dynamic thresholds and ML isolation forest scores. | Expose `GET /api/v1/network/telemetry` returning raw observations along with detected anomaly flags, thresholds, and epistemic tags. |
| **Network Overview Summary** | Integrated pipeline state across `UnifiedIngestionPipeline` and `TelecomTopologyGraph` | None | Topology element counts by domain, alarm counters, anomaly counts, and sync timestamps. | Expose `GET /api/v1/network/overview` with explicit counts, zero-handling (distinguishing 0 from unavailable), and provenance metadata. |

---

## 3. Grounding & Epistemic Separation

| Metric / Artifact | Backend Source | Epistemic Classification | UI Representation & Caveats |
| :--- | :--- | :--- | :--- |
| **Network Element Metadata** | `TelecomTopologyGraph._nodes` | `OBSERVED_FACT` (Static Topology Registry) | Rendered as nodes with site ID, element type, and registered nominal subscribers. |
| **Topology Adjacency & Dependencies** | `TelecomTopologyGraph._edges`, `_downstream`, `_upstream` | `OBSERVED_FACT` / `COMPUTED_TOPOLOGY` | Directed edges indicate functional dependency (upstream provider $\to$ downstream dependent). Missing edges are explicitly rendered as non-connected. |
| **Raw Alarms** | `UnifiedIngestionPipeline._alarms` | `OBSERVED_FACT` | Alarm codes, probable cause, timestamps, severity. Uncorrelated alarms are explicitly marked as `INDIVIDUAL_ALARM`. |
| **Correlated Alarm Clusters** | `TemporalAlarmCorrelator.correlate_events()` | `HYPOTHESIS` / `DERIVED_ESTIMATE` | Composite score $\ge 0.55$. Correlation rationale explicitly rendered (time $\Delta$, topological hop distance, domain affinity). |
| **Raw Telemetry Metrics** | `UnifiedIngestionPipeline._telemetry` | `OBSERVED_FACT` | Metric name, timestamp, value, unit (e.g., `%`, `ms`, `pps`). Gaps in time series displayed with broken lines, not zero-filled illusions. |
| **Telemetry Anomalies** | `TelemetryAnomalyPipeline.process_records()` | `MODEL_PREDICTION` | Statistical $\sigma$ violation and Isolation Forest score. Baseline and dynamic threshold boundaries explicitly drawn. |
| **Blast Radius & Affected Subscribers** | `NetworkImpactAnalyzer.assess_impact()` | `DERIVED_ESTIMATE` | Downstream nodes found via graph BFS. Subscriber count accompanied by basis notice: *"Aggregated nominal capacity from registered topology metadata. Not dynamically observed from active UE counters."* |

---

## 4. REST Surface Specifications (`/api/v1/network`)

All endpoints are strictly **read-only** (`GET`), authenticated via existing PIIS bearer tokens, and governed by RBAC permission `VIEW_INCIDENTS` or `VIEW_EVIDENCE`.

### 4.1. `GET /api/v1/network/overview`
- **Description:** Summary metrics for the network intelligence domain.
- **Query Params:** None.
- **Response Model:**
  ```json
  {
    "total_elements": 13,
    "elements_by_domain": {
      "RAN": 7,
      "TRANSPORT": 4,
      "5G_CORE": 4,
      "SERVICE": 1
    },
    "total_links": 12,
    "active_alarms_count": 5,
    "correlated_clusters_count": 2,
    "active_anomalies_count": 1,
    "last_sync_timestamp": "2026-11-03T13:00:00Z",
    "topology_version": "1.0.0-reference",
    "provenance": {
      "source": "TelecomTopologyGraph",
      "integrity_hash": "sha256-..."
    }
  }
  ```

### 4.2. `GET /api/v1/network/topology`
- **Description:** Attributed network topology graph nodes and directed links.
- **Query Params:** `domain` (optional filter: `RAN`, `TRANSPORT`, `5G_CORE`, `SERVICE`, or omitted for all).
- **Response Model:**
  ```json
  {
    "nodes": [
      {
        "element_id": "GNB-TESTBED-5G-01",
        "domain": "RAN",
        "element_type": "GNB",
        "site_id": "SITE01",
        "nominal_subscribers": 5000,
        "active_alarm_count": 1,
        "has_anomaly": false
      }
    ],
    "links": [
      {
        "source": "SW-ACCESS-SITE01",
        "target": "GNB-TESTBED-5G-01",
        "relation": "fronthaul",
        "is_dependency": true,
        "direction": "downstream"
      }
    ]
  }
  ```

### 4.3. `GET /api/v1/network/elements/{element_id}`
- **Description:** Detailed view of an individual element, its upstream dependencies, and downstream children.
- **Query Params:** None.
- **Response Model:**
  ```json
  {
    "element_id": "GNB-TESTBED-5G-01",
    "domain": "RAN",
    "element_type": "GNB",
    "site_id": "SITE01",
    "nominal_subscribers": 5000,
    "neighbors": ["SW-ACCESS-SITE01", "CELL-101", "CELL-102", "CELL-103"],
    "upstream_parents": ["SW-ACCESS-SITE01"],
    "downstream_children": ["CELL-101", "CELL-102", "CELL-103"],
    "active_alarms": [],
    "recent_telemetry_count": 24
  }
  ```

### 4.4. `GET /api/v1/network/impact`
- **Description:** Blast radius and risk quantification for a given network element or cluster.
- **Query Params:** `element_id` (required if `incident_id` omitted), `incident_id` (optional).
- **Response Model:**
  ```json
  {
    "target_element": "SW-ACCESS-SITE01",
    "direct_elements": ["SW-ACCESS-SITE01"],
    "inferred_elements": ["GNB-TESTBED-5G-01", "CELL-101", "CELL-102", "CELL-103"],
    "total_element_count": 4,
    "affected_domains": ["TRANSPORT", "RAN"],
    "severity_risk_level": "MAJOR",
    "risk_score": 0.55,
    "estimated_affected_subscribers": 10000,
    "subscriber_impact_basis": "Aggregated nominal capacity across 4 direct/inferred elements from registered topology metadata. Not dynamically observed from active UE counters.",
    "epistemic_status": "DERIVED_ESTIMATE"
  }
  ```

### 4.5. `GET /api/v1/network/alarms`
- **Description:** Active alarms and correlation clusters.
- **Query Params:** `element_id` (optional), `domain` (optional), `severity` (optional).
- **Response Model:**
  ```json
  {
    "alarms": [
      {
        "alarm_id": "ALM-001",
        "network_element_id": "GNB-TESTBED-5G-01",
        "network_domain": "RAN",
        "alarm_code": "CELL-DEG-01",
        "probable_cause": "Radio link failure",
        "severity": "MAJOR",
        "timestamp": "2026-11-03T12:30:00Z",
        "cluster_id": "CLUSTER-01"
      }
    ],
    "clusters": [
      {
        "cluster_id": "CLUSTER-01",
        "dominant_domain": "RAN",
        "event_count": 3,
        "affected_elements": ["GNB-TESTBED-5G-01", "CELL-101"],
        "mean_confidence": 0.88,
        "rationales": ["Shared fault category (RADIO_CAPACITY)"]
      }
    ]
  }
  ```

### 4.6. `GET /api/v1/network/telemetry`
- **Description:** Raw telemetry series and anomaly violations for a network element.
- **Query Params:** `element_id` (required), `metric_name` (optional).
- **Response Model:**
  ```json
  {
    "element_id": "CELL-101",
    "series": [
      {
        "metric_name": "prb_utilization_pct",
        "unit": "%",
        "timestamps": ["2026-11-03T12:00:00Z", "2026-11-03T12:05:00Z"],
        "values": [45.2, 89.6],
        "is_imputed": [false, false]
      }
    ],
    "anomalies": [
      {
        "anomaly_id": "ANOM-01",
        "metric_name": "prb_utilization_pct",
        "timestamp": "2026-11-03T12:05:00Z",
        "observed_value": 89.6,
        "expected_value": 45.0,
        "threshold_value": 75.0,
        "severity": "CRITICAL",
        "score": 0.82,
        "epistemic_status": "MODEL_PREDICTION"
      }
    ]
  }
  ```

---

## 5. Security and Operational Bounds

1. **Zero Network Write Access:** Endpoints are strictly `GET`. No capability to send CLI, NETCONF, gNMI, or SNMP writes.
2. **Permission Gate:** Enforced via FastAPI dependencies `require_permissions(Permission.VIEW_INCIDENTS)`.
3. **No Phantom Elements:** All elements returned originate from the canonical topology registry. Elements without telemetry or alarms return empty arrays with explicit zero-state indicators.
