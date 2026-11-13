import React, { useState } from 'react'
import {
  Clock,
  ArrowUpDown,
  Calendar,
} from 'lucide-react'
import type {
  CanonicalIncidentItem,
  InvestigationResponse,
  InvestigationEvidenceItem,
  DiagnosticRecommendationItem,
} from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

export interface InvestigationTimelineProps {
  incident: CanonicalIncidentItem | null
  lineage?: {
    observation_timestamp?: string | null
    ingested_at?: string | null
    source_system?: string | null
    envelope_id?: string | null
  } | null
  investigation: InvestigationResponse | null
  evidenceItems?: InvestigationEvidenceItem[]
  recommendations?: DiagnosticRecommendationItem[]
}

interface TimelineEvent {
  id: string
  timestamp: string
  title: string
  description: string
  sourceSystem: string
  type: 'OBSERVATION' | 'INGESTION' | 'EVIDENCE' | 'INVESTIGATION' | 'REVIEW' | 'RESOLUTION'
  epistemicCategory: 'OBSERVED_FACT' | 'MODEL_PREDICTION' | 'APPROVED_POLICY' | 'CORROBORATED_FINDING'
}

export const InvestigationTimeline: React.FC<InvestigationTimelineProps> = ({
  incident,
  lineage,
  investigation,
  evidenceItems = [],
  recommendations = [],
}) => {
  const [ascending, setAscending] = useState(true)

  // Construct real events strictly from backend data
  const events: TimelineEvent[] = []

  // 1. External Event Observation
  if (lineage?.observation_timestamp) {
    events.push({
      id: 'event-obs',
      timestamp: lineage.observation_timestamp,
      title: 'Telemetry / Alarm Event Observed',
      description: `Observed in source domain prior to ingestion. Originating ticket/record ID: ${incident?.source_record_id || 'N/A'}.`,
      sourceSystem: lineage.source_system || incident?.source_dataset || 'External NOC',
      type: 'OBSERVATION',
      epistemicCategory: 'OBSERVED_FACT',
    })
  }

  // 2. Incident Ingested into PIIS
  if (lineage?.ingested_at) {
    events.push({
      id: 'event-ingest',
      timestamp: lineage.ingested_at,
      title: 'Canonical Normalization & Envelope Validation',
      description: `Validated against schema and ingested via Unified Ingestion Pipeline. Envelope ID: ${lineage.envelope_id || 'ENV-UNKNOWN'}.`,
      sourceSystem: 'UnifiedIngestionPipeline',
      type: 'INGESTION',
      epistemicCategory: 'OBSERVED_FACT',
    })
  }

  // 3. Correlated Evidence Observations
  evidenceItems.forEach((ev) => {
    if (ev.observed_at) {
      events.push({
        id: `event-ev-${ev.evidence_id}`,
        timestamp: ev.observed_at,
        title: `Evidence Registered: ${ev.evidence_id}`,
        description: `${ev.content_summary} (Ref: ${ev.source_ref}).`,
        sourceSystem: ev.source_ref,
        type: 'EVIDENCE',
        epistemicCategory: ev.evidence_type.includes('ANOMALY') || ev.evidence_type.includes('ALARM')
          ? 'OBSERVED_FACT'
          : 'CORROBORATED_FINDING',
      })
    }
  })

  // 4. Investigation Context Generated
  if (investigation?.created_at) {
    events.push({
      id: 'event-inv-run',
      timestamp: investigation.created_at,
      title: 'Automated Multi-Source Investigation Executed',
      description: `Correlation and retrieval engine synthesized ${investigation.hypotheses_count} ranked hypotheses and ${investigation.recommendations.length} diagnostic checks.`,
      sourceSystem: 'IncidentInvestigationEngine',
      type: 'INVESTIGATION',
      epistemicCategory: 'MODEL_PREDICTION',
    })
  }

  // 5. Human Reviews Completed
  recommendations.forEach((rec) => {
    if (rec.review_timestamp && rec.reviewed_by) {
      events.push({
        id: `event-rec-${rec.recommendation_id}`,
        timestamp: rec.review_timestamp,
        title: `Human Review: ${rec.recommendation_id} (${rec.approval_status})`,
        description: `Operator '${rec.reviewed_by}' reviewed procedure. Decision: ${rec.approval_status}. ${rec.review_notes ? `Notes: "${rec.review_notes}"` : ''}`,
        sourceSystem: 'HumanApprovalWorkflow',
        type: 'REVIEW',
        epistemicCategory: 'APPROVED_POLICY',
      })
    }
  })

  // 6. Resolution Event
  if (incident?.resolved_at) {
    events.push({
      id: 'event-resolution',
      timestamp: incident.resolved_at,
      title: 'Ticket Marked Resolved',
      description: incident.resolution_summary || 'Incident marked resolved in upstream ticketing system.',
      sourceSystem: incident.source_dataset || 'ITSM',
      type: 'RESOLUTION',
      epistemicCategory: 'OBSERVED_FACT',
    })
  }

  // Sort chronologically
  const sortedEvents = [...events].sort((a, b) => {
    const diff = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    return ascending ? diff : -diff
  })

  if (sortedEvents.length === 0) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-8 text-center">
        <Clock className="w-6 h-6 text-[var(--text-muted)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          No Timeline Events Recorded
        </h3>
        <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto mt-1 font-mono">
          Timestamps unavailable for external observation and pipeline stages.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Timeline Controls Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)] text-xs">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-[var(--text-muted)]" />
          <span className="font-semibold text-[var(--text-primary)]">
            Chronological Lifecycle ({sortedEvents.length} events)
          </span>
        </div>

        <button
          onClick={() => setAscending(!ascending)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-mono bg-[var(--bg-card)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
        >
          <ArrowUpDown className="w-3 h-3 text-[var(--text-muted)]" />
          <span>{ascending ? 'Oldest First' : 'Newest First'}</span>
        </button>
      </div>

      {/* Vertical Stepper Timeline */}
      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-[var(--border-subtle)]">
        {sortedEvents.map((evt) => {
          return (
            <div key={evt.id} className="relative group">
              {/* Dot Icon */}
              <div className="absolute -left-6 top-1 w-5 h-5 rounded-full bg-[var(--bg-surface)] border-2 border-[var(--text-primary)] flex items-center justify-center shrink-0">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--text-primary)]" />
              </div>

              {/* Event Content Card */}
              <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-3.5 space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-[var(--text-primary)]">
                      {evt.title}
                    </h4>
                    <span className="text-xs font-mono px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                      Source: {evt.sourceSystem}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-[var(--text-secondary)]">
                      {new Date(evt.timestamp).toLocaleString()}
                    </span>
                    <EpistemicBadge category={evt.epistemicCategory} size="sm" />
                  </div>
                </div>

                <p className="text-xs text-[var(--text-muted)] font-mono leading-relaxed">
                  {evt.description}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
