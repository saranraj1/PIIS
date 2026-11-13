# Model Card: Telemetry Anomaly Detection Pipeline

- **Model name/version:** `piis-telemetry-anomaly-v1.0`
- **Intended task:** Multi-metric anomaly detection and KPI degradation alerting on normalized telecom time-series telemetry streams.
- **Intended users:** NOC operators, automated incident correlation engines, and performance assurance teams.
- **Observation frequency:** 10 Hz high-frequency telemetry (TelecomTS) and periodic polling intervals (1-minute, 5-minute, 15-minute).

---

## 1. Architectural Overview

The pipeline combines a deterministic statistical dynamic thresholding detector with an unsupervised machine learning anomaly detector:
1. **Conditioning & Preprocessing:**
   - 3-step rolling median filter to suppress spurious single-sample sensor noise.
   - Forward/backward imputation for missing samples up to 3 timesteps.
2. **Statistical Dynamic Thresholding (`StatisticalThresholdDetector`):**
   - Asymmetric exponential moving average (EWMA) envelope ($\alpha = 0.1, \beta = 0.05, k_{\sigma} = 2.5$).
   - Directional penalties: DROP-only for quality metrics (`RSRP`, `MCS`, `Throughput`), SURGE-only for error/saturation metrics (`BLER`, `PRB_UTIL`, `Latency`), TWO-SIDED for environmental metrics.
3. **Unsupervised ML Scoring (`IsolationForestDetector`):**
   - Multivariate isolation forest ($n_{\text{estimators}} = 100, \text{contamination} = 0.08$).
   - Feature space: Multi-metric raw levels, first differences ($\Delta x$), and rolling velocity.
4. **Ensemble Fusion & Confidence:**
   - Maximum fusion score $s_{\text{fused}} = \max(s_{\text{stat}}, s_{\text{IF}})$.
   - Confidence estimate $c = 1.0 - |s_{\text{stat}} - s_{\text{IF}}| \cdot (1 - s_{\text{fused}})$.

---

## 2. Evaluation Results on Real TelecomTS 5G Jammer Telemetry

- **Source Dataset:** `AliMaatouk/TelecomTS` (`data/processed/telemetry/telecomts_jammer_telemetry.jsonl`).
- **Total Time Steps:** 500 timesteps @ 10 Hz (5,000 raw observations across 10 physical/MAC KPIs).
- **Ground-Truth Attack Episode:** 40 contiguous timesteps labeled `ground_truth_anomaly = True` (RF Jammer active).

| Metric / Attribute | Isolation Forest | Statistical EWMA | Hybrid Ensemble Pipeline |
| :--- | :--- | :--- | :--- |
| **Precision** | 0.2941 | 0.2525 | **0.2525** |
| **Recall** | 0.1250 | 0.6250 | **0.6250 (62.5%)** |
| **F1-Score** | 0.1754 | 0.3597 | **0.3597** |
| **PR-AUC** | 0.1793 | N/A | **0.1793** |
| **ROC-AUC** | 0.7291 | N/A | **0.7291** |
| **Detection Delay** | N/A | 0 timesteps | **0 timesteps (Instantaneous)** |
| **Nominal False Alarm Rate** | 0.0652 | 0.2121 | **0.2121** |

### Operational Interpretation
- **Zero Detection Delay:** The ensemble pipeline triggered its first alert at the exact onset timestep of the RF jamming attack (`2025-01-01T00:00:33.000Z`, timestep 330).
- **Recall Advantage:** Dynamic statistical thresholding captured 62.5% of the attack duration, substantially outperforming single-instance point isolation trees (12.5%).

---

## 3. Strict Provenance & Output Schema

Outputs conform to `TelemetryAnomaly` model:
- `anomaly_id`: Deterministic hash `ANOM-<NE>-<hash>`.
- `epistemic_status`: `STATISTICAL_INFERENCE`.
- `affected_metrics`: List of violating metrics with exact trigger value, baseline mean, and deviation sigmas.
- `provenance`: Traceable to exact source observation IDs and transformation version.

---

## 4. Limitations & Edge Cases

1. **Stationarity Assumption:** Sudden step-changes due to legitimate network configuration re-allocation (e.g., carrier reconfiguration) will cause transient alerts until EWMA adapts (approx. 10–15 timesteps).
2. **Missing Telemetry Gaps:** Extended telemetry loss (> 5 polling intervals) is flagged as missing data rather than extrapolated.
3. **No Autonomous Actions:** Emits decision-support evidence only; never modifies radio or core parameters autonomously.
