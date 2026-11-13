"""Unit tests for PIIS-TelcoBench-v2 Decoupled Scenario Generator."""

from piis.synthetic.generator_v2 import TelecomScenarioGeneratorV2


def test_generator_v2_determinism():
    gen1 = TelecomScenarioGeneratorV2(seed=42)
    inc1 = gen1.generate_incident("FAM-01", template_id="T1", causal_config_id="C1", variant_idx=1)

    gen2 = TelecomScenarioGeneratorV2(seed=42)
    inc2 = gen2.generate_incident("FAM-01", template_id="T1", causal_config_id="C1", variant_idx=1)

    assert inc1["incident_id"] == inc2["incident_id"]
    assert inc1["title"] == inc2["title"]
    assert inc1["description"] == inc2["description"]
    assert inc1["severity"] == inc2["severity"]
    assert inc1["support_level_label"] == inc2["support_level_label"]


def test_generator_v2_severity_calculus_diversity():
    gen = TelecomScenarioGeneratorV2(seed=100)

    # Moderate IoS slice with full protection
    sev_low = gen.calculate_severity(
        subscribers=15,
        criticality="BEST_EFFORT_IOT",
        redundancy="FULLY_PROTECTED",
        timing="MAINTENANCE_WINDOW",
    )
    assert sev_low in ["MINOR", "WARNING"]

    # Massive emergency outage on single point of failure
    sev_crit = gen.calculate_severity(
        subscribers=2500,
        criticality="EMERGENCY_PSAP",
        redundancy="SINGLE_POINT_OF_FAILURE",
        timing="BUSY_HOUR_PEAK",
    )
    assert sev_crit == "CRITICAL"


def test_generator_v2_support_level_independence():
    gen = TelecomScenarioGeneratorV2(seed=100)

    # L1: Standard runbook
    t_l1, _ = gen.determine_support_level(runbook=True, advanced_diag=False, specialist=False)
    assert t_l1 == "L1"

    # L2: Advanced diagnostic required
    t_l2, _ = gen.determine_support_level(runbook=True, advanced_diag=True, specialist=False)
    assert t_l2 == "L2"

    # L3: Specialist dependency
    t_l3, _ = gen.determine_support_level(runbook=True, advanced_diag=True, specialist=True)
    assert t_l3 == "L3"

    # HUMAN_REVIEW: Negative control
    t_hr, _ = gen.determine_support_level(runbook=False, advanced_diag=False, specialist=False, is_negative=True)
    assert t_hr == "HUMAN_REVIEW"


def test_generator_v2_zero_text_leakage_between_splits():
    gen = TelecomScenarioGeneratorV2(seed=42)
    train_recs, test_recs = gen.generate_benchmark_v2(variants_per_combo=2, validate=True)

    train_texts = set(f"{r['title']}. {r['description']}" for r in train_recs)
    test_texts = [f"{r['title']}. {r['description']}" for r in test_recs]

    exact_matches = sum(1 for t in test_texts if t in train_texts)
    assert exact_matches == 0
