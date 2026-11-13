"""Local Test OIDC Provider for Milestone M7 Portfolio Demonstration & Local Reproducibility.

Provides a deterministic, local OpenID Connect (OIDC) identity provider implementing
RFC 8414 discovery, dynamic JWKS generation, RS256/ES256 cryptographic signing,
token minting, key rotation, and revocation tracking.

NOTE: This is a local simulation / test provider for portfolio demonstration and testing.
It must never be labeled as an enterprise production IdP.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from cryptography.hazmat.primitives.asymmetric import ec, rsa
import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm



class LocalTestOIDCProvider:
    """Local deterministic OpenID Connect (OIDC) identity provider for test and portfolio execution."""

    def __init__(
        self,
        issuer: str = "https://local-test-idp.piis.internal",
        audience: str = "piis-decision-support",
    ):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.is_online = True
        self._revoked_jtis: Set[str] = set()

        # Generate initial cryptographic key pairs (RS256 and ES256)
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._active_rsa_kid = "test-key-rsa-v1"
        self._active_ec_kid = "test-key-ec-v1"

        self._generate_rsa_key(self._active_rsa_kid)
        self._generate_ec_key(self._active_ec_kid)

    def _generate_rsa_key(self, kid: str) -> None:
        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_key = priv_key.public_key()
        jwk_dict = json.loads(RSAAlgorithm.to_jwk(pub_key))
        jwk_dict["kid"] = kid
        jwk_dict["alg"] = "RS256"
        jwk_dict["use"] = "sig"
        self._keys[kid] = {
            "private_key": priv_key,
            "public_key": pub_key,
            "jwk": jwk_dict,
            "alg": "RS256",
        }

    def _generate_ec_key(self, kid: str) -> None:
        priv_key = ec.generate_private_key(ec.SECP256R1())
        pub_key = priv_key.public_key()
        jwk_dict = json.loads(ECAlgorithm.to_jwk(pub_key))
        jwk_dict["kid"] = kid
        jwk_dict["alg"] = "ES256"
        jwk_dict["use"] = "sig"
        self._keys[kid] = {
            "private_key": priv_key,
            "public_key": pub_key,
            "jwk": jwk_dict,
            "alg": "ES256",
        }

    def rotate_keys(self) -> str:
        """Rotate the active RSA key pair, keeping the previous key in JWKS for transition."""
        new_kid = f"test-key-rsa-v{len(self._keys) + 1}"
        self._generate_rsa_key(new_kid)
        self._active_rsa_kid = new_kid
        return new_kid

    def revoke_token(self, jti: str) -> None:
        """Mark a specific JWT ID as revoked."""
        self._revoked_jtis.add(jti)

    def is_token_revoked(self, jti: str) -> bool:
        """Check if JWT ID has been revoked."""
        return jti in self._revoked_jtis

    def simulate_outage(self, active: bool = True) -> None:
        """Simulate IdP network connectivity failure / downtime."""
        self.is_online = not active

    def get_openid_configuration(self) -> Dict[str, Any]:
        """RFC 8414 OpenID Connect Discovery document."""
        if not self.is_online:
            raise ConnectionError("IdP server is currently unavailable (simulated outage).")
        return {
            "issuer": self.issuer,
            "jwks_uri": f"{self.issuer}/.well-known/jwks.json",
            "response_types_supported": ["code", "token", "id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256", "ES256"],
            "scopes_supported": ["openid", "profile", "email"],
            "token_endpoint": f"{self.issuer}/oauth/v2/token",
            "userinfo_endpoint": f"{self.issuer}/oauth/v2/userinfo",
        }

    def get_jwks(self) -> Dict[str, Any]:
        """JSON Web Key Set (JWKS) containing all published public keys."""
        if not self.is_online:
            raise ConnectionError("IdP server is currently unavailable (simulated outage).")
        keys = [entry["jwk"] for entry in self._keys.values()]
        return {"keys": keys}

    def http_client(self, url: str, timeout: float = 5.0) -> bytes:
        """In-memory HTTP client adapter for direct injection into ProductionOIDCVerifier."""
        if not self.is_online:
            raise ConnectionError(f"HTTP GET {url} failed: Simulated IdP network outage.")

        clean_url = url.split("?")[0]
        if clean_url.endswith("/.well-known/openid-configuration"):
            return json.dumps(self.get_openid_configuration()).encode("utf-8")
        elif clean_url.endswith("/.well-known/jwks.json"):
            return json.dumps(self.get_jwks()).encode("utf-8")
        else:
            raise ValueError(f"HTTP 404: Unknown path '{url}' on LocalTestOIDCProvider.")

    def mint_human_token(
        self,
        operator_id: str = "OP-10492",
        role: str = "NOC_L2",
        expires_in: int = 3600,
        nbf_offset: int = 0,
        jti: Optional[str] = None,
        algorithm: str = "RS256",
        kid: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        custom_claims: Optional[Dict[str, Any]] = None,
        sign_with_invalid_key: bool = False,
    ) -> str:
        """Mint a cryptographic JWT representing an authenticated human NOC operator."""
        now = int(time.time())
        token_jti = jti or f"tok-human-{uuid.uuid4().hex[:12]}"

        selected_kid = kid or (self._active_rsa_kid if algorithm == "RS256" else self._active_ec_kid)
        if sign_with_invalid_key:
            # Generate temporary untrusted key not in JWKS
            if algorithm == "RS256":
                priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            else:
                priv_key = ec.generate_private_key(ec.SECP256R1())
            selected_kid = kid or "untrusted-kid-999"
        else:
            if selected_kid not in self._keys:
                raise KeyError(f"Key ID '{selected_kid}' not present in provider.")
            priv_key = self._keys[selected_kid]["private_key"]

        payload: Dict[str, Any] = {
            "sub": operator_id,
            "role": role,
            "iss": issuer or self.issuer,
            "aud": audience or self.audience,
            "iat": now,
            "nbf": now + nbf_offset,
            "exp": now + expires_in,
            "jti": token_jti,
            "auth_time": now,
            "operator_tier": role,
        }

        if custom_claims:
            payload.update(custom_claims)

        headers = {
            "kid": selected_kid,
            "alg": algorithm,
            "typ": "JWT",
        }

        return jwt.encode(payload, priv_key, algorithm=algorithm, headers=headers)

    def mint_service_token(
        self,
        service_id: str = "svc-telecom-ingestion",
        service_name: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        expires_in: int = 3600,
        jti: Optional[str] = None,
        algorithm: str = "RS256",
        kid: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        custom_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Mint a cryptographic JWT representing an automated internal service principal."""
        now = int(time.time())
        token_jti = jti or f"tok-svc-{uuid.uuid4().hex[:12]}"
        selected_kid = kid or (self._active_rsa_kid if algorithm == "RS256" else self._active_ec_kid)

        if selected_kid not in self._keys:
            raise KeyError(f"Key ID '{selected_kid}' not present in provider.")

        priv_key = self._keys[selected_kid]["private_key"]

        payload: Dict[str, Any] = {
            "sub": service_id,
            "service_id": service_id,
            "service_name": service_name or f"Service {service_id}",
            "principal_type": "SERVICE",
            "scopes": scopes or ["PIIS_READ_ONLY_OBSERVATION", "PIIS_DIAGNOSTIC_QUERY"],
            "iss": issuer or self.issuer,
            "aud": audience or self.audience,
            "iat": now,
            "exp": now + expires_in,
            "jti": token_jti,
        }

        if custom_claims:
            payload.update(custom_claims)

        headers = {
            "kid": selected_kid,
            "alg": algorithm,
            "typ": "JWT",
        }

        return jwt.encode(payload, priv_key, algorithm=algorithm, headers=headers)
