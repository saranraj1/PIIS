import React, { useState, useMemo, useRef } from 'react'
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Search,
  Server,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  X,
} from 'lucide-react'
import type { NetworkTopologyResponse, NetworkNodeItem, NetworkLinkItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface NetworkTopologyExplorerProps {
  topology?: NetworkTopologyResponse
  isLoading: boolean
  selectedElementId: string | null
  onSelectElement: (elementId: string | null) => void
  onAnalyzeImpact?: (elementId: string) => void
}

interface NodePosition {
  x: number
  y: number
  node: NetworkNodeItem
}

export const NetworkTopologyExplorer: React.FC<NetworkTopologyExplorerProps> = ({
  topology,
  isLoading,
  selectedElementId,
  onSelectElement,
  onAnalyzeImpact,
}) => {
  const [zoom, setZoom] = useState<number>(1)
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [activeDomainFilter, setActiveDomainFilter] = useState<string>('ALL')

  const svgRef = useRef<SVGSVGElement | null>(null)

  // Layout engine assigning tiered (x, y) coordinates
  const { nodePositions, links } = useMemo(() => {
    if (!topology || !topology.nodes.length) {
      return { nodePositions: new Map<string, NodePosition>(), links: [] }
    }

    // Filter nodes by domain if not ALL
    const visibleNodes = topology.nodes.filter((n) => {
      if (activeDomainFilter === 'ALL') return true
      return n.domain.toUpperCase() === activeDomainFilter.toUpperCase()
    })

    const visibleNodeIds = new Set(visibleNodes.map((n) => n.element_id))

    // Filter links between visible nodes
    const visibleLinks = topology.links.filter(
      (l) => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target)
    )

    // Group into 4 structural tiers
    // Tier 0: Core & Service (y=70)
    // Tier 1: Transport (y=190)
    // Tier 2: RAN Base Stations (gNodeB / CU-DU) (y=310)
    // Tier 3: RAN Cells (y=430)
    const tier0: NetworkNodeItem[] = []
    const tier1: NetworkNodeItem[] = []
    const tier2: NetworkNodeItem[] = []
    const tier3: NetworkNodeItem[] = []

    visibleNodes.forEach((node) => {
      const dom = node.domain.toUpperCase()
      const type = node.element_type.toUpperCase()
      if (dom === '5G_CORE' || dom === 'SERVICE') {
        tier0.push(node)
      } else if (dom === 'TRANSPORT') {
        tier1.push(node)
      } else if (dom === 'RAN') {
        if (type === 'CELL') {
          tier3.push(node)
        } else {
          tier2.push(node)
        }
      } else {
        tier1.push(node)
      }
    })

    const positions = new Map<string, NodePosition>()
    const svgWidth = 980

    const placeTier = (tierNodes: NetworkNodeItem[], y: number) => {
      const count = tierNodes.length
      if (count === 0) return
      const step = svgWidth / (count + 1)
      tierNodes.forEach((node, idx) => {
        positions.set(node.element_id, {
          x: Math.round(step * (idx + 1)),
          y,
          node,
        })
      })
    }

    placeTier(tier0, 70)
    placeTier(tier1, 190)
    placeTier(tier2, 310)
    placeTier(tier3, 430)

    return { nodePositions: positions, links: visibleLinks }
  }, [topology, activeDomainFilter])

  // Mouse pan handlers
  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDragging) return
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleZoom = (delta: number) => {
    setZoom((prev) => Math.min(2.0, Math.max(0.5, prev + delta)))
  }

  const handleResetView = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setSearchQuery('')
    setActiveDomainFilter('ALL')
  }

  const selectedNode = selectedElementId ? nodePositions.get(selectedElementId)?.node : null

  // Upstream and downstream sets for the selected element
  const { upstreamIds, downstreamIds } = useMemo(() => {
    if (!selectedElementId || !topology) return { upstreamIds: new Set<string>(), downstreamIds: new Set<string>() }
    const up = new Set<string>()
    const down = new Set<string>()
    topology.links.forEach((l) => {
      if (l.target === selectedElementId && (l.direction === 'downstream' || l.is_dependency)) {
        up.add(l.source)
      }
      if (l.source === selectedElementId && (l.direction === 'downstream' || l.is_dependency)) {
        down.add(l.target)
      }
    })
    return { upstreamIds: up, downstreamIds: down }
  }, [selectedElementId, topology])

  const getDomainColor = (domain: string) => {
    switch (domain.toUpperCase()) {
      case '5G_CORE':
        return { bg: '#0284c7', border: '#38bdf8', text: '#38bdf8' }
      case 'SERVICE':
        return { bg: '#9333ea', border: '#c084fc', text: '#c084fc' }
      case 'TRANSPORT':
        return { bg: '#059669', border: '#34d399', text: '#34d399' }
      case 'RAN':
        return { bg: '#d97706', border: '#fbbf24', text: '#fbbf24' }
      default:
        return { bg: '#475569', border: '#94a3b8', text: '#94a3b8' }
    }
  }

  if (isLoading) {
    return (
      <div className="h-96 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 flex flex-col items-center justify-center animate-pulse">
        <Server className="w-8 h-8 text-[var(--text-muted)] animate-bounce" />
        <span className="mt-2 text-xs text-[var(--text-muted)]">Reconciling network topology graph...</span>
      </div>
    )
  }

  return (
    <div className="rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs overflow-hidden flex flex-col">
      {/* Topology Toolbar */}
      <div className="p-3 border-b border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between flex-wrap gap-2">
        {/* Domain Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-[var(--text-muted)] mr-1 flex items-center gap-1">
            <Layers className="w-3.5 h-3.5" /> Domain:
          </span>
          {['ALL', '5G_CORE', 'TRANSPORT', 'RAN', 'SERVICE'].map((dom) => (
            <button
              key={dom}
              onClick={() => setActiveDomainFilter(dom)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-xs transition-colors cursor-pointer ${
                activeDomainFilter === dom
                  ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-bold'
                  : 'bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border-subtle)] hover:text-[var(--text-primary)]'
              }`}
            >
              {dom}
            </button>
          ))}
        </div>

        {/* Search & Zoom Controls */}
        <div className="flex items-center gap-2">
          {/* Element Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Find element..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-2 py-1 text-xs rounded-md bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] w-36 focus:w-48 transition-all"
            />
          </div>

          {/* Zoom Buttons */}
          <div className="flex items-center border border-[var(--border-subtle)] rounded-md bg-[var(--bg-surface)]">
            <button
              onClick={() => handleZoom(0.15)}
              className="p-1 hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleZoom(-0.15)}
              className="p-1 hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetView}
              className="p-1 hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors border-l border-[var(--border-subtle)]"
              title="Reset View"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div className="relative h-[480px] bg-[var(--bg-page)] overflow-hidden select-none">
        <svg
          ref={svgRef}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          viewBox="0 0 980 500"
        >
          {/* Defs for directed link arrow markers */}
          <defs>
            <marker
              id="arrow-downstream"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#0284c7" />
            </marker>
            <marker
              id="arrow-highlighted"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#fbbf24" />
            </marker>
          </defs>

          {/* Canvas Transform Group */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {/* Tier Guidelines */}
            <line x1="20" y1="70" x2="960" y2="70" stroke="var(--border-subtle)" strokeDasharray="3 3" opacity="0.4" />
            <text x="24" y="64" fill="var(--text-muted)" fontSize="9" fontFamily="monospace">TIER 0: 5G CORE & SERVICE</text>

            <line x1="20" y1="190" x2="960" y2="190" stroke="var(--border-subtle)" strokeDasharray="3 3" opacity="0.4" />
            <text x="24" y="184" fill="var(--text-muted)" fontSize="9" fontFamily="monospace">TIER 1: OPTICAL & IP TRANSPORT</text>

            <line x1="20" y1="310" x2="960" y2="310" stroke="var(--border-subtle)" strokeDasharray="3 3" opacity="0.4" />
            <text x="24" y="304" fill="var(--text-muted)" fontSize="9" fontFamily="monospace">TIER 2: RADIO ACCESS (gNodeB / CU-DU)</text>

            <line x1="20" y1="430" x2="960" y2="430" stroke="var(--border-subtle)" strokeDasharray="3 3" opacity="0.4" />
            <text x="24" y="424" fill="var(--text-muted)" fontSize="9" fontFamily="monospace">TIER 3: SECTOR CELLS</text>

            {/* Links */}
            {links.map((link: NetworkLinkItem, idx: number) => {
              const srcPos = nodePositions.get(link.source)
              const dstPos = nodePositions.get(link.target)
              if (!srcPos || !dstPos) return null

              const isHighlighted =
                selectedElementId &&
                (link.source === selectedElementId || link.target === selectedElementId)

              const isDownstream = link.direction === 'downstream' || link.is_dependency

              return (
                <line
                  key={`${link.source}-${link.target}-${idx}`}
                  x1={srcPos.x}
                  y1={srcPos.y}
                  x2={dstPos.x}
                  y2={dstPos.y}
                  stroke={isHighlighted ? '#fbbf24' : isDownstream ? 'var(--primary)' : 'var(--border)'}
                  strokeWidth={isHighlighted ? 2.5 : 1.5}
                  strokeDasharray={isDownstream ? undefined : '4 4'}
                  markerEnd={isDownstream ? (isHighlighted ? 'url(#arrow-highlighted)' : 'url(#arrow-downstream)') : undefined}
                  opacity={isHighlighted ? 1.0 : 0.6}
                />
              )
            })}

            {/* Nodes */}
            {Array.from(nodePositions.values()).map(({ x, y, node }) => {
              const isSelected = selectedElementId === node.element_id
              const isMatch = searchQuery && node.element_id.toLowerCase().includes(searchQuery.toLowerCase())
              const colors = getDomainColor(node.domain)

              return (
                <g
                  key={node.element_id}
                  transform={`translate(${x}, ${y})`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectElement(isSelected ? null : node.element_id)
                  }}
                  className="cursor-pointer group"
                >
                  {/* Selection Glow */}
                  {isSelected && (
                    <circle r="22" fill="none" stroke="#38bdf8" strokeWidth="3" opacity="0.8" className="animate-pulse" />
                  )}

                  {/* Search Match Highlight */}
                  {isMatch && !isSelected && (
                    <circle r="22" fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="3 2" />
                  )}

                  {/* Node Circle */}
                  <circle
                    r="15"
                    fill="var(--bg-card)"
                    stroke={isSelected ? '#38bdf8' : colors.border}
                    strokeWidth={isSelected ? '2.5' : '1.5'}
                    className="transition-all group-hover:scale-110"
                  />

                  {/* Domain Icon / Dot */}
                  <circle r="5" fill={colors.bg} />

                  {/* Node Label */}
                  <text
                    y="27"
                    textAnchor="middle"
                    fill={isSelected ? '#38bdf8' : 'var(--text-primary)'}
                    fontSize="9.5"
                    fontWeight={isSelected ? '700' : '500'}
                    fontFamily="monospace"
                    className="pointer-events-none drop-shadow-xs"
                  >
                    {node.element_id}
                  </text>

                  {/* Active Alarm Beacon */}
                  {node.active_alarm_count > 0 && (
                    <g transform="translate(10, -10)">
                      <circle r="7" fill="#ef4444" />
                      <text
                        y="2.5"
                        textAnchor="middle"
                        fill="#ffffff"
                        fontSize="7.5"
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {node.active_alarm_count}
                      </text>
                    </g>
                  )}

                  {/* Anomaly Indicator */}
                  {node.has_anomaly && (
                    <g transform="translate(-10, -10)">
                      <circle r="5" fill="#a855f7" />
                    </g>
                  )}
                </g>
              )
            })}
          </g>
        </svg>

        {/* Selected Element Detail Drawer */}
        {selectedNode && (
          <div className="absolute right-3 top-3 bottom-3 w-80 bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-xs p-4 overflow-y-auto space-y-4 flex flex-col z-10">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-[var(--text-muted)]" />
                <h4 className="text-xs font-mono font-bold text-[var(--text-primary)]">
                  {selectedNode.element_id}
                </h4>
                <EpistemicBadge category="REFERENCE_DATA" size="sm" />
              </div>
              <button
                onClick={() => onSelectElement(null)}
                className="p-1 rounded-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Element Attributes */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Domain:</span>
                <span className="font-semibold text-[var(--text-primary)]">{selectedNode.domain}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Element Type:</span>
                <span className="font-mono text-[var(--text-primary)]">{selectedNode.element_type}</span>
              </div>
              {selectedNode.site_id && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Site ID:</span>
                  <span className="font-mono text-[var(--text-primary)]">{selectedNode.site_id}</span>
                </div>
              )}
              {selectedNode.nominal_subscribers !== null && selectedNode.nominal_subscribers !== undefined && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Nominal Subscribers:</span>
                  <span className="font-mono font-semibold text-[var(--text-primary)]">
                    {selectedNode.nominal_subscribers.toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            {/* Upstream & Downstream Dependencies */}
            <div className="space-y-2 pt-2 border-t border-[var(--border-subtle)] text-xs">
              <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-medium">
                <ArrowUpRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <span>Upstream Infrastructure ({upstreamIds.size}):</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {upstreamIds.size === 0 ? (
                  <span className="text-xs text-[var(--text-muted)] italic">Root element / None</span>
                ) : (
                  Array.from(upstreamIds).map((id) => (
                    <button
                      key={id}
                      onClick={() => onSelectElement(id)}
                      className="px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] hover:border-[var(--text-primary)] cursor-pointer"
                    >
                      {id}
                    </button>
                  ))
                )}
              </div>

              <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-medium pt-2">
                <ArrowDownRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <span>Downstream Dependents ({downstreamIds.size}):</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {downstreamIds.size === 0 ? (
                  <span className="text-xs text-[var(--text-muted)] italic">Leaf element / None</span>
                ) : (
                  Array.from(downstreamIds).map((id) => (
                    <button
                      key={id}
                      onClick={() => onSelectElement(id)}
                      className="px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] hover:border-[var(--text-primary)] cursor-pointer"
                    >
                      {id}
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Health & Alarms State */}
            <div className="pt-2 border-t border-[var(--border-subtle)] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[var(--text-muted)]">Active Alarms:</span>
                <span className="font-mono font-bold text-[var(--text-primary)] tabular-nums">
                  {selectedNode.active_alarm_count}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[var(--text-muted)]">Anomaly Stream:</span>
                <span className="inline-flex items-center gap-1.5 font-mono font-medium text-[var(--text-primary)]">
                  <span className={`w-1.5 h-1.5 rounded-full ${selectedNode.has_anomaly ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                  {selectedNode.has_anomaly ? 'VIOLATION DETECTED' : 'NOMINAL'}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            {onAnalyzeImpact && (
              <div className="pt-3 border-t border-[var(--border-subtle)] mt-auto">
                <button
                  onClick={() => onAnalyzeImpact(selectedNode.element_id)}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xs bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 transition-colors cursor-pointer"
                >
                  <Activity className="w-3.5 h-3.5" />
                  <span>Analyze Blast Radius</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
