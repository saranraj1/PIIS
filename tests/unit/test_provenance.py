"""Unit tests for provenance models and governance rules."""

import pytest
from piis.provenance import SourceType, ProvenanceRecord


def test_source_type_enum():
    assert SourceType.PUBLIC_REAL.value == "PUBLIC_REAL"
    assert SourceType.SYNTHETIC.value == "SYNTHETIC"
    assert SourceType.DERIVED.value == "DERIVED"
    assert SourceType.HUMAN_ANNOTATED.value == "HUMAN_ANNOTATED"
    assert SourceType.OPERATOR_INTERNAL.value == "OPERATOR_INTERNAL"


def test_provenance_record_immutability():
    prov = ProvenanceRecord(
        source_type=SourceType.PUBLIC_REAL,
        source_dataset="test_repo",
        source_record_id="row_42",
        original_timezone="UTC",
    )
    assert prov.source_type == SourceType.PUBLIC_REAL
    assert prov.source_dataset == "test_repo"

    # Verify frozen immutability
    with pytest.raises(Exception):
        prov.source_dataset = "mutated"  # type: ignore


def test_provenance_serialization():
    prov = ProvenanceRecord(
        source_type=SourceType.SYNTHETIC,
        source_dataset="PIIS-TelcoBench",
        source_record_id="syn_001",
        metadata={"seed": 42},
    )
    d = prov.to_dict()
    assert d["source_type"] == "SYNTHETIC"
    assert d["source_dataset"] == "PIIS-TelcoBench"
    assert d["metadata"]["seed"] == 42
    assert "ingested_at" in d
