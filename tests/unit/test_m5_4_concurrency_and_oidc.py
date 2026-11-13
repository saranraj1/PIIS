"""
Unit tests for PIIS M5.4 Workstreams A & B:
- FIND-M5.3-001: Service Token Direct Revocation & Claim Enforcement
- FIND-M5.3-002: Session Validation Concurrency & RLock Reentrancy
"""

from datetime import datetime, timezone, timedelta
import threading

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from piis.investigation.approval import (
    ProductionOIDCVerifier,
    AuthenticatedServicePrincipal,
    AuthenticatedReviewer,
    ServicePrincipalClaims,
    ReviewerClaims,
    UnauthenticatedReviewerError,
)


@pytest.fixture
def rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key, "key-m54-test-01"


@pytest.fixture
def configured_verifier(rsa_key_pair):
    private_key, public_key, kid = rsa_key_pair
    verifier = ProductionOIDCVerifier(
        issuer="https://auth.telecom.internal",
        audience="piis-service",
        jwks_url="https://auth.telecom.internal/.well-known/jwks.json",
        allow_insecure_http_for_tests=True,
    )
    # Patch signing key resolution
    verifier._get_signing_key = lambda key_id: public_key if key_id == kid else (_ for _ in ()).throw(
        UnauthenticatedReviewerError(f"Unknown key {key_id}")
    )
    return verifier, private_key, kid


# =========================================================================
# Workstream A: FIND-M5.3-001 Service Token Revocation & Claim Enforcement
# =========================================================================

def test_service_token_direct_revocation_enforced(configured_verifier):
    """Verify that verify_service_token checks revocation and rejects revoked tokens."""
    verifier, private_key, kid = configured_verifier
    now = datetime.now(timezone.utc)
    revoked_jti = "jti-svc-revoked-001"
    
    payload = {
        "iss": "https://auth.telecom.internal",
        "sub": "sp-network-core",
        "aud": "piis-service",
        "service_name": "5G Core Orchestrator",
        "principal_type": "SERVICE",
        "scopes": ["read_evidence"],
        "jti": revoked_jti,
        "iat": now.timestamp(),
        "exp": (now + timedelta(hours=1)).timestamp(),
    }
    tok = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})
    
    # Revoke before verification
    verifier.revoke_token(revoked_jti)
    assert verifier.is_revoked(revoked_jti)
    
    with pytest.raises(UnauthenticatedReviewerError, match="has been revoked"):
        verifier.verify_service_token(tok)


def test_service_token_valid_unrevoked_succeeds(configured_verifier):
    """Verify that an unrevoked, properly signed service token validates successfully."""
    verifier, private_key, kid = configured_verifier
    now = datetime.now(timezone.utc)
    valid_jti = "jti-svc-valid-002"
    
    payload = {
        "iss": "https://auth.telecom.internal",
        "sub": "sp-nss-worker",
        "aud": "piis-service",
        "service_name": "Slice Worker",
        "principal_type": "SERVICE",
        "scopes": ["read_evidence", "validate_telemetry"],
        "jti": valid_jti,
        "iat": now.timestamp(),
        "exp": (now + timedelta(hours=1)).timestamp(),
    }
    tok = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})
    
    claims = verifier.verify_service_token(tok)
    assert claims.service_id == "sp-nss-worker"
    assert claims.service_name == "Slice Worker"
    assert claims.token_id == valid_jti
    assert "read_evidence" in claims.allowed_scopes


def test_service_token_missing_required_claims_rejected(configured_verifier):
    """Verify that missing exp, iss, aud, or sub claims are rejected."""
    verifier, private_key, kid = configured_verifier
    now = datetime.now(timezone.utc)
    
    # Missing exp
    payload_no_exp = {
        "iss": "https://auth.telecom.internal",
        "sub": "sp-worker",
        "aud": "piis-service",
        "principal_type": "SERVICE",
        "jti": "jti-no-exp",
    }
    tok_no_exp = jwt.encode(payload_no_exp, private_key, algorithm="RS256", headers={"kid": kid})
    with pytest.raises(UnauthenticatedReviewerError, match="Service token signature verification failed|Missing required claim"):
        verifier.verify_service_token(tok_no_exp)

    # Missing sub
    payload_no_sub = {
        "iss": "https://auth.telecom.internal",
        "aud": "piis-service",
        "principal_type": "SERVICE",
        "jti": "jti-no-sub",
        "exp": (now + timedelta(hours=1)).timestamp(),
    }
    tok_no_sub = jwt.encode(payload_no_sub, private_key, algorithm="RS256", headers={"kid": kid})
    with pytest.raises(UnauthenticatedReviewerError, match="Service token signature verification failed|Missing required claim"):
        verifier.verify_service_token(tok_no_sub)


def test_service_token_wrong_principal_type_rejected(configured_verifier):
    """Verify that tokens without principal_type='SERVICE' are rejected by verify_service_token."""
    verifier, private_key, kid = configured_verifier
    now = datetime.now(timezone.utc)
    
    payload = {
        "iss": "https://auth.telecom.internal",
        "sub": "operator-alice",
        "aud": "piis-service",
        "principal_type": "HUMAN",
        "role": "TIER_2",
        "jti": "jti-human-01",
        "iat": now.timestamp(),
        "exp": (now + timedelta(hours=1)).timestamp(),
    }
    tok = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})
    with pytest.raises(UnauthenticatedReviewerError, match="Credential is not a service principal token"):
        verifier.verify_service_token(tok)


# =========================================================================
# Workstream B: FIND-M5.3-002 Session Validation Concurrency & RLock
# =========================================================================

def test_session_validation_no_deadlock(configured_verifier):
    """Verify that validate_service_session and validate_reviewer_session do not deadlock with RLock."""
    verifier, _, _ = configured_verifier
    
    # 1. Test validate_service_session
    svc_id = "sp-concurrent-test"
    token_id = "jti-concurrent-test-01"
    token_hash = "hash-concurrent-01"
    
    principal = AuthenticatedServicePrincipal(
        service_id=svc_id,
        service_name="Concurrent Svc",
        token_id=token_id,
        auth_token_hash=token_hash,
        scopes=["read_evidence"],
    )
    
    claims = ServicePrincipalClaims(
        service_id=svc_id,
        service_name="Concurrent Svc",
        allowed_scopes=["read_evidence"],
        issuer="https://auth.telecom.internal",
        token_hash=token_hash,
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        token_id=token_id,
    )
    with verifier._lock:
        verifier._verified_service_sessions[token_id] = claims
        
    # Must complete instantaneously without timeout
    assert verifier.validate_service_session(principal) is True
    
    # 2. Test validate_reviewer_session
    reviewer_id = "eng-charlie"
    rev_tok_id = "jti-rev-test-01"
    rev_tok_hash = "hash-rev-01"
    
    reviewer = AuthenticatedReviewer(
        operator_id=reviewer_id,
        role="NOC_TIER_2",
        token_id=rev_tok_id,
        auth_token_hash=rev_tok_hash,
    )
    
    rev_claims = ReviewerClaims(
        operator_id=reviewer_id,
        role="NOC_TIER_2",
        issuer="https://auth.telecom.internal",
        audience="piis-decision-support",
        token_hash=rev_tok_hash,
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        token_id=rev_tok_id,
    )
    with verifier._lock:
        verifier._verified_sessions[rev_tok_id] = rev_claims
        
    assert verifier.validate_reviewer_session(reviewer) is True


def test_concurrent_session_validation_under_load(configured_verifier):
    """Stress test session validations across 10 concurrent threads to ensure zero race conditions or deadlocks."""
    verifier, _, _ = configured_verifier
    
    # Register 20 sessions
    principals = []
    for i in range(20):
        t_id = f"jti-stress-{i:03d}"
        t_hash = f"hash-stress-{i:03d}"
        p = AuthenticatedServicePrincipal(
            service_id=f"sp-worker-{i}",
            service_name=f"Worker {i}",
            token_id=t_id,
            auth_token_hash=t_hash,
            scopes=["read_evidence"],
        )
        c = ServicePrincipalClaims(
            service_id=f"sp-worker-{i}",
            service_name=f"Worker {i}",
            allowed_scopes=["read_evidence"],
            issuer="https://auth.telecom.internal",
            token_hash=t_hash,
            issued_at_utc=datetime.now(timezone.utc).isoformat(),
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            token_id=t_id,
        )
        verifier._verified_service_sessions[t_id] = c
        principals.append(p)
        
    success_count = 0
    lock = threading.Lock()
    
    def worker_task():
        nonlocal success_count
        for _ in range(50):
            for p in principals:
                if verifier.validate_service_session(p):
                    with lock:
                        success_count += 1

    threads = [threading.Thread(target=worker_task) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
        assert not t.is_alive(), "Worker thread deadlocked during concurrent validation!"

    assert success_count == 8 * 50 * 20
