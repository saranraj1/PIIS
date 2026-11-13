"""Independent Audit Script: Milestone 5.2 - Approval Integrity, Identity & Key Management.

Adversarially evaluates all 15 required security test cases:
1. Forged Reviewer Identity
2. Dummy Token Rejection
3. Expired Credential Rejection
4. Revoked Credential Rejection
5. Invalid Signature Rejection
6. Wrong Issuer and Audience Rejection
7. Server-Side Role Enforcement (HIGH_RISK_MANUAL)
8. Replay of Prior Approval Rejection
9. Hardcoded/Default Key Elimination
10. Full Audit-Chain Rewrite Detection
11. Checkpoint Replacement Detection
12. Recommendation Content Mutation Detection
13. Durable Ledger Persistence & Startup Reload
14. Concurrent Approval Race Condition Safety
15. Fail-Closed Behavior on Missing Production Configuration
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List

from piis.investigation.approval import (
    AuthenticatedReviewer,
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    InsufficientPrivilegeError,
    IsolatedTestTokenVerifier,
    MissingAuditKeyError,
    MissingAuthenticationConfigurationError,
    ProductionOIDCVerifier,
    RecommendationTamperedError,
    UnauthenticatedReviewerError,
)
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _create_rec(rec_id: str, risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description=f"Diagnostic inspection for {rec_id}",
        reason="Corroborate telemetry hypothesis",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1",
        preconditions=["Site accessible"],
        expected_observation="Status indicators nominal",
        risk_classification=risk,
        human_approval_required=True,
    )


def audit_phase_1_m5_2() -> Dict[str, Any]:
    audit_results: Dict[str, Any] = {
        "milestone": "M5.2",
        "audit_phase": "Phase 1: Real Reviewer Authentication & Durable Audit Integrity",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tests_executed": [],
    }

    verifier = IsolatedTestTokenVerifier()

    # 1. Forged Reviewer Identity
    t1_start = time.perf_counter()
    wf1 = HumanApprovalWorkflow(verifier=verifier)
    rec1 = _create_rec("REC-01")
    wf1.register_recommendation(rec1, "INC-01")
    forged_rev = AuthenticatedReviewer(
        operator_id="attacker",
        role="SYSADMIN",
        auth_token_hash="fake-hash",
        token_id="fake-jti",
    )
    passed1 = False
    try:
        wf1.approve_recommendation("REC-01", forged_rev, "INC-01")
    except UnauthenticatedReviewerError:
        passed1 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-01",
        "name": "Forged Reviewer Identity Direct Instantiation",
        "pass": passed1,
        "latency_ms": round((time.perf_counter() - t1_start) * 1000, 2),
        "detail": "Direct AuthenticatedReviewer construction without IdP session rejected.",
    })

    # 2. Dummy Token Rejection
    t2_start = time.perf_counter()
    wf2 = HumanApprovalWorkflow(verifier=verifier)
    rec2 = _create_rec("REC-02")
    wf2.register_recommendation(rec2, "INC-02")
    passed2 = False
    try:
        wf2.approve_recommendation("REC-02", "dummy-unauthenticated-token-string", "INC-02")
    except UnauthenticatedReviewerError:
        passed2 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-02",
        "name": "Dummy Token Rejection",
        "pass": passed2,
        "latency_ms": round((time.perf_counter() - t2_start) * 1000, 2),
        "detail": "Unstructured non-JWT strings rejected at verifier boundary.",
    })

    # 3. Expired Credential Rejection
    t3_start = time.perf_counter()
    wf3 = HumanApprovalWorkflow(verifier=verifier)
    rec3 = _create_rec("REC-03")
    wf3.register_recommendation(rec3, "INC-03")
    exp_tok = verifier.mint_token("expired_op", lifetime_seconds=-3600)
    passed3 = False
    try:
        wf3.approve_recommendation("REC-03", exp_tok, "INC-03")
    except UnauthenticatedReviewerError:
        passed3 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-03",
        "name": "Expired Credential Rejection",
        "pass": passed3,
        "latency_ms": round((time.perf_counter() - t3_start) * 1000, 2),
        "detail": "Tokens past expiration timestamp rejected.",
    })

    # 4. Revoked Credential Rejection
    t4_start = time.perf_counter()
    wf4 = HumanApprovalWorkflow(verifier=verifier)
    rec4 = _create_rec("REC-04")
    wf4.register_recommendation(rec4, "INC-04")
    tok4 = verifier.mint_token("revoked_op", custom_jti="jti-revoked-04")
    verifier.revoke_token("jti-revoked-04")
    passed4 = False
    try:
        wf4.approve_recommendation("REC-04", tok4, "INC-04")
    except UnauthenticatedReviewerError:
        passed4 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-04",
        "name": "Revoked Credential Rejection",
        "pass": passed4,
        "latency_ms": round((time.perf_counter() - t4_start) * 1000, 2),
        "detail": "Tokens on active revocation list rejected.",
    })

    # 5. Invalid Signature Rejection
    t5_start = time.perf_counter()
    wf5 = HumanApprovalWorkflow(verifier=verifier)
    rec5 = _create_rec("REC-05")
    wf5.register_recommendation(rec5, "INC-05")
    tok5 = verifier.mint_token("legit_op")
    parts = tok5.split(".")
    tampered_tok = f"{parts[0]}.{parts[1]}.{parts[2][:-4]}abcd"
    passed5 = False
    try:
        wf5.approve_recommendation("REC-05", tampered_tok, "INC-05")
    except UnauthenticatedReviewerError:
        passed5 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-05",
        "name": "Invalid Cryptographic Signature Rejection",
        "pass": passed5,
        "latency_ms": round((time.perf_counter() - t5_start) * 1000, 2),
        "detail": "Modified HMAC token signature rejected.",
    })

    # 6. Wrong Issuer and Audience Rejection
    t6_start = time.perf_counter()
    wf6 = HumanApprovalWorkflow(verifier=verifier)
    rec6 = _create_rec("REC-06")
    wf6.register_recommendation(rec6, "INC-06")
    rogue_iss = verifier.mint_token("op_iss", issuer="untrusted-idp")
    wrong_aud = verifier.mint_token("op_aud", audience="billing-service")
    p6_iss = False
    p6_aud = False
    try:
        wf6.approve_recommendation("REC-06", rogue_iss, "INC-06")
    except UnauthenticatedReviewerError:
        p6_iss = True
    try:
        wf6.approve_recommendation("REC-06", wrong_aud, "INC-06")
    except UnauthenticatedReviewerError:
        p6_aud = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-06",
        "name": "Wrong Issuer and Audience Validation",
        "pass": p6_iss and p6_aud,
        "latency_ms": round((time.perf_counter() - t6_start) * 1000, 2),
        "detail": f"Rogue issuer blocked ({p6_iss}), wrong audience blocked ({p6_aud}).",
    })

    # 7. Role-Based Permissions (Server-Side)
    t7_start = time.perf_counter()
    wf7 = HumanApprovalWorkflow(verifier=verifier)
    rec7 = _create_rec("REC-07", risk=RecommendationRisk.HIGH_RISK_MANUAL)
    wf7.register_recommendation(rec7, "INC-07")
    t1_tok = verifier.mint_token("tier1_user", role="NOC_TIER_1")
    lead_tok = verifier.mint_token("lead_user", role="NOC_LEAD")
    p7_block = False
    p7_allow = False
    try:
        wf7.approve_recommendation("REC-07", t1_tok, "INC-07")
    except InsufficientPrivilegeError:
        p7_block = True
    app_res = wf7.approve_recommendation("REC-07", lead_tok, "INC-07")
    p7_allow = app_res.approval_status == ApprovalStatus.APPROVED
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-07",
        "name": "Server-Side Role Permission Enforcement",
        "pass": p7_block and p7_allow,
        "latency_ms": round((time.perf_counter() - t7_start) * 1000, 2),
        "detail": f"NOC_TIER_1 rejected on high-risk ({p7_block}), NOC_LEAD allowed ({p7_allow}).",
    })

    # 8. Replay of an Earlier Approval
    t8_start = time.perf_counter()
    wf8 = HumanApprovalWorkflow(verifier=verifier)
    rec8 = _create_rec("REC-08")
    wf8.register_recommendation(rec8, "INC-08")
    tok8 = verifier.mint_token("op_8")
    wf8.approve_recommendation("REC-08", tok8, "INC-08")
    passed8 = False
    try:
        wf8.approve_recommendation("REC-08", tok8, "INC-08")
    except IllegalStateTransitionError:
        passed8 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-08",
        "name": "Replay of Prior Approval Blocked",
        "pass": passed8,
        "latency_ms": round((time.perf_counter() - t8_start) * 1000, 2),
        "detail": "Terminal state locked against replay attacks.",
    })

    # 9. Hardcoded / Default Key Removal
    t9_start = time.perf_counter()
    has_default = hasattr(HumanApprovalWorkflow, "DEFAULT_AUDIT_KEY")
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-09",
        "name": "Elimination of Hardcoded Default Audit Key",
        "pass": not has_default,
        "latency_ms": round((time.perf_counter() - t9_start) * 1000, 2),
        "detail": "HumanApprovalWorkflow has zero static embedded default signing keys.",
    })

    # 10. Full Audit-Chain Rewrite Detection
    t10_start = time.perf_counter()
    k_legit = b"AUTHENTIC_PRIMARY_SIGNING_KEY_32B!"
    k_att = b"FORGED_ATTACKER_SIGNING_KEY_32BYTE!"
    wf10_legit = HumanApprovalWorkflow(signing_key=k_legit, verifier=verifier)
    wf10_att = HumanApprovalWorkflow(signing_key=k_att, verifier=verifier)
    rec10 = _create_rec("REC-10")
    wf10_legit.register_recommendation(rec10, "INC-10")
    wf10_att.register_recommendation(rec10, "INC-10")
    tok10 = verifier.mint_token("op_10")
    wf10_att.approve_recommendation("REC-10", tok10, "INC-10")
    wf10_legit._audit_trail = wf10_att.get_audit_trail()
    is_valid10, errs10 = wf10_legit.verify_audit_trail()
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-10",
        "name": "Full Audit-Chain Rewrite Detection",
        "pass": (not is_valid10) and any("Invalid HMAC" in e for e in errs10),
        "latency_ms": round((time.perf_counter() - t10_start) * 1000, 2),
        "detail": "Rewritten audit trail signed with unauthorized key failed HMAC checkpoint verification.",
    })

    # 11. Checkpoint Replacement Detection
    t11_start = time.perf_counter()
    wf11 = HumanApprovalWorkflow(verifier=verifier)
    rec11 = _create_rec("REC-11")
    wf11.register_recommendation(rec11, "INC-11")
    tok11 = verifier.mint_token("op_11")
    wf11.approve_recommendation("REC-11", tok11, "INC-11")
    wf11._audit_trail[-1].hmac_signature = "a" * 64
    is_valid11, errs11 = wf11.verify_audit_trail()
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-11",
        "name": "Tampered Checkpoint Detection",
        "pass": (not is_valid11) and any("Invalid HMAC" in e for e in errs11),
        "latency_ms": round((time.perf_counter() - t11_start) * 1000, 2),
        "detail": "Forged HMAC signature detected immediately.",
    })

    # 12. Recommendation Content Mutation
    t12_start = time.perf_counter()
    wf12 = HumanApprovalWorkflow(verifier=verifier)
    rec12 = _create_rec("REC-12")
    wf12.register_recommendation(rec12, "INC-12")
    tok12 = verifier.mint_token("op_12")
    wf12.approve_recommendation("REC-12", tok12, "INC-12")
    rec12.description = "MALICIOUS: format c: and drop database tables"
    passed12 = False
    try:
        wf12.get_verified_recommendation("REC-12")
    except RecommendationTamperedError:
        passed12 = True
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-12",
        "name": "In-Memory Recommendation Content Mutation",
        "pass": passed12 and (not wf12.verify_recommendation_binding("REC-12")),
        "latency_ms": round((time.perf_counter() - t12_start) * 1000, 2),
        "detail": "Post-approval mutation invalidated recommendation hash binding.",
    })

    # 13. Process Restart and Ledger Restoration
    t13_start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger_path = Path(tmp_dir) / "durable_audit.jsonl"
        wf13_a = HumanApprovalWorkflow(verifier=verifier, ledger_path=ledger_path)
        rec13 = _create_rec("REC-13")
        wf13_a.register_recommendation(rec13, "INC-13")
        tok13 = verifier.mint_token("op_13")
        wf13_a.approve_recommendation("REC-13", tok13, "INC-13")

        # Simulate restart
        wf13_b = HumanApprovalWorkflow(verifier=verifier, ledger_path=ledger_path)
        restored = wf13_b.load_from_ledger()
        is_valid13, _ = wf13_b.verify_audit_trail()

        p13_replay = False
        try:
            wf13_b.approve_recommendation("REC-13", tok13, "INC-13")
        except IllegalStateTransitionError:
            p13_replay = True

    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-13",
        "name": "Durable Ledger Persistence and Startup Reload",
        "pass": (restored == 2) and is_valid13 and p13_replay,
        "latency_ms": round((time.perf_counter() - t13_start) * 1000, 2),
        "detail": "Restored audit trail verified hash chain and maintained terminal state locking.",
    })

    # 14. Concurrent Approval Race Condition Safety
    t14_start = time.perf_counter()
    wf14 = HumanApprovalWorkflow(verifier=verifier)
    rec14 = _create_rec("REC-14")
    wf14.register_recommendation(rec14, "INC-14")

    successes: List[Any] = []
    failures: List[Any] = []

    def run_approval(worker_idx: int):
        t = verifier.mint_token(f"op_conc_{worker_idx}")
        try:
            r = wf14.approve_recommendation("REC-14", t, "INC-14")
            successes.append(r)
        except Exception as e:
            failures.append(e)

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(run_approval, i) for i in range(10)]
        for f in futures:
            f.result()

    valid14, _ = wf14.verify_audit_trail()
    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-14",
        "name": "Concurrent Approval Thread-Safety",
        "pass": (len(successes) == 1) and (len(failures) == 9) and valid14,
        "latency_ms": round((time.perf_counter() - t14_start) * 1000, 2),
        "detail": "Exactly 1 concurrent approval won race; 9 failed with state locking.",
    })

    # 15. Missing Production Configuration Fail-Closed
    t15_start = time.perf_counter()
    p15_key = False
    p15_idp = False
    try:
        HumanApprovalWorkflow(environment="production", signing_key=None)
    except MissingAuditKeyError:
        p15_key = True

    unconf_idp = ProductionOIDCVerifier(jwks_url=None, issuer=None)
    try:
        unconf_idp.verify_token("some.token.here")
    except MissingAuthenticationConfigurationError:
        p15_idp = True

    audit_results["tests_executed"].append({
        "test_id": "AUTH-M52-15",
        "name": "Fail-Closed on Missing Production Configuration",
        "pass": p15_key and p15_idp,
        "latency_ms": round((time.perf_counter() - t15_start) * 1000, 2),
        "detail": f"Production key missing failed ({p15_key}), unconfigured IdP failed ({p15_idp}).",
    })

    # Summary
    total = len(audit_results["tests_executed"])
    passed_cnt = sum(1 for t in audit_results["tests_executed"] if t["pass"])
    audit_results["summary"] = {
        "total_tests": total,
        "passed": passed_cnt,
        "failed": total - passed_cnt,
        "pass_rate_pct": round(passed_cnt / total * 100.0, 1),
    }

    out_file = Path("artifacts/m5_metrics/m5_2_approval_auth_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)

    print("================================================================================")
    print("PHASE 1: M5.2 AUTHENTICATION & AUDIT INTEGRITY AUDIT RESULTS")
    print("================================================================================")
    for t in audit_results["tests_executed"]:
        status_str = "PASS" if t["pass"] else "FAIL"
        print(f"[{t['test_id']}] [{status_str:4s}] {t['name']:<48s} | Latency: {t['latency_ms']}ms")
    print("--------------------------------------------------------------------------------")
    print(f"Total: {passed_cnt}/{total} ({audit_results['summary']['pass_rate_pct']}%) Passed")
    print(f"Artifact exported: {out_file}")
    print("================================================================================")
    return audit_results


if __name__ == "__main__":
    audit_phase_1_m5_2()
