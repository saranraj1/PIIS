"""Unified multi-source incident, telemetry, and alarm ingestion pipeline for PIIS."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid
import jsonschema

from piis.integrations.contracts import (
    AdapterHealth,
    IngestionEnvelope,
    IngestionResult,
    IngestionStatus,
    IntegrationAdapter,
    IntegrationType,
)
from piis.pipeline.dead_letter import DeadLetterQueue
from piis.pipeline.deduplication import IdempotencyEngine
from piis.security.decoder import BoundedRecursiveDecoder
from piis.security.guardrails import RetrievalSecurityGuard


# Load Canonical Schemas
SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"

with (SCHEMA_DIR / "incident.schema.json").open("r", encoding="utf-8") as f:
    INCIDENT_SCHEMA = json.load(f)
with (SCHEMA_DIR / "telemetry.schema.json").open("r", encoding="utf-8") as f:
    TELEMETRY_SCHEMA = json.load(f)
with (SCHEMA_DIR / "alarm.schema.json").open("r", encoding="utf-8") as f:
    ALARM_SCHEMA = json.load(f)

INCIDENT_VALIDATOR = jsonschema.Draft202012Validator(INCIDENT_SCHEMA, format_checker=jsonschema.FormatChecker())
TELEMETRY_VALIDATOR = jsonschema.Draft202012Validator(TELEMETRY_SCHEMA, format_checker=jsonschema.FormatChecker())
ALARM_VALIDATOR = jsonschema.Draft202012Validator(ALARM_SCHEMA, format_checker=jsonschema.FormatChecker())


class UnifiedIngestionPipeline:
    """Orchestrates multi-source ingestion, security sanitization, deduplication, and normalization."""

    def __init__(
        self,
        idempotency_engine: Optional[IdempotencyEngine] = None,
        dead_letter_queue: Optional[DeadLetterQueue] = None,
        security_decoder: Optional[BoundedRecursiveDecoder] = None,
        security_guard: Optional[RetrievalSecurityGuard] = None,
    ):
        self.idempotency = idempotency_engine or IdempotencyEngine()
        self.dlq = dead_letter_queue or DeadLetterQueue()
        self.decoder = security_decoder or BoundedRecursiveDecoder()
        self.security_guard = security_guard or RetrievalSecurityGuard()

        self._lock = threading.RLock()
        self._adapters: Dict[str, IntegrationAdapter] = {}

        # Canonical In-Memory Repositories
        self._incidents: Dict[str, Dict[str, Any]] = {}
        self._telemetry: Dict[str, List[Dict[str, Any]]] = {}  # element_id -> list of observations
        self._alarms: Dict[str, List[Dict[str, Any]]] = {}     # element_id -> list of alarms
        self._lineage_records: Dict[str, Dict[str, Any]] = {}  # canonical_id -> lineage metadata
        self._investigations: Dict[str, Any] = {}              # incident_id -> InvestigationContext
        self._engine: Optional[Any] = None
        self._activity_events: List[Dict[str, Any]] = []
        self._ingested_events_count: int = 0
        self._seed_reference_activity()

    def _seed_reference_activity(self) -> None:
        """Seed initial local reference activity events for UI-7 demonstration."""
        now = datetime.now(timezone.utc)
        initial_events = [
            {
                "event_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
                "timestamp": now.isoformat(),
                "adapter_id": "OSS-ALARM-01",
                "source_system": "NokiaOSS",
                "event_type": "HEARTBEAT_CHECK",
                "status": "HEALTHY",
                "details": "Periodic 3GPP alarm broker heartbeat check: 0 active socket errors",
                "epistemic_tag": "REFERENCE_DATA",
            },
            {
                "event_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
                "timestamp": now.isoformat(),
                "adapter_id": "PROM-TELEM-01",
                "source_system": "Prometheus",
                "event_type": "METRIC_POLL",
                "status": "SUCCESS",
                "details": "Polled 24 RAN gNodeB cell vectors; all ratio dimensions within boundary",
                "epistemic_tag": "REFERENCE_DATA",
            },
            {
                "event_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
                "timestamp": now.isoformat(),
                "adapter_id": "SNOW-ITSM-01",
                "source_system": "ServiceNow",
                "event_type": "HEALTH_CHECK",
                "status": "HEALTHY",
                "details": "TLS 1.3 simulated health check: REST webhook ingress ready",
                "epistemic_tag": "REFERENCE_DATA",
            },
        ]
        self._activity_events.extend(initial_events)

    def record_activity(
        self,
        event_type: str,
        adapter_id: str,
        source_system: str,
        status: str,
        details: str,
        canonical_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        epistemic_tag: str = "SIMULATED_EVENT",
    ) -> Dict[str, Any]:
        """Record an integration activity event in the in-memory ring buffer."""
        with self._lock:
            event = {
                "event_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "adapter_id": adapter_id,
                "source_system": source_system,
                "event_type": event_type,
                "status": status,
                "details": details,
                "canonical_id": canonical_id,
                "envelope_id": envelope_id,
                "epistemic_tag": epistemic_tag,
            }
            self._activity_events.insert(0, event)
            if len(self._activity_events) > 500:
                self._activity_events.pop()
            return event

    def list_activity(
        self,
        limit: int = 50,
        offset: int = 0,
        adapter_id: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List paginated integration activities with optional filtering."""
        with self._lock:
            filtered = self._activity_events
            if adapter_id:
                aid = adapter_id.strip().lower()
                filtered = [e for e in filtered if aid in e.get("adapter_id", "").lower()]
            if event_type:
                et = event_type.strip().upper()
                filtered = [e for e in filtered if et in e.get("event_type", "").upper()]
            if status:
                st = status.strip().upper()
                filtered = [e for e in filtered if st in e.get("status", "").upper()]

            total = len(filtered)
            page = filtered[offset : offset + limit]
            return page, total

    def count_ingested_events(self) -> int:
        """Total number of successfully ingested events."""
        with self._lock:
            return self._ingested_events_count

    def _get_engine(self) -> Any:
        """Lazy load investigation engine to preserve startup latency."""
        if self._engine is None:
            from piis.investigation.engine import IncidentInvestigationEngine
            self._engine = IncidentInvestigationEngine()
        return self._engine

    def investigate_incident(self, incident_id: str) -> Optional[Any]:
        """Run M2-M5 investigation on a stored incident, correlating relevant alarms and telemetry."""
        incident = self.get_incident(incident_id)
        if not incident:
            return None

        # Gather relevant alarms
        elements = incident.get("network_element_ids", [])
        correlated_alarms: List[Dict[str, Any]] = []
        for elem in elements:
            correlated_alarms.extend(self.get_element_alarms(elem))

        # Build M3 intelligence structure
        m3_intelligence: Dict[str, Any] = {
            "active_alarms": correlated_alarms,
            "incident_domain": incident.get("network_domain", "CROSS_DOMAIN"),
        }

        engine = self._get_engine()
        ctx = engine.investigate(
            incident=incident,
            m3_network_intelligence=m3_intelligence,
        )

        with self._lock:
            self._investigations[incident_id] = ctx

        return ctx

    def get_investigation(self, incident_id: str) -> Optional[Any]:
        """Retrieve cached investigation context for an incident."""
        with self._lock:
            return self._investigations.get(incident_id)

    def register_adapter(self, adapter: IntegrationAdapter) -> None:
        """Register an integration adapter with the pipeline."""
        with self._lock:
            self._adapters[adapter.adapter_id] = adapter

    def get_adapter(self, adapter_id: str) -> Optional[IntegrationAdapter]:
        """Retrieve a registered adapter."""
        with self._lock:
            return self._adapters.get(adapter_id)

    def list_adapters(self) -> List[AdapterHealth]:
        """List health states of all registered adapters."""
        with self._lock:
            return [adapter.get_health() for adapter in self._adapters.values()]

    def ingest_envelope(self, envelope: IngestionEnvelope, adapter_id: Optional[str] = None) -> IngestionResult:
        """Process an incoming ingestion envelope through the unified pipeline."""
        # Step 1: Resolve adapter
        adapter = None
        with self._lock:
            if adapter_id:
                adapter = self._adapters.get(adapter_id)
            else:
                # Find matching adapter by source system
                for a in self._adapters.values():
                    if a.source_system.lower() == envelope.source_system.lower():
                        adapter = a
                        break

        if not adapter:
            err = f"No adapter found for source system: '{envelope.source_system}' (adapter_id: '{adapter_id}')"
            self.dlq.push(envelope, "NO_ADAPTER", err)
            self.record_activity(
                event_type="NO_ADAPTER",
                adapter_id="UNKNOWN",
                source_system=envelope.source_system,
                status="FAILED",
                details=err,
                envelope_id=envelope.envelope_id,
            )
            return IngestionResult(
                status=IngestionStatus.FAILED,
                envelope_id=envelope.envelope_id,
                error=err,
            )

        # Step 2: Rate Limiting Check
        if not adapter.rate_limiter.acquire(1.0):
            err = f"Rate limit exceeded for adapter '{adapter.adapter_id}'"
            self.dlq.push(envelope, "RATE_LIMITED", err)
            self.record_activity(
                event_type="RATE_LIMITED",
                adapter_id=adapter.adapter_id,
                source_system=envelope.source_system,
                status="QUARANTINED",
                details=err,
                envelope_id=envelope.envelope_id,
            )
            return IngestionResult(
                status=IngestionStatus.RATE_LIMITED,
                envelope_id=envelope.envelope_id,
                error=err,
            )

        # Step 3: Deduplication / Idempotency Check
        dedup_key = self.idempotency.compute_key(
            source_system=envelope.source_system,
            external_event_id=envelope.external_event_id,
            raw_payload=envelope.raw_payload,
        )
        is_dup, existing_canonical_id = self.idempotency.check_and_record(dedup_key)
        if is_dup:
            self.record_activity(
                event_type="DUPLICATE_DETECTED",
                adapter_id=adapter.adapter_id,
                source_system=envelope.source_system,
                status="DUPLICATE",
                details=f"Duplicate event matched canonical ID '{existing_canonical_id}'",
                canonical_id=existing_canonical_id,
                envelope_id=envelope.envelope_id,
            )
            return IngestionResult(
                status=IngestionStatus.DUPLICATE,
                envelope_id=envelope.envelope_id,
                canonical_id=existing_canonical_id,
                message=f"Duplicate event detected for key '{dedup_key}'",
                is_duplicate=True,
            )

        # Step 4: Security Inspection on raw text fields
        self._sanitize_envelope_strings(envelope)

        # Step 5: Normalize Payload via Adapter
        try:
            canonical_record = adapter.normalize(envelope)
        except Exception as e:
            adapter.record_failure(e)
            self.idempotency.remove(dedup_key)
            err = f"Normalization failed in adapter '{adapter.adapter_id}': {str(e)}"
            self.dlq.push(envelope, "NORMALIZATION_ERROR", err)
            self.record_activity(
                event_type="NORMALIZATION_FAILED",
                adapter_id=adapter.adapter_id,
                source_system=envelope.source_system,
                status="FAILED",
                details=err,
                envelope_id=envelope.envelope_id,
            )
            return IngestionResult(
                status=IngestionStatus.FAILED,
                envelope_id=envelope.envelope_id,
                error=err,
            )

        # Step 6: Validate against Canonical Schema
        val_status, val_error = self._validate_canonical_record(adapter.adapter_type, canonical_record)
        if not val_status:
            adapter.record_failure(Exception(val_error))
            self.idempotency.remove(dedup_key)
            self.dlq.push(envelope, "SCHEMA_VALIDATION_ERROR", val_error)
            self.record_activity(
                event_type="VALIDATION_FAILED",
                adapter_id=adapter.adapter_id,
                source_system=envelope.source_system,
                status="FAILED",
                details=val_error,
                envelope_id=envelope.envelope_id,
            )
            return IngestionResult(
                status=IngestionStatus.VALIDATION_FAILED,
                envelope_id=envelope.envelope_id,
                error=val_error,
            )

        # Step 7: Store Record and Record Lineage
        canonical_id = self._store_canonical_record(adapter.adapter_type, canonical_record, envelope)
        self.idempotency.update_canonical_id(dedup_key, canonical_id)
        with self._lock:
            self._ingested_events_count += 1

        self.record_activity(
            event_type="INGESTION_SUCCESS",
            adapter_id=adapter.adapter_id,
            source_system=envelope.source_system,
            status="SUCCESS",
            details=f"Normalized and stored canonical {adapter.adapter_type.value} record '{canonical_id}'",
            canonical_id=canonical_id,
            envelope_id=envelope.envelope_id,
        )

        return IngestionResult(
            status=IngestionStatus.SUCCESS,
            envelope_id=envelope.envelope_id,
            canonical_id=canonical_id,
            message="Event ingested and normalized successfully",
            is_duplicate=False,
            details={"adapter_type": adapter.adapter_type.value},
        )

    def _sanitize_envelope_strings(self, envelope: IngestionEnvelope) -> None:
        """Scan and defang prompt injections, null bytes, and malicious scripts in ticket text."""
        p = envelope.raw_payload
        for k in ["short_description", "description", "summary", "notes"]:
            if k in p and isinstance(p[k], str):
                dec_res = self.decoder.decode(p[k])
                raw_decoded = dec_res.final_text
                flags = self.security_guard.scan_content(raw_decoded)
                neutralized = self.security_guard.neutralize_content(raw_decoded, flags)
                p[k] = neutralized

    def _validate_canonical_record(
        self,
        adapter_type: IntegrationType,
        record: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Validate canonical record against corresponding schema."""
        if adapter_type == IntegrationType.ITSM:
            validator = INCIDENT_VALIDATOR
        elif adapter_type == IntegrationType.TELEMETRY:
            validator = TELEMETRY_VALIDATOR
        elif adapter_type == IntegrationType.OSS_NMS_ALARM:
            validator = ALARM_VALIDATOR
        else:
            return True, ""

        errors = list(validator.iter_errors(record))
        if errors:
            msg = "; ".join(f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors)
            return False, f"Schema validation error: {msg}"
        return True, ""

    def _store_canonical_record(
        self,
        adapter_type: IntegrationType,
        record: Dict[str, Any],
        envelope: IngestionEnvelope,
    ) -> str:
        """Store validated record in canonical repository and record lineage."""
        with self._lock:
            if adapter_type == IntegrationType.ITSM:
                canonical_id = record["incident_id"]
                self._incidents[canonical_id] = record
            elif adapter_type == IntegrationType.TELEMETRY:
                canonical_id = record["observation_id"]
                element_id = record["network_element_id"]
                if element_id not in self._telemetry:
                    self._telemetry[element_id] = []
                self._telemetry[element_id].append(record)
            elif adapter_type == IntegrationType.OSS_NMS_ALARM:
                canonical_id = record["alarm_id"]
                element_id = record["network_element_id"]
                if element_id not in self._alarms:
                    self._alarms[element_id] = []
                self._alarms[element_id].append(record)
            else:
                canonical_id = f"REC-{envelope.envelope_id}"

            # Store explicit provenance lineage
            self._lineage_records[canonical_id] = {
                "canonical_id": canonical_id,
                "envelope_id": envelope.envelope_id,
                "source_system": envelope.source_system,
                "source_type": envelope.source_type,
                "external_event_id": envelope.external_event_id,
                "observation_timestamp": envelope.observation_timestamp,
                "ingested_at": envelope.ingested_at,
            }
            return canonical_id

    # Repository Accessors
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve canonical incident record."""
        with self._lock:
            return self._incidents.get(incident_id)

    def list_incidents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List canonical incidents sorted by creation date."""
        with self._lock:
            records = sorted(
                self._incidents.values(),
                key=lambda x: str(x.get("created_at", "")),
                reverse=True,
            )
            return records[offset : offset + limit]

    def count_incidents(self) -> int:
        """Total number of stored incidents."""
        with self._lock:
            return len(self._incidents)

    def get_element_telemetry(self, element_id: str) -> List[Dict[str, Any]]:
        """Retrieve telemetry observations for a specific network element."""
        with self._lock:
            return list(self._telemetry.get(element_id, []))

    def get_element_alarms(self, element_id: str) -> List[Dict[str, Any]]:
        """Retrieve alarms for a specific network element."""
        with self._lock:
            return list(self._alarms.get(element_id, []))

    def get_lineage(self, canonical_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lineage metadata for a record."""
        with self._lock:
            return self._lineage_records.get(canonical_id)

    def replay_dead_letter(self, item_id: str) -> IngestionResult:
        """Attempt audited replay of a dead-letter queue envelope."""
        with self._lock:
            dlq_item = self.dlq.get(item_id)
            if not dlq_item:
                return IngestionResult(
                    status=IngestionStatus.FAILED,
                    envelope_id="",
                    error=f"Dead-letter item '{item_id}' not found",
                )

            if dlq_item.attempt_count >= self.dlq.MAX_REPLAY_ATTEMPTS:
                self.dlq.update_status(item_id, "PERMANENTLY_FAILED", "Maximum replay attempts exceeded")
                return IngestionResult(
                    status=IngestionStatus.FAILED,
                    envelope_id=dlq_item.envelope.envelope_id,
                    error=f"Dead-letter item '{item_id}' exceeded maximum replay attempts ({self.dlq.MAX_REPLAY_ATTEMPTS})",
                )

            res = self.ingest_envelope(dlq_item.envelope)
            if res.status in {IngestionStatus.SUCCESS, IngestionStatus.DUPLICATE}:
                self.dlq.remove(item_id)
                self.record_activity(
                    event_type="DEAD_LETTER_REPLAY",
                    adapter_id=dlq_item.envelope.source_system,
                    source_system=dlq_item.envelope.source_system,
                    status="SUCCESS",
                    details=f"Dead-letter item '{item_id}' replayed successfully",
                    canonical_id=res.canonical_id,
                    envelope_id=dlq_item.envelope.envelope_id,
                )
            else:
                self.dlq.update_status(item_id, "FAILED", res.error)
                self.record_activity(
                    event_type="DEAD_LETTER_REPLAY",
                    adapter_id=dlq_item.envelope.source_system,
                    source_system=dlq_item.envelope.source_system,
                    status="FAILED",
                    details=f"Dead-letter replay failed: {res.error}",
                    envelope_id=dlq_item.envelope.envelope_id,
                )
            return res
