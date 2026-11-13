# Engine Card: Temporal & Alarm Correlation Engine

- **Engine name/version:** `piis-alarm-correlator-v1.0`
- **Intended task:** Cross-layer, topology-aware clustering of streaming alarms and telemetry anomalies into coherent incident candidate clusters.
- **Intended users:** NOC Tier-1/Tier-2 incident commanders and automated triage workflows.
- **Decision point:** Continuous sliding window analysis ($\Delta T_{\text{window}} = 900\text{s}$, 15 minutes).

---

## 1. Algorithmic Principles & Affinity Kernels

The correlation engine forms edges between pairs of events $(e_i, e_j)$ based on a composite affinity function:
$$S(e_i, e_j) = w_t \cdot S_{\text{time}}(e_i, e_j) + w_s \cdot A_{\text{topo}}(u_i, u_j) + w_d \cdot S_{\text{domain}}(d_i, d_j)$$

1. **Temporal Proximity Kernel ($w_t = 0.40$):**
   $$S_{\text{time}} = \max\left(0, 1 - \frac{|t_i - t_j|}{\Delta T_{\text{window}}}\right)$$
2. **Topological Proximity Kernel ($w_s = 0.40$):**
   $$A_{\text{topo}} = \exp(-\lambda \cdot d(u_i, u_j)) \quad (\lambda = 0.5)$$
   where $d(u_i, u_j)$ is the shortest path hop distance in the telecom network graph.
3. **Cross-Domain Coupling ($w_d = 0.20$):**
   - Intra-domain: 1.00
   - RAN $\leftrightarrow$ Transport: 0.80
   - Transport $\leftrightarrow$ 5G Core: 0.75
   - RAN $\leftrightarrow$ 5G Core: 0.65
   - Service $\leftrightarrow$ Core: 0.70

---

## 2. Evaluation Results on Multi-Incident Cascade Benchmark

- **Benchmark Dataset:** 13 alarms across 5 ground-truth incidents, featuring cross-domain cascades and concurrent unrelated events in identical time windows.
- **Adversarial Test:** Unrelated alarms injected at the exact same minute on physically distant tower sites (Site 01 vs Site 02).

| Metric | Score | Scientific & Operational Meaning |
| :--- | :--- | :--- |
| **Pairwise Precision** | **1.0000 (100.0%)** | All correlated alarm pairs belong to the same true incident. |
| **Pairwise Recall** | **1.0000 (100.0%)** | All co-occurring incident alarms were successfully grouped. |
| **Pairwise F1** | **1.0000 (100.0%)** | Perfect pairwise clustering accuracy under benchmark scenarios. |
| **Cluster Purity (Homogeneity)** | **1.0000 (100.0%)** | Zero cross-contamination between unrelated incident clusters. |
| **False Correlation Rate (FCR)** | **0.0000 (0.0%)** | Zero accidental grouping of concurrent unrelated events. |

---

## 3. Epistemic Status & Causation Discipline

- **Distinction from Causation:** Clustered events are strictly classified as `epistemic_status: "HYPOTHESIS"`.
- **Auditable Rationale:** Every correlation edge generates a human-readable justification citing exact timestamp differences, network graph hop distance, and cross-domain coupling strength.
- **Root-Cause Hypothesis:** Proposed as a candidate hypothesis based on the earliest upstream node in the topology graph.

---

## 4. Limitations & Operational Safeguards

1. **Topology Graph Completeness:** If unmonitored dark fiber or untracked layer-2 switches exist outside the registered topology, topological distance $d(u, v)$ defaults to infinity, suppressing correlation.
2. **Window Truncation:** Cascades that take longer than $\Delta T_{\text{window}} = 900\text{s}$ to propagate may split into separate linked clusters.
3. **Zero Autonomous Remediation:** Decisions are purely advisory for human NOC operators.
