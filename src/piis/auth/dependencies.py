"""FastAPI authentication and authorization dependencies for PIIS endpoints."""

from __future__ import annotations

from typing import Callable, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from piis.auth.manager import AuthenticatedPrincipal, AuthManager
from piis.auth.roles import ApplicationRole, Permission


# Security scheme for OpenAPI Swagger UI
security_scheme = HTTPBearer(auto_error=False)

# Singleton AuthManager instance for API
_auth_manager_instance: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Dependency returning the configured AuthManager."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


def set_auth_manager(manager: AuthManager) -> None:
    """Set custom auth manager (used in tests)."""
    global _auth_manager_instance
    _auth_manager_instance = manager


async def get_current_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    auth_manager: AuthManager = Depends(get_auth_manager),
) -> AuthenticatedPrincipal:
    """Extract and authenticate the bearer token, returning the verified principal."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Bearer authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return auth_manager.authenticate_token(credentials.credentials)
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_roles(*allowed_roles: ApplicationRole) -> Callable:
    """FastAPI dependency enforcing that the principal possesses at least one of the specified roles."""
    async def role_checker(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if not any(principal.has_role(r) for r in allowed_roles):
            allowed_names = [r.value for r in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Principal '{principal.principal_id}' lacks required role from {allowed_names}",
            )
        return principal

    return role_checker


async def require_human_operator(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """Strictly prohibit automated service principals from executing human review actions."""
    if principal.is_service_principal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Forbidden: Principal '{principal.principal_id}' is an automated service account. "
                "Human approval is legally and architecturally mandatory."
            ),
        )
    return principal


def require_permissions(*required_permissions: Permission) -> Callable:
    """FastAPI dependency enforcing that the principal has all specified granular permissions."""
    async def permission_checker(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        missing = [p.value for p in required_permissions if not principal.has_permission(p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Principal lacks required permissions: {missing}",
            )
        return principal

    return permission_checker
