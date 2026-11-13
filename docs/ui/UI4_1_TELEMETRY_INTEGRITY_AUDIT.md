# UI-4.1 Telemetry Integrity & Temporal Causality Audit

**Milestone:** UI-4.1 — Network Intelligence Evidence Grounding & Independent Verification  
**Module:** Telemetry Anomaly Pipeline & Time-Series Visualizer  
**Status:** AUDITED & ACCEPTED  
**Date:** 2026-11-03  
**Auditor / Engineering Role:** Antigravity Engineering Agent  
**Operational Scope:** Strictly Read-Only Decision Support  

---

## 1. Executive Summary & Verification Mandate

This audit investigates the statistical, algorithmic, and visual integrity of the PIIS telemetry ingestion and anomaly detection pipeline.

### Core Temporal Invariant
**Strict Causal Temporal Ordering:** Under no circumstances may observations from future time steps $t + \Delta t$ leak backward to alter statistical baselines, dynamic threshold envelopes, or anomaly predictions at time $t$.

---

## 2. Ingestion & Preservation of Recorded Samples

1. **Source Adapters:** Telemetry samples are ingested through `PrometheusAdapter` or `OTLPAdapter` and stored in `UnifiedIngestionPipeline._telemetry[element_id]`.
2. **Field Preservation:**
   - `timestamp` / `observation_timestamp`: Stored in ISO-8601 UTC format. Preserved verbatim through `TelemetrySeriesItem.timestamps`.
   - `unit`: Preserved directly from raw metric payloads (e.g. `%`, `dBm`, `ms`, `packets/s`).
   - `metric_value`: Converted to IEEE-754 floating point without loss of precision.

---

## 3. Dynamic Thresholding & Causal EWMA Implementation

The dynamic threshold calculation in `StatisticalThresholdDetector` (`src/piis/anomaly/statistical.py`) uses an Exponentially Weighted Moving Average (EWMA) with asymmetric directional sensitivity:

```python
def update_and_evaluate(
    self,
    metric_name: str,
    value: float,
    unit: Optional[str] = None,
    timestamp: Optional[str] = None,
    observation_id: Optional[str] = None,
) -> Optional[MetricViolation]:
    ...
    current_mean, current_var, count = self._state[metric_name]
    current_std = math.sqrt(max(current_var, self.epsilon))

    # Evaluate deviation against PRE-EXISTING state (strictly past samples)
    deviation = value - current_mean
    sigmas = deviation / current_std
    ...
    # Only AFTER evaluation is state updated for future samples
    if not is_violation or abs(sigmas) < (self.k_sigma * 1.5):
        new_mean = self.alpha * value + (1.0 - self.alpha) * current_mean
        new_var = self.beta * ((value - new_mean) ** 2) + (1.0 - self.beta) * current_var
        self._state[metric_name] = (new_mean, new_var, count + 1)
```

### Causality Guarantees:
1. **Pre-Evaluation State:** Sample $x_t$ is tested against $\mu_{t-1}$ and $\sigma_{t-1}$.
2. **Anomaly Isolation:** Severe anomalies ($\ge 1.5 \times k\sigma$) are excluded from updating the EWMA baseline to prevent pollution of the nominal operational envelope.
3. **No Centered Rolling Windows:** `rolling(..., center=False)` is enforced everywhere. Future lookahead leakage is structurally impossible.

---

## 4. Empirical Temporal Mutation Test Evidence

To independently prove temporal integrity, a dedicated mutation test was executed in `tests/unit/test_ui4_telemetry_temporal_integrity.py`:

```python
def test_future_mutation_does_not_alter_past_predictions(self):
    """Mutating future observations at t >= 15 MUST NOT alter anomaly outcomes at t < 15."""
    base_time = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    past_values = [30.0, 31.0, 29.5, 30.5, 32.0, 28.5, 31.2, 30.1, 29.8, 30.4, 31.1, 29.9, 30.2, 31.5, 30.0]
    past_records = _generate_telemetry_series("GNB-SITE01", "PRB_UTIL_DL", base_time, past_values)

    pipeline_a = TelemetryAnomalyPipeline()
    anomalies_past_only = pipeline_a.process_records(past_records)

    # Append extreme future spikes at t=15..19
    future_spikes = [100.0, 99.0, 100.0, 98.5, 100.0]
    future_records = _generate_telemetry_series(
        "GNB-SITE01", "PRB_UTIL_DL", base_time + timedelta(seconds=15 * 60), future_spikes
    )
    combined_records = past_records + future_records

    pipeline_b = TelemetryAnomalyPipeline()
    anomalies_with_future = pipeline_b.process_records(combined_records)

    cutoff_iso = (base_time + timedelta(seconds=14 * 60)).isoformat()
    past_window_anoms = [a for a in anomalies_with_future if a.start_timestamp <= cutoff_iso]

    assert len(past_window_anoms) == len(anomalies_past_only)
    for a_past, a_comb in zip(anomalies_past_only, past_window_anoms):
        assert a_past.anomaly_id == a_comb.anomaly_id
        assert a_past.anomaly_score == a_comb.anomaly_score
```

**Outcome:** Passed (100% deterministic invariance). Predictions at $t < 15$ remain identical regardless of subsequent spikes.

---

## 5. Missing Data & Visual Interpolation Safeguards

A major hazard in operations monitoring is the "continuous line illusion," where missing data points are silently connected by a smooth line, misleading engineers into believing physical monitoring was continuous.

### Safeguards Implemented in `TelemetryExplorerCard.tsx`:
1. **Discontinuous Segment Rendering:** Rather than rendering a single unbroken `<path>`, the chart splits the series into discrete `<line>` segments:
   - **Observed Physical Segments:** Rendered with solid sky-blue lines (`#38bdf8`, width 2px).
   - **Imputed / Missing Intervals:** Rendered with **dashed amber lines** (`#f59e0b`, `strokeDasharray="4 3"`, width 1.5px).
2. **Point Markers:** Imputed points are rendered as dashed hollow rings (`strokeDasharray="2 1"`) with explicit hover titles: `[IMPUTED / MISSING] value @ timestamp`.
3. **Missing Telemetry Warning Banner:** Displayed automatically whenever `activeSeries.is_imputed.some(Boolean)`:
   > **Missing Telemetry Notice:** Dashed amber segments denote forward-imputed values. Physical observations were unrecorded for those intervals.
4. **Warm-Up Notice:** When fewer than 10 samples exist in the window:
   > **Insufficient Warm-Up:** Current series has N observations (< 10 required for calibrated statistical envelopes).

---

## 6. Audit Verdict

| Telemetry Dimension | Verification Standard | Implementation Status | Verdict |
| :--- | :--- | :--- | :--- |
| **Sample Provenance** | Ingested via standard adapters | In-memory buffer preserved | **PASS** |
| **Temporal Causality** | No future-to-past leakage | Demonstrated via mutation test | **PASS** |
| **Denoising Direction** | Causal rolling operations only | `center=False`, forward-fill only | **PASS** |
| **Visual Gaps** | No continuous illusion across gaps | Dashed amber lines for imputed data | **PASS** |
| **Warm-up Handling** | Explicit insufficient data notice | Banner displayed for $N < 10$ | **PASS** |
| **Epistemic Label** | Raw=Fact, Anomaly=Model Prediction | Badges cleanly separated | **PASS** |
