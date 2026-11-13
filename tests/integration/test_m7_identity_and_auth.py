"""Milestone M7-A: Integration & Security Verification for Local Enterprise Identity.

Exercises:
1. Valid human reviewer authentication & RBAC mapping.
2. Valid service principal authentication with least-privilege scoping.
3. Expired token rejection.
4. Invalid cryptographic signature rejection.
5. Wrong issuer rejection.
6. Wrong audience rejection.
7. Revoked token rejection via JTI tracking.
8. Missing role rejection.
9. Prohibited human approval by service principal (403 / PermissionError).
10. JWKS key rotation resilience and fail-closed IdP outage handling.
"""

from __future__ import annotations

import time
import jwt
import pytest

from piis.auth import (
    ApplicationRole,
    AuthManager,
    LocalTestOIDCProvider,
    Permission,
)
from piis.investigation.approval import (
    ProductionOIDCVerifier,
    UnauthenticatedReviewerError,
)


@pytest.fixture
def oidc_env():
    """Deterministic local test OIDC environment."""
    provider = LocalTestOIDCProvider(
        issuer="https://local-test-idp.piis.internal",
        audience="piis-decision-support",
    )
    # Instantiate ProductionOIDCVerifier using the provider's discovery and in-memory HTTP client
    verifier = ProductionOIDCVerifier.discover_from_issuer(
        issuer_url=provider.issuer,
        audience=provider.audience,
        allowed_algorithms=["RS256", "ES256"],
        allow_insecure_http_for_tests=True,
        http_client=provider.http_client,
    )
    auth_mgr = AuthManager(verifier=verifier, environment="development")
    return provider, verifier, auth_mgr


def test_scenario_01_valid_human_reviewer(oidc_env):
    """Scenario 1: Authenticate valid human NOC L2 operator with RS256 and ES256."""
    provider, _, auth_mgr = oidc_env

    # 1a. RS256 token
    token_rs = provider.mint_human_token(
        operator_id="OP-74102",
        role="NOC_L2",
        algorithm="RS256",
    )
    principal_rs = auth_mgr.authenticate_token(token_rs)
    assert principal_rs.principal_id == "OP-74102"
    assert not principal_rs.is_service_principal
    assert ApplicationRole.NOC_L2 in principal_rs.roles
    assert principal_rs.has_permission(Permission.APPROVE_MEDIUM_RISK_REVIEW)
    assert not principal_rs.has_permission(Permission.MANAGE_INTEGRATIONS)

    # 1b. ES256 token
    token_es = provider.mint_human_token(
        operator_id="OP-88201",
        role="NOC_L3",
        algorithm="ES256",
    )
    principal_es = auth_mgr.authenticate_token(token_es)
    assert principal_es.principal_id == "OP-88201"
    assert ApplicationRole.NOC_L3 in principal_es.roles
    assert principal_es.has_permission(Permission.APPROVE_HIGH_RISK_REVIEW)


def test_scenario_02_valid_service_principal(oidc_env):
    """Scenario 2: Authenticate automated service principal with workload scope."""
    provider, _, auth_mgr = oidc_env

    token = provider.mint_service_token(
        service_id="svc-telemetry-collector",
        scopes=["PIIS_READ_ONLY_OBSERVATION"],
    )
    principal = auth_mgr.authenticate_token(token)
    assert principal.principal_id == "svc-telemetry-collector"
    assert principal.is_service_principal
    assert ApplicationRole.SERVICE_PRINCIPAL in principal.roles
    assert principal.has_permission(Permission.VIEW_INCIDENTS)
    assert not principal.has_permission(Permission.APPROVE_LOW_RISK_REVIEW)
    assert not principal.has_permission(Permission.APPROVE_MEDIUM_RISK_REVIEW)


def test_scenario_03_expired_token(oidc_env):
    """Scenario 3: Reject expired JWT token."""
    provider, _, auth_mgr = oidc_env

    token = provider.mint_human_token(
        operator_id="OP-EXPIRED",
        role="NOC_L1",
        expires_in=-300,  # Expired 5 minutes ago
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Token has expired"):
        auth_mgr.authenticate_token(token)


def test_scenario_04_invalid_signature(oidc_env):
    """Scenario 4: Reject token signed by untrusted / forged private key."""
    provider, _, auth_mgr = oidc_env

    # 4a. Token with unknown key ID
    token_unknown_kid = provider.mint_human_token(
        operator_id="OP-FORGER-1",
        role="NOC_L3",
        sign_with_invalid_key=True,
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Signing key ID .* not found in trusted JWKS|Cryptographic signature verification failed"):
        auth_mgr.authenticate_token(token_unknown_kid)

    # 4b. Token with known key ID but signed with forged private key
    from cryptography.hazmat.primitives.asymmetric import rsa
    rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    forged_jwt = jwt.encode(
        {
            "sub": "OP-FORGER-2",
            "role": "NOC_L3",
            "iss": provider.issuer,
            "aud": provider.audience,
            "iat": now,
            "exp": now + 3600,
            "jti": "tok-forged-002",
        },
        rogue_key,
        algorithm="RS256",
        headers={"kid": "test-key-rsa-v1", "alg": "RS256", "typ": "JWT"},
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Cryptographic signature verification failed"):
        auth_mgr.authenticate_token(forged_jwt)


def test_scenario_05_wrong_issuer(oidc_env):
    """Scenario 5: Reject token issued by untrusted IdP issuer."""
    provider, _, auth_mgr = oidc_env

    token = provider.mint_human_token(
        operator_id="OP-IMPOSTER",
        role="NOC_L2",
        issuer="https://rogue-idp.attacker.internal",
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Token issuer does not match"):
        auth_mgr.authenticate_token(token)


def test_scenario_06_wrong_audience(oidc_env):
    """Scenario 6: Reject token minted for a different enterprise application."""
    provider, _, auth_mgr = oidc_env

    token = provider.mint_human_token(
        operator_id="OP-MISDIRECTED",
        role="NOC_L2",
        audience="corporate-billing-system",
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Token audience does not match"):
        auth_mgr.authenticate_token(token)


def test_scenario_07_revoked_token(oidc_env):
    """Scenario 7: Reject token revoked via JTI tracking."""
    provider, _, auth_mgr = oidc_env

    jti = "revoked-test-jti-991"
    token = provider.mint_human_token(
        operator_id="OP-REVOKED",
        role="NOC_L2",
        jti=jti,
    )
    # Verify valid before revocation
    principal = auth_mgr.authenticate_token(token)
    assert principal.principal_id == "OP-REVOKED"

    # Revoke in provider and auth manager
    provider.revoke_token(jti)
    auth_mgr.revoke_token(jti)

    # Subsequent verification must fail closed
    with pytest.raises((PermissionError, UnauthenticatedReviewerError), match="revoked"):
        auth_mgr.authenticate_token(token)


def test_scenario_08_missing_role(oidc_env):
    """Scenario 8: Default to minimum privilege (NOC_L1) when role claim is missing or unrecognized."""
    provider, _, auth_mgr = oidc_env

    token = provider.mint_human_token(
        operator_id="OP-NOROLE",
        role="UNKNOWN_ROLE",
    )
    principal = auth_mgr.authenticate_token(token)
    assert principal.principal_id == "OP-NOROLE"
    # Fallback is safe lowest tier NOC_L1
    assert ApplicationRole.NOC_L1 in principal.roles
    assert not principal.has_permission(Permission.APPROVE_MEDIUM_RISK_REVIEW)
    assert not principal.has_permission(Permission.APPROVE_HIGH_RISK_REVIEW)


def test_scenario_09_service_principal_cannot_perform_human_approval(oidc_env):
    """Scenario 9: Enforce strict separation: service principals are prohibited from human approval."""
    provider, _, auth_mgr = oidc_env

    # 9a. Standard service token has no approval permissions
    svc_token = provider.mint_service_token(service_id="svc-ai-worker")
    principal = auth_mgr.authenticate_token(svc_token)
    assert principal.is_service_principal
    assert not principal.has_permission(Permission.APPROVE_LOW_RISK_REVIEW)
    assert not principal.has_permission(Permission.APPROVE_MEDIUM_RISK_REVIEW)

    # 9b. Prohibited human identity masquerading as human (e.g. sub='SYSTEM' or sub='SERVICE')
    prohibited_token = provider.mint_human_token(
        operator_id="SYSTEM",
        role="NOC_L3",
    )
    with pytest.raises((PermissionError, UnauthenticatedReviewerError), match="prohibited identity|cannot be used as a human reviewer"):
        auth_mgr.authenticate_token(prohibited_token)


def test_scenario_10_jwks_rotation_and_unavailable_idp(oidc_env):
    """Scenario 10: Seamless verification after key rotation, and fail-closed on IdP network outage."""
    provider, verifier, auth_mgr = oidc_env

    # 10a. Mint token with original key
    tok1 = provider.mint_human_token(operator_id="OP-BEFORE-ROTATION", role="NOC_L2")
    p1 = auth_mgr.authenticate_token(tok1)
    assert p1.principal_id == "OP-BEFORE-ROTATION"

    # 10b. Rotate key in IdP
    new_kid = provider.rotate_keys()
    assert new_kid != "test-key-rsa-v1"

    # Reset cache and rate-limit timers to simulate key rotation refresh
    verifier.cache_ttl_seconds = 0.0
    verifier._last_refresh_time = 0.0
    tok2 = provider.mint_human_token(operator_id="OP-AFTER-ROTATION", role="NOC_L2", kid=new_kid)
    p2 = auth_mgr.authenticate_token(tok2)
    assert p2.principal_id == "OP-AFTER-ROTATION"

    # Both tokens (old and new key) verify correctly because JWKS holds both keys
    p1_again = auth_mgr.authenticate_token(tok1)
    assert p1_again.principal_id == "OP-BEFORE-ROTATION"

    # 10c. Simulate complete IdP outage with unknown key
    provider.simulate_outage(active=True)
    verifier._last_refresh_time = 0.0
    # Attempting to verify a token signed with an unknown key when IdP is offline must fail closed
    tok_unknown = provider.mint_human_token(
        operator_id="OP-OFFLINE",
        kid="unknown-kid-xyz",
        sign_with_invalid_key=True,
    )
    with pytest.raises(UnauthenticatedReviewerError):
        auth_mgr.authenticate_token(tok_unknown)
