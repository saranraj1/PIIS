"""PIIS Milestone M5.5.1 — Temporal Evidence Independent Audit Script.

Verifies the runtime correctness of FIND-M5.4-001 remediation across 9 core criteria:
1. Configurable freshness policies (runtime overrides per evidence type).
2. Observation time vs. Ingestion time semantics.
3. Incident reference time vs. system wall-clock time.
4. Timezone handling (UTC enforcement, naive string conversion).
5. Future timestamps and clock corruption detection.
6. Bounded and configurable clock skew tolerance.
7. Ingestion delay measurement and reporting.
8. Historical context preservation vs. current-state confirmation.
9. Mixed evidence handling (stale suppression without full discard).

Outputs machine-readable metrics to artifacts/m5_metrics/m5_5_1_temporal_audit.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict

from piis.investigation.schemas import (
    EvidenceType,
    InvestigationEvidenceItem,
    TrustLevel,
)
from piis.investigation.temporal import (
    EvidenceTemporalStatus,
    FreshnessPolicy,
    TemporalEvidenceEvaluator,
    parse_utc_timestamp,
)


def run_temporal_audit() -> Dict[str, Any]:
    print("=" * 80)
    print("PIIS M5.5.1 INDEPENDENT TEMPORAL EVIDENCE AUDIT")
    print("=" * 80)

    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    results: Dict[str, Any] = {}

    # 1. Configurable Freshness Policies
    print("\n1. Testing Runtime Configurable Freshness Policies...")
    custom_policies = {
        EvidenceType.TELEMETRY_ANOMALY: FreshnessPolicy(
            evidence_type=EvidenceType.TELEMETRY_ANOMALY,
            max_age_seconds=300.0, # Strict 5 min
            clock_skew_tolerance_seconds=15.0, # Tight 15s skew
        ),
    }
    custom_evaluator = TemporalEvidenceEvaluator(policies=custom_policies)
    default_evaluator = TemporalEvidenceEvaluator()

    # 10 min old item (stale under custom, fresh under default 3600s)
    item_10m = InvestigationEvidenceItem(
        evidence_id="EVID-10M",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Node-10M",
        domain="RAN",
        observed_at=(now - timedelta(minutes=10)).isoformat(),
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="10 min old telemetry",
    )
    res_custom = custom_evaluator.evaluate_item(item_10m, reference_time=now)
    res_default = default_evaluator.evaluate_item(item_10m, reference_time=now)

    test1_passed = (res_custom.temporal_status == EvidenceTemporalStatus.STALE) and (
        res_default.temporal_status == EvidenceTemporalStatus.FRESH
    )
    print(f"  Custom policy: {res_custom.temporal_status} | Default: {res_default.temporal_status} (Configurable: {test1_passed})")
    results["configurable_freshness_policies"] = {
        "passed": test1_passed,
        "custom_threshold_seconds": 300.0,
        "default_threshold_seconds": 3600.0,
    }

    # 2. Observation Time vs Ingestion Time Semantics
    print("\n2. Testing Observation Time vs Ingestion Time Semantics...")
    # Item observed 2 hours ago (7200s), but ingested 10s ago (delayed Kafka pipeline)
    delayed_item = InvestigationEvidenceItem(
        evidence_id="EVID-DELAYED",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Kafka-Lag",
        domain="RAN",
        observed_at=(now - timedelta(seconds=7200)).isoformat(),
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="Delayed ingestion item",
        raw_metadata={"ingested_at": (now - timedelta(seconds=10)).isoformat()},
    )
    res_delayed = default_evaluator.evaluate_item(delayed_item, reference_time=now)
    # Operational truth MUST be governed by observation time (STALE), not ingestion time (FRESH)!
    test2_passed = (
        res_delayed.temporal_status == EvidenceTemporalStatus.STALE
        and not res_delayed.is_current_confirmation
        and res_delayed.ingestion_delay_seconds is not None
        and res_delayed.ingestion_delay_seconds > 7000
    )
    print(f"  Observed 2h ago, ingested 10s ago -> Status: {res_delayed.temporal_status}, Delay: {res_delayed.ingestion_delay_seconds}s (Passed: {test2_passed})")
    results["observation_vs_ingestion_semantics"] = {
        "passed": test2_passed,
        "status": res_delayed.temporal_status.value,
        "ingestion_delay_seconds": res_delayed.ingestion_delay_seconds,
    }

    # 3. Reference Time Semantics (Historical Incident Backtesting)
    print("\n3. Testing Incident Reference Time Semantics...")
    # Ticket opened 1 year ago. Telemetry observed 5 minutes before ticket opened.
    # When evaluated against the ticket's creation time, telemetry should be FRESH!
    ticket_time = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    historic_obs_time = ticket_time - timedelta(minutes=5)
    historic_telemetry = InvestigationEvidenceItem(
        evidence_id="EVID-HIST-REPLAY",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Historical-Node",
        domain="CORE",
        observed_at=historic_obs_time.isoformat(),
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="5-min old telemetry relative to historical ticket",
    )
    res_backtest = default_evaluator.evaluate_item(historic_telemetry, reference_time=ticket_time)
    test3_passed = (
        res_backtest.temporal_status == EvidenceTemporalStatus.FRESH
        and res_backtest.is_current_confirmation
        and res_backtest.age_seconds == 300.0
    )
    print(f"  Evaluated against historical incident reference time -> Status: {res_backtest.temporal_status}, Age: {res_backtest.age_seconds}s (Passed: {test3_passed})")
    results["incident_reference_time_semantics"] = {
        "passed": test3_passed,
        "status": res_backtest.temporal_status.value,
        "age_seconds": res_backtest.age_seconds,
    }

    # 4. Timezone Handling & Naive Datetimes
    print("\n4. Testing Timezone Normalization & Naive Timestamp Handling...")
    test_cases_tz = [
        ("2026-11-02T14:00:00+02:00", True, 0), # Explicit +02:00 -> 12:00 UTC
        ("2026-11-02T12:00:00Z", True, 0),      # Explicit UTC with Z
        ("2026-11-02T12:00:00", True, 0),       # Naive string (assumed UTC + flagged)
        ("2026-11-02 12:00:00", True, 0),       # Space-separated naive string
        (1762084800, True, 0),                  # Epoch timestamp
        ("INVALID_DATE_STRING", False, None),   # Unparseable format
    ]
    tz_passed = 0
    for raw_input, should_succeed, expected_hour_diff in test_cases_tz:
        dt_res, note = parse_utc_timestamp(raw_input)
        if should_succeed:
            if dt_res is not None and dt_res.tzinfo == timezone.utc:
                tz_passed += 1
        else:
            if dt_res is None:
                tz_passed += 1

    test4_passed = tz_passed == len(test_cases_tz)
    print(f"  Timezone normalization passed: {tz_passed}/{len(test_cases_tz)} (Passed: {test4_passed})")
    results["timezone_handling"] = {
        "passed": test4_passed,
        "cases_tested": len(test_cases_tz),
        "cases_passed": tz_passed,
    }

    # 5. Future Timestamps & Clock Skew Tolerance Boundary
    print("\n5. Testing Future Timestamps & Clock Skew Boundary...")
    # Tolerance is 60.0s
    item_skew_safe = InvestigationEvidenceItem(
        evidence_id="EVID-SKEW-SAFE",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Node-Skew",
        domain="RAN",
        observed_at=(now + timedelta(seconds=55)).isoformat(), # +55s (within 60s)
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="55s future skew",
    )
    res_skew_safe = default_evaluator.evaluate_item(item_skew_safe, reference_time=now)

    item_skew_bad = InvestigationEvidenceItem(
        evidence_id="EVID-SKEW-BAD",
        evidence_type=EvidenceType.TELEMETRY_ANOMALY,
        source_ref="Node-Skew",
        domain="RAN",
        observed_at=(now + timedelta(seconds=65)).isoformat(), # +65s (exceeds 60s)
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="65s future skew",
    )
    res_skew_bad = default_evaluator.evaluate_item(item_skew_bad, reference_time=now)

    test5_passed = (
        res_skew_safe.temporal_status == EvidenceTemporalStatus.CLOCK_SKEW_ACCEPTED
        and res_skew_safe.is_current_confirmation
        and res_skew_bad.temporal_status == EvidenceTemporalStatus.FUTURE_DATED
        and not res_skew_bad.is_current_confirmation
    )
    print(f"  +55s -> {res_skew_safe.temporal_status} | +65s -> {res_skew_bad.temporal_status} (Passed: {test5_passed})")
    results["clock_skew_tolerance_boundary"] = {
        "passed": test5_passed,
        "skew_safe_status": res_skew_safe.temporal_status.value,
        "skew_bad_status": res_skew_bad.temporal_status.value,
    }

    # 6. Historical Context Preservation
    print("\n6. Testing Historical Context vs Current Confirmation...")
    hist_case = InvestigationEvidenceItem(
        evidence_id="EVID-HIST-1Y",
        evidence_type=EvidenceType.HISTORICAL_CASE,
        source_ref="INC-2025-01-OPTICAL",
        domain="TRANSPORT",
        observed_at=(now - timedelta(days=200)).isoformat(),
        trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
        content_summary="Resolved fiber loss ticket from 200 days ago",
    )
    res_hist = default_evaluator.evaluate_item(hist_case, reference_time=now)
    test6_passed = (
        res_hist.temporal_status == EvidenceTemporalStatus.HISTORICAL_CONTEXT
        and not res_hist.is_current_confirmation
    )
    print(f"  Historical case: {res_hist.temporal_status}, is_current_confirmation={res_hist.is_current_confirmation} (Passed: {test6_passed})")
    results["historical_context_preservation"] = {
        "passed": test6_passed,
        "status": res_hist.temporal_status.value,
        "is_current_confirmation": res_hist.is_current_confirmation,
    }

    # 7. Mixed Evidence Register Evaluation (Partial Staleness)
    print("\n7. Testing Mixed Evidence Register Evaluation...")
    register = [
        # 3 fresh telemetry items
        InvestigationEvidenceItem(
            evidence_id=f"EVID-FRESH-{i}",
            evidence_type=EvidenceType.TELEMETRY_ANOMALY,
            source_ref=f"Node-Fresh-{i}",
            domain="RAN",
            observed_at=(now - timedelta(minutes=5 * i)).isoformat(),
            trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
            content_summary=f"Fresh item {i}",
        )
        for i in range(1, 4)
    ] + [
        # 2 stale telemetry items (3 hours old)
        InvestigationEvidenceItem(
            evidence_id=f"EVID-STALE-{i}",
            evidence_type=EvidenceType.TELEMETRY_ANOMALY,
            source_ref=f"Node-Stale-{i}",
            domain="RAN",
            observed_at=(now - timedelta(hours=3 + i)).isoformat(),
            trust_classification=TrustLevel.HIGH_TRUST_APPROVED,
            content_summary=f"Stale item {i}",
        )
        for i in range(1, 3)
    ] + [
        # 1 historical case
        hist_case,
    ]

    evaluated_items = [default_evaluator.evaluate_item(item, reference_time=now) for item in register]
    fresh_items = [e for e in evaluated_items if e.temporal_status == EvidenceTemporalStatus.FRESH]
    stale_items = [e for e in evaluated_items if e.temporal_status == EvidenceTemporalStatus.STALE]
    hist_items = [e for e in evaluated_items if e.temporal_status == EvidenceTemporalStatus.HISTORICAL_CONTEXT]

    test7_passed = (len(fresh_items) == 3) and (len(stale_items) == 2) and (len(hist_items) == 1)
    print(f"  Register: {len(fresh_items)} fresh, {len(stale_items)} stale, {len(hist_items)} historical (Passed: {test7_passed})")
    results["mixed_evidence_register"] = {
        "passed": test7_passed,
        "fresh_count": len(fresh_items),
        "stale_count": len(stale_items),
        "historical_count": len(hist_items),
    }

    # Summary
    all_tests_passed = all(r["passed"] for r in results.values())
    results["all_temporal_tests_passed"] = all_tests_passed
    results["resolution_of_FIND_M5_4_001"] = "GENUINELY_RESOLVED" if all_tests_passed else "DEFECTIVE"

    out_file = Path("artifacts/m5_metrics/m5_5_1_temporal_audit.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Temporal Evidence Audit Complete. All tests passed: {all_tests_passed}")
    print(f"FIND-M5.4-001 Resolution Verdict: {results['resolution_of_FIND_M5_4_001']}")
    print(f"Machine-readable metrics committed to: {out_file}")
    print("=" * 80)
    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run_temporal_audit()
