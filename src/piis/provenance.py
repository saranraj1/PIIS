"""Data provenance models and validation helpers for PIIS records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class SourceType(str, Enum):
    """Canonical provenance classification for all records."""
    PUBLIC_REAL = "PUBLIC_REAL"
    SYNTHETIC = "SYNTHETIC"
    DERIVED = "DERIVED"
    HUMAN_ANNOTATED = "HUMAN_ANNOTATED"
    OPERATOR_INTERNAL = "OPERATOR_INTERNAL"


@dataclass(frozen=True)
class ProvenanceRecord:
    """Immutable audit tracking block attached to normalized records."""
    source_type: SourceType
    source_dataset: str
    source_record_id: str
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    transformation_version: str = "1.0.0"
    original_timezone: Optional[str] = None
    checksum_sha256: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert provenance metadata to dictionary for JSON serialization."""
        return {
            "source_type": self.source_type.value,
            "source_dataset": self.source_dataset,
            "source_record_id": self.source_record_id,
            "ingested_at": self.ingested_at,
            "transformation_version": self.transformation_version,
            "original_timezone": self.original_timezone,
            "checksum_sha256": self.checksum_sha256,
            "metadata": dict(self.metadata),
        }
