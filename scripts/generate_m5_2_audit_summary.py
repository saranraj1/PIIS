"""Consolidates independent audit results into artifacts/m5_metrics/m5_2_independent_validation_summary.json."""

from datetime import datetime, timezone
import json
from pathlib import Path

def main():
    metrics_dir = Path("artifacts/m5_metrics")

    with (metrics_dir / "m5_2_independent_phase1_auth.json").open("r", encoding="utf-8") as f:
        p1 = json.load(f)
    with (metrics_dir / "m5_2_independent_phase2_ledger.json").open("r", encoding="utf-8") as f:
        p2 = json.load(f)
    with (metrics_dir / "m5_2_independent_phase3_unicode.json").open("r", encoding="utf-8") as f:
        p3 = json.load(f)
    with (metrics_dir / "m5_2_independent_phase4_equipment.json").open("r", encoding="utf-8") as f:
        p4 = json.load(f)
    with (metrics_dir / "m5_2_independent_phase5_holdout.json").open("r", encoding="utf-8") as f:
        p5 = json.load(f)
    with (metrics_dir / "m5_2_independent_phase6_regression.json").open("r", encoding="utf-8") as f:
        p6 = json.load(f)

    summary = {
        "milestone": "M5.2",
        "title": "M5.2 Independent Adversarial Revalidation & Acceptance Gate Ledger",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "final_acceptance_decision": "ACCEPTED WITH LIMITATIONS",
        "decision_rationale": (
            "Core security, identity, equipment grounding, and holdout behaviors are independently verified. "
            "However, residual architectural limitations require formal acceptance with limitations: "
            "(1) Production OIDC JWKS token verification is an incomplete network adapter that raises NotImplementedError (Unresolved Integration Dependency); "
            "(2) AuditLogEntry 'notes' field is excluded from canonical payload and HMAC signature, allowing undetected note alterations in JSONL; "
            "(3) Vietnamese stacked tone marks trigger false-positive homoglyph flags (2.9% FP); "
            "(4) Standalone JSONL ledgers lack an external trust anchor (e.g. cloud KMS / monotonic hardware counter) to detect clean state rollback."
        ),
        "phases": {
            "phase1_authentication_and_oidc": {
                "total_checks": p1["total_checks"],
                "passed_checks": p1["passed_checks"],
                "unresolved_integration_dependencies": p1["unresolved_integration_dependencies"],
                "pass_rate_pct": round((p1["passed_checks"] / p1["total_checks"]) * 100, 2),
            },
            "phase2_key_governance_and_ledger": {
                "total_tests": p2["total_tests"],
                "passed_tests": p2["passed_tests"],
                "pass_rate_pct": round((p2["passed_tests"] / p2["total_tests"]) * 100, 2),
                "unprotected_notes_vulnerability_detected": True,
            },
            "phase3_unicode_and_security": {
                "adversarial_vectors": p3["adversarial_evaluation"]["total_vectors"],
                "detected_count": p3["adversarial_evaluation"]["detected_count"],
                "detection_rate_pct": p3["adversarial_evaluation"]["detection_rate_pct"],
                "neutralization_rate_pct": p3["adversarial_evaluation"]["neutralization_rate_pct"],
                "evasion_rate_pct": p3["adversarial_evaluation"]["evasion_rate_pct"],
                "benign_controls": p3["benign_evaluation"]["total_controls"],
                "false_positive_rate_pct": p3["benign_evaluation"]["false_positive_rate_pct"],
                "redos_65kb_latency_ms": p3["performance_and_preservation"]["redos_65kb_latency_ms"],
                "original_evidence_preserved": p3["performance_and_preservation"]["original_evidence_preserved"],
            },
            "phase4_equipment_grounding": {
                "total_cases": p4["total_cases"],
                "passed_cases": p4["passed_cases"],
                "pass_rate_pct": p4["pass_rate_pct"],
            },
            "phase5_sealed_holdout_evaluation": {
                "total_scenarios": p5["total_scenarios"],
                "metrics": p5["metrics"],
            },
            "phase6_regression_and_performance": {
                "total_unit_tests": p6["regression_results"]["total_unit_tests"],
                "unit_tests_passed": p6["regression_results"]["unit_tests_passed"],
                "ruff_clean": p6["regression_results"]["ruff_exit_code"] == 0,
                "latency_p50_ms": p6["latency_metrics_ms"]["p50"],
                "latency_p95_ms": p6["latency_metrics_ms"]["p95"],
                "latency_p99_ms": p6["latency_metrics_ms"]["p99"],
                "error_rate_pct": p6["latency_metrics_ms"]["error_rate_pct"],
            },
        },
        "locked_constraints": {
            "m6_unauthorized": True,
            "production_pilot_blocked": True,
            "epistemic_mode": "READ_ONLY_DECISION_SUPPORT",
            "production_commands_executed": 0,
            "network_mutations_applied": 0,
        },
    }

    out_file = metrics_dir / "m5_2_independent_validation_summary.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Successfully wrote {out_file}")

if __name__ == "__main__":
    main()
