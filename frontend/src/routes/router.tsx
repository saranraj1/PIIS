import { createBrowserRouter, Navigate } from 'react-router-dom'
import { RootLayout } from '../components/layout/RootLayout'
import { CommandCenterPage } from '../pages/CommandCenterPage'
import { IncidentExplorerPage } from '../pages/IncidentExplorerPage'
import { InvestigationPage } from '../pages/InvestigationPage'
import { NetworkIntelligencePage } from '../pages/NetworkIntelligencePage'
import { HumanReviewPage } from '../pages/HumanReviewPage'
import { AuditLedgerPage } from '../pages/AuditLedgerPage'
import { IntegrationsPage } from '../pages/IntegrationsPage'
import { SystemHealthPage } from '../pages/SystemHealthPage'
import { SettingsPage } from '../pages/SettingsPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <CommandCenterPage />,
      },
      {
        path: 'incidents',
        element: <IncidentExplorerPage />,
      },
      {
        path: 'investigation',
        element: <InvestigationPage />,
      },
      {
        path: 'network',
        element: <NetworkIntelligencePage />,
      },
      {
        path: 'reviews',
        element: <HumanReviewPage />,
      },
      {
        path: 'audit',
        element: <AuditLedgerPage />,
      },
      {
        path: 'integrations',
        element: <IntegrationsPage />,
      },
      {
        path: 'system',
        element: <SystemHealthPage />,
      },
      {
        path: 'system-health',
        element: <SystemHealthPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
])
