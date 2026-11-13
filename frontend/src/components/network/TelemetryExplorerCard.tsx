import React, { useState, useMemo } from 'react'
import { Activity, AlertCircle, CheckCircle2, BarChart2 } from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'
import { SeverityBadge } from '../common/SeverityBadge'
import { EmptyState } from '../common/EmptyState'
import type { NetworkTelemetryResponse } from '../../api/types'

const CHART_WIDTH = 700
const CHART_HEIGHT = 220
const PADDING = { top: 20, right: 30, bottom: 35, left: 45 }

interface TelemetryExplorerCardProps {
  telemetryData?: NetworkTelemetryResponse
  isLoading: boolean
  selectedElementId: string | null
}

export const TelemetryExplorerCard: React.FC<TelemetryExplorerCardProps> = ({
  telemetryData,
  isLoading,
  selectedElementId,
}) => {
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)

  const series = useMemo(() => telemetryData?.series ?? [], [telemetryData?.series])
  const anomalies = telemetryData?.anomalies ?? []

  // Default active metric
  const activeMetricName = selectedMetric || (series.length > 0 ? series[0].metric_name : null)
  const activeSeries = useMemo(() => {
    return series.find((s) => s.metric_name === activeMetricName) ?? (series.length > 0 ? series[0] : null)
  }, [series, activeMetricName])

  // Chart coordinate mapping
  const chartData = useMemo(() => {
    if (!activeSeries || activeSeries.values.length === 0) return null

    const vals = activeSeries.values
    const minVal = Math.min(0, ...vals)
    const maxVal = Math.max(100, ...vals.map((v) => v * 1.15))
    const valRange = maxVal - minVal || 1

    const widthAvail = CHART_WIDTH - PADDING.left - PADDING.right
    const heightAvail = CHART_HEIGHT - PADDING.top - PADDING.bottom

    const stepX = widthAvail / Math.max(1, vals.length - 1)

    const points = vals.map((v, idx) => ({
      x: PADDING.left + idx * stepX,
      y: PADDING.top + heightAvail - ((v - minVal) / valRange) * heightAvail,
      val: v,
      timestamp: activeSeries.timestamps[idx] || '',
      isImputed: activeSeries.is_imputed[idx] || false,
    }))

    // Build line segments: solid for physical observed, dashed amber for imputed
    const segments: Array<{ x1: number; y1: number; x2: number; y2: number; isImputed: boolean }> = []
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1]
      const curr = points[i]
      segments.push({
        x1: prev.x,
        y1: prev.y,
        x2: curr.x,
        y2: curr.y,
        isImputed: prev.isImputed || curr.isImputed,
      })
    }

    // Dynamic Upper Threshold (e.g. mean + 2*sigma)
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length
    const std = Math.sqrt(vals.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / vals.length) || 5
    const thresholdVal = Math.min(maxVal, mean + 2.0 * std)
    const thresholdY = PADDING.top + heightAvail - ((thresholdVal - minVal) / valRange) * heightAvail

    return { points, segments, minVal, maxVal, thresholdVal, thresholdY }
  }, [activeSeries])

  if (isLoading) {
    return (
      <div className="rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 animate-pulse space-y-4">
        <div className="h-6 w-48 bg-[var(--bg-card)] rounded-md" />
        <div className="h-48 bg-[var(--bg-card)] rounded-md" />
      </div>
    )
  }

  if (!selectedElementId) {
    return (
      <div className="rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 text-center space-y-2">
        <BarChart2 className="w-8 h-8 text-[var(--text-muted)] mx-auto opacity-50" />
        <h4 className="text-sm font-semibold text-[var(--text-primary)]">Telemetry Explorer Standby</h4>
        <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
          Select any network element from the topology graph to inspect its telemetry time-series and ML anomaly bounds.
        </p>
      </div>
    )
  }

  if (series.length === 0) {
    return (
      <div className="rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6">
        <EmptyState
          title={`No Telemetry Ingested for ${selectedElementId}`}
          description="Prometheus or gNMI telemetry stream has not yet reported observations for this element in the current window."
        />
      </div>
    )
  }

  return (
    <div className="rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--text-muted)]" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Telemetry Time-Series & Anomaly Stream
          </h3>
          <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
            {selectedElementId}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <EpistemicBadge category="OBSERVED_FACT" size="sm" />
          {anomalies.length > 0 && <EpistemicBadge category="MODEL_PREDICTION" size="sm" />}
        </div>
      </div>

      {/* Metric Selector Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2 overflow-x-auto">
        <span className="text-xs text-[var(--text-muted)] mr-1">Metrics:</span>
        {series.map((s) => (
          <button
            key={s.metric_name}
            onClick={() => setSelectedMetric(s.metric_name)}
            className={`px-3 py-1 rounded-xs text-xs font-mono transition-colors cursor-pointer ${
              activeSeries?.metric_name === s.metric_name
                ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-bold'
                : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
            }`}
          >
            {s.metric_name} ({s.unit || 'val'})
          </button>
        ))}
      </div>

      {/* SVG Time-Series Chart */}
      {chartData && (
        <div className="p-3 rounded-lg bg-[var(--bg-page)] border border-[var(--border-subtle)] overflow-x-auto">
          <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="w-full h-48 select-none">
            {/* Grid Lines */}
            <line
              x1={PADDING.left}
              y1={PADDING.top}
              x2={CHART_WIDTH - PADDING.right}
              y2={PADDING.top}
              stroke="var(--border-subtle)"
              strokeDasharray="2 2"
              opacity="0.4"
            />
            <line
              x1={PADDING.left}
              y1={CHART_HEIGHT - PADDING.bottom}
              x2={CHART_WIDTH - PADDING.right}
              y2={CHART_HEIGHT - PADDING.bottom}
              stroke="var(--border-subtle)"
              strokeDasharray="2 2"
              opacity="0.6"
            />

            {/* Threshold Line (Dynamic k-sigma) */}
            <line
              x1={PADDING.left}
              y1={chartData.thresholdY}
              x2={CHART_WIDTH - PADDING.right}
              y2={chartData.thresholdY}
              stroke="#ef4444"
              strokeDasharray="4 3"
              strokeWidth="1.5"
            />
            <text
              x={CHART_WIDTH - PADDING.right - 4}
              y={chartData.thresholdY - 4}
              textAnchor="end"
              fill="#ef4444"
              fontSize="9"
              fontFamily="monospace"
              fontWeight="bold"
            >
              Threshold ({chartData.thresholdVal.toFixed(1)})
            </text>

            {/* Metric Polyline Segments: Solid Sky Blue for physical observed, Dashed Amber for imputed */}
            {chartData.segments.map((seg, idx) => (
              <line
                key={idx}
                x1={seg.x1}
                y1={seg.y1}
                x2={seg.x2}
                y2={seg.y2}
                stroke={seg.isImputed ? '#f59e0b' : '#38bdf8'}
                strokeWidth={seg.isImputed ? 1.5 : 2}
                strokeDasharray={seg.isImputed ? '4 3' : undefined}
                strokeLinecap="round"
              />
            ))}

            {/* Data Points */}
            {chartData.points.map((pt, idx) => {
              const isAnomaly = pt.val >= chartData.thresholdVal
              return (
                <g key={idx}>
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={isAnomaly ? 5 : pt.isImputed ? 4 : 3}
                    fill={isAnomaly ? '#ef4444' : pt.isImputed ? '#f59e0b33' : '#38bdf8'}
                    stroke={isAnomaly ? '#ffffff' : pt.isImputed ? '#f59e0b' : 'none'}
                    strokeWidth={isAnomaly ? 1.5 : pt.isImputed ? 1.5 : 0}
                    strokeDasharray={pt.isImputed ? '2 1' : undefined}
                    className="hover:r-6 transition-all"
                  >
                    <title>
                      {`${pt.isImputed ? '[IMPUTED / MISSING] ' : ''}${pt.val.toFixed(1)} ${activeSeries?.unit} @ ${
                        pt.timestamp ? new Date(pt.timestamp).toLocaleTimeString() : 'now'
                      }${isAnomaly ? ' (ANOMALY BREACH)' : ''}`}
                    </title>
                  </circle>
                  {/* Bottom Timestamp labels for first and last */}
                  {(idx === 0 || idx === chartData.points.length - 1) && (
                    <text
                      x={pt.x}
                      y={CHART_HEIGHT - 12}
                      textAnchor={idx === 0 ? 'start' : 'end'}
                      fill="var(--text-muted)"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      {pt.timestamp ? new Date(pt.timestamp).toLocaleTimeString() : ''}
                    </text>
                  )}
                </g>
              )
            })}

            {/* Y Axis Max & Min labels */}
            <text
              x={PADDING.left - 6}
              y={PADDING.top + 10}
              textAnchor="end"
              fill="var(--text-muted)"
              fontSize="9"
              fontFamily="monospace"
            >
              {chartData.maxVal.toFixed(0)}
            </text>
            <text
              x={PADDING.left - 6}
              y={CHART_HEIGHT - PADDING.bottom}
              textAnchor="end"
              fill="var(--text-muted)"
              fontSize="9"
              fontFamily="monospace"
            >
              {chartData.minVal.toFixed(0)}
            </text>
          </svg>
        </div>
      )}

      {/* Imputed / Missing Telemetry Warning Banner */}
      {activeSeries?.is_imputed?.some(Boolean) && (
        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center gap-2 text-xs text-[var(--text-primary)] font-mono">
          <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
          <span>
            <strong>Missing Telemetry Notice:</strong> Dashed amber segments denote forward-imputed values. Physical observations were unrecorded for those intervals.
          </span>
        </div>
      )}

      {/* Insufficient Samples Warning Banner */}
      {activeSeries && activeSeries.values.length < 10 && (
        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center gap-2 text-xs text-[var(--text-muted)] font-mono">
          <AlertCircle className="w-4 h-4 text-zinc-400 shrink-0" />
          <span>
            <strong>Insufficient Warm-Up:</strong> Current series has {activeSeries.values.length} observations (&lt; 10 required for calibrated statistical envelopes).
          </span>
        </div>
      )}

      {/* Detected Anomalies List */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-medium text-[var(--text-muted)]">
          <span>Algorithmic Anomaly Detections ({anomalies.length}):</span>
          <span className="text-xs font-mono">k-sigma statistical + Isolation Forest</span>
        </div>

        {anomalies.length === 0 ? (
          <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center text-xs text-emerald-500 flex items-center justify-center gap-1.5 font-mono">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Nominal operational envelope — zero active anomaly breaches</span>
          </div>
        ) : (
          <div className="space-y-2">
            {anomalies.map((anom) => (
              <div
                key={anom.anomaly_id}
                className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-between text-xs flex-wrap gap-2"
              >
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-500" />
                  <div>
                    <span className="font-mono font-bold text-[var(--text-primary)]">{anom.metric_name}</span>
                    <span className="text-[var(--text-muted)] ml-2">
                      Observed: <strong className="text-[var(--text-primary)] font-mono">{anom.observed_value.toFixed(1)}</strong> (Threshold: {anom.threshold_value?.toFixed(1) || 'N/A'})
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <SeverityBadge severity={anom.severity} size="sm" />
                  <span className="font-mono text-xs text-[var(--text-primary)]">Score: {anom.score.toFixed(2)}</span>
                  <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
