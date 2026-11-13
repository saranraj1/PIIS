"""Unit tests for knowledge source governance and structure-aware document chunking."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from piis.knowledge.chunker import StructureAwareChunker
from piis.knowledge.models import KnowledgeDocument
from piis.knowledge.sources import KnowledgeSourceRegistry, SourceType, TrustClassification
from piis.provenance import ProvenanceRecord


def test_knowledge_source_registry_quarantine_synthetic():
    registry = KnowledgeSourceRegistry()

    # Synthetic source must automatically receive BENCHMARK_ONLY trust classification
    meta = registry.register_source(
        source_id="SRC-TELCOBENCH-V2",
        source_type=SourceType.SYNTHETIC_BENCHMARK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,  # Attempting high trust
        title="PIIS-TelcoBench-v2 Evaluation Incidents",
        original_location="data/processed/incidents/synthetic_v2.jsonl",
    )
    assert meta.source_type == SourceType.SYNTHETIC_BENCHMARK
    assert meta.trust_classification == TrustClassification.BENCHMARK_ONLY


def test_knowledge_source_registry_file_sha256():
    registry = KnowledgeSourceRegistry()
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as tmp:
        tmp.write("# Test SOP Document\nDiagnostic steps.")
        tmp_path = Path(tmp.name)

    try:
        expected_sha = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        meta = registry.register_source(
            source_id="SRC-TEST-001",
            source_type=SourceType.APPROVED_RUNBOOK,
            trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
            title="Test SOP",
            original_location=str(tmp_path),
            file_path=tmp_path,
        )
        assert meta.sha256 == expected_sha
        assert registry.verify_integrity("SRC-TEST-001", tmp_path) is True
    finally:
        tmp_path.unlink()


def test_structure_aware_chunker_hierarchy_and_warnings():
    chunker = StructureAwareChunker(target_tokens=100, max_tokens=200, overlap_tokens=20)

    sample_doc_content = """# SOP-RAN-VSWR-001: Antenna VSWR High Fault Resolution

## 1. Symptoms & Initial Verification
High Voltage Standing Wave Ratio detected on antenna feedline.
Alarm code: ALM-RAN-VSWR-HIGH.
RSRP drops by > 15 dB in sector coverage.

> [!WARNING]
> DANGER: High RF Radiation. De-energize sector radio before physical inspection.

## 2. Diagnostic Procedure
Execute diagnostic commands from OSS terminal:
```bash
sri -rru 1 get vswr
sri -rru 1 get tx-power
```
Step 1: Check return loss reading. Threshold must be > 15 dB.
Step 2: Inspect jumper cable connectors for water ingress.
Step 3: Test feeder line with Site Master antenna analyzer.

## 3. Remediation & Rollback
If return loss is below 14 dB, replace the damaged jumper cable.
Once replaced, re-energize sector and verify VSWR return loss improves to > 18 dB.
Rollback: If new jumper fails to seat, reinstall original cable and engage field riggers.
"""
    doc = KnowledgeDocument(
        doc_id="SOP-RAN-VSWR-001",
        source_id="SRC-SOP-RAN",
        doc_type=SourceType.APPROVED_RUNBOOK,
        trust_classification=TrustClassification.HIGH_TRUST_APPROVED,
        title="Antenna VSWR High Fault Resolution",
        version="1.0.0",
        network_domain="RAN",
        target_subsystems=["gNodeB", "AAU", "Feeder"],
        severity_applicability=["CRITICAL", "MAJOR"],
        raw_content=sample_doc_content,
        checksum_sha256=hashlib.sha256(sample_doc_content.encode()).hexdigest(),
        provenance=ProvenanceRecord(
            source_type=SourceType.APPROVED_RUNBOOK,
            source_dataset="SRC-SOP-RAN",
            source_record_id="SOP-RAN-VSWR-001",
        ),
    )

    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 3

    # Verify section preservation
    sections = [c.section_name for c in chunks]
    assert any("Symptoms" in s for s in sections)
    assert any("Diagnostic" in s for s in sections)
    assert any("Remediation" in s for s in sections)

    # Verify heading hierarchy
    diag_chunk = next(c for c in chunks if "Diagnostic" in c.section_name)
    assert "SOP-RAN-VSWR-001: Antenna VSWR High Fault Resolution" in diag_chunk.heading_hierarchy
    assert "2. Diagnostic Procedure" in diag_chunk.heading_hierarchy
    assert diag_chunk.has_diagnostic_commands is True

    # Verify warnings preserved
    symptoms_chunk = next(c for c in chunks if "Symptoms" in c.section_name)
    assert symptoms_chunk.has_safety_warnings is True
    assert any("High RF Radiation" in w for w in symptoms_chunk.safety_warnings)

    # Verify chunk IDs are deterministic
    chunks2 = chunker.chunk_document(doc)
    assert [c.chunk_id for c in chunks] == [c.chunk_id for c in chunks2]
