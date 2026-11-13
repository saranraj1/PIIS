"""Controlled synthetic scenario generator for PIIS-TelcoBench.

Generates physically coherent, causal telecom incidents, alarms, and telemetry.
All generated records carry source_type="SYNTHETIC", explicit seeds,
and scenario family identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional

import jsonschema

from piis.provenance import SourceType

# Load schemas
ROOT = Path(__file__).resolve().parents[3]
with (ROOT / "schemas" / "incident.schema.json").open("r", encoding="utf-8") as f:
    INCIDENT_SCHEMA = json.load(f)
with (ROOT / "schemas" / "alarm.schema.json").open("r", encoding="utf-8") as f:
    ALARM_SCHEMA = json.load(f)
with (ROOT / "schemas" / "telemetry.schema.json").open("r", encoding="utf-8") as f:
    TELEMETRY_SCHEMA = json.load(f)

INCIDENT_VALIDATOR = jsonschema.Draft202012Validator(INCIDENT_SCHEMA, format_checker=jsonschema.FormatChecker())
ALARM_VALIDATOR = jsonschema.Draft202012Validator(ALARM_SCHEMA, format_checker=jsonschema.FormatChecker())
TELEMETRY_VALIDATOR = jsonschema.Draft202012Validator(TELEMETRY_SCHEMA, format_checker=jsonschema.FormatChecker())


@dataclass
class ScenarioOutcome:
    incident: Dict[str, Any]
    alarms: List[Dict[str, Any]]
    telemetry: List[Dict[str, Any]]


class TelecomScenarioGenerator:
    """Deterministic synthetic telecom incident and telemetry generator."""

    def __init__(self, seed: int = 42, base_epoch: Optional[datetime] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base_epoch = base_epoch or datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)

    def generate_scenario(
        self,
        scenario_family: str,
        variant_idx: int = 1,
        validate: bool = True
    ) -> ScenarioOutcome:
        """Generate a complete coherent scenario outcome."""
        generator_fn = getattr(self, f"_gen_{scenario_family.lower()}", None)
        if not generator_fn:
            raise ValueError(f"Unknown scenario family: {scenario_family}")

        outcome = generator_fn(variant_idx)

        if validate:
            INCIDENT_VALIDATOR.validate(outcome.incident)
            for a in outcome.alarms:
                ALARM_VALIDATOR.validate(a)
            for t in outcome.telemetry:
                TELEMETRY_VALIDATOR.validate(t)

        return outcome

    # S01: RAN Signal Degradation
    def _gen_s01(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S01-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-CELL-{100 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        # Causal variable: antenna line attenuation in dB
        attenuation_db = self.rng.uniform(15.0, 25.0)

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Severe downlink signal attenuation and elevated block error rate",
            "description": (
                f"Sector {ne_id} reports progressive radio link degradation. "
                "Subscribers observe low throughput and frequent modulation drops."
            ),
            "network_domain": "RAN",
            "fault_category": "ran_signal_degradation",
            "severity": "MAJOR",
            "support_level_label": "L2",
            "support_level_rationale": "Requires physical RF antenna feeder line inspection and VSWR measurement.",
            "affected_region": "NORTH-SECTOR-RURAL",
            "affected_subscribers": int(self.rng.randint(45, 120)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s01_{variant_idx}",
            "scenario_family_id": "S01",
            "split_group_id": f"S01-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {
                "causal_variable": "feeder_attenuation_db",
                "causal_value": round(attenuation_db, 2),
                "negative_control": False,
            },
        }

        # Alarm
        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-VSWR-01",
            "severity": "MAJOR",
            "probable_cause": "Antenna line impedance mismatch / VSWR high",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s01_{variant_idx}",
            "metadata": {"vswr_ratio": 2.4},
        }

        # Telemetry window
        telemetry = []
        for step in range(5):
            ts = (t0 + timedelta(minutes=step * 2)).isoformat().replace("+00:00", "Z")
            rsrp_val = round(-85.0 - (step * (attenuation_db / 4.0)), 1)
            bler_val = round(min(0.01 + (step * 0.08), 0.45), 3)

            telemetry.append({
                "schema_version": "1.0",
                "observation_id": f"OBS-{inc_id}-{step:02d}-RSRP",
                "incident_id": inc_id,
                "timestamp": ts,
                "network_element_id": ne_id,
                "network_domain": "RAN",
                "metric_name": "RSRP",
                "metric_value": rsrp_val,
                "unit": "dBm",
                "source_type": SourceType.SYNTHETIC.value,
                "source_dataset": "PIIS-TelcoBench-Synthetic",
                "source_record_id": f"syn_obs_s01_{variant_idx}_{step}_rsrp",
                "original_timezone": "UTC",
                "metadata": {"simulation_step": step},
            })
            telemetry.append({
                "schema_version": "1.0",
                "observation_id": f"OBS-{inc_id}-{step:02d}-BLER",
                "incident_id": inc_id,
                "timestamp": ts,
                "network_element_id": ne_id,
                "network_domain": "RAN",
                "metric_name": "DL_BLER",
                "metric_value": bler_val,
                "unit": "ratio",
                "source_type": SourceType.SYNTHETIC.value,
                "source_dataset": "PIIS-TelcoBench-Synthetic",
                "source_record_id": f"syn_obs_s01_{variant_idx}_{step}_bler",
                "original_timezone": "UTC",
                "metadata": {"simulation_step": step},
            })

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=telemetry)

    # S03: Cell Congestion (L1 Runbook)
    def _gen_s03(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S03-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-CELL-{200 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Severe downlink PRB saturation and queue delay",
            "description": f"Sector {ne_id} reports PRB utilization exceeding 98%. User throughput degraded.",
            "network_domain": "RAN",
            "fault_category": "cell_congestion",
            "severity": "MINOR",
            "support_level_label": "L1",
            "support_level_rationale": "Standard load-balancing SOP-RAN-CONGEST applies via automated OSS portal.",
            "affected_region": "METRO-ARENA-DISTRICT",
            "affected_subscribers": int(self.rng.randint(250, 600)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s03_{variant_idx}",
            "scenario_family_id": "S03",
            "split_group_id": f"S03-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"runbook_available": "SOP-RAN-CONGEST-01"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-PRB-CONGEST",
            "severity": "MINOR",
            "probable_cause": "Downlink Physical Resource Block capacity exhausted",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s03_{variant_idx}",
            "metadata": {"prb_util": 0.99},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-PRB",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "metric_name": "PRB_UTIL_DL",
            "metric_value": 0.985,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s03_{variant_idx}_prb",
            "original_timezone": "UTC",
            "metadata": {"active_ue_count": 480},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S02: Handover Failure
    def _gen_s02(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S02-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-CELL-{150 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Elevated inter-frequency handover preparation failure",
            "description": f"Sector {ne_id} reports handover failure rate exceeding 35% on boundary with adjacent cluster.",
            "network_domain": "RAN",
            "fault_category": "handover_failure",
            "severity": "MAJOR",
            "support_level_label": "L2",
            "support_level_rationale": "Requires multi-sector neighbor relation and RF boundary offset investigation.",
            "affected_region": "EAST-TRANSIT-CORRIDOR",
            "affected_subscribers": int(self.rng.randint(60, 180)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s02_{variant_idx}",
            "scenario_family_id": "S02",
            "split_group_id": f"S02-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"target_neighbor_id": f"GNB-CELL-{151 + variant_idx}"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "alarm_code": "ALM-RAN-HO-EXC-FAIL",
            "severity": "MAJOR",
            "probable_cause": "Target cell Xn preparation timeout",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s02_{variant_idx}",
            "metadata": {"ho_success_rate": 0.62},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-HO",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "metric_name": "HO_SUCCESS_RATE",
            "metric_value": 0.62,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s02_{variant_idx}_ho",
            "original_timezone": "UTC",
            "metadata": {"attempt_count": 210},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S04: Base Station Outage
    def _gen_s04(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S04-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-SITE-{300 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Complete site transmission loss following commercial power drop",
            "description": f"Base station site {ne_id} unreachable. Mains AC power lost and backup battery exhausted.",
            "network_domain": "RAN",
            "fault_category": "base_station_outage",
            "severity": "CRITICAL",
            "support_level_label": "L1",
            "support_level_rationale": "SOP-PWR-GENERATOR-DISPATCH applies for routine mobile generator deployment.",
            "affected_region": "WEST-HIGHLANDS",
            "affected_subscribers": int(self.rng.randint(300, 950)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s04_{variant_idx}",
            "scenario_family_id": "S04",
            "split_group_id": f"S04-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"power_status": "OFFLINE"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "alarm_code": "ALM-PWR-BATT-LOW",
            "severity": "CRITICAL",
            "probable_cause": "DC busbar voltage below operating threshold",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s04_{variant_idx}",
            "metadata": {"battery_voltage": 43.2},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-PWR",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "metric_name": "DC_VOLTAGE",
            "metric_value": 43.2,
            "unit": "volts",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s04_{variant_idx}_pwr",
            "original_timezone": "UTC",
            "metadata": {"alarm_triggered": True},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S05: Authentication Failures
    def _gen_s05(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S05-{self.seed}-{variant_idx:03d}"
        ne_id = "5GC-AUSF-01"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "5G AKA subscriber authentication timeout and vector rejection",
            "description": "Subscribers unable to register on 5GC slice. AUSF reports HTTP/2 SBI interface timeouts.",
            "network_domain": "5G_CORE",
            "fault_category": "subscriber_authentication_failure",
            "severity": "CRITICAL",
            "support_level_label": "L2",
            "support_level_rationale": "Requires core security and UDM mutual-TLS certificate validation.",
            "affected_region": "CORE-DATACENTER-DC1",
            "affected_subscribers": int(self.rng.randint(500, 2500)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s05_{variant_idx}",
            "scenario_family_id": "S05",
            "split_group_id": f"S05-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"slice": "eMBB-Commercial"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "alarm_code": "ALM-5GC-AUTH-TIMEOUT",
            "severity": "CRITICAL",
            "probable_cause": "SBI interface connection timeout to UDM",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s05_{variant_idx}",
            "metadata": {"http_status": 504},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-AUTH",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "metric_name": "AUTH_SUCCESS_RATE",
            "metric_value": 0.04,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s05_{variant_idx}_auth",
            "original_timezone": "UTC",
            "metadata": {"failure_code": "MAC_FAILURE_OR_TIMEOUT"},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S06: PDU Session Establishment Failure
    def _gen_s06(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S06-{self.seed}-{variant_idx:03d}"
        ne_id = "5GC-SMF-02"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "PDU session establishment rejection due to DNN pool exhaustion",
            "description": "New data session setup requests rejected by SMF with resource exhaustion status.",
            "network_domain": "5G_CORE",
            "fault_category": "session_establishment_failure",
            "severity": "MAJOR",
            "support_level_label": "L1",
            "support_level_rationale": "SOP-CORE-IP-POOL applies to reallocate dynamic pool subnet block.",
            "affected_region": "CORE-DATACENTER-DC2",
            "affected_subscribers": int(self.rng.randint(150, 400)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s06_{variant_idx}",
            "scenario_family_id": "S06",
            "split_group_id": f"S06-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"dnn": "internet.telecom.com"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "alarm_code": "ALM-5GC-DNN-IP-POOL-EXHAUST",
            "severity": "MAJOR",
            "probable_cause": "Subnet IP address pool full",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s06_{variant_idx}",
            "metadata": {"allocated_pct": 100.0},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-PDU",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "metric_name": "PDU_SUCCESS_RATE",
            "metric_value": 0.12,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s06_{variant_idx}_pdu",
            "original_timezone": "UTC",
            "metadata": {"reject_cause": "INSUFFICIENT_RESOURCES"},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S07: User-Plane Forwarding Degradation
    def _gen_s07(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S07-{self.seed}-{variant_idx:03d}"
        ne_id = "5GC-UPF-EDGE-01"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Severe GTP-U packet drop and jitter on edge UPF",
            "description": "User plane reports 25% packet drops. DPDK ring buffers experiencing continuous drops.",
            "network_domain": "5G_CORE",
            "fault_category": "user_plane_degradation",
            "severity": "MAJOR",
            "support_level_label": "L2",
            "support_level_rationale": "Requires virtualization host hypervisor inspection and DPDK core tuning.",
            "affected_region": "EDGE-DC-SOUTH",
            "affected_subscribers": int(self.rng.randint(400, 1200)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s07_{variant_idx}",
            "scenario_family_id": "S07",
            "split_group_id": f"S07-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"dpdk_ring": "rx_ring_0"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "alarm_code": "ALM-5GC-UPF-BUFFER-OVERFLOW",
            "severity": "MAJOR",
            "probable_cause": "Ingress ring buffer exhausted",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s07_{variant_idx}",
            "metadata": {"drop_rate_pct": 24.8},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-DROP",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "5G_CORE",
            "metric_name": "PACKET_DROP_RATE",
            "metric_value": 0.248,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s07_{variant_idx}_drop",
            "original_timezone": "UTC",
            "metadata": {"ring_id": "rx_0"},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S08: Transport Link Degradation
    def _gen_s08(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S08-{self.seed}-{variant_idx:03d}"
        ne_id = f"TX-OPTICAL-ROUTER-{variant_idx:02d}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Backhaul interface intermittent carrier flap and optical CRC errors",
            "description": "Optical 10GE backhaul reports framing errors and frequent link re-synchronization.",
            "network_domain": "TRANSPORT",
            "fault_category": "transport_link_failure",
            "severity": "MAJOR",
            "support_level_label": "L2",
            "support_level_rationale": "Requires transport fiber testing, optical power margin check, and OTDR diagnosis.",
            "affected_region": "METRO-RING-NORTH",
            "affected_subscribers": int(self.rng.randint(800, 2200)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s08_{variant_idx}",
            "scenario_family_id": "S08",
            "split_group_id": f"S08-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"interface": "TenGigE0/1/0/4"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "TRANSPORT",
            "alarm_code": "ALM-TX-CRC-ERR",
            "severity": "MAJOR",
            "probable_cause": "Optical power level below receiver sensitivity threshold",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s08_{variant_idx}",
            "metadata": {"rx_power_dbm": -24.8},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-CRC",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "TRANSPORT",
            "metric_name": "CRC_ERROR_COUNT",
            "metric_value": 1420.0,
            "unit": "count",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s08_{variant_idx}_crc",
            "original_timezone": "UTC",
            "metadata": {"interface": "TenGigE0/1/0/4"},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S09: DNS & Service Resolution Failures
    def _gen_s09(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S09-{self.seed}-{variant_idx:03d}"
        ne_id = "SRV-DNS-CLUSTER-01"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Gi-LAN primary DNS resolver cluster query timeout",
            "description": "Subscribers establish data session successfully but cannot resolve hostnames. High UDP port 53 drop rate.",
            "network_domain": "SERVICE",
            "fault_category": "dns_service_failure",
            "severity": "CRITICAL",
            "support_level_label": "L1",
            "support_level_rationale": "SOP-SRV-DNS-RESTART applies to restart caching named pods and failover to secondary.",
            "affected_region": "REGIONAL-INTERNET-GATEWAY",
            "affected_subscribers": int(self.rng.randint(1200, 5000)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s09_{variant_idx}",
            "scenario_family_id": "S09",
            "split_group_id": f"S09-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"dns_ip": "10.200.1.53"},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "SERVICE",
            "alarm_code": "ALM-SRV-DNS-FAIL",
            "severity": "CRITICAL",
            "probable_cause": "Named process thread pool deadlocked",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s09_{variant_idx}",
            "metadata": {"query_timeout_pct": 98.4},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-DNS",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "SERVICE",
            "metric_name": "DNS_TIMEOUT_RATE",
            "metric_value": 0.984,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s09_{variant_idx}_dns",
            "original_timezone": "UTC",
            "metadata": {"health": "CRITICAL"},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S10: Configuration Regressions
    def _gen_s10(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S10-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-CELL-{400 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Mismatched interface MTU causing large TCP payload transmission blackhole",
            "description": "Small packets pass normally; large TCP transfers hang due to MTU fragmentation drop.",
            "network_domain": "CROSS_DOMAIN",
            "fault_category": "configuration_regression",
            "severity": "MAJOR",
            "support_level_label": "L1",
            "support_level_rationale": "SOP-CFG-ROLLBACK applies to revert automated maintenance change batch.",
            "affected_region": "METRO-CLUSTER-NORTH",
            "affected_subscribers": int(self.rng.randint(180, 420)),
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s10_{variant_idx}",
            "scenario_family_id": "S10",
            "split_group_id": f"S10-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"mismatched_mtu": 1500, "transport_mtu": 1420},
        }

        alarm = {
            "schema_version": "1.0",
            "alarm_id": f"ALM-{inc_id}-01",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "CROSS_DOMAIN",
            "alarm_code": "ALM-CFG-MISMATCH-MTU",
            "severity": "MAJOR",
            "probable_cause": "Path MTU smaller than interface configured MTU",
            "clear_timestamp": None,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_alm_s10_{variant_idx}",
            "metadata": {"configured_mtu": 1500},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-MTU",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "CROSS_DOMAIN",
            "metric_name": "TCP_RETX_RATE",
            "metric_value": 0.38,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s10_{variant_idx}_mtu",
            "original_timezone": "UTC",
            "metadata": {"df_drops": 450},
        }

        return ScenarioOutcome(incident=incident, alarms=[alarm], telemetry=[obs])

    # S00: Negative Control (Healthy Baseline)
    def _gen_s00(self, variant_idx: int) -> ScenarioOutcome:
        inc_id = f"SYN-INC-S00-NC-{self.seed}-{variant_idx:03d}"
        ne_id = f"GNB-CELL-{500 + variant_idx}"
        t0 = self.base_epoch + timedelta(hours=variant_idx)
        t0_str = t0.isoformat().replace("+00:00", "Z")

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": "Nominal traffic variation within normal operating boundaries",
            "description": f"Sector {ne_id} reports routine diurnal user activity drop.",
            "network_domain": "RAN",
            "fault_category": "nominal_operation",
            "severity": "WARNING",
            "support_level_label": "HUMAN_REVIEW",
            "support_level_rationale": "No anomaly detected; review for closure without dispatch.",
            "affected_region": "SUBURBAN-RESIDENTIAL",
            "affected_subscribers": 0,
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_s00_{variant_idx}",
            "scenario_family_id": "S00",
            "split_group_id": f"S00-seed-{self.seed}",
            "annotation_status": "REVIEWED",
            "metadata": {"negative_control": True},
        }

        obs = {
            "schema_version": "1.0",
            "observation_id": f"OBS-{inc_id}-01-PRB",
            "incident_id": inc_id,
            "timestamp": t0_str,
            "network_element_id": ne_id,
            "network_domain": "RAN",
            "metric_name": "PRB_UTIL_DL",
            "metric_value": 0.22,
            "unit": "ratio",
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-Synthetic",
            "source_record_id": f"syn_obs_s00_{variant_idx}_prb",
            "original_timezone": "UTC",
            "metadata": {"active_ue_count": 35},
        }

        return ScenarioOutcome(incident=incident, alarms=[], telemetry=[obs])
