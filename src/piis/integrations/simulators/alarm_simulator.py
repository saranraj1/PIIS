"""Simulated OSS/NMS alarm stream generator emitting vendor-specific and 3GPP alarms."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


class SimulatedAlarmBroker:
    """Mock alarm broker simulating real-time Kafka or REST webhook alarms from OSS/NMS."""

    def __init__(self):
        self.active_alarms: Dict[str, Dict[str, Any]] = {}

    def emit_vswr_alarm(self, element_id: str = "GNB-RAN-701", vendor: str = "NOKIA") -> Dict[str, Any]:
        """Emit a high VSWR alarm on a radio antenna element."""
        alarm_id = f"ALM-{uuid.uuid4().hex[:8].upper()}"
        vendor_code = "7100" if vendor == "NOKIA" else ("A102" if vendor == "ERICSSON" else "ALM-26241")
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        alarm = {
            "alarm_id": alarm_id,
            "element_id": element_id,
            "domain": "RAN",
            "vendor": vendor,
            "alarm_code": vendor_code,
            "severity": "MAJOR",
            "probable_cause": "Antenna and feeder transmission line VSWR above threshold",
            "timestamp": now_iso,
            "lifecycle": "ACTIVE",
            "site_id": "SITE-NORTH-04",
            "cell_id": "CELL-5G-01",
        }
        self.active_alarms[alarm_id] = alarm
        return alarm

    def emit_core_drop_alarm(self, element_id: str = "UPF-CORE-01") -> Dict[str, Any]:
        """Emit a core packet loss / session drop alarm."""
        alarm_id = f"ALM-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        alarm = {
            "alarm_id": alarm_id,
            "element_id": element_id,
            "domain": "CORE",
            "vendor": "GENERIC",
            "alarm_code": "ALM-CORE-SESSION-DROP-HIGH",
            "severity": "CRITICAL",
            "probable_cause": "GTP-U tunnel packet drop threshold exceeded",
            "timestamp": now_iso,
            "lifecycle": "ACTIVE",
        }
        self.active_alarms[alarm_id] = alarm
        return alarm

    def clear_alarm(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Emit alarm clear event."""
        if alarm_id not in self.active_alarms:
            return None
        alarm = self.active_alarms.pop(alarm_id)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        alarm["lifecycle"] = "CLEARED"
        alarm["clear_timestamp"] = now_iso
        return alarm
