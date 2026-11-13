import React, { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BrainCircuit,
  FileText,
  FileCheck2,
  Clock,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import {
  useIncidentsQuery,
  useIncidentDetailQuery,
  useInvestigationQuery,
  useInvestigationEvidenceQuery,
  useInvestigationHypothesesQuery,
  useInvestigationRecommendationsQuery,
  useTriggerInvestigationMutation,
} from '../api/queries'
import { useIncidentContextStore } from '../store/incidentContextStore'
import { ApiClientError } from '../api/client'
import { IncidentContextHeader } from '../components/investigation/IncidentContextHeader'
import { SufficiencyAlertBanner } from '../components/investigation/SufficiencyAlertBanner'
import { HypothesisAnalysisCard } from '../components/investigation/HypothesisAnalysisCard'
import { EvidenceRegisterCard } from '../components/investigation/EvidenceRegisterCard'
import { RecommendationCard } from '../components/investigation/RecommendationCard'
import { InvestigationTimeline } from '../components/investigation/InvestigationTimeline'
import { ErrorState } from '../components/common/ErrorState'
import { EmptyState } from '../components/common/EmptyState'

export type ActiveTab = 'hypotheses' | 'evidence' | 'recommendations' | 'timeline'

export const InvestigationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const { selectedIncidentId, setSelectedIncidentId } = useIncidentContextStore()

  const [activeTab, setActiveTab] = useState<ActiveTab>('hypotheses')
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null)

  // 1. Fetch available incidents to allow switching and default selection
  const { data: incidentList, isLoading: listLoading } = useIncidentsQuery({ limit: 50 })
  const availableIncidents = useMemo(() => incidentList?.items || [], [incidentList?.items])

  // 2. Determine target incident ID: search param > store > first available incident
  const paramId = searchParams.get('id')
  const activeIncidentId =
    paramId || selectedIncidentId || (availableIncidents.length > 0 ? availableIncidents[0].incident_id : null)

  // 3. Primary Investigation Queries
  const {
    data: detailData,
    isLoading: detailLoading,
    isError: detailError,
    error: detailErr,
    refetch: refetchDetail,
  } = useIncidentDetailQuery(activeIncidentId)

  // Synchronize store and URL search params when active ID resolves
  useEffect(() => {
    if (activeIncidentId && activeIncidentId !== selectedIncidentId) {
      setSelectedIncidentId(activeIncidentId)
    }
    if (activeIncidentId && paramId !== activeIncidentId) {
      setSearchParams({ id: activeIncidentId }, { replace: true })
    }
  }, [activeIncidentId, selectedIncidentId, paramId, setSelectedIncidentId, setSearchParams])

  // Automatic recovery: If current incident 404s but other incidents exist, auto-select first available incident
  useEffect(() => {
    if (detailError && availableIncidents.length > 0) {
      const fallbackId = availableIncidents[0].incident_id
      if (fallbackId && fallbackId !== activeIncidentId) {
        setSelectedIncidentId(fallbackId)
        setSearchParams({ id: fallbackId }, { replace: true })
      }
    }
  }, [detailError, availableIncidents, activeIncidentId, setSelectedIncidentId, setSearchParams])

  const {
    data: investigationData,
    isLoading: invLoading,
    isError: invError,
    error: invErr,
    refetch: refetchInv,
  } = useInvestigationQuery(activeIncidentId)

  const {
    data: evidenceData,
    isLoading: evLoading,
    error: evErr,
    refetch: refetchEvidence,
  } = useInvestigationEvidenceQuery(activeIncidentId)

  const {
    data: hypothesesData,
    isLoading: hypLoading,
    refetch: refetchHypotheses,
  } = useInvestigationHypothesesQuery(activeIncidentId)

  const {
    data: recsData,
    isLoading: recsLoading,
    refetch: refetchRecs,
  } = useInvestigationRecommendationsQuery(activeIncidentId)

  // 4. Manual trigger mutation (POST /api/v1/incidents/{id}/investigate)
  const triggerInvestigationMutation = useTriggerInvestigationMutation()

  // Combined Loading & Error States
  const isPrimaryLoading = detailLoading || invLoading || evLoading || hypLoading || recsLoading
  const isIncidentNotFound =
    detailError && detailErr instanceof ApiClientError && detailErr.status === 404
  const isUngeneratedState =
    !isIncidentNotFound && invError && invErr instanceof ApiClientError && invErr.status === 404

  const hasCriticalError =
    detailError ||
    (invError && !isUngeneratedState)

  const primaryError = detailErr || invErr || evErr

  const handleRefreshAll = () => {
    refetchDetail()
    refetchInv()
    refetchEvidence()
    refetchHypotheses()
    refetchRecs()
  }

  const handleTriggerInvestigation = () => {
    if (activeIncidentId) {
      triggerInvestigationMutation.mutate(activeIncidentId)
    }
  }

  // Handle switching to evidence from hypothesis link
  const handleSelectEvidence = (evidenceId: string) => {
    setHighlightedEvidenceId(evidenceId)
    setActiveTab('evidence')
    // Smooth scroll to evidence item
    setTimeout(() => {
      const el = document.getElementById(`evidence-${evidenceId}`)
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 100)
  }

  // Derive consolidated arrays
  const incident = detailData?.incident || null
  const lineage = detailData?.lineage || null
  const evidenceItems = Array.isArray(evidenceData) ? evidenceData : []
  const hypotheses = Array.isArray(hypothesesData)
    ? hypothesesData
    : Array.isArray(investigationData?.hypotheses)
    ? investigationData.hypotheses
    : []
  const recommendations = Array.isArray(recsData)
    ? recsData
    : Array.isArray(investigationData?.recommendations)
    ? investigationData.recommendations
    : []

  // If no incidents exist at all in system
  if (!activeIncidentId && !listLoading) {
    return (
      <div className="p-8">
        <EmptyState
          title="No Incident Selected for Investigation"
          description="Select an incident from the catalog or ingest new events through the ITSM adapters to launch investigation."
          actionLabel="Go to Incident Explorer"
          onAction={() => (window.location.href = '/incidents')}
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* 1. Incident Context Header */}
      <IncidentContextHeader
        incident={incident}
        lineage={lineage}
        availableIncidents={availableIncidents}
        onSelectIncident={(id) => {
          setSelectedIncidentId(id)
          setSearchParams({ id }, { replace: true })
          setHighlightedEvidenceId(null)
        }}
        onRefresh={handleRefreshAll}
        isLoading={isPrimaryLoading}
      />

      {/* Primary Error State */}
      {isIncidentNotFound ? (
        <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 transition-colors">
          <ErrorState
            error={primaryError}
            onRetry={handleRefreshAll}
            title="Incident Not Found"
            endpointName={`/api/v1/incidents/${activeIncidentId}`}
            actionLabel={availableIncidents.length > 0 ? `Switch to ${availableIncidents[0].incident_id}` : 'View Incidents'}
            onAction={() => {
              if (availableIncidents.length > 0) {
                const fallbackId = availableIncidents[0].incident_id
                setSelectedIncidentId(fallbackId)
                setSearchParams({ id: fallbackId }, { replace: true })
              } else {
                window.location.href = '/incidents'
              }
            }}
          />
        </div>
      ) : hasCriticalError ? (
        <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 transition-colors">
          <ErrorState
            error={primaryError}
            onRetry={handleRefreshAll}
            title="Failed to Load Investigation Context"
            endpointName={`/api/v1/incidents/${activeIncidentId}/investigation`}
          />
        </div>
      ) : isUngeneratedState ? (
        <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-8 transition-colors">
          <div className="max-w-2xl mx-auto text-center space-y-4">
            <div className="w-12 h-12 rounded-xs bg-zinc-500/10 text-[var(--text-primary)] flex items-center justify-center mx-auto border border-[var(--border-subtle)]">
              <BrainCircuit className="w-6 h-6" />
            </div>
            <div>
              <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
                Status: Not Initiated
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                Investigation Not Yet Generated
              </h3>
              <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">
                Diagnostic correlation has not yet been executed for this incident ({activeIncidentId}). In accordance with read-only operational boundaries, diagnostic pipelines require explicit operator invocation.
              </p>
            </div>

            {triggerInvestigationMutation.isError && (
              <div className="p-3 text-xs bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 rounded-xs font-mono text-left">
                Failed to trigger investigation: {triggerInvestigationMutation.error?.message}
              </div>
            )}

            <div className="pt-2 flex justify-center gap-3">
              <button
                type="button"
                onClick={handleTriggerInvestigation}
                disabled={triggerInvestigationMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xs bg-[var(--text-primary)] hover:opacity-90 text-[var(--bg-surface)] font-medium text-xs font-mono transition-opacity disabled:opacity-50 cursor-pointer"
              >
                {triggerInvestigationMutation.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Executing Investigation Pipeline...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Trigger Investigation</span>
                  </>
                )}
              </button>
            </div>

            <div className="text-xs text-[var(--text-muted)] font-mono">
              Strict Lifecycle Guard: Pure GET requests will not trigger automated background investigations.
            </div>
          </div>
        </div>
      ) : isPrimaryLoading && !incident ? (
        <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-12 text-center text-xs text-[var(--text-muted)] flex flex-col items-center justify-center gap-2 font-mono transition-colors">
          <RefreshCw className="w-6 h-6 animate-spin text-[var(--text-primary)]" />
          <span>Synthesizing evidence register and executing diagnostic investigation engine...</span>
        </div>
      ) : (
        <>
          {/* 2. Evidence Sufficiency & Stale Signals Alert Banner */}
          {investigationData && (
            <SufficiencyAlertBanner
              isSufficient={investigationData.is_sufficient}
              isTransientEvent={investigationData.is_transient_event}
              missingEvidence={investigationData.missing_evidence}
              contradictions={investigationData.contradictions}
              staleEvidence={investigationData.stale_evidence}
            />
          )}

          {/* 3. Section Navigation Tabs */}
          <div className="border-b border-[var(--border-subtle)] flex flex-wrap items-center gap-2 text-xs font-mono">
            <button
              onClick={() => setActiveTab('hypotheses')}
              className={`inline-flex items-center gap-2 px-4 py-2.5 font-bold border-b-2 transition-colors ${
                activeTab === 'hypotheses'
                  ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]'
              }`}
            >
              <BrainCircuit className="w-4 h-4" />
              <span>Hypothesis Analysis</span>
              <span className="px-1.5 py-0.5 rounded-xs text-xs tabular-nums bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                {hypotheses.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('evidence')}
              className={`inline-flex items-center gap-2 px-4 py-2.5 font-bold border-b-2 transition-colors ${
                activeTab === 'evidence'
                  ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Evidence Register</span>
              <span className="px-1.5 py-0.5 rounded-xs text-xs tabular-nums bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                {evidenceItems.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('recommendations')}
              className={`inline-flex items-center gap-2 px-4 py-2.5 font-bold border-b-2 transition-colors ${
                activeTab === 'recommendations'
                  ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]'
              }`}
            >
              <FileCheck2 className="w-4 h-4" />
              <span>Recommendations & Approval</span>
              <span className="px-1.5 py-0.5 rounded-xs text-xs tabular-nums bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                {recommendations.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('timeline')}
              className={`inline-flex items-center gap-2 px-4 py-2.5 font-bold border-b-2 transition-colors ${
                activeTab === 'timeline'
                  ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]'
              }`}
            >
              <Clock className="w-4 h-4" />
              <span>Investigation Timeline</span>
            </button>
          </div>

          {/* 4. Active Tab Content Panel */}
          <div className="pt-2">
            {activeTab === 'hypotheses' && (
              <HypothesisAnalysisCard
                hypotheses={hypotheses}
                onSelectEvidence={handleSelectEvidence}
              />
            )}

            {activeTab === 'evidence' && (
              <EvidenceRegisterCard
                evidenceItems={evidenceItems}
                highlightedEvidenceId={highlightedEvidenceId}
              />
            )}

            {activeTab === 'recommendations' && (
              <RecommendationCard
                recommendations={recommendations}
                incidentId={activeIncidentId || ''}
                onSelectEvidence={handleSelectEvidence}
              />
            )}

            {activeTab === 'timeline' && (
              <InvestigationTimeline
                incident={incident}
                lineage={lineage}
                investigation={investigationData || null}
                evidenceItems={evidenceItems}
                recommendations={recommendations}
              />
            )}
          </div>
        </>
      )}
    </div>
  )
}
