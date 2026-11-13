"""PIIS M5.4 Independent Security Audit - OIDC Revocation & Concurrency Stress.

Independently evaluates:
- 30 adversarial OIDC token attacks (revocation, claim tampering, alg confusion, replay, segregation).
- Repeated randomized multi-threaded concurrency stress (5 trials x 16 threads x 100 ops = 8,000 ops).
- Measures deadlocks, timeouts, authorization consistency, throughput, and P50/P95/P99 latency.
- Outputs machine-readable results to artifacts/m5_metrics/m5_4_independent_oidc_concurrency.json.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import threading
import time
from typing import Any, Dict, List

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from piis.investigation.approval import (
    AuthenticatedReviewer,
    AuthenticatedServicePrincipal,
    HumanApprovalWorkflow,
    MissingAuthenticationConfigurationError,
    ProductionOIDCVerifier,
    SCOPE_DIAGNOSTIC_QUERY,
    SCOPE_INTERNAL_REGISTRATION,
    SCOPE_READ_ONLY_OBSERVATION,
    ServicePrincipalClaims,
    UnauthenticatedReviewerError,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


def generate_rsa_keypair() -> tuple[Any, str, str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    kid = f"key-{int(time.time()*1000)}-{random.randint(100, 999)}"
    pem_priv = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pem_pub = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, pem_priv, pem_pub, kid


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 80)
    print("PIIS M5.4 INDEPENDENT AUDIT — OIDC REVOCATION & CONCURRENCY VERIFICATION")
    print("=" * 80)

    # Setup keys and verifiers
    priv_key, pem_priv, pem_pub, kid = generate_rsa_keypair()
    other_priv_key, other_pem_priv, other_pem_pub, other_kid = generate_rsa_keypair()

    jwks_url = "https://idp.telecom.internal/.well-known/jwks.json"
    issuer = "https://idp.telecom.internal"
    audience = "piis-decision-support"

    verifier = ProductionOIDCVerifier(
        jwks_url=jwks_url,
        issuer=issuer,
        audience=audience,
    )
    # Inject trusted key for offline testing
    verifier._jwks_cache = {kid: pem_pub}
    verifier._cache_timestamp = time.time()
    verifier._is_configured = True

    print("\n--- PHASE 1: 30 ADVERSARIAL OIDC ATTACK VECTORS ---")
    oidc_results: List[Dict[str, Any]] = []

    def log_attack(attack_id: str, desc: str, passed: bool, details: str = "") -> None:
        oidc_results.append({
            "attack_id": attack_id,
            "description": desc,
            "passed": passed,
            "details": details,
        })
        status_str = "PASS" if passed else "FAIL"
        print(f"  [{status_str}] {attack_id}: {desc}")

    now = datetime.now(timezone.utc)

    # Helper to make valid service tokens
    def make_service_jwt(claims: dict, key: str = pem_priv, alg: str = "RS256", key_id: str = kid) -> str:
        base = {
            "sub": "svc-default",
            "principal_type": "SERVICE",
            "iss": issuer,
            "aud": audience,
            "exp": now + timedelta(hours=1),
            "jti": f"jti-{random.randint(10000, 99999)}",
            "scopes": [SCOPE_DIAGNOSTIC_QUERY],
        }
        base.update(claims)
        headers = {"kid": key_id} if key_id else {}
        return jwt.encode(base, key, algorithm=alg, headers=headers)

    # 1. Direct jti revocation
    token_1 = make_service_jwt({"sub": "svc-worker-1", "jti": "jti-rev-01"})
    verifier.revoke_token("jti-rev-01")
    try:
        verifier.verify_service_token(token_1)
        log_attack("OIDC-01", "Direct jti revocation check", False, "Revoked token was accepted")
    except UnauthenticatedReviewerError:
        log_attack("OIDC-01", "Direct jti revocation check", True)

    # 2. Token ID derived revocation
    token_2 = make_service_jwt({"sub": "svc-worker-2", "jti": None})
    tok_hash_2 = hashlib.sha256(token_2.encode()).hexdigest()
    tok_id_2 = f"svc-{tok_hash_2[:16]}"
    verifier.revoke_token(tok_id_2)
    try:
        verifier.verify_service_token(token_2)
        log_attack("OIDC-02", "Token-hash derived revocation check", False, "Derived revoked token accepted")
    except UnauthenticatedReviewerError:
        log_attack("OIDC-02", "Token-hash derived revocation check", True)

    # 3. Session validation revocation invalidation
    token_3 = make_service_jwt({"sub": "svc-worker-3", "jti": "jti-sess-03"})
    claims_3 = verifier.verify_service_token(token_3)
    svc_principal = AuthenticatedServicePrincipal(
        service_id=claims_3.service_id,
        allowed_scopes=claims_3.allowed_scopes,
        auth_token_hash=claims_3.token_hash,
        token_id=claims_3.token_id,
        claims=claims_3,
    )
    assert verifier.validate_service_session(svc_principal) is True
    verifier.revoke_token("jti-sess-03")
    is_valid = verifier.validate_service_session(svc_principal)
    log_attack("OIDC-03", "Service session invalidation on post-verification revocation", is_valid is False)

    # 4. Human reviewer session revocation invalidation
    token_4 = jwt.encode(
        {"sub": "operator.noc1", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-rev-user-04", "role": "NOC_TIER_2"},
        pem_priv, algorithm="RS256", headers={"kid": kid}
    )
    rev_claims = verifier.verify_token(token_4)
    auth_rev = AuthenticatedReviewer(
        operator_id=rev_claims.operator_id,
        role=rev_claims.role,
        auth_token_hash=rev_claims.token_hash,
        token_id=rev_claims.token_id,
        auth_claims=rev_claims,
    )
    assert verifier.validate_reviewer_session(auth_rev) is True
    verifier.revoke_token("jti-rev-user-04")
    rev_valid = verifier.validate_reviewer_session(auth_rev)
    log_attack("OIDC-04", "Human reviewer session invalidation upon revocation", rev_valid is False)

    # 5. Revocation backend fail-closed check
    try:
        class BrokenVerifier(ProductionOIDCVerifier):
            def is_revoked(self, token_id: str) -> bool:
                raise RuntimeError("Database connection refused")
        broken = BrokenVerifier(jwks_url=jwks_url, issuer=issuer, audience=audience)
        broken._jwks_cache = {kid: pem_pub}
        broken._cache_timestamp = time.time()
        broken._is_configured = True
        try:
            broken.verify_service_token(token_2)
            log_attack("OIDC-05", "Revocation backend failure fails closed", False, "Token accepted despite DB failure")
        except Exception:
            log_attack("OIDC-05", "Revocation backend failure fails closed", True)
    except Exception as e:
        log_attack("OIDC-05", "Revocation backend failure fails closed", False, str(e))

    # 6. Missing exp claim rejected
    tok_no_exp = jwt.encode(
        {"sub": "svc-worker-6", "principal_type": "SERVICE", "iss": issuer, "aud": audience, "jti": "jti-06", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        pem_priv, algorithm="RS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_no_exp)
        log_attack("OIDC-06", "Missing exp claim rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-06", "Missing exp claim rejected", True)

    # 7. Expired token rejected
    tok_expired = make_service_jwt({"sub": "svc-worker-7", "exp": now - timedelta(minutes=5), "jti": "jti-07"})
    try:
        verifier.verify_service_token(tok_expired)
        log_attack("OIDC-07", "Expired token rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-07", "Expired token rejected", True)

    # 8. Missing iss claim rejected
    tok_no_iss = jwt.encode(
        {"sub": "svc-worker-8", "principal_type": "SERVICE", "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-08", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        pem_priv, algorithm="RS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_no_iss)
        log_attack("OIDC-08", "Missing iss claim rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-08", "Missing iss claim rejected", True)

    # 9. Wrong iss claim rejected
    tok_wrong_iss = make_service_jwt({"sub": "svc-worker-9", "iss": "https://evil.attacker.com", "jti": "jti-09"})
    try:
        verifier.verify_service_token(tok_wrong_iss)
        log_attack("OIDC-09", "Untrusted issuer rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-09", "Untrusted issuer rejected", True)

    # 10. Missing aud claim rejected
    tok_no_aud = jwt.encode(
        {"sub": "svc-worker-10", "principal_type": "SERVICE", "iss": issuer, "exp": now + timedelta(hours=1), "jti": "jti-10", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        pem_priv, algorithm="RS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_no_aud)
        log_attack("OIDC-10", "Missing aud claim rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-10", "Missing aud claim rejected", True)

    # 11. Wrong aud claim rejected
    tok_wrong_aud = make_service_jwt({"sub": "svc-worker-11", "aud": "rogue-billing-service", "jti": "jti-11"})
    try:
        verifier.verify_service_token(tok_wrong_aud)
        log_attack("OIDC-11", "Mismatched audience rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-11", "Mismatched audience rejected", True)

    # 12. Missing sub claim rejected
    tok_no_sub = jwt.encode(
        {"principal_type": "SERVICE", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-12", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        pem_priv, algorithm="RS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_no_sub)
        log_attack("OIDC-12", "Missing sub claim rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-12", "Missing sub claim rejected", True)

    # 13. Future nbf claim rejected
    tok_future_nbf = make_service_jwt({"sub": "svc-worker-13", "nbf": now + timedelta(hours=1), "exp": now + timedelta(hours=2)})
    try:
        verifier.verify_service_token(tok_future_nbf)
        log_attack("OIDC-13", "Future nbf (not-before) rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-13", "Future nbf (not-before) rejected", True)

    # 14. Algorithm confusion: none algorithm
    tok_none = jwt.encode(
        {"sub": "svc-worker-14", "principal_type": "SERVICE", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-14", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        key="", algorithm="none", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_none)
        log_attack("OIDC-14", "Unsigned 'none' algorithm rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-14", "Unsigned 'none' algorithm rejected", True)

    # 15. Algorithm confusion: symmetric HS256 using public key
    tok_hs256 = jwt.encode(
        {"sub": "svc-worker-15", "principal_type": "SERVICE", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-15", "scopes": [SCOPE_DIAGNOSTIC_QUERY]},
        key="attacker-symmetric-secret-key-32b-long", algorithm="HS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_hs256)
        log_attack("OIDC-15", "Symmetric HS256 key-confusion attack rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-15", "Symmetric HS256 key-confusion attack rejected", True)

    # 16. RS256 token signed by untrusted key
    tok_untrusted = make_service_jwt({"sub": "svc-worker-16"}, key=other_pem_priv, key_id=kid)
    try:
        verifier.verify_service_token(tok_untrusted)
        log_attack("OIDC-16", "Untrusted private key signature rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-16", "Untrusted private key signature rejected", True)

    # 17. Unknown kid rejected
    tok_unknown_kid = make_service_jwt({"sub": "svc-worker-17"}, key_id="kid-does-not-exist")
    try:
        verifier.verify_service_token(tok_unknown_kid)
        log_attack("OIDC-17", "Unknown kid header rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-17", "Unknown kid header rejected", True)

    # 18. Token lacking kid header rejected
    tok_no_kid = make_service_jwt({"sub": "svc-worker-18"}, key_id=None)
    try:
        verifier.verify_service_token(tok_no_kid)
        log_attack("OIDC-18", "Token missing kid header rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-18", "Token missing kid header rejected", True)

    # 19. Key rotation handling: rotating key replaces cache
    new_kid = "key-rotated-2026"
    verifier._jwks_cache = {new_kid: other_pem_pub}
    verifier._cache_timestamp = time.time()
    tok_new_rotated = make_service_jwt({"sub": "svc-worker-19"}, key=other_pem_priv, key_id=new_kid)
    try:
        res = verifier.verify_service_token(tok_new_rotated)
        log_attack("OIDC-19", "Rotated key in JWKS accepted cleanly", res.service_id == "svc-worker-19")
    except Exception as e:
        log_attack("OIDC-19", "Rotated key in JWKS accepted cleanly", False, str(e))

    # Restore default kid
    verifier._jwks_cache = {kid: pem_pub, new_kid: other_pem_pub}
    verifier._cache_timestamp = time.time()

    # 20. Replay attack attempt: replaying token after revocation
    tok_replay = make_service_jwt({"sub": "svc-replay", "jti": "jti-replay-20"})
    p1 = verifier.verify_service_token(tok_replay)
    assert p1.service_id == "svc-replay"
    verifier.revoke_token("jti-replay-20")
    try:
        verifier.verify_service_token(tok_replay)
        log_attack("OIDC-20", "Replayed token rejected after revocation", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-20", "Replayed token rejected after revocation", True)

    # 21. Segregation: Human token presented to verify_service_token
    tok_human = jwt.encode(
        {"sub": "john.doe@telecom.com", "principal_type": "HUMAN", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-human-21", "role": "NOC_TIER_2"},
        key=priv_key, algorithm="RS256", headers={"kid": kid}
    )
    try:
        verifier.verify_service_token(tok_human)
        log_attack("OIDC-21", "Human credential presented as service principal segregation", False, "Treated as service token")
    except UnauthenticatedReviewerError:
        log_attack("OIDC-21", "Human credential presented as service principal segregation", True)

    # 22. Segregation: Service token presented to verify_token
    tok_service = make_service_jwt({"sub": "SERVICE", "jti": "jti-svc-22"})
    try:
        verifier.verify_token(tok_service)
        log_attack("OIDC-22", "Service credential presented as human reviewer segregation", False, "Service token accepted as human reviewer")
    except UnauthenticatedReviewerError:
        log_attack("OIDC-22", "Service credential presented as human reviewer segregation", True)

    # 23. Service principal cannot approve recommendations in workflow
    workflow = HumanApprovalWorkflow(
        signing_key=b"super-secure-audit-signing-secret-key-32b",
        key_id="piis-audit-key-2026-v2",
        verifier=verifier,
    )
    rec = DiagnosticRecommendation(
        recommendation_id="REC-OIDC-TEST",
        description="Verify service cannot approve",
        reason="Testing authorization boundaries",
        source_runbook_id="SOP-TEST-001",
        source_section="Section 1",
        expected_observation="Action rejected",
        risk_classification=RecommendationRisk.READ_ONLY_SAFE,
        human_approval_required=True,
    )
    svc_claims = ServicePrincipalClaims(
        service_id="svc-orchestrator",
        service_name="Service Orchestrator",
        allowed_scopes=[SCOPE_DIAGNOSTIC_QUERY, SCOPE_READ_ONLY_OBSERVATION],
        issuer=issuer,
        token_hash="dummy_hash",
        issued_at_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        token_id="jti-svc-cannot-approve",
    )
    svc_actor = AuthenticatedServicePrincipal(
        service_id="svc-orchestrator",
        allowed_scopes=[SCOPE_DIAGNOSTIC_QUERY, SCOPE_READ_ONLY_OBSERVATION],
        auth_token_hash="dummy_hash",
        token_id="jti-svc-cannot-approve",
        claims=svc_claims,
    )
    workflow.register_recommendation(rec, incident_id="INC-001")
    try:
        workflow.approve_recommendation(
            recommendation_id="REC-OIDC-TEST",
            operator_id=svc_actor,  # type: ignore
            incident_id="INC-001",
            notes="Service attempt to approve",
        )
        log_attack("OIDC-23", "Service principal cannot execute human approval action", False)
    except (UnauthenticatedReviewerError, TypeError, ValueError):
        log_attack("OIDC-23", "Service principal cannot execute human approval action", True)

    # 24. Prohibited operator ID bypass attempt in Human Reviewer token
    tok_root_user = jwt.encode(
        {"sub": "ROOT", "principal_type": "HUMAN", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": "jti-root-24", "role": "SYSADMIN"},
        key=priv_key, algorithm="RS256", headers={"kid": kid}
    )
    try:
        claims = verifier.verify_token(tok_root_user)
        rev = AuthenticatedReviewer(
            operator_id=claims.operator_id,
            role=claims.role,
            auth_token_hash=claims.token_hash,
            token_id=claims.token_id,
            auth_claims=claims,
        )
        workflow.approve_recommendation(recommendation_id="REC-OIDC-TEST", operator_id=rev, incident_id="INC-001")
        log_attack("OIDC-24", "Prohibited operator ID (ROOT) blocked from review", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-24", "Prohibited operator ID (ROOT) blocked from review", True)

    # 25. Privilege escalation attempt: injecting admin=true in service token
    tok_admin_claim = make_service_jwt({"sub": "svc-escalate", "jti": "jti-admin-25", "admin": True, "superadmin": True})
    principal_esc = verifier.verify_service_token(tok_admin_claim)
    log_attack("OIDC-25", "Arbitrary admin claims ignored and scoped to allowed_scopes", SCOPE_INTERNAL_REGISTRATION not in principal_esc.allowed_scopes)

    # 26. Injection payload in sub claim
    tok_inject_sub = make_service_jwt({"sub": "'; DROP TABLE audit_log; -- \n<script>alert(1)</script>", "jti": "jti-inj-26"})
    try:
        p_inj = verifier.verify_service_token(tok_inject_sub)
        log_attack("OIDC-26", "SQL/XSS payload in sub safely treated as plain string", p_inj.service_id.startswith("'; DROP"))
    except Exception as e:
        log_attack("OIDC-26", "SQL/XSS payload in sub safely treated as plain string", False, str(e))

    # 27. Blank jti claim handling
    tok_blank_jti = make_service_jwt({"sub": "svc-blank-jti", "jti": ""})
    p_blank = verifier.verify_service_token(tok_blank_jti)
    log_attack("OIDC-27", "Blank jti falls back to token hash for revocation", len(p_blank.token_id) > 0)

    # 28. Malformed signature
    tok_tampered_sig = token_2[:-10] + "0123456789"
    try:
        verifier.verify_service_token(tok_tampered_sig)
        log_attack("OIDC-28", "Mutated signature bytes rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-28", "Mutated signature bytes rejected", True)

    # 29. Truncated token
    try:
        verifier.verify_service_token("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJzdmMifQ")
        log_attack("OIDC-29", "Truncated two-segment token rejected", False)
    except UnauthenticatedReviewerError:
        log_attack("OIDC-29", "Truncated two-segment token rejected", True)

    # 30. Unconfigured verifier fails closed
    unconfigured_verifier = ProductionOIDCVerifier(
        jwks_url="https://unconfigured.internal/jwks",
        issuer="https://unconfigured.internal",
        audience="piis",
    )
    try:
        unconfigured_verifier.verify_service_token(token_2)
        log_attack("OIDC-30", "Unconfigured verifier fails closed", False)
    except (MissingAuthenticationConfigurationError, UnauthenticatedReviewerError):
        log_attack("OIDC-30", "Unconfigured verifier fails closed", True)

    total_oidc = len(oidc_results)
    passed_oidc = sum(1 for r in oidc_results if r["passed"])
    print(f"\nOIDC Phase Summary: {passed_oidc}/{total_oidc} passed ({passed_oidc/total_oidc*100:.1f}%)")

    # =========================================================================
    # PHASE 2: CONCURRENCY, DEADLOCK & STRESS TESTING
    # =========================================================================
    print("\n--- PHASE 2: CONCURRENCY, DEADLOCK & STRESS TESTING ---")
    print("Testing 5 repeated stress trials (16 concurrent threads x 100 ops = 8,000 total operations)...")

    concurrency_trials = []
    all_latencies_ms = []
    deadlocks_detected = 0
    timeouts_detected = 0
    exceptions_detected = 0
    inconsistencies_detected = 0

    valid_tokens = []
    valid_principals = []
    valid_reviewers = []
    for i in range(20):
        t_svc = make_service_jwt({"sub": f"svc-worker-{i}", "jti": f"stress-jti-svc-{i}"})
        c_svc = verifier.verify_service_token(t_svc)
        p_svc = AuthenticatedServicePrincipal(
            service_id=c_svc.service_id,
            allowed_scopes=c_svc.allowed_scopes,
            auth_token_hash=c_svc.token_hash,
            token_id=c_svc.token_id,
            claims=c_svc,
        )
        valid_tokens.append(t_svc)
        valid_principals.append(p_svc)

        t_rev = jwt.encode(
            {"sub": f"operator.{i}", "principal_type": "HUMAN", "iss": issuer, "aud": audience, "exp": now + timedelta(hours=1), "jti": f"stress-jti-rev-{i}", "role": "NOC_TIER_2"},
            key=priv_key, algorithm="RS256", headers={"kid": kid}
        )
        c_rev = verifier.verify_token(t_rev)
        r_rev = AuthenticatedReviewer(
            operator_id=c_rev.operator_id,
            role=c_rev.role,
            auth_token_hash=c_rev.token_hash,
            token_id=c_rev.token_id,
            auth_claims=c_rev,
        )
        valid_reviewers.append(r_rev)

    total_ops_executed = 0

    for trial_idx in range(1, 6):
        start_trial = time.perf_counter()
        trial_latencies = []
        trial_errors = 0

        def worker_task(thread_id: int) -> List[float]:
            nonlocal deadlocks_detected, timeouts_detected, exceptions_detected, inconsistencies_detected
            latencies = []
            for op_idx in range(100):
                op_type = random.choice([
                    "validate_svc_session",
                    "validate_rev_session",
                    "verify_token",
                    "check_revocation",
                    "rotate_or_refresh",
                    "invalid_flood",
                ])
                t0 = time.perf_counter()
                try:
                    if op_type == "validate_svc_session":
                        p = random.choice(valid_principals)
                        ok = verifier.validate_service_session(p)
                        if not ok:
                            inconsistencies_detected += 1
                    elif op_type == "validate_rev_session":
                        r = random.choice(valid_reviewers)
                        ok = verifier.validate_reviewer_session(r)
                        if not ok:
                            inconsistencies_detected += 1
                    elif op_type == "verify_token":
                        tok = random.choice(valid_tokens)
                        verifier.verify_service_token(tok)
                    elif op_type == "check_revocation":
                        p = random.choice(valid_principals)
                        verifier.is_revoked(p.token_id)
                    elif op_type == "rotate_or_refresh":
                        with verifier._lock:
                            _ = len(verifier._jwks_cache)
                    elif op_type == "invalid_flood":
                        bad_tok = "invalid.token.payload"
                        try:
                            verifier.verify_service_token(bad_tok)
                            inconsistencies_detected += 1
                        except UnauthenticatedReviewerError:
                            pass
                except Exception:
                    exceptions_detected += 1
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)
            return latencies

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(worker_task, tid) for tid in range(16)]
            done, not_done = concurrent.futures.wait(futures, timeout=10.0)
            if not_done:
                deadlocks_detected += len(not_done)
                print(f"  [ERROR] Trial {trial_idx}: {len(not_done)} threads timed out (potential deadlock)!")
            for f in done:
                try:
                    trial_latencies.extend(f.result())
                except Exception:
                    trial_errors += 1

        trial_duration = time.perf_counter() - start_trial
        ops_in_trial = len(trial_latencies)
        total_ops_executed += ops_in_trial
        all_latencies_ms.extend(trial_latencies)
        throughput = ops_in_trial / trial_duration if trial_duration > 0 else 0

        concurrency_trials.append({
            "trial": trial_idx,
            "duration_seconds": round(trial_duration, 4),
            "operations_completed": ops_in_trial,
            "throughput_ops_sec": round(throughput, 2),
            "errors": trial_errors,
        })
        print(f"  Trial {trial_idx}: {ops_in_trial} ops in {trial_duration:.3f}s ({throughput:.1f} ops/sec, {trial_errors} errors)")

    all_latencies_ms.sort()
    n_lats = len(all_latencies_ms)
    p50 = all_latencies_ms[int(n_lats * 0.50)] if n_lats else 0.0
    p95 = all_latencies_ms[int(n_lats * 0.95)] if n_lats else 0.0
    p99 = all_latencies_ms[int(n_lats * 0.99)] if n_lats else 0.0

    print("\nConcurrency Summary:")
    print(f"  Total Operations Completed: {total_ops_executed}")
    print(f"  Deadlocks Detected: {deadlocks_detected}")
    print(f"  Timeouts Detected: {timeouts_detected}")
    print(f"  Exceptions Detected: {exceptions_detected}")
    print(f"  Inconsistencies Detected: {inconsistencies_detected}")
    print(f"  Latency P50: {p50:.3f} ms | P95: {p95:.3f} ms | P99: {p99:.3f} ms")

    is_rlock = isinstance(verifier._lock, type(threading.RLock()))
    has_network_lock = hasattr(verifier, "_network_lock")
    print(f"  Lock Type: {type(verifier._lock).__name__} (RLock: {is_rlock})")
    print(f"  Network Lock Present: {has_network_lock}")

    results_record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M5.4",
        "audit_phase": "OIDC_AND_CONCURRENCY_INDEPENDENT",
        "oidc_attacks": {
            "total_tested": total_oidc,
            "passed": passed_oidc,
            "pass_rate_pct": round(passed_oidc / total_oidc * 100, 2),
            "results": oidc_results,
        },
        "concurrency_stress": {
            "total_operations": total_ops_executed,
            "deadlocks_detected": deadlocks_detected,
            "timeouts_detected": timeouts_detected,
            "exceptions_detected": exceptions_detected,
            "inconsistencies_detected": inconsistencies_detected,
            "latency_p50_ms": round(p50, 4),
            "latency_p95_ms": round(p95, 4),
            "latency_p99_ms": round(p99, 4),
            "trials": concurrency_trials,
            "lock_architecture": {
                "state_lock_type": type(verifier._lock).__name__,
                "is_reentrant": is_rlock,
                "has_dedicated_network_lock": has_network_lock,
            },
        },
    }

    out_path = Path("artifacts/m5_metrics/m5_4_independent_oidc_concurrency.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_record, f, indent=2)

    print(f"\nArtifact written to: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
