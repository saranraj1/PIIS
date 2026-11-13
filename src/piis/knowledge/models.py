"""Data models for knowledge documents, sections, and structure-aware chunks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from piis.knowledge.sources import SourceType, TrustClassification
from piis.provenance import ProvenanceRecord


class DocumentSection(BaseModel):
    """Hierarchical section extracted from a knowledge document."""
    heading_path: List[str]
    heading_level: int
    title: str
    body: str
    warnings: List[str] = Field(default_factory=list)
    code_blocks: List[str] = Field(default_factory=list)
    substeps: List[str] = Field(default_factory=list)


class KnowledgeDocument(BaseModel):
    """Authoritative document registered in PIIS knowledge base."""
    doc_id: str
    source_id: str
    doc_type: SourceType
    trust_classification: TrustClassification
    title: str
    version: str = "1.0.0"
    network_domain: str
    target_subsystems: List[str] = Field(default_factory=list)
    severity_applicability: List[str] = Field(default_factory=list)
    technology_generation: Optional[str] = None
    vendor: Optional[str] = None
    equipment_family: Optional[str] = None
    raw_content: str
    checksum_sha256: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceRecord


class KnowledgeChunk(BaseModel):
    """Structure-aware atomic passage indexed for hybrid retrieval."""
    chunk_id: str
    doc_id: str
    source_id: str
    doc_title: str
    source_type: SourceType
    trust_classification: TrustClassification
    network_domain: str
    target_subsystems: List[str] = Field(default_factory=list)
    technology_generation: Optional[str] = None
    vendor: Optional[str] = None
    equipment_family: Optional[str] = None
    section_name: str
    heading_hierarchy: List[str] = Field(default_factory=list)
    content: str
    token_count: int
    has_diagnostic_commands: bool = False
    has_safety_warnings: bool = False
    safety_warnings: List[str] = Field(default_factory=list)
    checksum: str
    provenance: ProvenanceRecord
    metadata: Dict[str, Any] = Field(default_factory=dict)
