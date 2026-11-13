import React from 'react'

export interface DistributionSegment {
  key: string
  label: string
  count: number
  colorClass: string
  bgClass: string
}

interface DistributionBarProps {
  title: string
  segments: DistributionSegment[]
  totalCount: number
  provenanceLabel?: string
}

export const DistributionBar: React.FC<DistributionBarProps> = ({
  title,
  segments,
  totalCount,
  provenanceLabel = 'Computed from active incident items',
}) => {
  return (
    <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 space-y-3 transition-colors">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] font-mono">
          {title}
        </h4>
        <span className="text-[0.68rem] font-mono tabular-nums text-[var(--text-muted)]">
          Total: {totalCount}
        </span>
      </div>

      {totalCount === 0 ? (
        <div className="py-4 text-center text-xs text-[var(--text-muted)] font-mono">
          No records to distribute
        </div>
      ) : (
        <>
          {/* Segmented Progress Bar */}
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={totalCount}
            aria-valuenow={totalCount}
            aria-label={title}
            className="h-2.5 w-full bg-[var(--bg-subtle)] rounded-xs overflow-hidden flex"
          >
            {segments.map((seg) => {
              if (seg.count === 0) return null
              const pct = (seg.count / totalCount) * 100
              return (
                <div
                  key={seg.key}
                  style={{ width: `${pct}%` }}
                  className={`h-full ${seg.bgClass} transition-all duration-300 relative group`}
                  title={`${seg.label}: ${seg.count} (${pct.toFixed(1)}%)`}
                />
              )
            })}
          </div>

          {/* Breakdown Legend Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
            {segments.map((seg) => {
              const pct = totalCount > 0 ? (seg.count / totalCount) * 100 : 0
              return (
                <div
                  key={seg.key}
                  className="flex items-center justify-between p-1.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs"
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className={`w-1.5 h-1.5 rounded-full ${seg.bgClass} shrink-0`} />
                    <span className="text-[var(--text-muted)] font-medium truncate text-[0.72rem]">
                      {seg.label}
                    </span>
                  </div>
                  <span className="font-mono tabular-nums font-semibold text-[0.72rem] text-[var(--text-primary)] ml-1">
                    {seg.count} <span className="font-normal text-[var(--text-muted)]">({pct.toFixed(0)}%)</span>
                  </span>
                </div>
              )
            })}
          </div>
        </>
      )}

      <div className="text-[0.65rem] font-mono text-[var(--text-muted)] pt-1 border-t border-[var(--border-subtle)]">
        Source: {provenanceLabel}
      </div>
    </div>
  )
}
