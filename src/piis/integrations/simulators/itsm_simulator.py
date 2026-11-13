"""Simulated external ITSM service (ServiceNow & Jira Service Management) for M6 integration testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import uuid


class SimulatedITSMPlatform:
    """Mock enterprise ITSM server generating realistic telecom incident tickets."""

    def __init__(self, failure_rate: float = 0.0, rate_limit_threshold: int = 100):
        self.failure_rate = failure_rate
        self.rate_limit_threshold = rate_limit_threshold
        self.request_count = 0
        self.tickets: Dict[str, Dict[str, Any]] = {}
        self._seed_sample_tickets()

    def _seed_sample_tickets(self) -> None:
        """Seed representative telecom incident records."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.tickets["INC0089201"] = {
            "sys_id": "a98df7b01b827300c0147596cc4bcb11",
            "number": "INC0089201",
            "short_description": "Sector degraded: High VSWR on 5G NR Cell-1",
            "description": "NOC telemetry indicates RF feeder mismatch and VSWR > 1.8 on gNodeB GNB-RAN-701.",
            "priority": "2",
            "urgency": "2",
            "impact": "2",
            "category": "RAN",
            "u_network_domain": "RAN",
            "cmdb_ci": "GNB-RAN-701",
            "state": "1",
            "sys_created_on": now_str,
            "assignment_group": "Tier-1 RAN Operations",
            "location": "North-Region-Substation-04",
            "u_affected_subscribers": 1420,
            "u_fault_category": "antenna_vswr_fault",
        }
        self.tickets["INC0089202"] = {
            "sys_id": "b12cf8e02c918400d0258607dd5cdc22",
            "number": "INC0089202",
            "short_description": "Core 5G UPF session drops and high forwarding latency",
            "description": "Sustained session drops on UPF-CORE-01 exceeding 12% drop ratio over 15 minutes.",
            "priority": "1",
            "urgency": "1",
            "impact": "1",
            "category": "Core Network",
            "u_network_domain": "5G_CORE",
            "cmdb_ci": "UPF-CORE-01",
            "state": "1",
            "sys_created_on": now_str,
            "assignment_group": "Tier-2 Core Operations",
            "location": "Central-DC-Zone-1",
            "u_affected_subscribers": 8900,
            "u_fault_category": "upf_session_drop",
        }

    def fetch_servicenow_incidents(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Simulate ServiceNow Table API GET /api/now/table/incident."""
        self.request_count += 1
        if self.request_count > self.rate_limit_threshold:
            raise ConnectionError("HTTP 429: Too Many Requests (Rate limit exceeded)")

        all_records = list(self.tickets.values())
        page = all_records[offset : offset + limit]
        return {
            "result": page,
            "total_count": len(all_records),
            "offset": offset,
            "limit": limit,
        }

    def fetch_jira_issues(self, jql: str = "project = NOC", max_results: int = 10) -> Dict[str, Any]:
        """Simulate Jira Service Management REST API GET /rest/api/3/search."""
        self.request_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        issues = [
            {
                "id": "10452",
                "key": "NOC-452",
                "fields": {
                    "summary": "Optical transponder frame slip on IP backhaul router",
                    "description": "Bit error rate degradation observed on 100G link CSR-ROUTER-99.",
                    "created": now_iso,
                    "priority": {"name": "High"},
                    "status": {"name": "Open"},
                    "labels": ["TRANSPORT", "OPTICAL"],
                    "components": [{"name": "CSR-ROUTER-99"}],
                    "issuetype": {"name": "Incident"},
                },
            }
        ]
        return {"issues": issues, "total": len(issues)}

    def emit_new_incident(self, domain: str = "RAN", severity_code: str = "2") -> Dict[str, Any]:
        """Dynamically generate a new synthetic ticket for stream testing."""
        num = f"INC{uuid.uuid4().int % 900000 + 100000}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "sys_id": uuid.uuid4().hex,
            "number": num,
            "short_description": f"Automated test fault on {domain} node",
            "description": f"Synthetic incident event created for integration verification in {domain}.",
            "priority": severity_code,
            "u_network_domain": domain,
            "cmdb_ci": f"{domain}-NODE-{num[-3:]}",
            "state": "1",
            "sys_created_on": now_str,
            "u_affected_subscribers": 500,
        }
        self.tickets[num] = record
        return record
