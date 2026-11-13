"""PIIS-TelcoBench-v2 Decoupled Scenario Generator.

Remediates M1/M2 synthetic benchmark limitations by decoupling:
1. fault_category and fault_subtype
2. scenario_family_id
3. causal_configuration_id (C1, C2, C3)
4. template_id (T1: NOC Alarm Synopsis, T2: Field Operations Log, T3: Customer SLA Statement)
5. severity (computed via multi-attribute operational risk calculus)
6. support_level (determined via operational triage case card variables)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional
import jsonschema

from piis.provenance import SourceType

ROOT = Path(__file__).resolve().parents[3]
with (ROOT / "schemas" / "incident.schema.json").open("r", encoding="utf-8") as f:
    INCIDENT_SCHEMA = json.load(f)

INCIDENT_VALIDATOR = jsonschema.Draft202012Validator(
    INCIDENT_SCHEMA, format_checker=jsonschema.FormatChecker()
)


@dataclass(frozen=True)
class CausalParameters:
    causal_id: str
    subscriber_range: tuple[int, int]
    service_criticality: str
    redundancy_state: str
    operational_timing: str
    runbook_available: bool
    requires_advanced_diag: bool
    requires_specialist: bool


class TelecomScenarioGeneratorV2:
    """Decoupled, linguistically diverse synthetic telecom incident generator."""

    FAMILIES = [
        "FAM-01", "FAM-02", "FAM-03", "FAM-04", "FAM-05", "FAM-06",
        "FAM-07", "FAM-08", "FAM-09", "FAM-10", "FAM-11", "FAM-12",
    ]

    FAULT_TAXONOMY = {
        "FAM-01": {"category": "ran_signal_degradation", "subtype": "feeder_attenuation", "domain": "RAN"},
        "FAM-02": {"category": "handover_failure", "subtype": "xn_boundary_timeout", "domain": "RAN"},
        "FAM-03": {"category": "cell_congestion", "subtype": "prb_capacity_exhaustion", "domain": "RAN"},
        "FAM-04": {"category": "base_station_outage", "subtype": "mains_power_loss", "domain": "RAN"},
        "FAM-05": {"category": "subscriber_authentication_failure", "subtype": "ausf_sbi_timeout", "domain": "5G_CORE"},
        "FAM-06": {"category": "session_establishment_failure", "subtype": "ip_pool_exhaustion", "domain": "5G_CORE"},
        "FAM-07": {"category": "user_plane_degradation", "subtype": "dpdk_buffer_drop", "domain": "5G_CORE"},
        "FAM-08": {"category": "transport_link_failure", "subtype": "optical_crc_errors", "domain": "TRANSPORT"},
        "FAM-09": {"category": "dns_service_failure", "subtype": "resolver_thread_exhaustion", "domain": "SERVICE"},
        "FAM-10": {"category": "configuration_regression", "subtype": "mtu_fragmentation_blackhole", "domain": "CROSS_DOMAIN"},
        "FAM-11": {"category": "nominal_operation", "subtype": "diurnal_traffic_trough", "domain": "RAN"},
        "FAM-12": {"category": "ambiguous_low_evidence", "subtype": "transient_telemetry_jitter", "domain": "CROSS_DOMAIN"},
    }

    CAUSAL_CONFIGS: Dict[str, Dict[str, CausalParameters]] = {
        # High, standard, and low severity configurations per family
        "DEFAULT": {
            "C1": CausalParameters("C1", (15, 80), "BEST_EFFORT_IOT", "FULLY_PROTECTED", "MAINTENANCE_WINDOW", True, False, False),
            "C2": CausalParameters("C2", (150, 450), "COMMERCIAL_EMBB", "DEGRADED_REDUNDANCY", "BUSINESS_HOURS", True, True, False),
            "C3": CausalParameters("C3", (800, 3500), "EMERGENCY_PSAP", "SINGLE_POINT_OF_FAILURE", "BUSY_HOUR_PEAK", False, True, True),
        }
    }

    def __init__(self, seed: int = 42, base_epoch: Optional[datetime] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base_epoch = base_epoch or datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)

    def calculate_severity(
        self,
        subscribers: int,
        criticality: str,
        redundancy: str,
        timing: str,
        is_negative: bool = False,
    ) -> str:
        """Calculate operational severity using multi-attribute risk calculus."""
        if is_negative:
            return "WARNING"

        # Explicit SLA override for emergency service or critical SPOF
        if criticality == "EMERGENCY_PSAP":
            return "CRITICAL"
        if redundancy == "SINGLE_POINT_OF_FAILURE" and subscribers >= 500:
            return "CRITICAL"

        score = 0
        # Subscribers factor (1 to 4)
        if subscribers > 1000:
            score += 4
        elif subscribers >= 200:
            score += 3
        elif subscribers >= 20:
            score += 2
        else:
            score += 1

        # Criticality factor (1 to 4)
        crit_map = {"EMERGENCY_PSAP": 4, "ENTERPRISE_VIP": 3, "COMMERCIAL_EMBB": 2, "BEST_EFFORT_IOT": 1}
        score += crit_map.get(criticality, 2)

        # Redundancy factor (1 to 4)
        red_map = {"SINGLE_POINT_OF_FAILURE": 4, "DEGRADED_REDUNDANCY": 2, "FULLY_PROTECTED": 1}
        score += red_map.get(redundancy, 2)

        # Timing factor (1 to 3)
        time_map = {"BUSY_HOUR_PEAK": 3, "BUSINESS_HOURS": 2, "MAINTENANCE_WINDOW": 1}
        score += time_map.get(timing, 2)

        if score >= 11:
            return "CRITICAL"
        elif score >= 8:
            return "MAJOR"
        elif score >= 5:
            return "MINOR"
        else:
            return "WARNING"

    def determine_support_level(
        self,
        runbook: bool,
        advanced_diag: bool,
        specialist: bool,
        is_negative: bool = False,
    ) -> tuple[str, str]:
        """Determine independent ground truth support level."""
        if is_negative:
            return "HUMAN_REVIEW", "Telemetry nominal or below diagnostic threshold; requires triage engineer review before closure."
        if specialist:
            return "L3", "Requires third-party vendor engineering or field physical cable replacement crew."
        if advanced_diag:
            return "L2", "Requires physical RF instrumentation, optical OTDR testing, or multi-domain core protocol analysis."
        if runbook:
            return "L1", "Standard operating procedure applies via automated operational management portal."
        return "HUMAN_REVIEW", "Uncertain fault signature with missing runbook; requires supervisory assessment."

    def _render_text(
        self,
        fam: str,
        template_id: str,
        ne_id: str,
        region: str,
        subscribers: int,
        causal: CausalParameters,
    ) -> tuple[str, str]:
        """Generate linguistically diverse title and description across T1, T2, and T3."""
        tax = self.FAULT_TAXONOMY[fam]
        subtype = tax["subtype"]

        # Synonyms and surface variation
        verb = self.rng.choice(["degraded", "compromised", "impaired", "unstable"])
        drop_word = self.rng.choice(["packet loss", "buffer discard", "frame drops"])

        # Template T1: NOC Automated Alarm Synopsis
        if template_id == "T1":
            title = f"ALM-{tax['domain']}-{subtype.upper().replace('_', '-')}: Threshold violation on {ne_id}"
            desc = (
                f"Automated monitoring alert on node {ne_id} in {region}. "
                f"Condition: {subtype.replace('_', ' ')} detected. Primary metric exceeded threshold. "
                f"Redundancy state is {causal.redundancy_state.lower()}."
            )

        # Template T2: Field Engineering / Tier-1 Triage Log
        elif template_id == "T2":
            sop_id = f"SOP-{tax['domain'][:3]}-{abs(hash(fam)) % 900 + 100}"
            title = f"Dispatch queue ticket: Operational review for {ne_id}"
            runbook_txt = f"Runbook {sop_id} initiated by desk." if causal.runbook_available else "No standard runbook indexed."
            desc = (
                f"Shift triage engineer notes on sector {ne_id}. Field observation: subsystem performance is {verb}. "
                f"Investigation target: {subtype.replace('_', ' ')}. {runbook_txt} "
                f"Operational window: {causal.operational_timing.lower().replace('_', ' ')}."
            )

        # Template T3: End-User & Service SLA Impact Statement (Zero technical keywords from T1)
        elif template_id == "T3":
            crit_label = causal.service_criticality.lower().replace('_', ' ')
            title = f"SLA service impact notice: {crit_label} connectivity degradation in {region}"
            desc = (
                f"Subscribers in {region} report difficulty accessing applications. "
                f"Estimated affected customer count: {subscribers}. "
                f"Service impact classified under {crit_label} policy due to {drop_word} and latency. "
                f"Impacted infrastructure cluster: {ne_id}."
            )
        else:
            raise ValueError(f"Unknown template_id: {template_id}")

        return title, desc

    def generate_incident(
        self,
        scenario_family: str,
        template_id: str = "T1",
        causal_config_id: str = "C2",
        variant_idx: int = 1,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Generate a single schema-compliant decoupled incident record."""
        if scenario_family not in self.FAMILIES:
            raise ValueError(f"Unknown scenario family: {scenario_family}")

        tax = self.FAULT_TAXONOMY[scenario_family]
        causal_opts = self.CAUSAL_CONFIGS["DEFAULT"]
        causal = causal_opts.get(causal_config_id, causal_opts["C2"])

        is_negative = scenario_family in ["FAM-11", "FAM-12"]

        # Draw randomized values within causal ranges
        sub_min, sub_max = causal.subscriber_range
        subs = 0 if is_negative else int(self.rng.randint(sub_min, sub_max))

        regions = ["NORTH-METRO", "SOUTH-RURAL", "EAST-INDUSTRIAL", "WEST-HIGHLANDS", "CENTRAL-CORE-DC"]
        region = self.rng.choice(regions)

        ne_prefix = tax["domain"].replace("5G_", "")
        ne_id = f"{ne_prefix}-NODE-{self.rng.randint(100, 999)}"

        t0 = self.base_epoch + timedelta(hours=variant_idx, minutes=self.rng.randint(0, 59))
        t0_str = t0.isoformat().replace("+00:00", "Z")

        severity = self.calculate_severity(
            subscribers=subs,
            criticality=causal.service_criticality,
            redundancy=causal.redundancy_state,
            timing=causal.operational_timing,
            is_negative=is_negative,
        )

        support_tier, support_rationale = self.determine_support_level(
            runbook=causal.runbook_available,
            advanced_diag=causal.requires_advanced_diag,
            specialist=causal.requires_specialist,
            is_negative=is_negative,
        )

        title, desc = self._render_text(
            fam=scenario_family,
            template_id=template_id,
            ne_id=ne_id,
            region=region,
            subscribers=subs,
            causal=causal,
        )

        inc_id = f"SYN2-INC-{scenario_family}-{template_id}-{causal_config_id}-{self.seed}-{variant_idx:03d}"

        incident = {
            "schema_version": "1.0",
            "incident_id": inc_id,
            "title": title,
            "description": desc,
            "network_domain": tax["domain"],
            "fault_category": tax["category"],
            "severity": severity,
            "support_level_label": support_tier,
            "support_level_rationale": support_rationale,
            "affected_region": region,
            "affected_subscribers": subs,
            "network_element_ids": [ne_id],
            "created_at": t0_str,
            "resolved_at": None,
            "resolution_summary": None,
            "root_cause_confirmed": False,
            "source_type": SourceType.SYNTHETIC.value,
            "source_dataset": "PIIS-TelcoBench-v2",
            "source_record_id": f"syn2_{scenario_family.lower()}_{variant_idx}",
            "scenario_family_id": scenario_family,
            "split_group_id": f"{scenario_family}-{causal_config_id}",
            "annotation_status": "REVIEWED",
            "metadata": {
                "fault_subtype": tax["subtype"],
                "template_id": template_id,
                "causal_configuration_id": causal_config_id,
                "service_criticality": causal.service_criticality,
                "redundancy_state": causal.redundancy_state,
                "operational_timing": causal.operational_timing,
                "runbook_available": causal.runbook_available,
                "requires_advanced_diag": causal.requires_advanced_diag,
                "requires_specialist": causal.requires_specialist,
                "evidence_sufficient": not is_negative,
                "is_negative_control": is_negative,
            },
        }

        if validate:
            INCIDENT_VALIDATOR.validate(incident)

        return incident

    def generate_benchmark_v2(
        self,
        variants_per_combo: int = 5,
        validate: bool = True,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate balanced Train and Holdout Test benchmark partitions.

        Train Partition: Templates T1, T2 across C1, C2.
        Holdout Test Partition: Template T3 across C3 (zero template or causal overlap).
        """
        train_records = []
        test_records = []

        for fam in self.FAMILIES:
            # Training: T1 and T2 with C1 and C2
            for tmpl in ["T1", "T2"]:
                for c_cfg in ["C1", "C2"]:
                    for v in range(1, variants_per_combo + 1):
                        inc = self.generate_incident(
                            scenario_family=fam,
                            template_id=tmpl,
                            causal_config_id=c_cfg,
                            variant_idx=v,
                            validate=validate,
                        )
                        train_records.append(inc)

            # Holdout Test: T3 with C3 (held-out linguistic and causal configurations)
            for v in range(1, (variants_per_combo * 2) + 1):
                inc = self.generate_incident(
                    scenario_family=fam,
                    template_id="T3",
                    causal_config_id="C3",
                    variant_idx=v + 100,
                    validate=validate,
                )
                test_records.append(inc)

        return train_records, test_records
