"""Knowledge source registry, provenance classification, and governance contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from piis.provenance import ProvenanceRecord


class SourceType(str, Enum):
    """Canonical classification for knowledge sources."""
    APPROVED_RUNBOOK = "APPROVED_RUNBOOK"                  # Engineering-vetted SOPs
    HISTORICAL_INCIDENT = "HISTORICAL_INCIDENT"            # Genuine closed incident postmortems & tickets
    PUBLIC_TECHNICAL_REFERENCE = "PUBLIC_TECHNICAL_REFERENCE" # 3GPP specs, IEEE standards, RFCs
    SYNTHETIC_BENCHMARK = "SYNTHETIC_BENCHMARK"            # Synthetic benchmark scenarios (quarantined)
    DERIVED_RECORD = "DERIVED_RECORD"                      # Aggregated or transformed records


class TrustClassification(str, Enum):
    """Trust hierarchy for retrieval filtering and execution gating."""
    HIGH_TRUST_APPROVED = "HIGH_TRUST_APPROVED"            # Vetted by principal engineering
    MEDIUM_TRUST_VERIFIED = "MEDIUM_TRUST_VERIFIED"        # Verified closed incident tickets
    LOW_TRUST_UNCURATED = "LOW_TRUST_UNCURATED"            # Unvetted operator text / draft notes
    BENCHMARK_ONLY = "BENCHMARK_ONLY"                      # Strictly for evaluation, not production


class IngestionStatus(str, Enum):
    """Lifecycle state of a registered source document."""
    REGISTERED = "REGISTERED"
    PARSED = "PARSED"
    INDEXED = "INDEXED"
    QUARANTINED = "QUARANTINED"
    DEPRECATED = "DEPRECATED"


@dataclass
class SourceMetadata:
    """Immutable governance metadata block for knowledge documents."""
    source_id: str
    source_type: SourceType
    trust_classification: TrustClassification
    title: str
    original_location: str
    version: str = "1.0.0"
    publication_date: Optional[str] = None
    access_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    license: str = "PROPRIETARY_INTERNAL"
    usage_restrictions: str = "Internal operations only"
    sha256: str = ""
    ingestion_status: IngestionStatus = IngestionStatus.REGISTERED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_provenance(self, record_id: str, transformation: str = "1.0.0") -> ProvenanceRecord:
        """Derive standard PIIS ProvenanceRecord from source metadata."""
        # Map source_type to base provenance SourceType
        from piis.provenance import SourceType as BaseSourceType

        mapping = {
            SourceType.APPROVED_RUNBOOK: BaseSourceType.PUBLIC_REAL,
            SourceType.HISTORICAL_INCIDENT: BaseSourceType.PUBLIC_REAL,
            SourceType.PUBLIC_TECHNICAL_REFERENCE: BaseSourceType.PUBLIC_REAL,
            SourceType.SYNTHETIC_BENCHMARK: BaseSourceType.SYNTHETIC,
            SourceType.DERIVED_RECORD: BaseSourceType.DERIVED,
        }
        base_type = mapping.get(self.source_type, BaseSourceType.DERIVED)

        return ProvenanceRecord(
            source_type=base_type,
            source_dataset=self.source_id,
            source_record_id=record_id,
            transformation_version=transformation,
            checksum_sha256=self.sha256,
            metadata={
                "source_type": self.source_type.value,
                "trust_classification": self.trust_classification.value,
                "license": self.license,
                "version": self.version,
            },
        )


class KnowledgeSourceRegistry:
    """Authoritative registry for all ingestible knowledge sources in PIIS."""

    def __init__(self):
        self._sources: Dict[str, SourceMetadata] = {}

    def register_source(
        self,
        source_id: str,
        source_type: SourceType,
        trust_classification: TrustClassification,
        title: str,
        original_location: str,
        version: str = "1.0.0",
        publication_date: Optional[str] = None,
        license: str = "PROPRIETARY_INTERNAL",
        usage_restrictions: str = "Internal operations only",
        file_path: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SourceMetadata:
        """Register a knowledge source with SHA-256 integrity verification."""
        sha256_hash = ""
        if file_path and file_path.exists():
            sha256_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

        # Enforce quarantine for synthetic benchmark data
        if source_type == SourceType.SYNTHETIC_BENCHMARK:
            trust_classification = TrustClassification.BENCHMARK_ONLY

        meta = SourceMetadata(
            source_id=source_id,
            source_type=source_type,
            trust_classification=trust_classification,
            title=title,
            original_location=original_location,
            version=version,
            publication_date=publication_date,
            license=license,
            usage_restrictions=usage_restrictions,
            sha256=sha256_hash,
            metadata=metadata or {},
        )
        self._sources[source_id] = meta
        return meta

    def get_source(self, source_id: str) -> Optional[SourceMetadata]:
        """Retrieve registered metadata for a source ID."""
        return self._sources.get(source_id)

    def list_sources(
        self,
        source_type: Optional[SourceType] = None,
        trust_classification: Optional[TrustClassification] = None,
    ) -> List[SourceMetadata]:
        """List registered sources matching optional classification filters."""
        results = list(self._sources.values())
        if source_type:
            results = [s for s in results if s.source_type == source_type]
        if trust_classification:
            results = [s for s in results if s.trust_classification == trust_classification]
        return results

    def verify_integrity(self, source_id: str, file_path: Path) -> bool:
        """Verify file matches the registered SHA-256 digest."""
        meta = self.get_source(source_id)
        if not meta or not meta.sha256:
            return False
        computed = hashlib.sha256(file_path.read_bytes()).hexdigest()
        return computed == meta.sha256
