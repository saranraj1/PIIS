import React from 'react'
import { Server, ShieldCheck, Activity, AlertTriangle, Layers, GitFork } from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'
import type { NetworkOverviewResponse } from '../../api/types'

interface NetworkOverviewCardProps {
  overview?: NetworkOverviewResponse
  isLoading: boolean
}

export const NetworkOverviewCard: React.FC<NetworkOverviewCardProps> = ({
  overview,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4" />
        ))}
      </div>
    )
  }

  const totalElements = overview?.total_elements ?? 0
  const activeAlarms = overview?.active_alarms_count ?? 0
  const correlatedClusters = overview?.correlated_clusters_count ?? 0
  const activeAnomalies = overview?.active_anomalies_count ?? 0
  const totalLinks = overview?.total_links ?? 0
  const syncTime = overview?.last_sync_timestamp
    ? new Date(overview.last_sync_timestamp).toLocaleTimeString()
    : 'Unknown'

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Monitored Elements */}
        <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Registered Topology Elements</span>
            <Server className="w-4 h-4 text-[var(--text-muted)]" />
          </div>
          <div className="mt-2 text-2xl font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {totalElements}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <EpistemicBadge category="REFERENCE_DATA" size="sm" />
              <span className="text-xs text-[var(--text-muted)] font-mono">{totalLinks} Directed Links</span>
            </div>
            <span className="text-xs font-mono tabular-nums text-[var(--text-muted)]">Sync: {syncTime}</span>
          </div>
        </div>

        {/* Active Alarms */}
        <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Active Network Alarms</span>
            <AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />
          </div>
          <div className="mt-2 text-2xl font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {activeAlarms}
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <EpistemicBadge category="OBSERVED_FACT" size="sm" />
            <span className="text-xs text-[var(--text-muted)]">
              {activeAlarms === 0 ? 'Zero active faults' : 'OSS/NMS ingested stream'}
            </span>
          </div>
        </div>

        {/* Correlated Clusters */}
        <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Correlated Incident Clusters</span>
            <GitFork className="w-4 h-4 text-[var(--text-muted)]" />
          </div>
          <div className="mt-2 text-2xl font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {correlatedClusters}
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <EpistemicBadge category="HYPOTHESIS" size="sm" />
            <span className="text-xs text-[var(--text-muted)]">Temporal-topological affinity</span>
          </div>
        </div>

        {/* Active Anomalies */}
        <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Telemetry Stream Violations</span>
            <Activity className="w-4 h-4 text-[var(--text-muted)]" />
          </div>
          <div className="mt-2 text-2xl font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {activeAnomalies}
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
            <span className="text-xs text-[var(--text-muted)]">k-sigma + Isolation Forest</span>
          </div>
        </div>
      </div>

      {/* Domain Breakdown Sub-bar */}
      {overview?.elements_by_domain && (
        <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex items-center justify-between text-xs flex-wrap gap-2">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Layers className="w-3.5 h-3.5 text-zinc-400" />
            <span className="font-semibold text-[var(--text-primary)]">Domain Inventory:</span>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            {Object.entries(overview.elements_by_domain).map(([dom, count]) => (
              <div key={dom} className="flex items-center gap-1 font-mono text-xs">
                <span className="text-[var(--text-muted)]">{dom}:</span>
                <span className="font-bold text-[var(--text-primary)]">{count}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-500 font-mono">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Read-Only Boundary Enforced</span>
          </div>
        </div>
      )}
    </div>
  )
}
