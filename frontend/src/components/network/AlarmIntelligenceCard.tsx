import React, { useState } from 'react'
import { AlertTriangle, GitFork, Filter, CheckCircle2 } from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'
import { SeverityBadge } from '../common/SeverityBadge'
import { DomainBadge } from '../common/DomainBadge'
import type { NetworkAlarmsResponse } from '../../api/types'

interface AlarmIntelligenceCardProps {
  alarmsData?: NetworkAlarmsResponse
  isLoading: boolean
  selectedElementId: string | null
  onSelectElement?: (elementId: string) => void
}

export const AlarmIntelligenceCard: React.FC<AlarmIntelligenceCardProps> = ({
  alarmsData,
  isLoading,
  selectedElementId,
  onSelectElement,
}) => {
  const [activeTab, setActiveTab] = useState<'CLUSTERS' | 'RAW_ALARMS'>('CLUSTERS')
  const [domainFilter, setDomainFilter] = useState<string>('ALL')
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')

  if (isLoading) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 animate-pulse space-y-4">
        <div className="h-6 w-48 bg-[var(--bg-card)] rounded-xs" />
        <div className="h-40 bg-[var(--bg-card)] rounded-xs" />
      </div>
    )
  }

  const clusters = alarmsData?.clusters ?? []
  const allAlarms = alarmsData?.alarms ?? []

  // Filter alarms
  const filteredAlarms = allAlarms.filter((a) => {
    if (domainFilter !== 'ALL' && a.network_domain.toUpperCase() !== domainFilter.toUpperCase()) return false
    if (severityFilter !== 'ALL' && a.severity.toUpperCase() !== severityFilter.toUpperCase()) return false
    if (selectedElementId && a.network_element_id !== selectedElementId) return false
    return true
  })

  // Filter clusters
  const filteredClusters = clusters.filter((c) => {
    if (domainFilter !== 'ALL' && c.dominant_domain.toUpperCase() !== domainFilter.toUpperCase()) return false
    if (selectedElementId && !c.affected_elements.includes(selectedElementId)) return false
    return true
  })

  return (
    <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Alarm Intelligence & Causal Clusters
          </h3>
          {selectedElementId && (
            <span className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
              Filtered: {selectedElementId}
            </span>
          )}
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-2">
          <div className="flex border border-[var(--border-subtle)] rounded-xs bg-[var(--bg-card)] p-0.5 text-xs">
            <button
              onClick={() => setActiveTab('CLUSTERS')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-xs transition-colors cursor-pointer ${
                activeTab === 'CLUSTERS'
                  ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <GitFork className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <span>Clusters ({filteredClusters.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('RAW_ALARMS')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-xs transition-colors cursor-pointer ${
                activeTab === 'RAW_ALARMS'
                  ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <span>Alarms ({filteredAlarms.length})</span>
            </button>
          </div>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex items-center gap-2 text-xs flex-wrap">
        <Filter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        <span className="text-[var(--text-muted)] font-medium">Domain:</span>
        {['ALL', 'RAN', 'TRANSPORT', '5G_CORE', 'SERVICE'].map((d) => (
          <button
            key={d}
            onClick={() => setDomainFilter(d)}
            className={`px-2 py-0.5 rounded-xs text-xs font-mono transition-colors cursor-pointer ${
              domainFilter === d
                ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
                : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
            }`}
          >
            {d}
          </button>
        ))}

        <span className="text-[var(--text-muted)] ml-2 font-medium">Severity:</span>
        {['ALL', 'CRITICAL', 'MAJOR', 'MINOR'].map((s) => (
          <button
            key={s}
            onClick={() => setSeverityFilter(s)}
            className={`px-2 py-0.5 rounded-xs text-xs font-mono transition-colors cursor-pointer ${
              severityFilter === s
                ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
                : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Main Tab Content */}
      {activeTab === 'CLUSTERS' ? (
        <div className="space-y-3">
          {filteredClusters.length === 0 ? (
            <div className="p-6 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-muted)] space-y-1">
              <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto" />
              <div className="font-semibold text-[var(--text-primary)]">No Correlated Incident Clusters</div>
              <div>No multi-event temporal or topological correlations detected for current filters.</div>
            </div>
          ) : (
            filteredClusters.map((cluster) => (
              <div
                key={cluster.cluster_id}
                className="p-4 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-3"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <GitFork className="w-4 h-4 text-[var(--text-muted)]" />
                    <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                      {cluster.cluster_id}
                    </span>
                    <DomainBadge domain={cluster.dominant_domain} size="sm" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-[var(--text-muted)]">
                      {cluster.event_count} Events
                    </span>
                    <span
                      title="Calculated composite affinity score based on temporal delta, topological hops, and domain coupling. Not a calibrated probability."
                      className="text-xs font-mono font-medium text-[var(--text-primary)]"
                    >
                      {(cluster.mean_confidence * 100).toFixed(0)}% Affinity Proxy
                    </span>
                    <EpistemicBadge category="HYPOTHESIS" size="sm" />
                  </div>
                </div>

                {/* Affected Elements */}
                <div className="flex items-center gap-2 text-xs flex-wrap">
                  <span className="text-[var(--text-muted)]">Affected Nodes:</span>
                  {cluster.affected_elements.map((el) => (
                    <button
                      key={el}
                      onClick={() => onSelectElement?.(el)}
                      className="px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] hover:border-[var(--text-primary)] cursor-pointer"
                    >
                      {el}
                    </button>
                  ))}
                </div>

                {/* Rationales */}
                <div className="space-y-1 text-xs">
                  <span className="text-[var(--text-muted)] font-medium">Correlation Rationales:</span>
                  <ul className="space-y-1">
                    {cluster.rationales.map((r, idx) => (
                      <li
                        key={idx}
                        className="text-xs text-[var(--text-muted)] bg-[var(--bg-surface)] p-2 rounded-xs border border-[var(--border-subtle)] font-mono"
                      >
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Raw Alarms Table */
        <div className="overflow-x-auto">
          {filteredAlarms.length === 0 ? (
            <div className="p-6 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-muted)] space-y-1">
              <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto" />
              <div className="font-semibold text-[var(--text-primary)]">No Active Alarms</div>
              <div>All network elements matching current filters are operating within normal thresholds.</div>
            </div>
          ) : (
            <table className="w-full text-left text-xs border border-[var(--border-subtle)] rounded-xs">
              <thead className="bg-[var(--bg-card)] text-[var(--text-muted)] border-b border-[var(--border-subtle)] font-mono uppercase text-xs">
                <tr>
                  <th className="p-2.5">Severity</th>
                  <th className="p-2.5">Element</th>
                  <th className="p-2.5">Alarm Code</th>
                  <th className="p-2.5">Probable Cause</th>
                  <th className="p-2.5">Domain</th>
                  <th className="p-2.5">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] font-mono">
                {filteredAlarms.map((alarm) => (
                  <tr key={alarm.alarm_id} className="hover:bg-[var(--bg-card)] transition-colors">
                    <td className="p-2.5">
                      <SeverityBadge severity={alarm.severity} size="sm" />
                    </td>
                    <td className="p-2.5">
                      <button
                        onClick={() => onSelectElement?.(alarm.network_element_id)}
                        className="text-[var(--text-primary)] font-medium hover:underline cursor-pointer"
                      >
                        {alarm.network_element_id}
                      </button>
                    </td>
                    <td className="p-2.5 font-bold text-[var(--text-primary)]">{alarm.alarm_code}</td>
                    <td className="p-2.5 text-[var(--text-muted)] font-sans max-w-xs truncate">
                      {alarm.probable_cause || '—'}
                    </td>
                    <td className="p-2.5">
                      <DomainBadge domain={alarm.network_domain} size="sm" />
                    </td>
                    <td className="p-2.5 text-[var(--text-muted)] text-xs">
                      {new Date(alarm.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
