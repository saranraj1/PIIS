import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Copy,
  Check,
  RefreshCw,
  Radio,
  Clock,
  Users,
  Server,
  Layers,
  ChevronDown,
} from 'lucide-react'
import type { CanonicalIncidentItem } from '../../api/types'
import { SeverityBadge } from '../common/SeverityBadge'
import { DomainBadge } from '../common/DomainBadge'

export interface IncidentContextHeaderProps {
  incident: CanonicalIncidentItem | null
  lineage?: {
    envelope_id?: string | null
    raw_payload_checksum?: string | null
    source_system?: string | null
    observation_timestamp?: string | null
    ingested_at?: string | null
  } | null
  availableIncidents?: CanonicalIncidentItem[]
  onSelectIncident: (id: string) => void
  onRefresh: () => void
  isLoading?: boolean
}

export const IncidentContextHeader: React.FC<IncidentContextHeaderProps> = ({
  incident,
  lineage,
  availableIncidents = [],
  onSelectIncident,
  onRefresh,
  isLoading = false,
}) => {
  const [copied, setCopied] = useState(false)
  const [selectorOpen, setSelectorOpen] = useState(false)

  const handleCopyId = () => {
    if (!incident) return
    navigator.clipboard?.writeText(incident.incident_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!incident) {
    return (
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 animate-pulse transition-colors">
        <div className="h-4 bg-[var(--bg-subtle)] rounded-xs w-1/4 mb-2"></div>
        <div className="h-6 bg-[var(--bg-subtle)] rounded-xs w-3/4"></div>
      </div>
    )
  }

  const isResolved = Boolean(incident.resolved_at)

  return (
    <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4 transition-colors">
      {/* Top Action Bar: Navigation + Switcher + Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-3">
        <div className="flex items-center gap-3">
          <Link
            to="/incidents"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors px-2.5 py-1 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] font-mono"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Incident Explorer</span>
          </Link>

          {/* Quick Incident Switcher Dropdown */}
          <div className="relative">
            <button
              onClick={() => setSelectorOpen(!selectorOpen)}
              className="inline-flex items-center gap-1.5 text-xs font-mono font-medium px-2.5 py-1 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] hover:border-[var(--border-strong)] transition-colors"
              aria-label="Switch Incident"
            >
              <Radio className="w-3 h-3 text-[var(--text-muted)]" />
              <span>Switch Ticket</span>
              <ChevronDown className="w-3 h-3 text-[var(--text-muted)]" />
            </button>

            {selectorOpen && (
              <div
                className="absolute left-0 mt-1 w-72 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-strong)] shadow-lg z-30 py-1 max-h-60 overflow-y-auto"
                onMouseLeave={() => setSelectorOpen(false)}
              >
                <div className="px-3 py-1.5 text-xs font-mono text-[var(--text-muted)] uppercase tracking-wider border-b border-[var(--border-subtle)]">
                  Available Canonical Incidents
                </div>
                {availableIncidents.map((item) => (
                  <button
                    key={item.incident_id}
                    onClick={() => {
                      onSelectIncident(item.incident_id)
                      setSelectorOpen(false)
                    }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-[var(--bg-subtle)] transition-colors flex items-center justify-between ${
                      item.incident_id === incident.incident_id
                        ? 'bg-[var(--bg-subtle)] font-bold text-[var(--text-primary)] border-l-2 border-[var(--text-primary)]'
                        : 'text-[var(--text-primary)]'
                    }`}
                  >
                    <div>
                      <div className="font-mono tabular-nums text-xs font-bold">{item.incident_id}</div>
                      <div className="text-xs text-[var(--text-muted)] truncate max-w-[180px]">
                        {item.title || item.description}
                      </div>
                    </div>
                    <SeverityBadge severity={item.severity} size="sm" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            aria-label="Refresh investigation data"
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-[var(--text-primary)] font-mono"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-[var(--text-muted)] ${isLoading ? 'animate-spin' : ''}`}
            />
            <span>Refresh Workspace</span>
          </button>
        </div>
      </div>

      {/* Main Context Details */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono tabular-nums text-xs font-bold px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] flex items-center gap-1">
              <span>{incident.incident_id}</span>
              <button
                onClick={handleCopyId}
                title="Copy Incident ID"
                className="hover:text-[var(--text-primary)] ml-1"
                aria-label="Copy incident ID"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3 text-[var(--text-muted)]" />}
              </button>
            </span>

            <SeverityBadge severity={incident.severity} size="sm" />
            <DomainBadge domain={incident.network_domain} size="sm" />

            <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] uppercase font-medium">
              <span className={`w-1.5 h-1.5 rounded-full ${isResolved ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              {isResolved ? 'RESOLVED' : 'ACTIVE TICKET'}
            </span>
          </div>

          <h1 className="text-base sm:text-lg font-bold text-[var(--text-primary)] tracking-tight">
            {incident.title || incident.description}
          </h1>

          {incident.title && (
            <p className="text-xs text-[var(--text-muted)] line-clamp-2 max-w-3xl">
              {incident.description}
            </p>
          )}
        </div>

        {/* Operational Attributes Matrix */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-[var(--bg-subtle)] p-3 rounded-xs border border-[var(--border-subtle)] shrink-0 font-mono tabular-nums">
          <div>
            <div className="text-xs text-[var(--text-muted)] flex items-center gap-1 font-mono">
              <Users className="w-3 h-3 text-[var(--text-muted)]" /> Subscribers
            </div>
            <div className="font-bold text-[var(--text-primary)] mt-0.5 font-mono tabular-nums">
              {incident.affected_subscribers?.toLocaleString() ?? 'None reported'}
            </div>
          </div>

          <div>
            <div className="text-xs text-[var(--text-muted)] flex items-center gap-1 font-mono">
              <Server className="w-3 h-3 text-[var(--text-muted)]" /> Target Elements
            </div>
            <div className="font-bold text-[var(--text-primary)] truncate mt-0.5 max-w-[120px] font-mono">
              {incident.network_element_ids?.join(', ') || 'Global domain'}
            </div>
          </div>

          <div>
            <div className="text-xs text-[var(--text-muted)] flex items-center gap-1 font-mono">
              <Layers className="w-3 h-3 text-[var(--text-muted)]" /> Ingestion Source
            </div>
            <div className="font-bold text-[var(--text-primary)] mt-0.5 font-mono">
              {incident.source_dataset || incident.source_type}
            </div>
          </div>

          <div>
            <div className="text-xs text-[var(--text-muted)] flex items-center gap-1 font-mono">
              <Clock className="w-3 h-3 text-[var(--text-muted)]" /> Observed Date
            </div>
            <div className="font-bold text-[var(--text-primary)] truncate mt-0.5 font-mono tabular-nums">
              {incident.created_at ? new Date(incident.created_at).toLocaleTimeString() : 'N/A'}
            </div>
          </div>
        </div>
      </div>

      {/* Envelope Provenance & Cryptographic Integrity Distinctions */}
      <div className="pt-2 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-[var(--text-muted)]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-[var(--text-primary)]">Envelope Provenance:</span>
          {lineage?.raw_payload_checksum ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              <span>SHA-256 Checksum Available:</span>
              <span className="text-[var(--text-primary)] font-bold">
                {lineage.raw_payload_checksum.slice(0, 12)}...
              </span>
              <span className="text-[var(--text-muted)] text-xs">
                (Digest calculated at ingestion; audit root verification separate)
              </span>
            </span>
          ) : lineage ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-amber-500/20 text-amber-500">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              <span>Checksum Unavailable (Ingested without raw payload digest)</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 shrink-0" />
              <span>Verification Incomplete (Pending Lineage Ingestion Trace)</span>
            </span>
          )}
        </div>

        {lineage?.envelope_id && (
          <div className="text-[var(--text-muted)] font-mono">
            Envelope ID: <span className="text-[var(--text-primary)] font-bold">{lineage.envelope_id}</span>
          </div>
        )}
      </div>
    </div>
  )
}
