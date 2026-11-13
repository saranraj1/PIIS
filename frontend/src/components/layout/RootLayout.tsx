import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'
import { StatusBanner } from './StatusBanner'
import { EpistemicLegend } from '../epistemic/EpistemicLegend'
import { AppSidebar } from './AppSidebar'

export const RootLayout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <div className="fixed inset-0 h-full w-full overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)] flex flex-col font-sans transition-colors duration-150 select-none md:select-auto">
      {/* Top Banner: Strict read-only posture */}
      <div className="shrink-0">
        <StatusBanner />
      </div>

      {/* Persistent App Header */}
      <div className="shrink-0 z-30">
        <AppHeader
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        />
      </div>

      {/* Visual Epistemic Strip */}
      <div className="shrink-0 z-20">
        <EpistemicLegend />
      </div>

      {/* Main Content Area with Sidebar */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        <AppSidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />

        <main
          id="main-content"
          role="main"
          className="flex-1 overflow-y-auto p-4 md:p-6 min-w-0 h-full overscroll-contain"
        >
          {/* Child Route Outlet */}
          <Outlet />
        </main>
      </div>
    </div>
  )
}
