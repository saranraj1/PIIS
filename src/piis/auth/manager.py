"""Enterprise Authentication & Authorization Manager for PIIS."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Set
import jwt
from pydantic import BaseModel, Field

from piis.auth.roles import ApplicationRole, Permission, ROLE_PERMISSIONS
from piis.investigation.approval import (
    PROHIBITED_HUMAN_OPERATOR_IDS,
    IsolatedTestTokenVerifier,
    ProductionOIDCVerifier,
    ReviewerClaims,
    ReviewerTokenVerifier,
    ServicePrincipalClaims,
)


class AuthenticatedPrincipal(BaseModel):
    """Unified authenticated principal representation for API requests."""
    principal_id: str
    is_service_principal: bool
    roles: List[ApplicationRole] = Field(default_factory=list)
    permissions: Set[Permission] = Field(default_factory=set)
    raw_claims: Dict[str, Any] = Field(default_factory=dict)
    issuer: str = ""
    token_id: Optional[str] = None

    def has_role(self, role: ApplicationRole) -> bool:
        return role in self.roles

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


class AuthManager:
    """Enterprise authentication manager verifying OIDC tokens and checking application roles."""

    def __init__(
        self,
        verifier: Optional[ReviewerTokenVerifier] = None,
        environment: Optional[str] = None,
    ):
        self.environment = environment or os.environ.get("PIIS_ENVIRONMENT", "development").lower()
        self._lock = threading.RLock()
        self._revoked_tokens: Set[str] = set()

        if verifier is not None:
            self.verifier = verifier
        elif self.environment == "production":
            # In production, require live OIDC configuration or fail closed
            jwks_url = os.environ.get("PIIS_OIDC_JWKS_URL")
            issuer = os.environ.get("PIIS_OIDC_ISSUER")
            audience = os.environ.get("PIIS_OIDC_AUDIENCE")
            if not jwks_url or not issuer or not audience:
                raise RuntimeError(
                    "Production authentication misconfiguration: PIIS_OIDC_JWKS_URL, "
                    "PIIS_OIDC_ISSUER, and PIIS_OIDC_AUDIENCE must be set in production mode."
                )
            self.verifier = ProductionOIDCVerifier(
                jwks_url=jwks_url,
                expected_issuer=issuer,
                expected_audience=audience,
            )
        else:
            # Development / staging mode verifier
            self.verifier = IsolatedTestTokenVerifier()

    def revoke_token(self, token_id: str) -> None:
        """Revoke a token by jti or token ID."""
        with self._lock:
            self._revoked_tokens.add(token_id)
            if hasattr(self.verifier, "revoke_token"):
                self.verifier.revoke_token(token_id)

    def is_token_revoked(self, token_id: str) -> bool:
        """Check if token ID has been revoked."""
        with self._lock:
            if token_id in self._revoked_tokens:
                return True
            if hasattr(self.verifier, "is_revoked"):
                return bool(self.verifier.is_revoked(token_id))
            return False

    def authenticate_token(self, token: str) -> AuthenticatedPrincipal:
        """Verify bearer JWT and return an AuthenticatedPrincipal with resolved roles."""
        if not token:
            raise ValueError("Missing bearer token")

        # Strip Bearer prefix if present
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        # Check revocation before verification
        try:
            unverified_claims = jwt.decode(token, options={"verify_signature": False})
            jti = unverified_claims.get("jti")
            if jti and self.is_token_revoked(jti):
                raise PermissionError(f"Token '{jti}' has been explicitly revoked")
            
            # If payload explicitly declares service_id, try verify_service_token first
            if "service_id" in unverified_claims:
                claims = self.verifier.verify_service_token(token)
                return self._build_service_principal(claims)
        except jwt.PyJWTError:
            pass

        # Try human reviewer verification
        try:
            claims = self.verifier.verify_token(token)
            return self._build_human_principal(claims)
        except Exception as human_err:
            # Fallback to service principal verification
            try:
                svc_claims = self.verifier.verify_service_token(token)
                return self._build_service_principal(svc_claims)
            except Exception:
                raise human_err

    def _build_human_principal(self, claims: ReviewerClaims) -> AuthenticatedPrincipal:
        """Map verified reviewer claims to application roles and permissions."""
        operator_id = claims.operator_id.upper()

        # Prohibit service accounts claiming human identities
        if operator_id in PROHIBITED_HUMAN_OPERATOR_IDS:
            raise PermissionError(f"Operator ID '{operator_id}' cannot be used as a human reviewer")

        # Map role claims
        roles: List[ApplicationRole] = []
        raw_role = getattr(claims, "role", None)
        if raw_role:
            r_str = str(raw_role).upper()
            if "L3" in r_str:
                roles.append(ApplicationRole.NOC_L3)
            elif "L2" in r_str:
                roles.append(ApplicationRole.NOC_L2)
            elif "L1" in r_str:
                roles.append(ApplicationRole.NOC_L1)
            elif "ADMIN" in r_str:
                roles.append(ApplicationRole.PIIS_ADMIN)
            elif "AUDITOR" in r_str:
                roles.append(ApplicationRole.SECURITY_AUDITOR)
            elif "MANAGER" in r_str:
                roles.append(ApplicationRole.INCIDENT_MANAGER)

        if not roles:
            roles = [ApplicationRole.NOC_L1]

        # Aggregate permissions
        perms: Set[Permission] = set()
        for role in roles:
            perms.update(ROLE_PERMISSIONS.get(role, set()))

        return AuthenticatedPrincipal(
            principal_id=claims.operator_id,
            is_service_principal=False,
            roles=roles,
            permissions=perms,
            raw_claims=claims.model_dump() if hasattr(claims, "model_dump") else {},
            issuer=getattr(claims, "iss", "internal"),
            token_id=getattr(claims, "jti", None),
        )

    def _build_service_principal(self, claims: ServicePrincipalClaims) -> AuthenticatedPrincipal:
        """Map verified service principal claims to application roles."""
        roles = [ApplicationRole.SERVICE_PRINCIPAL]
        perms = set(ROLE_PERMISSIONS[ApplicationRole.SERVICE_PRINCIPAL])

        return AuthenticatedPrincipal(
            principal_id=claims.service_id,
            is_service_principal=True,
            roles=roles,
            permissions=perms,
            raw_claims=claims.model_dump() if hasattr(claims, "model_dump") else {},
            issuer=getattr(claims, "iss", "internal"),
            token_id=getattr(claims, "jti", None),
        )

    def mint_dev_token(
        self,
        principal_id: str,
        role: ApplicationRole = ApplicationRole.NOC_L1,
        is_service: bool = False,
        expires_in_seconds: int = 3600,
        jti: Optional[str] = None,
    ) -> str:
        """Mint a verified test JWT using IsolatedTestTokenVerifier."""
        if hasattr(self.verifier, "mint_service_token") and is_service:
            return self.verifier.mint_service_token(
                service_id=principal_id,
                service_name=f"Service {principal_id}",
                lifetime_seconds=expires_in_seconds,
                custom_jti=jti,
            )
        elif hasattr(self.verifier, "mint_token"):
            return self.verifier.mint_token(
                operator_id=principal_id,
                role=role.value,
                lifetime_seconds=expires_in_seconds,
                custom_jti=jti,
            )
        else:
            raise NotImplementedError("Current verifier does not support local token minting.")
