"""Unit tests for synthetic scenario generator."""

from piis.synthetic.generator import TelecomScenarioGenerator


def test_generator_deterministic_reproducibility():
    gen1 = TelecomScenarioGenerator(seed=42)
    outcome1 = gen1.generate_scenario("S01", variant_idx=1, validate=True)

    gen2 = TelecomScenarioGenerator(seed=42)
    outcome2 = gen2.generate_scenario("S01", variant_idx=1, validate=True)

    assert outcome1.incident["incident_id"] == outcome2.incident["incident_id"]
    assert outcome1.incident["affected_subscribers"] == outcome2.incident["affected_subscribers"]
    assert outcome1.incident["title"] == outcome2.incident["title"]
    assert len(outcome1.telemetry) == len(outcome2.telemetry)
    assert outcome1.telemetry[0]["metric_value"] == outcome2.telemetry[0]["metric_value"]


def test_generator_all_scenario_families():
    gen = TelecomScenarioGenerator(seed=100)
    families = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S00"]

    for fam in families:
        outcome = gen.generate_scenario(fam, variant_idx=1, validate=True)
        assert outcome.incident["schema_version"] == "1.0"
        assert outcome.incident["source_type"] == "SYNTHETIC"
        assert outcome.incident["scenario_family_id"] == fam
        assert isinstance(outcome.incident["network_element_ids"], list)
        assert len(outcome.incident["network_element_ids"]) > 0


def test_generator_negative_control():
    gen = TelecomScenarioGenerator(seed=999)
    outcome = gen.generate_scenario("S00", variant_idx=1, validate=True)

    assert outcome.incident["fault_category"] == "nominal_operation"
    assert outcome.incident["support_level_label"] == "HUMAN_REVIEW"
    assert outcome.incident["metadata"]["negative_control"] is True
