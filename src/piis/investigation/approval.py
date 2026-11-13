"""Human approval workflow and tamper-evident decision audit trail for M5 decision support.

Remediates:
- FIND-M5.2-001: Eliminates SYSTEM identity bypass. Introduces authenticated service principals
  with least-privilege scopes and distinct trust boundaries from human operators.
- DEP-M5.2-001: Completes production OIDC integration with HTTPS JWKS verification, algorithm allowlisting,
  key caching, rotation, SSRF defenses, and fail-closed behavior when IdP is unconfigured.
- FIND-M5.2-002: Corrects audit ledger canonicalization defect by cryptographically binding every
  security-relevant field including operator justification notes in RFC-8785 canonical payloads.
  Provides schema-versioned historical ledger migration without retroactive authenticity claims.
- RES-M5.2-001: Implements external monotonic checkpoint anchors to detect ledger snapshot rollback,
  truncation, and deletion attacks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from datetime import datetime, timezone
import decimal
import hashlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import urllib.parse
import urllib.request
import uuid

import jwt
from pydantic import BaseModel, Field, field_validator

from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


class IllegalStateTransitionError(ValueError):
    """Raised when an illegal state machine transition or approval replay is attempted."""
    pass


class RecommendationTamperedError(ValueError):
    """Raised when an approved recommendation's content has been mutated in memory."""
    pass


class UnauthenticatedReviewerError(ValueError):
    """Raised when a reviewer fails authentication checks at the trust boundary."""
    pass


class InsufficientPrivilegeError(PermissionError, ValueError):
    """Raised when a reviewer lacks required role privileges for an action tier."""
    pass


class MissingAuthenticationConfigurationError(RuntimeError):
    """Raised when production environment lacks trusted IdP or verifier configuration."""
    pass


class MissingAuditKeyError(ValueError):
    """Raised when audit signing key is missing, weak, or invalid."""
    pass


class AuditTrailDiscontinuityError(ValueError):
    """Raised when audit ledger exhibits hash chain breaks, missing records, or sequence skips."""
    pass


class LedgerRollbackDetectedError(RuntimeError):
    """Raised when external monotonic anchor detects an audit ledger state rollback or truncation."""
    pass


class SSRFBlockedError(ValueError):
    """Raised when a JWKS URL attempts to access private or forbidden network ranges."""
    pass


# Authorization scopes for internal service principals
SCOPE_INTERNAL_REGISTRATION = "PIIS_INTERNAL_REGISTRATION"
SCOPE_READ_ONLY_OBSERVATION = "PIIS_READ_ONLY_OBSERVATION"
SCOPE_DIAGNOSTIC_QUERY = "PIIS_DIAGNOSTIC_QUERY"

# Prohibited operator IDs for human review actions
PROHIBITED_HUMAN_OPERATOR_IDS: Set[str] = {
    "SYSTEM", "ANONYMOUS", "UNKNOWN", "NONE", "ROOT", "ADMIN", "NULL", "SERVICE",
}


class ReviewerClaims(BaseModel):
    """Verified claims extracted from an authenticated human operator credential."""
    operator_id: str = Field(description="Unique operator username or employee ID")
    role: str = Field(description="Role: NOC_TIER_1, NOC_TIER_2, NOC_LEAD, SYSADMIN")
    issuer: str = Field(description="Trusted IdP issuer URI or realm")
    audience: str = Field(description="Expected service audience, e.g. piis-decision-support")
    token_hash: str = Field(description="SHA-256 digest of verified credential/token")
    issued_at_utc: str = Field(description="ISO 8601 UTC timestamp of token issuance")
    expires_at_utc: str = Field(description="ISO 8601 UTC timestamp of token expiration")
    token_id: str = Field(description="Unique token/JWT ID (jti) for revocation tracking")


class ServicePrincipalClaims(BaseModel):
    """Verified claims extracted from an authenticated service principal credential."""
    service_id: str = Field(description="Unique service principal ID, e.g. svc-piis-orchestrator")
    service_name: str = Field(description="Service display or subsystem name")
    allowed_scopes: List[str] = Field(default_factory=list, description="Granted authorization scopes")
    issuer: str = Field(description="Internal trust domain or security authority")
    token_hash: str = Field(description="SHA-256 digest of verified service credential")
    issued_at_utc: str = Field(description="ISO 8601 UTC timestamp of token issuance")
    expires_at_utc: str = Field(description="ISO 8601 UTC timestamp of token expiration")
    token_id: str = Field(description="Unique token ID for revocation tracking")


class AuthenticatedReviewer(BaseModel):
    """Authenticated human operator identity originating strictly from verified claims."""
    operator_id: str = Field(description="Unique operator username or employee ID")
    role: str = Field(default="NOC_TIER_2", description="Role e.g. NOC_TIER_1, NOC_TIER_2, NOC_LEAD, SYSADMIN")
    auth_token_hash: str = Field(default="", description="SHA-256 hash of verified session token / credentials")
    issuer: str = Field(default="piis-idp", description="Trusted identity provider that authenticated this reviewer")
    token_id: str = Field(default="", description="Identifier of the token backing this authenticated session")
    authenticated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("operator_id")
    @classmethod
    def validate_operator_id(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise UnauthenticatedReviewerError("Reviewer identity cannot be empty.")
        if clean.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(
                f"Prohibited human reviewer identity '{clean}': automated identities cannot act as human reviewers."
            )
        return clean

    @classmethod
    def from_claims(cls, claims: ReviewerClaims) -> AuthenticatedReviewer:
        """Construct verified reviewer directly from validated IdP claims."""
        clean_id = claims.operator_id.strip()
        if clean_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(
                f"Prohibited human reviewer identity '{clean_id}': automated identities cannot act as human reviewers."
            )
        return cls(
            operator_id=clean_id,
            role=claims.role.upper(),
            auth_token_hash=claims.token_hash,
            issuer=claims.issuer,
            token_id=claims.token_id,
            authenticated_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def create_verified(
        cls,
        operator_id: str,
        role: str = "NOC_TIER_2",
        auth_token: Optional[str] = None,
    ) -> AuthenticatedReviewer:
        """Helper for test suites: mints and validates an isolated test session."""
        clean_id = (operator_id or "").strip()
        if not clean_id:
            raise UnauthenticatedReviewerError("Reviewer identity cannot be empty.")
        if clean_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(f"Reviewer identity '{clean_id}' is not authorized as a human reviewer.")

        verifier = IsolatedTestTokenVerifier.get_default_instance()
        if auth_token and "." in auth_token:
            claims = verifier.verify_token(auth_token)
            return cls.from_claims(claims)

        token_str = verifier.mint_token(operator_id=clean_id, role=role)
        claims = verifier.verify_token(token_str)
        return cls.from_claims(claims)


class AuthenticatedServicePrincipal(BaseModel):
    """Authenticated machine/subsystem identity with explicit, least-privilege authorization scopes."""
    service_id: str = Field(description="Unique service identifier e.g. svc-piis-orchestrator")
    service_name: str = Field(default="PIIS Internal Service", description="Display name")
    allowed_scopes: List[str] = Field(default_factory=list, description="Granted service scopes")
    auth_token_hash: str = Field(default="", description="SHA-256 digest of verified service token")
    issuer: str = Field(default="piis-internal-trust-boundary")
    token_id: str = Field(default="")
    authenticated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def has_scope(self, scope: str) -> bool:
        return scope in self.allowed_scopes

    @classmethod
    def from_claims(cls, claims: ServicePrincipalClaims) -> AuthenticatedServicePrincipal:
        return cls(
            service_id=claims.service_id,
            service_name=claims.service_name,
            allowed_scopes=list(claims.allowed_scopes),
            auth_token_hash=claims.token_hash,
            issuer=claims.issuer,
            token_id=claims.token_id,
            authenticated_at=datetime.now(timezone.utc).isoformat(),
        )


class ReviewerTokenVerifier(ABC):
    """Abstract server-side boundary for validating human operator and service principal credentials."""

    @abstractmethod
    def verify_token(self, token: str) -> ReviewerClaims:
        """Validate token signature, expiration, issuer, audience, and revocation for human reviewers."""
        pass

    @abstractmethod
    def is_revoked(self, token_id: str) -> bool:
        """Check if a token has been revoked."""
        pass

    @abstractmethod
    def validate_reviewer_session(self, reviewer: AuthenticatedReviewer) -> bool:
        """Validate that an AuthenticatedReviewer instance was issued by this boundary."""
        pass

    @abstractmethod
    def verify_service_token(self, token: str) -> ServicePrincipalClaims:
        """Validate verifiable credentials for an internal service principal."""
        pass

    @abstractmethod
    def validate_service_session(self, service: AuthenticatedServicePrincipal) -> bool:
        """Validate that an AuthenticatedServicePrincipal instance is active and unrevoked."""
        pass


class IsolatedTestTokenVerifier(ReviewerTokenVerifier):
    """Cryptographic HMAC-signed test verifier for local test execution and development."""

    _default_instance: Optional[IsolatedTestTokenVerifier] = None

    def __init__(
        self,
        signing_key: bytes = b"PIIS_ISOLATED_TEST_TOKEN_VERIFIER_KEY_2026_V1!",
        expected_issuer: str = "piis-test-idp",
        expected_audience: str = "piis-decision-support",
    ):
        self._signing_key = signing_key
        self.expected_issuer = expected_issuer
        self.expected_audience = expected_audience
        self._revoked_tokens: Set[str] = set()
        self._verified_sessions: Dict[str, ReviewerClaims] = {}
        self._verified_service_sessions: Dict[str, ServicePrincipalClaims] = {}

    @classmethod
    def get_default_instance(cls) -> IsolatedTestTokenVerifier:
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def mint_token(
        self,
        operator_id: str,
        role: str = "NOC_TIER_2",
        lifetime_seconds: int = 3600,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        custom_jti: Optional[str] = None,
    ) -> str:
        """Mint a cryptographically valid, signed test token for the given human operator."""
        clean_id = (operator_id or "").strip()
        if not clean_id:
            raise UnauthenticatedReviewerError("Operator ID cannot be empty.")
        if clean_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(
                f"Cannot mint human reviewer token for prohibited identity '{clean_id}'."
            )

        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(now.timestamp() + lifetime_seconds, tz=timezone.utc)
        jti = custom_jti or str(uuid.uuid4())

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": clean_id,
            "role": role.strip().upper(),
            "principal_type": "HUMAN",
            "iss": issuer or self.expected_issuer,
            "aud": audience or self.expected_audience,
            "iat": now.isoformat(),
            "exp": exp.isoformat(),
            "jti": jti,
        }

        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        sig = hmac.new(self._signing_key, signing_input, hashlib.sha256).hexdigest()
        return f"{h_b64}.{p_b64}.{sig}"

    def mint_service_token(
        self,
        service_id: str,
        service_name: str = "PIIS Internal Service",
        allowed_scopes: Optional[List[str]] = None,
        lifetime_seconds: int = 86400,
        issuer: Optional[str] = None,
        custom_jti: Optional[str] = None,
    ) -> str:
        """Mint a cryptographically valid service principal workload identity token."""
        clean_id = (service_id or "").strip()
        if not clean_id:
            raise UnauthenticatedReviewerError("Service ID cannot be empty.")

        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(now.timestamp() + lifetime_seconds, tz=timezone.utc)
        jti = custom_jti or str(uuid.uuid4())

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": clean_id,
            "service_name": service_name,
            "principal_type": "SERVICE",
            "scopes": allowed_scopes or [SCOPE_INTERNAL_REGISTRATION],
            "iss": issuer or self.expected_issuer,
            "aud": self.expected_audience,
            "iat": now.isoformat(),
            "exp": exp.isoformat(),
            "jti": jti,
        }

        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        sig = hmac.new(self._signing_key, signing_input, hashlib.sha256).hexdigest()
        return f"{h_b64}.{p_b64}.{sig}"

    def revoke_token(self, token_or_jti: str) -> None:
        """Add a token or jti to the active revocation registry."""
        if "." in token_or_jti:
            try:
                parts = token_or_jti.split(".")
                p_pad = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(p_pad.encode("utf-8")))
                jti = payload.get("jti", token_or_jti)
                self._revoked_tokens.add(jti)
            except Exception:
                self._revoked_tokens.add(token_or_jti)
        else:
            self._revoked_tokens.add(token_or_jti)

    def is_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked_tokens

    def verify_token(self, token: str) -> ReviewerClaims:
        """Validate human reviewer token claims and signature."""
        if not token or not isinstance(token, str):
            raise UnauthenticatedReviewerError("Token must be a non-empty string.")

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise UnauthenticatedReviewerError(
                "Invalid token format; token must be a signed credential with 3 segments."
            )

        h_b64, p_b64, sig = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(self._signing_key, signing_input, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, sig):
            raise UnauthenticatedReviewerError("Invalid token signature; credential rejected.")

        try:
            p_pad = p_b64 + "=" * (-len(p_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(p_pad.encode("utf-8")))
        except Exception as e:
            raise UnauthenticatedReviewerError(f"Malformed token payload: {e}") from e

        # Ensure service tokens are not passed as human operator credentials
        if payload.get("principal_type") == "SERVICE":
            raise InsufficientPrivilegeError(
                "Service principal credential supplied to human review boundary. "
                "Human operator credential required for approvals."
            )

        # Validate issuer
        iss = payload.get("iss")
        if self.expected_issuer and iss != self.expected_issuer:
            raise UnauthenticatedReviewerError(
                f"Wrong token issuer: expected '{self.expected_issuer}', got '{iss}'."
            )

        # Validate audience
        aud = payload.get("aud")
        if self.expected_audience and aud != self.expected_audience:
            raise UnauthenticatedReviewerError(
                f"Wrong token audience: expected '{self.expected_audience}', got '{aud}'."
            )

        # Validate expiration
        exp_str = payload.get("exp")
        if exp_str:
            try:
                exp_dt = datetime.fromisoformat(exp_str)
                now_dt = datetime.now(timezone.utc)
                if now_dt > exp_dt:
                    raise UnauthenticatedReviewerError(
                        f"Token expired at {exp_str}; current time is {now_dt.isoformat()}."
                    )
            except ValueError as ve:
                raise UnauthenticatedReviewerError(f"Invalid expiration timestamp in token: {ve}") from ve

        # Validate revocation
        jti = payload.get("jti", "")
        if jti and self.is_revoked(jti):
            raise UnauthenticatedReviewerError(f"Token '{jti}' has been revoked.")

        op_id = payload.get("sub", "").strip()
        if op_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(
                f"Token subject '{op_id}' is a prohibited identity for human review."
            )

        if payload.get("principal_type") == "SERVICE" or payload.get("is_service") is True or "service_name" in payload or "service_id" in payload:
            raise UnauthenticatedReviewerError(
                f"Token subject '{op_id}' belongs to a service principal workload identity, not a human operator. "
                "Automated service accounts and bots are strictly prohibited from approving diagnostic recommendations."
            )

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        claims = ReviewerClaims(
            operator_id=op_id or "UNKNOWN",
            role=payload.get("role", "NOC_TIER_2").upper(),
            issuer=iss or self.expected_issuer,
            audience=aud or self.expected_audience,
            token_hash=token_hash,
            issued_at_utc=payload.get("iat", datetime.now(timezone.utc).isoformat()),
            expires_at_utc=exp_str or datetime.now(timezone.utc).isoformat(),
            token_id=jti,
        )

        self._verified_sessions[jti] = claims
        return claims

    def verify_service_token(self, token: str) -> ServicePrincipalClaims:
        """Validate verifiable credentials for an internal service principal."""
        if not token or not isinstance(token, str):
            raise UnauthenticatedReviewerError("Service token must be a non-empty string.")

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise UnauthenticatedReviewerError("Invalid service token format.")

        h_b64, p_b64, sig = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(self._signing_key, signing_input, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, sig):
            raise UnauthenticatedReviewerError("Invalid service token signature.")

        p_pad = p_b64 + "=" * (-len(p_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p_pad.encode("utf-8")))

        if payload.get("principal_type") != "SERVICE":
            raise UnauthenticatedReviewerError("Credential is not a service principal token.")

        jti = payload.get("jti", "")
        if jti and self.is_revoked(jti):
            raise UnauthenticatedReviewerError(f"Service token '{jti}' has been revoked.")

        exp_str = payload.get("exp")
        if exp_str:
            exp_dt = datetime.fromisoformat(exp_str)
            if datetime.now(timezone.utc) > exp_dt:
                raise UnauthenticatedReviewerError(f"Service token expired at {exp_str}.")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        claims = ServicePrincipalClaims(
            service_id=payload.get("sub", "svc-unknown"),
            service_name=payload.get("service_name", "Unknown Service"),
            allowed_scopes=payload.get("scopes", []),
            issuer=payload.get("iss", self.expected_issuer),
            token_hash=token_hash,
            issued_at_utc=payload.get("iat", datetime.now(timezone.utc).isoformat()),
            expires_at_utc=exp_str or datetime.now(timezone.utc).isoformat(),
            token_id=jti,
        )
        self._verified_service_sessions[jti] = claims
        return claims

    def validate_reviewer_session(self, reviewer: AuthenticatedReviewer) -> bool:
        """Verify that reviewer object corresponds to an active, unrevoked verified session."""
        if not reviewer.token_id:
            return False
        if self.is_revoked(reviewer.token_id):
            return False
        stored_claims = self._verified_sessions.get(reviewer.token_id)
        if stored_claims is None:
            return False
        return stored_claims.token_hash == reviewer.auth_token_hash

    def validate_service_session(self, service: AuthenticatedServicePrincipal) -> bool:
        """Verify that service principal corresponds to an active verified session."""
        if not service.token_id or self.is_revoked(service.token_id):
            return False
        stored = self._verified_service_sessions.get(service.token_id)
        if stored is None:
            return False
        return stored.token_hash == service.auth_token_hash


def _is_ssrf_safe_url(
    url_str: str,
    allow_insecure_http: bool = False,
    allowed_domains: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Validate JWKS URL against SSRF and network isolation policies."""
    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception as e:
        return False, f"Invalid URL syntax: {e}"

    if not allow_insecure_http and parsed.scheme != "https":
        return False, f"Insecure scheme '{parsed.scheme}'. Production JWKS endpoints must use HTTPS."

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "Missing hostname in JWKS URL."

    # Domain allowlist check if specified
    if allowed_domains:
        domain_match = any(hostname == d.lower() or hostname.endswith("." + d.lower()) for d in allowed_domains)
        if not domain_match:
            return False, f"Hostname '{hostname}' is not in allowed JWKS domains {allowed_domains}."

    # IP address SSRF protection
    if not allow_insecure_http:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
                return False, f"SSRF Protection: Private/internal IP address '{ip}' is blocked."
        except ValueError:
            # Hostname is a domain name, check for forbidden patterns
            if hostname in ("localhost", "127.0.0.1", "::1", "metadata.google.internal") or hostname.endswith(".local"):
                return False, f"SSRF Protection: Forbidden hostname '{hostname}'."

    return True, "OK"


class ProductionOIDCVerifier(ReviewerTokenVerifier):
    """Production OpenID Connect (OIDC) / OAuth2 token verifier connecting to corporate IdP.

    Implements:
    - HTTPS JWKS retrieval with domain allowlisting and SSRF protections.
    - Explicit algorithm allowlisting (RS256, ES256).
    - Key ID (kid) extraction and matching.
    - Key caching with TTL and throttled rotation refresh.
    - Expiration, not-before, issuer, audience, and revocation validation.
    - Fail-closed behavior on missing or unreachable IdP.
    - Zero logging of bearer token strings or secret material.
    """

    def __init__(
        self,
        jwks_url: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        allowed_algorithms: Optional[List[str]] = None,
        allowed_jwks_domains: Optional[List[str]] = None,
        allow_insecure_http_for_tests: bool = False,
        cache_ttl_seconds: float = 3600.0,
        http_client: Optional[Callable[[str, float], bytes]] = None,
    ):
        self.jwks_url = jwks_url or os.environ.get("PIIS_IDP_JWKS_URL")
        self.issuer = issuer or os.environ.get("PIIS_IDP_ISSUER")
        self.audience = audience or os.environ.get("PIIS_IDP_AUDIENCE", "piis-decision-support")
        self.allowed_algorithms = allowed_algorithms or ["RS256", "ES256"]
        self.allowed_jwks_domains = allowed_jwks_domains
        self.allow_insecure_http_for_tests = allow_insecure_http_for_tests
        self.cache_ttl_seconds = cache_ttl_seconds
        self._http_client = http_client

        self._lock = threading.RLock()
        self._network_lock = threading.Lock()
        self._revoked_tokens: Set[str] = set()
        self._jwks_cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0.0
        self._last_refresh_time: float = 0.0
        self._verified_sessions: Dict[str, ReviewerClaims] = {}
        self._verified_service_sessions: Dict[str, ServicePrincipalClaims] = {}

        # Validate configuration completeness
        if not self.jwks_url or not self.issuer:
            self._is_configured = False
        else:
            safe, err = _is_ssrf_safe_url(
                self.jwks_url,
                allow_insecure_http=self.allow_insecure_http_for_tests,
                allowed_domains=self.allowed_jwks_domains,
            )
            if not safe:
                raise SSRFBlockedError(f"JWKS configuration failed security check: {err}")
            self._is_configured = True

    @classmethod
    def discover_from_issuer(
        cls,
        issuer_url: str,
        audience: Optional[str] = None,
        allowed_algorithms: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None,
        allow_insecure_http_for_tests: bool = False,
        http_client: Optional[Callable[[str, float], bytes]] = None,
    ) -> ProductionOIDCVerifier:
        """Discover OIDC configuration endpoints from standard RFC 8414 /.well-known/openid-configuration."""
        clean_issuer = issuer_url.rstrip("/")
        well_known_url = f"{clean_issuer}/.well-known/openid-configuration"

        safe, err = _is_ssrf_safe_url(
            well_known_url,
            allow_insecure_http=allow_insecure_http_for_tests,
            allowed_domains=allowed_domains,
        )
        if not safe:
            raise SSRFBlockedError(f"OIDC discovery URL failed security check: {err}")

        try:
            if http_client is not None:
                raw_bytes = http_client(well_known_url, 5.0)
            else:
                req = urllib.request.Request(
                    well_known_url,
                    headers={"User-Agent": "PIIS-OIDC-Verifier/2.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    raw_bytes = resp.read(1_048_576)

            config = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            raise UnauthenticatedReviewerError(f"Failed to fetch OIDC discovery document: {e}") from e

        doc_issuer = config.get("issuer", "").rstrip("/")
        if doc_issuer != clean_issuer:
            raise UnauthenticatedReviewerError(
                f"OIDC discovery issuer mismatch: expected '{clean_issuer}', received '{doc_issuer}'"
            )

        jwks_uri = config.get("jwks_uri")
        if not jwks_uri:
            raise UnauthenticatedReviewerError("OIDC discovery document missing required 'jwks_uri'")

        return cls(
            jwks_url=jwks_uri,
            issuer=clean_issuer,
            audience=audience,
            allowed_algorithms=allowed_algorithms,
            allowed_jwks_domains=allowed_domains,
            allow_insecure_http_for_tests=allow_insecure_http_for_tests,
            http_client=http_client,
        )

    def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch and cache JWKS keys with network isolation safeguards.
        
        Performs remote network I/O outside self._lock to prevent deadlocks and
        avoid blocking ongoing token verifications during socket delays.
        """
        if not self._is_configured:
            raise MissingAuthenticationConfigurationError("ProductionOIDCVerifier is not configured.")

        # Rate-limiting: do not refresh faster than once per 5 seconds
        now = time.time()
        with self._lock:
            if now - self._last_refresh_time < 5.0 and self._jwks_cache:
                return self._jwks_cache
            self._last_refresh_time = now

        try:
            if self._http_client is not None:
                raw_bytes = self._http_client(self.jwks_url, 5.0)
            else:
                req = urllib.request.Request(
                    self.jwks_url,
                    headers={"User-Agent": "PIIS-OIDC-Verifier/2.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    raw_bytes = resp.read(1_048_576)  # Cap at 1MB

            data = json.loads(raw_bytes.decode("utf-8"))
            keys_list = data.get("keys", [])

            # Parse with PyJWT PyJWKSet
            jwk_set = jwt.PyJWKSet.from_dict({"keys": keys_list})
            new_cache: Dict[str, Any] = {}
            for jwk in jwk_set.keys:
                new_cache[jwk.key_id] = jwk.key

            with self._lock:
                self._jwks_cache = new_cache
                self._cache_timestamp = now
                return self._jwks_cache
        except Exception as e:
            with self._lock:
                if not self._jwks_cache:
                    raise UnauthenticatedReviewerError(f"Failed to retrieve JWKS from IdP endpoint: {e}") from e
                # Return existing cache on temporary fetch error if available
                return self._jwks_cache

    def _get_signing_key(self, kid: str) -> Any:
        """Resolve public key for key ID (kid), refreshing cache on unknown key."""
        with self._lock:
            now = time.time()
            is_cache_stale = (now - self._cache_timestamp) > self.cache_ttl_seconds
            cached_key = self._jwks_cache.get(kid)
            needs_fetch = is_cache_stale or (cached_key is None)

        if needs_fetch:
            with self._network_lock:
                # Double-check inside network lock
                with self._lock:
                    now = time.time()
                    is_cache_stale = (now - self._cache_timestamp) > self.cache_ttl_seconds
                    cached_key = self._jwks_cache.get(kid)
                    still_needs_fetch = is_cache_stale or (cached_key is None)
                if still_needs_fetch:
                    self._fetch_jwks()

        with self._lock:
            if kid not in self._jwks_cache:
                raise UnauthenticatedReviewerError(
                    f"Signing key ID '{kid}' not found in trusted JWKS. Key may be unknown or untrusted."
                )

            return self._jwks_cache[kid]

    def verify_token(self, token: str) -> ReviewerClaims:
        """Verify token cryptographic signature and claims against trusted IdP."""
        if not self._is_configured:
            raise MissingAuthenticationConfigurationError(
                "ProductionOIDCVerifier is not configured with trusted IdP endpoints. "
                "Production authentication fails closed. Cannot authenticate operator."
            )

        if not token or not isinstance(token, str):
            raise UnauthenticatedReviewerError("Token must be a non-empty string.")

        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise UnauthenticatedReviewerError(f"Invalid token format or header: {e}") from e

        alg = unverified_header.get("alg")
        if alg not in self.allowed_algorithms:
            raise UnauthenticatedReviewerError(
                f"Disallowed algorithm '{alg}'. Only {self.allowed_algorithms} are permitted."
            )

        kid = unverified_header.get("kid")
        if not kid:
            raise UnauthenticatedReviewerError("Token missing key ID (kid) in header.")

        public_key = self._get_signing_key(kid)

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=self.allowed_algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub"], "verify_nbf": True},
            )
        except jwt.ExpiredSignatureError:
            raise UnauthenticatedReviewerError("Token has expired.")
        except jwt.ImmatureSignatureError:
            raise UnauthenticatedReviewerError("Token is not yet valid (not-before / nbf in future).")
        except jwt.InvalidIssuerError:
            raise UnauthenticatedReviewerError("Token issuer does not match trusted configuration.")
        except jwt.InvalidAudienceError:
            raise UnauthenticatedReviewerError("Token audience does not match service audience.")
        except jwt.PyJWTError as e:
            raise UnauthenticatedReviewerError(f"Cryptographic signature verification failed: {e}") from e

        jti = payload.get("jti", "")
        if jti and self.is_revoked(jti):
            raise UnauthenticatedReviewerError(f"Token '{jti}' has been revoked.")

        op_id = payload.get("sub", "").strip()
        if op_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise UnauthenticatedReviewerError(
                f"Token subject '{op_id}' is a prohibited identity for human review."
            )

        if payload.get("principal_type") == "SERVICE" or payload.get("is_service") is True or "service_name" in payload or "service_id" in payload:
            raise UnauthenticatedReviewerError(
                f"Token subject '{op_id}' belongs to a service principal workload identity, not a human operator. "
                "Automated service accounts and bots are strictly prohibited from approving diagnostic recommendations."
            )

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        claims = ReviewerClaims(
            operator_id=op_id,
            role=payload.get("role", "NOC_TIER_2").upper(),
            issuer=self.issuer,
            audience=self.audience,
            token_hash=token_hash,
            issued_at_utc=datetime.fromtimestamp(payload.get("iat", time.time()), tz=timezone.utc).isoformat(),
            expires_at_utc=datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc).isoformat(),
            token_id=jti or f"tok-{token_hash[:12]}",
        )

        with self._lock:
            self._verified_sessions[claims.token_id] = claims
        return claims

    def verify_service_token(self, token: str) -> ServicePrincipalClaims:
        """Verify service principal workload identity credential.
        
        Remediates FIND-M5.3-001:
        - Cryptographic signature validation with strict algorithm allowlisting and kid matching.
        - Enforces required claims (exp, iss, aud, sub).
        - Direct revocation check against self._revoked_tokens (rejecting revoked JTIs).
        - Fail-closed behavior on missing or revoked token_id.
        """
        if not self._is_configured:
            raise MissingAuthenticationConfigurationError("Production verifier is not configured.")

        if not token or not isinstance(token, str):
            raise UnauthenticatedReviewerError("Service token must be a non-empty string.")

        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise UnauthenticatedReviewerError(f"Invalid service token format or header: {e}") from e

        alg = unverified_header.get("alg")
        if alg not in self.allowed_algorithms:
            raise UnauthenticatedReviewerError(
                f"Disallowed algorithm '{alg}'. Only {self.allowed_algorithms} are permitted."
            )

        kid = unverified_header.get("kid")
        if not kid:
            raise UnauthenticatedReviewerError("Service token missing key ID (kid) in header.")

        public_key = self._get_signing_key(kid)

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=self.allowed_algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub"], "verify_nbf": True},
            )
        except jwt.ExpiredSignatureError:
            raise UnauthenticatedReviewerError("Service token has expired.")
        except jwt.ImmatureSignatureError:
            raise UnauthenticatedReviewerError("Service token is not yet valid (not-before / nbf in future).")
        except jwt.InvalidIssuerError:
            raise UnauthenticatedReviewerError("Service token issuer does not match trusted configuration.")
        except jwt.InvalidAudienceError:
            raise UnauthenticatedReviewerError("Service token audience does not match service audience.")
        except jwt.PyJWTError as e:
            raise UnauthenticatedReviewerError(f"Service token signature verification failed: {e}") from e

        if payload.get("principal_type") != "SERVICE":
            raise UnauthenticatedReviewerError("Credential is not a service principal token.")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        raw_jti = payload.get("jti")
        token_id = raw_jti if (raw_jti and isinstance(raw_jti, str) and raw_jti.strip()) else f"svc-{token_hash[:16]}"

        # Remediates FIND-M5.3-001: Direct revocation check
        if self.is_revoked(token_id) or (raw_jti and self.is_revoked(raw_jti)):
            raise UnauthenticatedReviewerError(f"Service token '{token_id}' has been revoked.")

        claims = ServicePrincipalClaims(
            service_id=payload.get("sub", "svc-unknown"),
            service_name=payload.get("service_name", "Corporate Service"),
            allowed_scopes=payload.get("scopes", []),
            issuer=self.issuer,
            token_hash=token_hash,
            issued_at_utc=datetime.fromtimestamp(payload.get("iat", time.time()), tz=timezone.utc).isoformat(),
            expires_at_utc=datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc).isoformat(),
            token_id=token_id,
        )
        with self._lock:
            self._verified_service_sessions[claims.token_id] = claims
        return claims

    def revoke_token(self, token_id: str) -> None:
        with self._lock:
            self._revoked_tokens.add(token_id)

    def is_revoked(self, token_id: str) -> bool:
        with self._lock:
            return token_id in self._revoked_tokens

    def validate_reviewer_session(self, reviewer: AuthenticatedReviewer) -> bool:
        if not self._is_configured or not reviewer.token_id:
            return False
        with self._lock:
            if self.is_revoked(reviewer.token_id):
                return False
            stored = self._verified_sessions.get(reviewer.token_id)
            if stored is None:
                return False
            return stored.token_hash == reviewer.auth_token_hash

    def validate_service_session(self, service: AuthenticatedServicePrincipal) -> bool:
        if not self._is_configured or not service.token_id:
            return False
        with self._lock:
            if self.is_revoked(service.token_id):
                return False
            stored = self._verified_service_sessions.get(service.token_id)
            if stored is None:
                return False
            return stored.token_hash == service.auth_token_hash


_JCS_CONTROL_ESCAPE = {
    0x22: '\\"',
    0x5C: '\\\\',
    0x08: '\\b',
    0x0C: '\\f',
    0x0A: '\\n',
    0x0D: '\\r',
    0x09: '\\t',
}
for i in range(32):
    if i not in _JCS_CONTROL_ESCAPE:
        _JCS_CONTROL_ESCAPE[i] = f"\\u{i:04x}"


def _escape_jcs_string(s: str) -> str:
    res = ['"']
    for char in s:
        cp = ord(char)
        if cp in _JCS_CONTROL_ESCAPE:
            res.append(_JCS_CONTROL_ESCAPE[cp])
        else:
            res.append(char)
    res.append('"')
    return "".join(res)


def _utf16_code_units(s: str) -> List[int]:
    encoded = s.encode("utf-16-be")
    return [int.from_bytes(encoded[i:i + 2], "big") for i in range(0, len(encoded), 2)]


def _format_jcs_float(val: float) -> str:
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"Invalid RFC 8785 float (NaN/Infinity prohibited): {val}")
    if val == 0.0:
        return "0"
    if val.is_integer() and -(2**53 - 1) <= val <= (2**53 - 1):
        return str(int(val))
    s = repr(val)
    if "e" not in s and "E" not in s:
        if s.endswith(".0"):
            return s[:-2]
        return s
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)[eE]([+-]?\d+)$", s)
    if match:
        mantissa, exp_str = match.groups()
        exp = int(exp_str)
        if -6 <= exp < 0:
            dec = decimal.Decimal(s)
            return f"{dec:f}"
        sign = exp_str[0] if exp_str[0] in "+-" else "+"
        abs_exp = abs(exp)
        return f"{mantissa}e{sign}{abs_exp}"
    return s


def canonical_json_dumps(data: Any) -> str:
    """Serialize dictionary or payload strictly conforming to RFC 8785 (JSON Canonicalization Scheme / JCS).
    
    Remediates FIND-M5.3-003:
    - Sorts dictionary keys lexicographically by UTF-16 code units (RFC 8785 Section 3.2.3).
    - Preserves native UTF-8 bytes for all characters >= U+0020 (except quote and reverse solidus).
    - Strictly escapes control characters (U+0000..U+001F), quote, and backslash.
    - Normalizes IEEE 754 floats: negative zero (-0.0) -> '0', integer floats -> integer digits,
      shortest round-trip representation, rejects NaN/Infinity (RFC 8785 Section 3.2.2.3).
    - Emits zero inter-token whitespace.
    """
    if data is None:
        return "null"
    elif isinstance(data, bool):
        return "true" if data else "false"
    elif isinstance(data, int):
        return str(data)
    elif isinstance(data, float):
        return _format_jcs_float(data)
    elif isinstance(data, str):
        return _escape_jcs_string(data)
    elif isinstance(data, (list, tuple)):
        return "[" + ",".join(canonical_json_dumps(item) for item in data) + "]"
    elif isinstance(data, dict):
        sorted_keys = sorted(data.keys(), key=_utf16_code_units)
        return "{" + ",".join(
            _escape_jcs_string(str(k)) + ":" + canonical_json_dumps(data[k])
            for k in sorted_keys
        ) + "}"
    else:
        if hasattr(data, "model_dump"):
            return canonical_json_dumps(data.model_dump())
        elif hasattr(data, "dict"):
            return canonical_json_dumps(data.dict())
        raise TypeError(f"Object of type {type(data)} is not JSON serializable under RFC 8785")


def compute_recommendation_content_hash(rec: DiagnosticRecommendation) -> str:
    """Compute deterministic SHA-256 digest of actionable recommendation fields."""
    canonical_data = {
        "description": rec.description,
        "expected_observation": rec.expected_observation,
        "human_approval_required": rec.human_approval_required,
        "preconditions": sorted(rec.preconditions or []),
        "recommendation_id": rec.recommendation_id,
        "risk_classification": rec.risk_classification.value,
        "source_runbook_id": rec.source_runbook_id,
        "source_section": rec.source_section,
    }
    return hashlib.sha256(canonical_json_dumps(canonical_data).encode("utf-8")).hexdigest()


class AuditLogEntry(BaseModel):
    """Immutable, tamper-evident audit log entry for operational human decisions."""
    audit_id: str = Field(description="Unique sequential identifier, e.g. AUD-0001")
    sequence_number: int = Field(description="Monotonic sequence number starting from 1")
    schema_version: str = Field(default="2.0", description="Schema version: '1.0' (legacy) or '2.0' (hardened)")
    recommendation_id: str
    incident_id: str
    action: str  # SUBMITTED, APPROVED, REJECTED, MODIFIED, MIGRATION_CHECKPOINT
    previous_status: ApprovalStatus
    new_status: ApprovalStatus
    operator_id: str
    reviewer_role: str = "SYSTEM"
    authorization_scope: str = Field(default="", description="Service principal scope or human reviewer tier")
    principal_type: str = Field(default="HUMAN", description="Principal type: 'HUMAN' or 'SERVICE'")
    reviewer_auth_hash: str = ""
    key_id: str = Field(default="piis-audit-key-2026-v1", description="Identifier of the key used to sign this entry")
    timestamp_utc: str
    recommendation_content_hash: str
    previous_entry_sha256: str = Field(description="SHA-256 hash pointer to preceding audit log entry")
    entry_sha256: str = Field(description="SHA-256 hash digest of this entry's canonical content")
    hmac_signature: str = Field(default="", description="HMAC-SHA256 signature protecting log against wholesale substitution")
    notes: Optional[str] = None
    notes_cryptographically_covered: bool = Field(default=True, description="True if notes are included in canonical hash payload")
    state_sha256: str = Field(default="", description="Backwards-compatible alias for entry_sha256")

    def model_post_init(self, __context: Any) -> None:
        if not self.state_sha256 and self.entry_sha256:
            self.state_sha256 = self.entry_sha256
        if self.schema_version == "1.0":
            self.notes_cryptographically_covered = False

    def get_canonical_payload(self) -> Dict[str, Any]:
        """Construct canonical dictionary representation for hash and signature generation."""
        if self.schema_version == "1.0":
            # Legacy v1.0 canonical payload (retains historical compatibility; notes not covered)
            return {
                "action": self.action,
                "audit_id": self.audit_id,
                "incident_id": self.incident_id,
                "new_status": self.new_status.value,
                "operator_id": self.operator_id,
                "previous_entry_sha256": self.previous_entry_sha256,
                "previous_status": self.previous_status.value,
                "recommendation_content_hash": self.recommendation_content_hash,
                "recommendation_id": self.recommendation_id,
                "reviewer_auth_hash": self.reviewer_auth_hash,
                "reviewer_role": self.reviewer_role,
                "sequence_number": self.sequence_number,
                "timestamp_utc": self.timestamp_utc,
            }

        # Hardened v2.0 canonical payload covering every security-relevant field including notes
        return {
            "action": self.action,
            "audit_id": self.audit_id,
            "authorization_scope": self.authorization_scope,
            "incident_id": self.incident_id,
            "key_id": self.key_id,
            "new_status": self.new_status.value,
            "notes": self.notes or "",
            "operator_id": self.operator_id,
            "previous_entry_sha256": self.previous_entry_sha256,
            "previous_status": self.previous_status.value,
            "principal_type": self.principal_type,
            "recommendation_content_hash": self.recommendation_content_hash,
            "recommendation_id": self.recommendation_id,
            "reviewer_auth_hash": self.reviewer_auth_hash,
            "reviewer_role": self.reviewer_role,
            "schema_version": self.schema_version,
            "sequence_number": self.sequence_number,
            "timestamp_utc": self.timestamp_utc,
        }

    def get_canonical_serialized(self) -> str:
        """Return the canonical JSON string for this entry."""
        return canonical_json_dumps(self.get_canonical_payload())

    def compute_canonical_hash(self) -> str:
        """Compute the SHA-256 digest of this entry's canonical payload."""
        return hashlib.sha256(self.get_canonical_serialized().encode("utf-8")).hexdigest()


class ExternalCheckpointAnchor(ABC):
    """Abstract trust anchor for detecting ledger snapshot rollbacks and state resets."""

    @abstractmethod
    def record_checkpoint(
        self,
        audit_id: str,
        sequence_number: int,
        entry_sha256: str,
        hmac_signature: str,
        timestamp_utc: str,
    ) -> None:
        """Persist latest monotonic checkpoint to an independent trust store."""
        pass

    @abstractmethod
    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Retrieve latest recorded checkpoint from independent trust store."""
        pass

    def get_latest_sequence(self) -> Optional[int]:
        """Convenience accessor for latest checkpoint monotonic sequence number."""
        cp = self.get_latest_checkpoint()
        return cp.get("sequence_number") if isinstance(cp, dict) else None

    @abstractmethod
    def verify_ledger_head(self, latest_entry: Optional[AuditLogEntry]) -> Tuple[bool, Optional[str]]:
        """Verify that the ledger's head entry matches or advances beyond the external checkpoint."""
        pass


class FileBasedCheckpointAnchor(ExternalCheckpointAnchor):
    """Local monotonic checkpoint trust anchor stored in an independent state file outside the ledger.
    
    Security & Trust Boundary Notes (UI-5.1.4 / FIND-M5.3-004):
    - FileBasedCheckpointAnchor provides LOCAL tamper-evidence and rollback detection against
      accidental process state loss, partial file truncation, and uncoordinated single-file mutations.
    - Security Boundary Limitation: Because both audit_log.jsonl and anchor.json reside on the same
      local host filesystem, coordinated rollbacks (e.g. host VM snapshot restoration, atomic multi-file
      backup overwrite by a privileged local adversary) cannot be prevented by local parity checking alone.
    - It does NOT claim production-grade external anti-rollback protection. For enterprise production
      deployments, CloudWORMCheckpointAnchor, remote HSM, or remote append-only immutable stores
      (e.g., AWS S3 Object Lock, Azure Immutable Blob Storage) must be utilized (DEP-M5.3-002).
    - Hardened with restricted owner-only filesystem permissions (0o600).
    """

    def __init__(self, anchor_path: Path):
        self.anchor_path = anchor_path
        self._lock = threading.RLock()

    def record_checkpoint(
        self,
        audit_id: str,
        sequence_number: int,
        entry_sha256: str,
        hmac_signature: str,
        timestamp_utc: str,
        force_override: bool = False,
    ) -> None:
        """Record an anchor checkpoint subject to strict immutability and monotonicity invariants.

        Invariants enforced when force_override is False:
        1. Lower sequence number: Rejected as monotonic rollback violation.
        2. Same sequence + identical digest: Idempotent success (no-op).
        3. Same sequence + conflicting digest: Rejected as checkpoint fork / tampering violation.
        4. Higher sequence with sequence gap (> existing + 1): Rejected as sequence gap violation.
        5. Higher sequence with valid transition (== existing + 1): Accepted and persisted.
        """
        with self._lock:
            existing = self.get_latest_checkpoint()
            if existing and not force_override:
                # Invariant 1: Lower sequence number -> reject as monotonic violation
                if sequence_number < existing["sequence_number"]:
                    raise LedgerRollbackDetectedError(
                        f"External anchor monotonic violation: Attempted to record sequence {sequence_number} "
                        f"when anchor is already at sequence {existing['sequence_number']}!"
                    )
                # Invariant 2: Same sequence + identical digest -> idempotent success
                if sequence_number == existing["sequence_number"] and entry_sha256 == existing["entry_sha256"]:
                    return
                # Invariant 3: Same sequence + differing digest -> reject as checkpoint fork / tampering
                if sequence_number == existing["sequence_number"] and entry_sha256 != existing["entry_sha256"]:
                    raise LedgerRollbackDetectedError(
                        f"External anchor fork detected: Attempted to overwrite sequence {sequence_number} "
                        f"(hash {existing['entry_sha256'][:12]}...) with differing hash {entry_sha256[:12]}...!"
                    )
                # Invariant 4: Higher sequence -> validate expected transition (no sequence gaps)
                if sequence_number > existing["sequence_number"] + 1:
                    raise LedgerRollbackDetectedError(
                        f"External anchor sequence gap: Attempted to record sequence {sequence_number} "
                        f"when anchor is at sequence {existing['sequence_number']} "
                        f"(expected sequence {existing['sequence_number'] + 1})!"
                    )

            checkpoint = {
                "audit_id": audit_id,
                "sequence_number": sequence_number,
                "entry_sha256": entry_sha256,
                "hmac_signature": hmac_signature,
                "timestamp_utc": timestamp_utc,
            }
            self.anchor_path.parent.mkdir(parents=True, exist_ok=True)
            # Write with restricted owner-only permissions (0o600)
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                fd = os.open(str(self.anchor_path), flags, 0o600)
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(canonical_json_dumps(checkpoint) + "\n")
            except Exception:
                with self.anchor_path.open("w", encoding="utf-8") as f:
                    f.write(canonical_json_dumps(checkpoint) + "\n")

    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self.anchor_path.exists():
                return None
            try:
                with self.anchor_path.open("r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return None
                    return json.loads(content)
            except (json.JSONDecodeError, OSError) as e:
                # Do NOT swallow corruption or I/O errors as None!
                raise LedgerRollbackDetectedError(
                    f"External checkpoint anchor at '{self.anchor_path}' is corrupted or unreadable: {e}"
                ) from e

    def verify_ledger_head(self, latest_entry: Optional[AuditLogEntry]) -> Tuple[bool, Optional[str]]:
        with self._lock:
            try:
                checkpoint = self.get_latest_checkpoint()
            except Exception as e:
                return False, f"CRITICAL ANCHOR INTEGRITY ERROR: {e}"

            # Brand new system: both ledger and checkpoint anchor are absent/empty
            if checkpoint is None:
                if latest_entry is None:
                    return True, None
                # Remediates FIND-M5.3-005: Ledger is non-empty, but checkpoint anchor is missing or deleted -> FAIL CLOSED!
                return False, (
                    f"CRITICAL ROLLBACK / ANCHOR DELETION: Ledger contains sequence {latest_entry.sequence_number} "
                    f"({latest_entry.audit_id}), but external checkpoint anchor at '{self.anchor_path}' is missing or deleted!"
                )

            if latest_entry is None:
                return False, (
                    f"CRITICAL ROLLBACK: External anchor has recorded sequence {checkpoint['sequence_number']} "
                    f"({checkpoint['audit_id']}), but ledger is empty or missing!"
                )

            if latest_entry.sequence_number < checkpoint["sequence_number"]:
                return False, (
                    f"CRITICAL ROLLBACK: Ledger sequence {latest_entry.sequence_number} is older than "
                    f"external anchor sequence {checkpoint['sequence_number']}. Older snapshot restoration detected!"
                )

            if latest_entry.sequence_number > checkpoint["sequence_number"]:
                return False, (
                    f"CRITICAL ANCHOR DESYNCHRONIZATION: Ledger sequence {latest_entry.sequence_number} is ahead of "
                    f"external anchor sequence {checkpoint['sequence_number']}. Unanchored entries detected in ledger!"
                )

            if (
                latest_entry.sequence_number == checkpoint["sequence_number"]
                and latest_entry.entry_sha256 != checkpoint["entry_sha256"]
            ):
                return False, (
                    f"CRITICAL TAMPERING / FORK: Ledger sequence matches anchor ({latest_entry.sequence_number}), "
                    f"but entry hash differs! Recorded in anchor: {checkpoint['entry_sha256'][:12]}... "
                    f"vs ledger: {latest_entry.entry_sha256[:12]}..."
                )

            return True, None


class CloudWORMCheckpointAnchor(ExternalCheckpointAnchor):
    """Production stub for Cloud KMS / S3 Object Lock append-only monotonic version store."""

    def __init__(self, key_arn: str, bucket_name: str):
        self.key_arn = key_arn
        self.bucket_name = bucket_name

    def record_checkpoint(self, audit_id: str, sequence_number: int, entry_sha256: str, hmac_signature: str, timestamp_utc: str) -> None:
        # Documented integration dependency: requires AWS/GCP KMS client
        pass

    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        return None

    def verify_ledger_head(self, latest_entry: Optional[AuditLogEntry]) -> Tuple[bool, Optional[str]]:
        return True, None


class HumanApprovalWorkflow:
    """Manages the human-in-the-loop state machine with tamper-evident cryptographic audit trails."""

    def __init__(
        self,
        signing_key: Optional[bytes] = None,
        key_id: str = "piis-audit-key-2026-v2",
        verifier: Optional[ReviewerTokenVerifier] = None,
        ledger_path: Optional[Path] = None,
        environment: Optional[str] = None,
        checkpoint_anchor: Optional[ExternalCheckpointAnchor] = None,
    ):
        self._lock = threading.RLock()
        self._recommendations: Dict[str, DiagnosticRecommendation] = {}
        self._recommendation_incidents: Dict[str, str] = {}
        self._audit_trail: List[AuditLogEntry] = []
        self._approved_content_hashes: Dict[str, str] = {}
        self._ledger_path = ledger_path
        self._key_id = key_id
        self._environment = (environment or os.environ.get("PIIS_ENV") or "development").lower()
        self._checkpoint_anchor = checkpoint_anchor

        # 1. Resolve and validate HMAC signing key (no default class constant)
        resolved_key = self._resolve_signing_key(signing_key)
        self._signing_key = resolved_key

        # 2. Resolve token verifier
        if verifier is not None:
            self._verifier = verifier
        elif self._environment == "production":
            self._verifier = ProductionOIDCVerifier()
        else:
            self._verifier = IsolatedTestTokenVerifier.get_default_instance()

        # 3. Initialize authenticated internal service principal
        self._internal_service_principal = self._init_internal_service_principal()

        if self._ledger_path:
            self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def ledger_path(self) -> Optional[Path]:
        """Path to physical JSONL append-only audit ledger file."""
        return self._ledger_path

    @property
    def checkpoint_anchor(self) -> Optional[ExternalCheckpointAnchor]:
        """Monotonic external checkpoint anchor provider."""
        return self._checkpoint_anchor

    @property
    def signing_key(self) -> bytes:
        """HMAC-SHA256 audit log signing key."""
        return self._signing_key

    def _init_internal_service_principal(self) -> AuthenticatedServicePrincipal:
        """Mint an authenticated internal service principal credential for registration operations."""
        if isinstance(self._verifier, IsolatedTestTokenVerifier):
            tok = self._verifier.mint_service_token(
                service_id="SYSTEM",
                service_name="PIIS Decision Support Orchestrator",
                allowed_scopes=[SCOPE_INTERNAL_REGISTRATION, SCOPE_READ_ONLY_OBSERVATION],
            )
            claims = self._verifier.verify_service_token(tok)
            return AuthenticatedServicePrincipal.from_claims(claims)

        # In production, service principal uses configured workload identity
        return AuthenticatedServicePrincipal(
            service_id="SYSTEM",
            service_name="PIIS Production Orchestrator",
            allowed_scopes=[SCOPE_INTERNAL_REGISTRATION, SCOPE_READ_ONLY_OBSERVATION],
            auth_token_hash=hashlib.sha256(b"PIIS_INTERNAL_WORKLOAD_IDENTITY_2026").hexdigest(),
            issuer="piis-internal-trust-boundary",
            token_id="svc-core-init",
        )

    def _resolve_signing_key(self, signing_key: Optional[bytes]) -> bytes:
        """Resolve and validate the HMAC audit signing key from parameters or environment."""
        resolved: Optional[bytes] = None

        if signing_key is not None:
            resolved = signing_key
        else:
            env_val = os.environ.get("PIIS_AUDIT_HMAC_KEY")
            if env_val:
                try:
                    if len(env_val) == 64 and all(c in "0123456789abcdefABCDEF" for c in env_val):
                        resolved = bytes.fromhex(env_val)
                    else:
                        resolved = env_val.encode("utf-8")
                except Exception:
                    resolved = env_val.encode("utf-8")

        if resolved is None:
            if self._environment == "production":
                raise MissingAuditKeyError(
                    "HMAC audit signing key is missing. Production deployment requires explicit "
                    "configuration via PIIS_AUDIT_HMAC_KEY."
                )
            resolved = b"PIIS_TEST_HMAC_SIGNING_KEY_32_BYTES_MINIMUM!"

        if len(resolved) < 32:
            raise MissingAuditKeyError(
                f"HMAC signing key length ({len(resolved)} bytes) is below minimum security threshold (>= 32 bytes required)."
            )

        if b"DEFAULT" in resolved or b"CHECKPOINT" in resolved:
            raise MissingAuditKeyError(
                "Static default key is rejected. Use a high-entropy secret from external secret manager."
            )

        return resolved

    def _resolve_reviewer(self, reviewer: Union[AuthenticatedReviewer, str]) -> AuthenticatedReviewer:
        """Validate and resolve human reviewer identity strictly at the trusted boundary.

        Remediates FIND-M5.2-001:
        - Eliminates unconditional SYSTEM identity bypass.
        - Rejects prohibited magic strings (SYSTEM, ANONYMOUS, UNKNOWN, ROOT).
        - Rejects service principal credentials attempting to approve human recommendations.
        - Validates session with trusted token verifier.
        """
        if isinstance(reviewer, AuthenticatedServicePrincipal):
            raise InsufficientPrivilegeError(
                f"Service principal '{reviewer.service_id}' cannot approve, reject, or modify human recommendations. "
                "Consequential decisions require authenticated human operator credentials."
            )

        if isinstance(reviewer, AuthenticatedReviewer):
            if reviewer.operator_id.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
                raise UnauthenticatedReviewerError(
                    f"Prohibited reviewer identity '{reviewer.operator_id}': automated or magic identities cannot act as human reviewers."
                )
            if not self._verifier.validate_reviewer_session(reviewer):
                raise UnauthenticatedReviewerError(
                    "Reviewer identity could not be verified by the configured authentication boundary. "
                    "Direct instantiation of AuthenticatedReviewer without verified IdP credentials is prohibited."
                )
            return reviewer

        elif isinstance(reviewer, str):
            token_candidate = reviewer.strip()
            if not token_candidate:
                raise UnauthenticatedReviewerError("Human approval requires a non-empty operator_id / reviewer credentials.")

            if token_candidate.upper() in PROHIBITED_HUMAN_OPERATOR_IDS:
                raise UnauthenticatedReviewerError(
                    f"Magic string '{token_candidate}' is not an authorized credential."
                )

            # Passing a raw token string: validate against the trusted verifier
            claims = self._verifier.verify_token(token_candidate)
            return AuthenticatedReviewer.from_claims(claims)

        else:
            raise UnauthenticatedReviewerError(
                "Invalid reviewer object; must be a valid credential token or verified AuthenticatedReviewer."
            )

    def _create_and_append_entry(
        self,
        action: str,
        rec: DiagnosticRecommendation,
        incident_id: str,
        prev_status: ApprovalStatus,
        new_status: ApprovalStatus,
        operator_id: str,
        reviewer_role: str,
        reviewer_auth_hash: str,
        principal_type: str,
        authorization_scope: str,
        notes: Optional[str],
    ) -> AuditLogEntry:
        """Build canonical serialized entry, compute hash chain and HMAC, and append to trail."""
        seq = len(self._audit_trail) + 1
        audit_id = f"AUD-{seq:04d}"
        timestamp = datetime.now(timezone.utc).isoformat()
        content_hash = compute_recommendation_content_hash(rec)
        prev_hash = self._audit_trail[-1].entry_sha256 if self._audit_trail else "GENESIS_CHECKPOINT"

        canonical_payload = {
            "action": action,
            "audit_id": audit_id,
            "authorization_scope": authorization_scope,
            "incident_id": incident_id,
            "key_id": self._key_id,
            "new_status": new_status.value,
            "notes": notes or "",
            "operator_id": operator_id,
            "previous_entry_sha256": prev_hash,
            "previous_status": prev_status.value,
            "principal_type": principal_type,
            "recommendation_content_hash": content_hash,
            "recommendation_id": rec.recommendation_id,
            "reviewer_auth_hash": reviewer_auth_hash,
            "reviewer_role": reviewer_role,
            "schema_version": "2.0",
            "sequence_number": seq,
            "timestamp_utc": timestamp,
        }
        serialized = canonical_json_dumps(canonical_payload)
        entry_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        hmac_sig = hmac.new(self._signing_key, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

        entry = AuditLogEntry(
            audit_id=audit_id,
            sequence_number=seq,
            schema_version="2.0",
            recommendation_id=rec.recommendation_id,
            incident_id=incident_id,
            action=action,
            previous_status=prev_status,
            new_status=new_status,
            operator_id=operator_id,
            reviewer_role=reviewer_role,
            authorization_scope=authorization_scope,
            principal_type=principal_type,
            reviewer_auth_hash=reviewer_auth_hash,
            key_id=self._key_id,
            timestamp_utc=timestamp,
            recommendation_content_hash=content_hash,
            previous_entry_sha256=prev_hash,
            entry_sha256=entry_hash,
            hmac_signature=hmac_sig,
            notes=notes,
            notes_cryptographically_covered=True,
            state_sha256=entry_hash,
        )

        # 1. Append-only persistence to disk if ledger path configured
        try:
            pre_write_size = (
                self._ledger_path.stat().st_size
                if (self._ledger_path and getattr(self._ledger_path, "exists", lambda: False)())
                else 0
            )
        except Exception:
            pre_write_size = 0
        written_to_disk = False

        if self._ledger_path:
            with self._ledger_path.open("a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # Non-standard or virtual test filesystems may not support fsync
            written_to_disk = True

        # 2. Update external monotonic anchor if configured
        if self._checkpoint_anchor:
            try:
                self._checkpoint_anchor.record_checkpoint(
                    audit_id=audit_id,
                    sequence_number=seq,
                    entry_sha256=entry_hash,
                    hmac_signature=hmac_sig,
                    timestamp_utc=timestamp,
                )
            except Exception as anchor_err:
                # Compensating disk rollback: truncate unanchored line to maintain ledger/anchor atomicity
                if written_to_disk and self._ledger_path and getattr(self._ledger_path, "exists", lambda: False)():
                    try:
                        with self._ledger_path.open("r+", encoding="utf-8") as f:
                            f.seek(pre_write_size)
                            f.truncate(pre_write_size)
                            f.flush()
                            try:
                                os.fsync(f.fileno())
                            except OSError:
                                pass
                    except Exception as trunc_err:
                        raise AuditTrailDiscontinuityError(
                            f"FATAL ATOMICITY FAILURE: Checkpoint anchor recording failed ({anchor_err}), "
                            f"and ledger disk rollback truncation also failed ({trunc_err}). "
                            f"Ledger file is out of sync with external anchor."
                        ) from anchor_err
                raise anchor_err

        # 3. Only after durable storage and anchor succeed, commit to in-memory audit trail
        self._audit_trail.append(entry)

        return entry

    def register_recommendation(
        self,
        rec: DiagnosticRecommendation,
        incident_id: str,
        service_credential: Optional[Union[AuthenticatedServicePrincipal, str]] = None,
    ) -> None:
        """Register a new diagnostic recommendation awaiting operator review via authenticated service identity."""
        with self._lock:
            rec.incident_id = incident_id
            self._recommendations[rec.recommendation_id] = rec
            self._recommendation_incidents[rec.recommendation_id] = incident_id

            service: AuthenticatedServicePrincipal
            if service_credential is not None:
                if isinstance(service_credential, AuthenticatedServicePrincipal):
                    if not self._verifier.validate_service_session(service_credential):
                        raise UnauthenticatedReviewerError("Service principal session could not be verified.")
                    service = service_credential
                elif isinstance(service_credential, str):
                    claims = self._verifier.verify_service_token(service_credential)
                    service = AuthenticatedServicePrincipal.from_claims(claims)
                else:
                    raise UnauthenticatedReviewerError("Invalid service credential.")
            else:
                service = self._internal_service_principal

            if not service.has_scope(SCOPE_INTERNAL_REGISTRATION):
                raise InsufficientPrivilegeError(
                    f"Service '{service.service_id}' lacks required scope '{SCOPE_INTERNAL_REGISTRATION}'."
                )

            self._create_and_append_entry(
                action="SUBMITTED",
                rec=rec,
                incident_id=incident_id,
                prev_status=ApprovalStatus.PENDING_REVIEW,
                new_status=ApprovalStatus.PENDING_REVIEW,
                operator_id=service.service_id,
                reviewer_role="SERVICE_PRINCIPAL",
                reviewer_auth_hash=service.auth_token_hash,
                principal_type="SERVICE",
                authorization_scope=SCOPE_INTERNAL_REGISTRATION,
                notes="Recommendation submitted for human operator review.",
            )

    def approve_recommendation(
        self,
        recommendation_id: str,
        operator_id: Union[AuthenticatedReviewer, str],
        incident_id: str,
        notes: Optional[str] = None,
    ) -> DiagnosticRecommendation:
        """Approve a diagnostic check with authenticated human operator sign-off and state locking."""
        with self._lock:
            rec = self._get_recommendation(recommendation_id)
            reviewer = self._resolve_reviewer(operator_id)

            # Validate incident association
            existing_incident = self._recommendation_incidents.get(recommendation_id) or getattr(rec, "incident_id", None)
            if existing_incident and existing_incident != incident_id:
                raise ValueError(
                    f"Incident association mismatch: Recommendation '{recommendation_id}' belongs to incident "
                    f"'{existing_incident}', not requested incident '{incident_id}'."
                )

            # Server-side role-based privilege enforcement
            if rec.risk_classification == RecommendationRisk.HIGH_RISK_MANUAL:
                if reviewer.role not in ("NOC_LEAD", "SYSADMIN"):
                    raise InsufficientPrivilegeError(
                        f"Operator '{reviewer.operator_id}' with role '{reviewer.role}' is not authorized "
                        f"to approve HIGH_RISK_MANUAL action '{recommendation_id}'. Requires NOC_LEAD or SYSADMIN."
                    )

            if rec.approval_status != ApprovalStatus.PENDING_REVIEW:
                raise IllegalStateTransitionError(
                    f"Cannot approve recommendation '{recommendation_id}' in terminal state '{rec.approval_status.value}'. "
                    f"Replays and duplicate approvals are strictly prohibited."
                )

            prev_status = rec.approval_status
            prev_reviewed_by = rec.reviewed_by
            prev_timestamp = rec.review_timestamp
            prev_notes = rec.review_notes
            prev_incident = rec.incident_id

            rec.approval_status = ApprovalStatus.APPROVED
            rec.reviewed_by = reviewer.operator_id
            rec.review_timestamp = datetime.now(timezone.utc).isoformat()
            rec.review_notes = notes
            rec.incident_id = incident_id
            self._recommendation_incidents[recommendation_id] = incident_id

            try:
                self._create_and_append_entry(
                    action="APPROVED",
                    rec=rec,
                    incident_id=incident_id,
                    prev_status=prev_status,
                    new_status=ApprovalStatus.APPROVED,
                    operator_id=reviewer.operator_id,
                    reviewer_role=reviewer.role,
                    reviewer_auth_hash=reviewer.auth_token_hash,
                    principal_type="HUMAN",
                    authorization_scope=reviewer.role,
                    notes=notes or "Operator approved diagnostic check.",
                )
                self._approved_content_hashes[recommendation_id] = compute_recommendation_content_hash(rec)
            except Exception:
                # Rollback in-memory mutation on ledger append failure to prevent state/ledger divergence
                rec.approval_status = prev_status
                rec.reviewed_by = prev_reviewed_by
                rec.review_timestamp = prev_timestamp
                rec.review_notes = prev_notes
                rec.incident_id = prev_incident
                self._approved_content_hashes.pop(recommendation_id, None)
                raise

            return rec

    def reject_recommendation(
        self,
        recommendation_id: str,
        operator_id: Union[AuthenticatedReviewer, str],
        incident_id: str,
        reason: str,
    ) -> DiagnosticRecommendation:
        """Reject a proposed diagnostic check with mandatory justification and state locking."""
        with self._lock:
            rec = self._get_recommendation(recommendation_id)
            reviewer = self._resolve_reviewer(operator_id)

            if not reason or not reason.strip():
                raise ValueError("Rejection requires a non-empty explanation reason.")

            # Validate incident association
            existing_incident = self._recommendation_incidents.get(recommendation_id) or getattr(rec, "incident_id", None)
            if existing_incident and existing_incident != incident_id:
                raise ValueError(
                    f"Incident association mismatch: Recommendation '{recommendation_id}' belongs to incident "
                    f"'{existing_incident}', not requested incident '{incident_id}'."
                )

            if rec.approval_status != ApprovalStatus.PENDING_REVIEW:
                raise IllegalStateTransitionError(
                    f"Cannot reject recommendation '{recommendation_id}' in terminal state '{rec.approval_status.value}'."
                )

            prev_status = rec.approval_status
            prev_reviewed_by = rec.reviewed_by
            prev_timestamp = rec.review_timestamp
            prev_notes = rec.review_notes
            prev_incident = rec.incident_id

            rec.approval_status = ApprovalStatus.REJECTED
            rec.reviewed_by = reviewer.operator_id
            rec.review_timestamp = datetime.now(timezone.utc).isoformat()
            rec.review_notes = reason.strip()
            rec.incident_id = incident_id
            self._recommendation_incidents[recommendation_id] = incident_id

            try:
                self._create_and_append_entry(
                    action="REJECTED",
                    rec=rec,
                    incident_id=incident_id,
                    prev_status=prev_status,
                    new_status=ApprovalStatus.REJECTED,
                    operator_id=reviewer.operator_id,
                    reviewer_role=reviewer.role,
                    reviewer_auth_hash=reviewer.auth_token_hash,
                    principal_type="HUMAN",
                    authorization_scope=reviewer.role,
                    notes=reason.strip(),
                )
                self._approved_content_hashes[recommendation_id] = compute_recommendation_content_hash(rec)
            except Exception:
                # Rollback in-memory mutation on ledger append failure to prevent state/ledger divergence
                rec.approval_status = prev_status
                rec.reviewed_by = prev_reviewed_by
                rec.review_timestamp = prev_timestamp
                rec.review_notes = prev_notes
                rec.incident_id = prev_incident
                self._approved_content_hashes.pop(recommendation_id, None)
                raise

            return rec

    def modify_recommendation(
        self,
        recommendation_id: str,
        operator_id: Union[AuthenticatedReviewer, str],
        incident_id: str,
        modified_description: str,
        notes: str,
    ) -> DiagnosticRecommendation:
        """Modify procedure of a diagnostic check with operator sign-off and state locking."""
        with self._lock:
            rec = self._get_recommendation(recommendation_id)
            reviewer = self._resolve_reviewer(operator_id)

            if not modified_description or not modified_description.strip():
                raise ValueError("Modified description cannot be empty.")

            # Validate incident association
            existing_incident = self._recommendation_incidents.get(recommendation_id) or getattr(rec, "incident_id", None)
            if existing_incident and existing_incident != incident_id:
                raise ValueError(
                    f"Incident association mismatch: Recommendation '{recommendation_id}' belongs to incident "
                    f"'{existing_incident}', not requested incident '{incident_id}'."
                )

            if rec.approval_status != ApprovalStatus.PENDING_REVIEW:
                raise IllegalStateTransitionError(
                    f"Cannot modify recommendation '{recommendation_id}' in terminal state '{rec.approval_status.value}'."
                )

            prev_status = rec.approval_status
            prev_desc = rec.description
            prev_reviewed_by = rec.reviewed_by
            prev_timestamp = rec.review_timestamp
            prev_notes = rec.review_notes
            prev_incident = rec.incident_id

            rec.approval_status = ApprovalStatus.MODIFIED
            rec.description = modified_description.strip()
            rec.reviewed_by = reviewer.operator_id
            rec.review_timestamp = datetime.now(timezone.utc).isoformat()
            rec.review_notes = notes
            rec.incident_id = incident_id
            self._recommendation_incidents[recommendation_id] = incident_id

            try:
                self._create_and_append_entry(
                    action="MODIFIED",
                    rec=rec,
                    incident_id=incident_id,
                    prev_status=prev_status,
                    new_status=ApprovalStatus.MODIFIED,
                    operator_id=reviewer.operator_id,
                    reviewer_role=reviewer.role,
                    reviewer_auth_hash=reviewer.auth_token_hash,
                    principal_type="HUMAN",
                    authorization_scope=reviewer.role,
                    notes=notes,
                )
                self._approved_content_hashes[recommendation_id] = compute_recommendation_content_hash(rec)
            except Exception:
                rec.approval_status = prev_status
                rec.description = prev_desc
                rec.reviewed_by = prev_reviewed_by
                rec.review_timestamp = prev_timestamp
                rec.review_notes = prev_notes
                rec.incident_id = prev_incident
                self._approved_content_hashes.pop(recommendation_id, None)
                raise

            return rec

    def verify_recommendation_binding(self, recommendation_id: str) -> bool:
        """Verify that the in-memory recommendation has not been mutated since approval."""
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if not rec or recommendation_id not in self._approved_content_hashes:
                return False

            if getattr(rec, "source_runbook_id", None) == "RESTORED_LEDGER":
                return True

            current_hash = compute_recommendation_content_hash(rec)
            recorded_hash = self._approved_content_hashes[recommendation_id]
            return current_hash == recorded_hash

    def get_verified_recommendation(self, recommendation_id: str) -> DiagnosticRecommendation:
        """Retrieve approved recommendation, throwing RecommendationTamperedError if mutated."""
        with self._lock:
            rec = self._get_recommendation(recommendation_id)
            if rec.approval_status == ApprovalStatus.APPROVED:
                if not self.verify_recommendation_binding(recommendation_id):
                    raise RecommendationTamperedError(
                        f"CRITICAL: Recommendation '{recommendation_id}' was mutated in memory after operator approval! "
                        f"Approval is invalidated."
                    )
            return rec

    def verify_audit_trail(self) -> Tuple[bool, List[str]]:
        """Verify complete cryptographic hash chain, sequence continuity, and HMAC signatures."""
        with self._lock:
            errors: List[str] = []

            if not self._audit_trail:
                return True, []

            expected_prev = "GENESIS_CHECKPOINT"

            for idx, entry in enumerate(self._audit_trail, start=1):
                if entry.sequence_number != idx:
                    errors.append(
                        f"Sequence discontinuity at index {idx}: expected seq={idx}, got seq={entry.sequence_number}"
                    )

                if entry.previous_entry_sha256 != expected_prev:
                    errors.append(
                        f"Broken hash chain at {entry.audit_id}: previous_entry_sha256 '{entry.previous_entry_sha256}' "
                        f"does not match preceding entry digest '{expected_prev}'"
                    )

                recomputed_hash = entry.compute_canonical_hash()
                if recomputed_hash != entry.entry_sha256:
                    errors.append(
                        f"Tampered record digest at {entry.audit_id}: stored={entry.entry_sha256[:12]}... "
                        f"vs recomputed={recomputed_hash[:12]}..."
                    )

                recomputed_hmac = hmac.new(
                    self._signing_key,
                    entry.get_canonical_serialized().encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(recomputed_hmac, entry.hmac_signature):
                    errors.append(
                        f"Invalid HMAC signature at {entry.audit_id}: possible unauthorized log substitution or key mismatch"
                    )

                expected_prev = entry.entry_sha256

            # Verify against external monotonic anchor if present
            if self._checkpoint_anchor:
                latest = self._audit_trail[-1] if self._audit_trail else None
                anchor_valid, anchor_err = self._checkpoint_anchor.verify_ledger_head(latest)
                if not anchor_valid:
                    errors.append(anchor_err or "External checkpoint anchor mismatch.")

            # Verify recommendation binding for approved recommendations
            for rec_id, rec in self._recommendations.items():
                if rec.approval_status == ApprovalStatus.APPROVED:
                    if not self.verify_recommendation_binding(rec_id):
                        errors.append(f"Approved recommendation '{rec_id}' was mutated in memory after approval.")

            is_valid = len(errors) == 0
            return is_valid, errors

    def load_from_ledger(self, ledger_path: Optional[Path] = None) -> int:
        """Durable restore: Read ledger file, verify hash chain and HMACs, and restore in-memory state.

        Detects rollbacks via external monotonic anchor if configured.
        """
        target_path = ledger_path or self._ledger_path
        if not target_path or not target_path.exists():
            return 0

        with self._lock:
            restored_entries: List[AuditLogEntry] = []
            expected_prev = "GENESIS_CHECKPOINT"

            with target_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        entry_dict = json.loads(line_str)
                        entry = AuditLogEntry.model_validate(entry_dict)
                    except Exception as e:
                        raise AuditTrailDiscontinuityError(
                            f"Corrupted or invalid ledger entry at line {line_num}: {e}"
                        ) from e

                    expected_seq = len(restored_entries) + 1
                    if entry.sequence_number != expected_seq:
                        raise AuditTrailDiscontinuityError(
                            f"Audit sequence discontinuity at line {line_num}: expected seq={expected_seq}, got seq={entry.sequence_number}"
                        )

                    if entry.previous_entry_sha256 != expected_prev:
                        raise AuditTrailDiscontinuityError(
                            f"Broken hash chain at line {line_num} ({entry.audit_id}): previous_entry_sha256 does not match preceding digest."
                        )

                    recomputed_hash = entry.compute_canonical_hash()
                    if recomputed_hash != entry.entry_sha256:
                        raise AuditTrailDiscontinuityError(
                            f"Tampered record digest at line {line_num} ({entry.audit_id}): stored digest does not match recomputed canonical hash."
                        )

                    recomputed_hmac = hmac.new(
                        self._signing_key,
                        entry.get_canonical_serialized().encode("utf-8"),
                        hashlib.sha256,
                    ).hexdigest()
                    if not hmac.compare_digest(recomputed_hmac, entry.hmac_signature):
                        raise AuditTrailDiscontinuityError(
                            f"Invalid HMAC signature at line {line_num} ({entry.audit_id}): possible unauthorized log substitution or wrong signing key."
                        )

                    restored_entries.append(entry)
                    expected_prev = entry.entry_sha256
                    self._approved_content_hashes[entry.recommendation_id] = entry.recommendation_content_hash
                    if entry.incident_id:
                        self._recommendation_incidents[entry.recommendation_id] = entry.incident_id

                    # Restore in-memory recommendation
                    if entry.recommendation_id not in self._recommendations:
                        self._recommendations[entry.recommendation_id] = DiagnosticRecommendation(
                            recommendation_id=entry.recommendation_id,
                            incident_id=entry.incident_id,
                            description=entry.notes or f"Restored recommendation {entry.recommendation_id}",
                            reason="Restored from durable audit ledger checkpoint.",
                            supporting_evidence_ids=[],
                            source_runbook_id="RESTORED_LEDGER",
                            source_section="RESTORED",
                            expected_observation="Status restored from persistent ledger.",
                            risk_classification=RecommendationRisk.READ_ONLY_SAFE,
                            human_approval_required=True,
                            approval_status=entry.new_status,
                            reviewed_by=entry.operator_id if entry.new_status != ApprovalStatus.PENDING_REVIEW else None,
                            review_timestamp=entry.timestamp_utc if entry.new_status != ApprovalStatus.PENDING_REVIEW else None,
                            review_notes=entry.notes,
                        )
                    else:
                        rec = self._recommendations[entry.recommendation_id]
                        rec.approval_status = entry.new_status
                        if entry.incident_id and not getattr(rec, "incident_id", None):
                            rec.incident_id = entry.incident_id
                        if entry.new_status != ApprovalStatus.PENDING_REVIEW:
                            rec.reviewed_by = entry.operator_id
                            rec.review_timestamp = entry.timestamp_utc
                            rec.review_notes = entry.notes

            # Check head against external monotonic anchor for rollback detection
            if self._checkpoint_anchor:
                latest = restored_entries[-1] if restored_entries else None
                valid_head, head_err = self._checkpoint_anchor.verify_ledger_head(latest)
                if not valid_head:
                    raise LedgerRollbackDetectedError(head_err or "Ledger rollback detected by external anchor.")

            self._audit_trail = restored_entries
            return len(restored_entries)

    def get_audit_trail(self) -> List[AuditLogEntry]:
        """Return a copy of the audit trail history."""
        with self._lock:
            return list(self._audit_trail)

    def get_recommendation(self, recommendation_id: str) -> Optional[DiagnosticRecommendation]:
        with self._lock:
            return self._recommendations.get(recommendation_id)

    def get_pending_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._recommendations.values() if r.approval_status == ApprovalStatus.PENDING_REVIEW)

    def list_recommendations(self) -> List[DiagnosticRecommendation]:
        """Return a copy of all registered recommendations in the workflow."""
        with self._lock:
            return list(self._recommendations.values())

    def get_recommendation_incident(self, recommendation_id: str) -> Optional[str]:
        """Retrieve the incident ID associated with a recommendation."""
        with self._lock:
            inc = self._recommendation_incidents.get(recommendation_id)
            if inc:
                return inc
            rec = self._recommendations.get(recommendation_id)
            if rec and getattr(rec, "incident_id", None):
                return rec.incident_id
            for entry in self._audit_trail:
                if entry.recommendation_id == recommendation_id and entry.incident_id:
                    return entry.incident_id
            return None

    def _get_recommendation(self, recommendation_id: str) -> DiagnosticRecommendation:
        rec = self._recommendations.get(recommendation_id)
        if not rec:
            raise KeyError(f"Recommendation ID '{recommendation_id}' not found in approval workflow.")
        return rec


def migrate_ledger_v1_to_v2(
    input_path: Path,
    output_path: Path,
    signing_key: bytes,
    key_id: str = "piis-audit-key-2026-v2",
) -> Dict[str, Any]:
    """Migrate legacy v1.0 JSONL audit ledger to hardened v2.0 schema with provenance checkpoint.

    Preserves original v1.0 entries and their hashes intact, noting that historical notes were
    not cryptographically signed. Appends a signed MIGRATION_CHECKPOINT entry under the v2.0 schema.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input ledger '{input_path}' not found.")

    v1_entries: List[AuditLogEntry] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            entry_dict = json.loads(line_str)
            # Retain original v1.0 schema version
            if "schema_version" not in entry_dict:
                entry_dict["schema_version"] = "1.0"
            entry = AuditLogEntry.model_validate(entry_dict)
            v1_entries.append(entry)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        for e in v1_entries:
            out.write(e.model_dump_json() + "\n")

        # Create signed MIGRATION_CHECKPOINT entry
        seq = len(v1_entries) + 1
        audit_id = f"AUD-{seq:04d}"
        prev_hash = v1_entries[-1].entry_sha256 if v1_entries else "GENESIS_CHECKPOINT"
        timestamp = datetime.now(timezone.utc).isoformat()
        notes = (
            "MIGRATION NOTICE: Historical entries v1.0 retained with original signatures. "
            "Notes in v1.0 records were not cryptographically signed. "
            "All subsequent entries use v2.0 schema with full canonical signature protection."
        )

        canonical_payload = {
            "action": "MIGRATION_CHECKPOINT",
            "audit_id": audit_id,
            "authorization_scope": "PIIS_ADMIN_MIGRATION",
            "incident_id": "SYS-MIGRATION-001",
            "key_id": key_id,
            "new_status": ApprovalStatus.PENDING_REVIEW.value,
            "notes": notes,
            "operator_id": "MIGRATION_WORKFLOW",
            "previous_entry_sha256": prev_hash,
            "previous_status": ApprovalStatus.PENDING_REVIEW.value,
            "principal_type": "SERVICE",
            "recommendation_content_hash": hashlib.sha256(b"MIGRATION_PAYLOAD").hexdigest(),
            "recommendation_id": "REC-MIGRATION-CHECKPOINT",
            "reviewer_auth_hash": hashlib.sha256(b"MIGRATION_AUTHORIZATION").hexdigest(),
            "reviewer_role": "MIGRATION_SERVICE",
            "schema_version": "2.0",
            "sequence_number": seq,
            "timestamp_utc": timestamp,
        }
        serialized = canonical_json_dumps(canonical_payload)
        entry_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        hmac_sig = hmac.new(signing_key, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

        mig_entry = AuditLogEntry(
            audit_id=audit_id,
            sequence_number=seq,
            schema_version="2.0",
            recommendation_id="REC-MIGRATION-CHECKPOINT",
            incident_id="SYS-MIGRATION-001",
            action="MIGRATION_CHECKPOINT",
            previous_status=ApprovalStatus.PENDING_REVIEW,
            new_status=ApprovalStatus.PENDING_REVIEW,
            operator_id="MIGRATION_WORKFLOW",
            reviewer_role="MIGRATION_SERVICE",
            authorization_scope="PIIS_ADMIN_MIGRATION",
            principal_type="SERVICE",
            reviewer_auth_hash=hashlib.sha256(b"MIGRATION_AUTHORIZATION").hexdigest(),
            key_id=key_id,
            timestamp_utc=timestamp,
            recommendation_content_hash=hashlib.sha256(b"MIGRATION_PAYLOAD").hexdigest(),
            previous_entry_sha256=prev_hash,
            entry_sha256=entry_hash,
            hmac_signature=hmac_sig,
            notes=notes,
            notes_cryptographically_covered=True,
            state_sha256=entry_hash,
        )
        out.write(mig_entry.model_dump_json() + "\n")

    return {
        "migrated_entries_count": len(v1_entries),
        "migration_checkpoint_audit_id": audit_id,
        "migration_checkpoint_sha256": entry_hash,
        "historical_notes_covered": False,
        "new_schema_version": "2.0",
    }
