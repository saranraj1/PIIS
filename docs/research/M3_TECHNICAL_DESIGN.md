# Milestone 3 Technical Design — Network Intelligence Architecture

**Component:** Telemetry Anomaly Detection, Alarm Correlation, and Impact Analysis  
**Module Prefix:** `src/piis/anomaly/`, `src/piis/correlation/`, `src/piis/impact/`  
**Date:** 2026-10-31  
**Status:** DESIGN BASELINE  

---

## 1. Mathematical Formulations

### 1.1. Telemetry Anomaly Detection

Let $X = \{x_t\}_{t=1}^T$ be a univariate time series of KPI observations for metric $m \in M$ and network element $u \in V$.

#### A. Exponentially Weighted Moving Average (EWMA) Baseline
To adapt continuously to non-stationary network diurnal trends, the background expectation $\hat{\mu}_t$ and variance $\hat{\sigma}_t^2$ are updated incrementally:
$$\hat{\mu}_t = \alpha \cdot x_t + (1 - \alpha) \cdot \hat{\mu}_{t-1}$$
$$\hat{\sigma}_t^2 = \beta \cdot (x_t - \hat{\mu}_t)^2 + (1 - \beta) \cdot \hat{\sigma}_{t-1}^2$$
where $\alpha \in (0, 1]$ is the center adaptation rate (default $\alpha = 0.1$) and $\beta \in (0, 1]$ is the variance update rate (default $\beta = 0.05$).

The dynamic upper and lower threshold envelopes are defined as:
$$T_{\text{upper}}(t) = \hat{\mu}_{t-1} + k_{\text{up}} \cdot \hat{\sigma}_{t-1}$$
$$T_{\text{lower}}(t) = \hat{\mu}_{t-1} - k_{\text{down}} \cdot \hat{\sigma}_{t-1}$$
where multipliers $k_{\text{up}}, k_{\text{down}} \ge 2.5$ reflect the asymmetric telecom penalty:
- **Degradation-Drop Metrics** (`RSRP`, `DL_MCS`, `UL_SNR`, `TX_THROUGHPUT`): $k_{\text{down}} = 2.5, k_{\text{up}} = \infty$.
- **Surge-Fault Metrics** (`DL_BLER`, `UL_BLER`, `PRB_UTIL_DL`, `PRB_UTIL_UL`, `LATENCY`): $k_{\text{up}} = 2.5, k_{\text{down}} = \infty$.
- **Two-Sided Metrics** (`TEMPERATURE`, `VOLTAGE`): $k_{\text{up}} = 3.0, k_{\text{down}} = 3.0$.

An observation is flagged if $x_t > T_{\text{upper}}(t)$ or $x_t < T_{\text{lower}}(t)$. The statistical severity score is:
$$s_{\text{stat}}(x_t) = \min\left(1.0, \frac{|x_t - \hat{\mu}_{t-1}|}{k \cdot \hat{\sigma}_{t-1}}\right)$$

#### B. Rolling Z-Score Formulation
For windowed telemetry frames of length $W$ (e.g., $W = 30$ timesteps):
$$\mu_W(t) = \frac{1}{W} \sum_{i=0}^{W-1} x_{t-i}, \quad \sigma_W(t) = \sqrt{\frac{1}{W} \sum_{i=0}^{W-1} (x_{t-i} - \mu_W(t))^2 + \epsilon}$$
$$z_t = \frac{x_t - \mu_W(t)}{\sigma_W(t)}$$
An anomaly is triggered if $|z_t| > z_{\text{thresh}}$ (default $z_{\text{thresh}} = 3.0$).

#### C. Multi-Metric Isolation Forest
For multivariate observation vectors $\mathbf{x}_t = [m_{1,t}, m_{2,t}, \dots, m_{K,t}]^\top$, an ensemble of $N$ isolation trees partitions the feature space. The path length $h(\mathbf{x})$ is averaged across trees:
$$s_{\text{IF}}(\mathbf{x}) = 2^{-\frac{\mathbb{E}[h(\mathbf{x})]}{c(n)}}$$
where $c(n) = 2(\ln(n - 1) + 0.5772156649) - \frac{2(n-1)}{n}$.

The raw score is mapped to a calibrated probability $p_{\text{anom}} \in [0, 1]$.

#### D. Ensemble Anomaly Score & Confidence
For any time window, the fused anomaly score is:
$$s_{\text{fused}} = \max(s_{\text{stat}}, s_{\text{IF}})$$
The confidence score $c \in [0.0, 1.0]$ represents the agreement between statistical bounds and ML scoring:
$$c = 1.0 - |s_{\text{stat}} - s_{\text{IF}}| \cdot (1 - s_{\text{fused}})$$

---

## 2. Temporal & Alarm Correlation Engine

Let $\mathcal{E} = \{e_1, e_2, \dots, e_M\}$ be the unified set of raw events (alarms and telemetry anomalies).

### 2.1. Telecom Topology Graph
The telecom network is represented as an attributed graph $G = (V, E_{\text{topo}})$:
- Nodes $u \in V$ have attribute `domain` $\in \{\text{RAN}, \text{TRANSPORT}, \text{5G\_CORE}, \text{SERVICE}\}$.
- Edges $(u, v) \in E_{\text{topo}}$ represent physical, logical, or hierarchical links (`cell_to_gnb`, `backhaul_link`, `n3_interface`, `n4_control`).
- Distance $d(u, v)$ is the shortest path length (in hops) between node $u$ and node $v$ in $G$. If no path exists, $d(u, v) = \infty$.

### 2.2. Composite Affinity Metric
For two events $e_i = (u_i, t_i, d_i)$ and $e_j = (u_j, t_j, d_j)$:

1. **Temporal Proximity Kernel:**
   $$S_{\text{time}}(e_i, e_j) = \begin{cases} 
   1 - \frac{|t_i - t_j|}{\Delta T_{\text{window}}}, & \text{if } |t_i - t_j| \le \Delta T_{\text{window}} \\
   0, & \text{otherwise}
   \end{cases}$$
   where $\Delta T_{\text{window}} = 900\text{ seconds}$ (15 minutes).

2. **Topological Proximity Kernel:**
   $$A_{\text{topo}}(u_i, u_j) = \begin{cases}
   1.0, & \text{if } u_i = u_j \\
   \exp(-\lambda \cdot d(u_i, u_j)), & \text{if } d(u_i, u_j) < \infty \\
   0.0, & \text{if disjoint}
   \end{cases}$$
   where decay parameter $\lambda = 0.5$ (hop distance 1: affinity 0.61; hop distance 2: 0.37; hop distance 3: 0.22).

3. **Cross-Layer Domain Affinity:**
   $S_{\text{domain}}(d_i, d_j)$ captures known operational causal couplings:
   - Same domain ($d_i = d_j$): $1.0$
   - RAN $\leftrightarrow$ Transport: $0.8$
   - Transport $\leftrightarrow$ 5G Core: $0.7$
   - RAN $\leftrightarrow$ 5G Core: $0.6$
   - Service $\leftrightarrow$ Any: $0.5$

4. **Total Affinity:**
   $$S(e_i, e_j) = w_t \cdot S_{\text{time}} + w_s \cdot A_{\text{topo}} + w_d \cdot S_{\text{domain}}$$
   with weights $w_t = 0.40, w_s = 0.40, w_d = 0.20$.

An undirected correlation edge is formed if $S(e_i, e_j) \ge \theta_{\text{corr}}$ (default $\theta_{\text{corr}} = 0.55$) and $S_{\text{time}} > 0$.

### 2.3. Incident Candidate Clustering
The connected components of the correlation graph form candidate incident clusters $\mathcal{C}_k$.

### 2.4. Epistemic Status & Causation Discipline
- **Status:** All clustered associations carry `epistemic_status: "CORRELATED_ASSOCIATION"`.
- **Causation Rationale:** Every correlation edge produces a structured rationale string:
  $$\text{rationale} = f(e_i, e_j) = \text{"Events occurred within } \Delta t \text{s on nodes } u_i, u_j \text{ (hop dist } d \text{, relation: } r\text{)"}$$
- Causal hypothesis is labeled `HYPOTHESIS`, reserving `FACT` strictly for directly observed alarms and measurements.

---

## 3. Network Impact Analysis

For an incident cluster $\mathcal{C}$ with directly affected elements $V_{\text{direct}} = \{u \in V \mid \exists e \in \mathcal{C} \text{ on node } u\}$:

### 3.1. Blast Radius Decomposition
- **Direct Blast Radius:** $V_{\text{direct}}$
- **Inferred Blast Radius:**
  $$V_{\text{inferred}} = \{v \in V \setminus V_{\text{direct}} \mid \min_{u \in V_{\text{direct}}} d(u, v) \le K_{\text{depth}}\}$$
  where $K_{\text{depth}} = 1$ (immediate downstream or dependent elements).
- **Total Blast Radius:** $V_{\text{total}} = V_{\text{direct}} \cup V_{\text{inferred}}$.
- **Domain Span:**
  $$\mathcal{D}_{\text{impact}} = \bigcup_{v \in V_{\text{total}}} \{\text{domain}(v)\}$$

### 3.2. Severity Escalation Risk
The blast risk score $R \in [0.0, 1.0]$ is formulated as:
$$R = \min\left(1.0, 0.3 \cdot |V_{\text{direct}}| + 0.1 \cdot |V_{\text{inferred}}| + 0.2 \cdot |\mathcal{D}_{\text{impact}}| + 0.2 \cdot \mathbb{I}(\text{5G\_CORE} \in \mathcal{D})\right)$$

---

## 4. Formal Data Contracts & Pydantic Schemas

### 4.1. Telemetry Anomaly Contract
```python
class AnomalySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    WARNING = "WARNING"

class MetricViolation(BaseModel):
    metric_name: str
    observed_value: float
    expected_mean: float
    deviation_sigmas: float
    unit: Optional[str] = None

class TelemetryAnomaly(BaseModel):
    anomaly_id: str
    start_timestamp: str
    end_timestamp: str
    network_element_id: str
    network_domain: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: AnomalySeverity
    affected_metrics: List[MetricViolation]
    detector_type: str
    epistemic_status: str = "STATISTICAL_INFERENCE"
    source_observation_ids: List[str]
    provenance: Dict[str, Any]
```

### 4.2. Correlation Cluster Contract
```python
class CorrelationRationale(BaseModel):
    event_id_a: str
    event_id_b: str
    time_delta_seconds: float
    hop_distance: Optional[int]
    affinity_score: float
    rationale_text: str

class CorrelatedIncidentCluster(BaseModel):
    cluster_id: str
    earliest_timestamp: str
    latest_timestamp: str
    primary_domain: str
    involved_domains: List[str]
    direct_alarm_ids: List[str]
    telemetry_anomaly_ids: List[str]
    affected_elements: List[str]
    correlation_edges: List[CorrelationRationale]
    root_cause_hypothesis: Optional[str] = None
    epistemic_status: str = "HYPOTHESIS"
    provenance: Dict[str, Any]
```

### 4.3. Impact Assessment Contract
```python
class ImpactAssessment(BaseModel):
    assessment_id: str
    cluster_id: str
    direct_elements: List[str]
    inferred_elements: List[str]
    total_element_count: int
    affected_domains: List[str]
    domain_count: int
    severity_risk_level: str
    risk_score: float = Field(ge=0.0, le=1.0)
    estimated_affected_subscribers: Optional[int] = None
    subscriber_impact_basis: Optional[str] = None
    epistemic_status: str = "DERIVED_ESTIMATE"
    provenance: Dict[str, Any]
```
