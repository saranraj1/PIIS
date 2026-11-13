import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  AlertTriangle,
  Search,
  Network,
  CheckSquare,
  History,
  Layers,
  Activity,
  Settings,
} from 'lucide-react'

interface AppSidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

interface NavItem {
  name: string
  path: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { name: 'Command Center', path: '/', icon: LayoutDashboard },
  { name: 'Incident Explorer', path: '/incidents', icon: AlertTriangle },
  { name: 'Investigation', path: '/investigation', icon: Search },
  { name: 'Network Intelligence', path: '/network', icon: Network },
  { name: 'Human Review', path: '/reviews', icon: CheckSquare },
  { name: 'Audit & Provenance', path: '/audit', icon: History },
  { name: 'Integrations & DLQ', path: '/integrations', icon: Layers },
  { name: 'System Health', path: '/system', icon: Activity },
  { name: 'Settings & Profile', path: '/settings', icon: Settings },
]

export const AppSidebar: React.FC<AppSidebarProps> = ({ isOpen, onClose }) => {
  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          aria-hidden="true"
        />
      )}

      <aside
        aria-label="Main Navigation"
        className={`fixed inset-y-0 left-0 z-40 md:static md:z-auto h-full w-60 shrink-0 bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] transition-transform duration-200 ease-in-out flex flex-col justify-between overflow-hidden select-none overscroll-contain ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="py-2.5 flex-1 min-h-0 overflow-y-auto no-scrollbar overscroll-contain flex flex-col">
          <div className="px-3 pb-2 mb-1 border-b border-[var(--border-subtle)] text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono shrink-0">
            NOC Operational Views
          </div>
          <nav aria-label="Main Navigation" className="space-y-0.5 px-2 flex-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-xs text-xs font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] ${
                    isActive
                      ? 'bg-[var(--bg-subtle)] text-[var(--text-primary)] font-semibold border-l-2 border-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]'
                  }`
                }
              >
                <item.icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.name}</span>
                {item.badge && (
                  <span className="ml-auto text-xs font-mono font-bold px-1.5 py-0.5 rounded-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="p-3 border-t border-[var(--border-subtle)] text-xs text-[var(--text-muted)] font-mono flex items-center justify-between shrink-0 bg-[var(--bg-surface)]">
          <span>PIIS Core</span>
          <span className="text-[var(--text-primary)] font-bold">v1.0.0</span>
        </div>
      </aside>
    </>
  )
}
