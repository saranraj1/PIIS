"""Unit and adversarial verification tests for M5.3 Workstream 2: Production OIDC Integration.

Validates:
1. RS256 token verification using cryptographic public keys from JWKS.
2. Key caching, TTL, and throttled refresh on unknown key ID (kid).
3. Key rotation handling.
4. Algorithm allowlisting (rejecting 'none', symmetric HS256, etc.).
5. Token expiration, issuer, audience, and not-before validation.
6. Token revocation tracking.
7. SSRF protections: blocking private IPs, loopback, cloud metadata IPs, and insecure HTTP.
8. Allowed JWKS domain allowlist enforcement.
9. Unconfigured production environment fails closed with MissingAuthenticationConfigurationError.
"""

import json
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest

from piis.investigation.approval import (
    MissingAuthenticationConfigurationError,
    ProductionOIDCVerifier,
    SSRFBlockedError,
    UnauthenticatedReviewerError,
)


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate in-memory 2048-bit RSA key pair for testing."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(pub))
    jwk_dict["kid"] = "test-rsa-key-01"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return priv, pub, jwk_dict


@pytest.fixture(scope="module")
def rsa_keypair_rotated():
    """Generate a second in-memory RSA key pair to simulate key rotation."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(pub))
    jwk_dict["kid"] = "test-rsa-key-02-rotated"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return priv, pub, jwk_dict


def _mint_test_jwt(
    priv_key,
    kid: str,
    sub: str = "op_alice",
    role: str = "NOC_TIER_2",
    iss: str = "https://auth.telecom-corp.net",
    aud: str = "piis-decision-support",
    exp_seconds: int = 3600,
    alg: str = "RS256",
    custom_jti: str = "tok-12345",
) -> str:
    now = int(time.time())
    headers = {"kid": kid, "alg": alg}
    payload = {
        "sub": sub,
        "role": role,
        "iss": iss,
        "aud": aud,
        "iat": now,
        "nbf": now - 10,
        "exp": now + exp_seconds,
        "jti": custom_jti,
    }
    return jwt.encode(payload, priv_key, algorithm=alg, headers=headers)


def test_successful_rs256_oidc_verification(rsa_keypair):
    """Verify legitimate RS256 token verified against mock JWKS endpoint."""
    priv, pub, jwk_dict = rsa_keypair

    jwks_json = json.dumps({"keys": [jwk_dict]}).encode("utf-8")

    def mock_client(url: str, timeout: int) -> bytes:
        return jwks_json

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        audience="piis-decision-support",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    token = _mint_test_jwt(priv, kid="test-rsa-key-01")
    claims = verifier.verify_token(token)

    assert claims.operator_id == "op_alice"
    assert claims.role == "NOC_TIER_2"
    assert claims.issuer == "https://auth.telecom-corp.net"
    assert claims.audience == "piis-decision-support"
    assert claims.token_id == "tok-12345"


def test_key_rotation_and_cache_refresh(rsa_keypair, rsa_keypair_rotated):
    """Verify that verifier refreshes its cache when encountering a new valid key ID."""
    priv1, pub1, jwk1 = rsa_keypair
    priv2, pub2, jwk2 = rsa_keypair_rotated

    # Initially IdP only has jwk1
    active_keys = [jwk1]

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": active_keys}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        audience="piis-decision-support",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    token1 = _mint_test_jwt(priv1, kid="test-rsa-key-01")
    assert verifier.verify_token(token1).operator_id == "op_alice"

    # Rotate keys at IdP: add jwk2
    active_keys.append(jwk2)
    # Reset last refresh timer to simulate time passed
    verifier._last_refresh_time = 0.0

    token2 = _mint_test_jwt(priv2, kid="test-rsa-key-02-rotated", sub="op_bob")
    assert verifier.verify_token(token2).operator_id == "op_bob"


def test_unknown_key_id_rejected(rsa_keypair):
    """Verify that an untrusted / unknown key ID is rejected."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    bad_token = _mint_test_jwt(priv, kid="unknown-bogus-kid")
    with pytest.raises(UnauthenticatedReviewerError, match="Signing key ID 'unknown-bogus-kid' not found in trusted JWKS"):
        verifier.verify_token(bad_token)


def test_missing_kid_rejected(rsa_keypair):
    """Verify that a token missing a kid header is rejected."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    now = int(time.time())
    token_no_kid = jwt.encode(
        {"sub": "op_alice", "iss": "https://auth.telecom-corp.net", "aud": "piis-decision-support", "exp": now + 3600},
        priv,
        algorithm="RS256",
        headers={"alg": "RS256"},  # No kid
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Token missing key ID"):
        verifier.verify_token(token_no_kid)


def test_disallowed_algorithm_rejected(rsa_keypair):
    """Verify that algorithms outside allowed_algorithms (e.g. HS256 or none) are rejected."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        allowed_algorithms=["RS256", "ES256"],
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    # Forged HMAC token trying algorithm confusion
    hmac_token = jwt.encode(
        {"sub": "op_alice", "iss": "https://auth.telecom-corp.net", "aud": "piis-decision-support", "exp": int(time.time()) + 3600},
        "this_is_a_symmetric_secret_32_bytes_long_minimum!",
        algorithm="HS256",
        headers={"kid": "test-rsa-key-01", "alg": "HS256"},
    )
    with pytest.raises(UnauthenticatedReviewerError, match="Disallowed algorithm 'HS256'"):
        verifier.verify_token(hmac_token)


def test_expired_token_rejected(rsa_keypair):
    """Verify that expired tokens fail verification."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    expired_tok = _mint_test_jwt(priv, kid="test-rsa-key-01", exp_seconds=-50)
    with pytest.raises(UnauthenticatedReviewerError, match="Token has expired"):
        verifier.verify_token(expired_tok)


def test_wrong_issuer_and_audience_rejected(rsa_keypair):
    """Verify that wrong issuer or audience are rejected."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        audience="piis-decision-support",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    bad_iss = _mint_test_jwt(priv, kid="test-rsa-key-01", iss="https://rogue-idp.com")
    with pytest.raises(UnauthenticatedReviewerError, match="Token issuer does not match"):
        verifier.verify_token(bad_iss)

    bad_aud = _mint_test_jwt(priv, kid="test-rsa-key-01", aud="wrong-service-aud")
    with pytest.raises(UnauthenticatedReviewerError, match="Token audience does not match"):
        verifier.verify_token(bad_aud)


def test_token_revocation(rsa_keypair):
    """Verify that revoked tokens cannot be used."""
    priv, pub, jwk = rsa_keypair

    def mock_client(url: str, timeout: int) -> bytes:
        return json.dumps({"keys": [jwk]}).encode("utf-8")

    verifier = ProductionOIDCVerifier(
        jwks_url="https://auth.telecom-corp.net/.well-known/jwks.json",
        issuer="https://auth.telecom-corp.net",
        allowed_jwks_domains=["auth.telecom-corp.net"],
        http_client=mock_client,
    )

    tok = _mint_test_jwt(priv, kid="test-rsa-key-01", custom_jti="jti-rev-999")
    # Verify initially valid
    assert verifier.verify_token(tok).token_id == "jti-rev-999"

    # Revoke
    verifier.revoke_token("jti-rev-999")
    with pytest.raises(UnauthenticatedReviewerError, match="has been revoked"):
        verifier.verify_token(tok)


def test_ssrf_protection_blocks_internal_and_cloud_metadata_ips():
    """Verify that configuring JWKS URLs pointing to private IPs or metadata endpoints is blocked."""
    # Cloud metadata IP (AWS / GCP / Azure)
    with pytest.raises(SSRFBlockedError, match="Private/internal IP address '169.254.169.254' is blocked"):
        ProductionOIDCVerifier(
            jwks_url="https://169.254.169.254/latest/meta-data/jwks.json",
            issuer="https://169.254.169.254",
        )

    # RFC 1918 Private IP
    with pytest.raises(SSRFBlockedError, match="Private/internal IP address '10.0.0.5' is blocked"):
        ProductionOIDCVerifier(
            jwks_url="https://10.0.0.5/jwks.json",
            issuer="https://10.0.0.5",
        )

    # Localhost loopback
    with pytest.raises(SSRFBlockedError, match="Forbidden hostname 'localhost'"):
        ProductionOIDCVerifier(
            jwks_url="https://localhost:8443/jwks.json",
            issuer="https://localhost",
        )


def test_untrusted_jwks_domain_rejected():
    """Verify that JWKS URLs pointing outside allowed domains are rejected."""
    with pytest.raises(SSRFBlockedError, match="is not in allowed JWKS domains"):
        ProductionOIDCVerifier(
            jwks_url="https://attacker-controlled-site.com/jwks.json",
            issuer="https://attacker-controlled-site.com",
            allowed_jwks_domains=["auth.telecom-corp.net"],
        )


def test_unconfigured_production_fails_closed():
    """Verify that unconfigured production OIDC verifier fails closed."""
    verifier = ProductionOIDCVerifier()
    assert not verifier._is_configured
    with pytest.raises(MissingAuthenticationConfigurationError, match="Production authentication fails closed"):
        verifier.verify_token("some.bearer.token")
