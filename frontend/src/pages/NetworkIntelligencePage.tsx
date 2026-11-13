import React, { useState } from 'react'
import { Network, RefreshCw, Radio, Link2 } from 'lucide-react'
import { useIncidentContextStore } from '../store/incidentContextStore'
import {
  useNetworkOverviewQuery,
  useNetworkTopologyQuery,
  useNetworkImpactQuery,
  useNetworkAlarmsQuery,
  useNetworkTelemetryQuery,
  useIncidentDetailQuery,
} from '../api/queries'
import { NetworkOverviewCard } from '../components/network/NetworkOverviewCard'
import { NetworkTopologyExplorer } from '../components/network/NetworkTopologyExplorer'
import { NetworkImpactCard } from '../components/network/NetworkImpactCard'
import { AlarmIntelligenceCard } from '../components/network/AlarmIntelligenceCard'
import { TelemetryExplorerCard } from '../components/network/TelemetryExplorerCard'

export const NetworkIntelligencePage: React.FC = () => {
  const { selectedIncidentId } = useIncidentContextStore()
  const { data: incidentDetail } = useIncidentDetailQuery(selectedIncidentId)

  // Selected element for detailed inspection & impact (prefers operator manual selection, falls back to active incident element)
  const [manualSelectedElementId, setManualSelectedElementId] = useState<string | null>(null)
  const incidentElementId = incidentDetail?.network_element_ids?.[0] ?? incidentDetail?.network_element_id ?? null
  const selectedElementId = manualSelectedElementId ?? incidentElementId

  // Queries
  const {
    data: overview,
    isLoading: isOverviewLoading,
    refetch: refetchOverview,
  } = useNetworkOverviewQuery(20_000)

  const {
    data: topology,
    isLoading: isTopologyLoading,
    refetch: refetchTopology,
  } = useNetworkTopologyQuery()

  const {
    data: impact,
    isLoading: isImpactLoading,
    refetch: refetchImpact,
  } = useNetworkImpactQuery(
    {
      element_id: selectedElementId || undefined,
      incident_id: !selectedElementId && selectedIncidentId ? selectedIncidentId : undefined,
    },
    Boolean(selectedElementId || selectedIncidentId)
  )

  const {
    data: alarmsData,
    isLoading: isAlarmsLoading,
    refetch: refetchAlarms,
  } = useNetworkAlarmsQuery()

  const {
    data: telemetryData,
    isLoading: isTelemetryLoading,
    refetch: refetchTelemetry,
  } = useNetworkTelemetryQuery({
    element_id: selectedElementId,
  })

  const handleRefreshAll = () => {
    refetchOverview()
    refetchTopology()
    refetchImpact()
    refetchAlarms()
    if (selectedElementId) refetchTelemetry()
  }

  const handleAnalyzeImpact = (elementId: string) => {
    setManualSelectedElementId(elementId)
    // Scroll to impact card smoothly
    const elem = document.getElementById('network-impact-section')
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Network className="w-5 h-5 text-[var(--text-primary)]" />
            <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
              Network Intelligence Workspace
            </h1>
          </div>
          <p className="text-xs text-[var(--text-muted)]">
            Multi-domain network topology, blast radius analysis, and telemetry stream correlation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {selectedIncidentId && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-primary)]">
              <Link2 className="w-3.5 h-3.5" />
              <span>Context: {selectedIncidentId}</span>
            </div>
          )}

          <button
            onClick={handleRefreshAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-semibold bg-[var(--bg-subtle)] border border-[var(--border-subtle)] hover:bg-[var(--border-subtle)] text-[var(--text-primary)] transition-colors font-mono cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh State</span>
          </button>
        </div>
      </div>

      {/* 1. Network Observability Overview */}
      <NetworkOverviewCard overview={overview} isLoading={isOverviewLoading} />

      {/* 2. Interactive Topology Graph Explorer */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
            <Radio className="w-4 h-4 text-[var(--text-muted)]" />
            <span>Topological Adjacency & Directed Service Hierarchy</span>
          </h2>
        </div>

        <NetworkTopologyExplorer
          topology={topology}
          isLoading={isTopologyLoading}
          selectedElementId={selectedElementId}
          onSelectElement={setManualSelectedElementId}
          onAnalyzeImpact={handleAnalyzeImpact}
        />
      </div>

      {/* 3. Deep Analysis Section: Impact Assessment & Telemetry Stream */}
      <div id="network-impact-section" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Blast Radius & Risk Assessment */}
        <NetworkImpactCard
          impact={impact}
          isLoading={isImpactLoading}
          targetElement={selectedElementId}
          onSelectElement={setManualSelectedElementId}
        />

        {/* Telemetry Time-Series & Anomaly Stream */}
        <TelemetryExplorerCard
          telemetryData={telemetryData}
          isLoading={isTelemetryLoading}
          selectedElementId={selectedElementId}
        />
      </div>

      {/* 4. Alarm Intelligence & Correlation Clusters */}
      <AlarmIntelligenceCard
        alarmsData={alarmsData}
        isLoading={isAlarmsLoading}
        selectedElementId={selectedElementId}
        onSelectElement={setManualSelectedElementId}
      />
    </div>
  )
}
