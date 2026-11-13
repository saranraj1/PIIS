import type {
  NetworkOverviewResponse,
  NetworkTopologyResponse,
  NetworkImpactResponse,
  NetworkAlarmsResponse,
  NetworkTelemetryResponse,
} from '../../api/types'

export const MOCK_NETWORK_OVERVIEW: NetworkOverviewResponse = {
  total_elements: 13,
  elements_by_domain: {
    RAN: 7,
    TRANSPORT: 4,
    '5G_CORE': 4,
    SERVICE: 1,
  },
  total_links: 12,
  active_alarms_count: 2,
  correlated_clusters_count: 1,
  active_anomalies_count: 1,
  last_sync_timestamp: '2026-11-03T12:00:00Z',
  topology_version: '1.0.0-reference',
  epistemic_status: 'OBSERVED_FACT',
  provenance: {
    source_model: 'TelecomTopologyGraph',
    integrity_hash: 'sha256-mock-overview',
  },
}

export const MOCK_NETWORK_TOPOLOGY: NetworkTopologyResponse = {
  nodes: [
    {
      element_id: 'GNB-TESTBED-5G-01',
      domain: 'RAN',
      element_type: 'GNB',
      site_id: 'SITE01',
      nominal_subscribers: 5000,
      active_alarm_count: 1,
      has_anomaly: false,
      epistemic_status: 'OBSERVED_FACT',
    },
    {
      element_id: 'CELL-101',
      domain: 'RAN',
      element_type: 'CELL',
      site_id: 'SITE01',
      nominal_subscribers: 1500,
      active_alarm_count: 0,
      has_anomaly: false,
      epistemic_status: 'OBSERVED_FACT',
    },
    {
      element_id: 'SW-ACCESS-SITE01',
      domain: 'TRANSPORT',
      element_type: 'SWITCH',
      site_id: 'SITE01',
      nominal_subscribers: undefined,
      active_alarm_count: 0,
      has_anomaly: false,
      epistemic_status: 'OBSERVED_FACT',
    },
    {
      element_id: 'UPF-CORE-PRIMARY',
      domain: '5G_CORE',
      element_type: 'UPF',
      site_id: 'CORE',
      nominal_subscribers: 50000,
      active_alarm_count: 0,
      has_anomaly: false,
      epistemic_status: 'OBSERVED_FACT',
    },
    {
      element_id: 'AMF-CORE-01',
      domain: '5G_CORE',
      element_type: 'AMF',
      site_id: 'CORE',
      nominal_subscribers: 100000,
      active_alarm_count: 0,
      has_anomaly: false,
      epistemic_status: 'OBSERVED_FACT',
    },
  ],
  links: [
    {
      source: 'UPF-CORE-PRIMARY',
      target: 'SW-ACCESS-SITE01',
      relation: 'n3_interface',
      is_dependency: true,
      direction: 'downstream',
    },
    {
      source: 'SW-ACCESS-SITE01',
      target: 'GNB-TESTBED-5G-01',
      relation: 'fronthaul',
      is_dependency: true,
      direction: 'downstream',
    },
    {
      source: 'GNB-TESTBED-5G-01',
      target: 'CELL-101',
      relation: 'serves_cell',
      is_dependency: true,
      direction: 'downstream',
    },
  ],
  epistemic_status: 'COMPUTED_TOPOLOGY',
}

export const MOCK_NETWORK_IMPACT: NetworkImpactResponse = {
  target_element: 'GNB-TESTBED-5G-01',
  direct_elements: ['GNB-TESTBED-5G-01'],
  inferred_elements: ['CELL-101', 'CELL-102', 'CELL-103'],
  total_element_count: 4,
  affected_domains: ['RAN'],
  severity_risk_level: 'MAJOR',
  risk_score: 0.65,
  estimated_affected_subscribers: 10000,
  subscriber_impact_basis:
    'Aggregated nominal capacity across 4 direct/inferred elements from registered topology metadata. Not dynamically observed from active UE counters.',
  epistemic_status: 'DERIVED_ESTIMATE',
  provenance: {
    source: 'NetworkImpactAnalyzer',
  },
}

export const MOCK_NETWORK_ALARMS: NetworkAlarmsResponse = {
  alarms: [
    {
      alarm_id: 'ALM-001',
      network_element_id: 'GNB-TESTBED-5G-01',
      network_domain: 'RAN',
      alarm_code: '7100',
      probable_cause: 'High VSWR on feeder',
      severity: 'CRITICAL',
      timestamp: '2026-11-03T12:00:00Z',
      cluster_id: 'CLUST-RAN-A1B2',
      epistemic_status: 'OBSERVED_FACT',
    },
    {
      alarm_id: 'ALM-002',
      network_element_id: 'CELL-101',
      network_domain: 'RAN',
      alarm_code: 'CELL-DEG',
      probable_cause: 'Radio link failure',
      severity: 'MAJOR',
      timestamp: '2026-11-03T12:01:00Z',
      cluster_id: 'CLUST-RAN-A1B2',
      epistemic_status: 'OBSERVED_FACT',
    },
  ],
  clusters: [
    {
      cluster_id: 'CLUST-RAN-A1B2',
      dominant_domain: 'RAN',
      event_count: 2,
      affected_elements: ['GNB-TESTBED-5G-01', 'CELL-101'],
      mean_confidence: 0.88,
      rationales: ['Shared fault category (RADIO_CAPACITY)'],
      epistemic_status: 'HYPOTHESIS',
    },
  ],
  total_alarms: 2,
  total_clusters: 1,
}

export const MOCK_NETWORK_TELEMETRY: NetworkTelemetryResponse = {
  element_id: 'GNB-TESTBED-5G-01',
  series: [
    {
      metric_name: 'prb_utilization_pct',
      unit: '%',
      timestamps: ['2026-11-03T12:00:00Z', '2026-11-03T12:05:00Z', '2026-11-03T12:10:00Z'],
      values: [45.2, 89.6, 92.1],
      is_imputed: [false, false, false],
    },
  ],
  anomalies: [
    {
      anomaly_id: 'ANOM-01',
      metric_name: 'prb_utilization_pct',
      timestamp: '2026-11-03T12:05:00Z',
      observed_value: 89.6,
      expected_value: 45.0,
      threshold_value: 75.0,
      severity: 'CRITICAL',
      score: 0.82,
      epistemic_status: 'MODEL_PREDICTION',
    },
  ],
  epistemic_status: 'OBSERVED_FACT',
}
