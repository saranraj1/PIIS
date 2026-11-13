"""Enterprise Identity & Access Package for PIIS."""

from piis.auth.dependencies import (
    get_auth_manager,
    get_current_principal,
    require_human_operator,
    require_permissions,
    require_roles,
    set_auth_manager,
)
from piis.auth.manager import AuthenticatedPrincipal, AuthManager
from piis.auth.roles import ApplicationRole, Permission, ROLE_PERMISSIONS
from piis.auth.test_oidc_provider import LocalTestOIDCProvider

__all__ = [
    "ApplicationRole",
    "AuthenticatedPrincipal",
    "AuthManager",
    "LocalTestOIDCProvider",
    "Permission",
    "ROLE_PERMISSIONS",
    "get_auth_manager",
    "get_current_principal",
    "require_human_operator",
    "require_permissions",
    "require_roles",
    "set_auth_manager",
]
