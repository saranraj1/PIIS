"""Base contracts, data classes, and abstract interfaces for external telecom integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import time
import uuid


class ReadOnlyBoundaryViolationError(RuntimeError):
    """Raised when any code attempts to invoke an unauthorized mutative production command."""
    pass


class IntegrationType(str, Enum):
    """Categorization of external telecom integration systems."""
    ITSM = "ITSM"
    TELEMETRY = "TELEMETRY"
    OSS_NMS_ALARM = "OSS_NMS_ALARM"


class IntegrationStatusLabel(str, Enum):
    """Qualification status for telecom enterprise integrations in portfolio/research mode."""
    LOCALLY_VERIFIED = "LOCALLY VERIFIED"
    SIMULATED = "SIMULATED"
    CONTRACT_TESTED = "CONTRACT TESTED"
    EXTERNALLY_UNVERIFIED = "EXTERNALLY UNVERIFIED"


class IngestionStatus(str, Enum):
    """Status outcomes for an event ingestion attempt."""
    SUCCESS = "SUCCESS"
    DUPLICATE = "DUPLICATE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    FAILED = "FAILED"


class HealthState(str, Enum):
    """Operational health state of an integration adapter."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class AdapterHealth:
    """Health check status representation for an integration adapter."""
    adapter_id: str
    adapter_type: IntegrationType
    state: HealthState
    last_heartbeat: str
    last_successful_ingestion: Optional[str] = None
    consecutive_failures: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionEnvelope:
    """Raw ingestion envelope preserving full source-system lineage and timestamps."""
    envelope_id: str
    source_system: str
    source_type: str
    raw_payload: Dict[str, Any]
    ingested_at: str
    external_event_id: Optional[str] = None
    observation_timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        source_system: str,
        source_type: str,
        raw_payload: Dict[str, Any],
        external_event_id: Optional[str] = None,
        observation_timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionEnvelope:
        return cls(
            envelope_id=f"ENV-{uuid.uuid4().hex[:12].upper()}",
            source_system=source_system,
            source_type=source_type,
            raw_payload=raw_payload,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            external_event_id=external_event_id,
            observation_timestamp=observation_timestamp,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IngestionEnvelope:
        """Reconstruct envelope from serialized dictionary."""
        return cls(
            envelope_id=data["envelope_id"],
            source_system=data["source_system"],
            source_type=data["source_type"],
            raw_payload=data.get("raw_payload", {}),
            ingested_at=data["ingested_at"],
            external_event_id=data.get("external_event_id"),
            observation_timestamp=data.get("observation_timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class IngestionResult:
    """Outcome of processing an ingestion envelope."""
    status: IngestionStatus
    envelope_id: str
    canonical_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None
    is_duplicate: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeadLetterItem:
    """Failed ingestion payload routed to the dead-letter queue for operator inspection."""
    item_id: str
    envelope: IngestionEnvelope
    failure_reason: str
    error_details: str
    attempt_count: int
    first_failed_at: str
    last_failed_at: str
    replay_status: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        """Convert dead letter item to serializable dictionary."""
        return {
            "item_id": self.item_id,
            "envelope": self.envelope.to_dict(),
            "failure_reason": self.failure_reason,
            "error_details": self.error_details,
            "attempt_count": self.attempt_count,
            "first_failed_at": self.first_failed_at,
            "last_failed_at": self.last_failed_at,
            "replay_status": self.replay_status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DeadLetterItem:
        """Reconstruct dead letter item from serialized dictionary."""
        return cls(
            item_id=data["item_id"],
            envelope=IngestionEnvelope.from_dict(data["envelope"]),
            failure_reason=data["failure_reason"],
            error_details=data["error_details"],
            attempt_count=int(data.get("attempt_count", 1)),
            first_failed_at=data["first_failed_at"],
            last_failed_at=data["last_failed_at"],
            replay_status=data.get("replay_status", "PENDING"),
        )


class RateLimiter:
    """Token bucket rate limiter for external integration calls."""

    def __init__(self, requests_per_second: float = 20.0, burst: int = 50):
        self.rate = requests_per_second
        self.burst = float(burst)
        self.tokens = float(burst)
        self.last_update = time.monotonic()

    def acquire(self, tokens: float = 1.0) -> bool:
        """Check if request is allowed under rate limits."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class IntegrationAdapter(ABC):
    """Abstract base class for all enterprise telecom integration adapters.
    
    LOCKED OPERATIONAL BOUNDARY:
    All adapters are strictly read-only and ingestive. Adapters only perform inbound
    data mapping and schema normalization. They are architecturally barred from issuing
    outbound command executions, ticket modifications, or configuration changes.
    """

    ALLOWED_OPERATIONS = frozenset(["NORMALIZE", "HEALTH_CHECK", "READ_ONLY_INGEST"])
    FORBIDDEN_OPERATIONS = frozenset([
        "CREATE_TICKET",
        "UPDATE_TICKET",
        "CLOSE_TICKET",
        "ASSIGN_TICKET",
        "EXECUTE_COMMAND",
        "MODIFY_CONFIG",
        "REBOOT_ELEMENT",
        "SEND_COMMUNICATION",
    ])

    # Explicit capability flags (enforced across all adapters)
    READ_ONLY: bool = True
    MUTATION_ALLOWED: bool = False
    SAFE_HTTP_METHODS: frozenset[str] = frozenset(["GET", "HEAD"])
    DEFAULT_STATUS_LABELS: tuple[str, ...] = (
        IntegrationStatusLabel.LOCALLY_VERIFIED.value,
        IntegrationStatusLabel.SIMULATED.value,
        IntegrationStatusLabel.CONTRACT_TESTED.value,
        IntegrationStatusLabel.EXTERNALLY_UNVERIFIED.value,
    )

    def __init__(
        self,
        adapter_id: str,
        adapter_type: IntegrationType,
        source_system: str,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.adapter_id = adapter_id
        self.adapter_type = adapter_type
        self.source_system = source_system
        self.rate_limiter = rate_limiter or RateLimiter()
        self.is_read_only = True
        self.mutation_allowed = False
        self.status_labels = list(self.DEFAULT_STATUS_LABELS)
        self.health = AdapterHealth(
            adapter_id=adapter_id,
            adapter_type=adapter_type,
            state=HealthState.HEALTHY,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )

    def validate_http_method(self, method: str) -> None:
        """Enforce outbound HTTP safety: only safe, idempotent methods (GET, HEAD) are allowed."""
        m_upper = method.upper().strip()
        if m_upper not in self.SAFE_HTTP_METHODS:
            raise ReadOnlyBoundaryViolationError(
                f"HTTP method '{method}' violates the strict read-only telecom operational boundary. "
                "Only safe, idempotent read-only methods (GET, HEAD) are permitted. "
                "Mutative methods (POST, PUT, PATCH, DELETE) to external operations are strictly prohibited."
            )

    def enforce_read_only_boundary(self, operation_name: str) -> None:
        """Enforce that only read-only normalization operations are permitted."""
        op_upper = operation_name.upper().strip()
        if op_upper in self.FORBIDDEN_OPERATIONS or op_upper not in self.ALLOWED_OPERATIONS:
            raise ReadOnlyBoundaryViolationError(
                f"Operation '{operation_name}' violates the strict read-only telecom operational boundary. "
                "PIIS is strictly barred from modifying tickets, configuring network elements, or executing commands."
            )

    def record_success(self) -> None:
        """Update health status on successful operation."""
        now_str = datetime.now(timezone.utc).isoformat()
        self.health.state = HealthState.HEALTHY
        self.health.last_heartbeat = now_str
        self.health.last_successful_ingestion = now_str
        self.health.consecutive_failures = 0
        self.health.error_message = None

    def record_failure(self, error: Exception) -> None:
        """Update health status on operation failure."""
        now_str = datetime.now(timezone.utc).isoformat()
        self.health.last_heartbeat = now_str
        self.health.consecutive_failures += 1
        self.health.error_message = str(error)
        if self.health.consecutive_failures >= 3:
            self.health.state = HealthState.UNHEALTHY
        else:
            self.health.state = HealthState.DEGRADED

    def get_health(self) -> AdapterHealth:
        """Return current health status."""
        self.health.last_heartbeat = datetime.now(timezone.utc).isoformat()
        return self.health

    @abstractmethod
    def normalize(self, envelope: IngestionEnvelope) -> Dict[str, Any]:
        """Normalize raw external payload into PIIS canonical representation."""
        pass
