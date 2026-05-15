# GAP 6 — RBAC ÉLARGI — rbac.py
"""Extended role-based access control with granular per-user permissions.

Two layers:
  1. Role-based defaults  –  every role has a fixed permission set.
  2. Per-user overrides    –  UserPermission rows grant / deny read/write
                              on a per-module basis.  When present they
                              take precedence over the role matrix.

Roles:
  SUPER_ADMIN, DAF, BIM, ADV, NOTAIRE, JURIDIQUE, DIRECTION,
  COMMERCIAL, MARKETING, RH, EMPLOYE, VIEWER

Backward-compatible aliases:
  admin → SUPER_ADMIN, accountant → DAF, hr_manager → RH,
  sales → COMMERCIAL, employee → EMPLOYE, viewer → VIEWER
"""
from __future__ import annotations

import enum
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User, UserPermission


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    DAF = "DAF"
    BIM = "BIM"
    ADV = "ADV"
    NOTAIRE = "NOTAIRE"
    JURIDIQUE = "JURIDIQUE"
    DIRECTION = "DIRECTION"
    COMMERCIAL = "COMMERCIAL"
    MARKETING = "MARKETING"
    RH = "RH"
    EMPLOYE = "EMPLOYE"
    VIEWER = "VIEWER"
    # ── GFI v7.0: 15 GFI-specific roles ──
    PDG_SUPER_ADMIN = "PDG_SUPER_ADMIN"
    CHARGE_MISSION = "CHARGE_MISSION"
    CHARGE_FINANCE = "CHARGE_FINANCE"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    TELECONSEILLERE = "TELECONSEILLERE"
    ARCHIVISTE = "ARCHIVISTE"
    SECURITE = "SECURITE"
    MAGASINIER = "MAGASINIER"
    ACHATS = "ACHATS"
    OPERATIONS_TECH = "OPERATIONS_TECH"
    ARCHITECTE = "ARCHITECTE"
    CHEF_PROJET_EXT = "CHEF_PROJET_EXT"


# Backward-compatible mapping from old roles to new
ROLE_ALIASES: dict[str, str] = {
    "admin": "SUPER_ADMIN",
    "accountant": "DAF",
    "hr_manager": "RH",
    "sales": "COMMERCIAL",
    "employee": "EMPLOYE",
    "viewer": "VIEWER",
}


def _normalize_role(role: str) -> str:
    """Map legacy role name to new canonical name."""
    return ROLE_ALIASES.get(role, role)


# ── Permission matrix ──────────────────────────────────────────────────────

# Central registry of all application modules available for per-user overrides.
MODULE_REGISTRY: list[dict[str, str]] = [
    {"code": "hr",          "label": "Ressources Humaines"},
    {"code": "employee",    "label": "Gestion des Employés"},
    {"code": "payroll",     "label": "Paie"},
    {"code": "tasks",       "label": "Tâches Quotidiennes"},
    {"code": "spi",         "label": "Score de Performance (SPI)"},
    {"code": "finance",     "label": "Finance / Trésorerie"},
    {"code": "treasury",    "label": "Trésorerie"},
    {"code": "accounting",  "label": "Comptabilité"},
    {"code": "cost_center", "label": "Centre de Coût"},
    {"code": "cloture",     "label": "Clôture Mensuelle"},
    {"code": "bim",         "label": "BIM Immobilier"},
    {"code": "edd",         "label": "État Des Droits"},
    {"code": "re_unit",     "label": "Unités Immobilières"},
    {"code": "adv",         "label": "Administration des Ventes"},
    {"code": "pricing",     "label": "Tarification"},
    {"code": "legal",       "label": "Juridique"},
    {"code": "registry",    "label": "Registre Foncier"},
    {"code": "documents",   "label": "Documents / GED"},
    {"code": "imports",     "label": "Import de Données"},
    {"code": "crm",         "label": "CRM / Relation Client"},
    {"code": "admin",       "label": "Administration Système"},
]

MODULE_CODES: set[str] = {m["code"] for m in MODULE_REGISTRY}

PERMISSIONS: dict[str, list[str]] = {
    "SUPER_ADMIN": ["*"],
    "DAF": [
        "finance:read", "finance:write",
        "cost_center:read", "cost_center:write",
        "cloture:trigger", "retrait:approve",
        "appel_fonds:create", "spi:read", "employee:read",
        "treasury:read", "treasury:write",
        "accounting:read", "accounting:write",
        "documents:read", "documents:write",
    ],
    "BIM": [
        "bim:import", "bim:read", "bim:write",
        "edd:generate", "edd:publish", "edd:read",
        "re_unit:write", "re_unit:read",
        "documents:read",
    ],
    "ADV": [
        "adv:read", "adv:write", "adv:sale:create",
        "edd:read", "edd:generate", "edd:publish",
        "re_unit:read",
        "pricing:read", "pricing:write",
        "documents:read",
    ],
    "NOTAIRE": [
        "adv:read", "edd:read",
        "documents:read", "registry:read",
    ],
    "JURIDIQUE": [
        "legal:read", "legal:write",
        "documents:read", "documents:write",
        "registry:read",
    ],
    "DIRECTION": [
        "*:read",
        "spi:read", "finance:read", "cost_center:read",
        "treasury:read", "accounting:read",
        "adv:read", "hr:read", "legal:read",
    ],
    "COMMERCIAL": [
        "adv:sale:create", "adv:read",
        "crm:read", "crm:write",
        "documents:read",
    ],
    "MARKETING": [
        "adv:read", "pricing:read",
        "crm:read",
        "documents:read",
    ],
    "RH": [
        "employee:read", "employee:write",
        "spi:read", "spi:write",
        "payroll:read", "payroll:write",
        "hr:read", "hr:write",
        "documents:read",
    ],
    "EMPLOYE": [
        "spi:own", "payroll:own", "tasks:own",
        "documents:read",
    ],
    "VIEWER": [
        "*:read",
    ],
    # ── GFI v7.0 roles ──
    "PDG_SUPER_ADMIN": ["*"],
    "CHARGE_MISSION": [
        "*:read",
        "finance:write", "cost_center:write", "cloture:trigger",
        "documents:write", "legal:write",
    ],
    "CHARGE_FINANCE": [
        "finance:read", "finance:write",
        "cost_center:read", "cost_center:write",
        "treasury:read", "treasury:write",
        "accounting:read", "accounting:write",
        "cloture:trigger",
    ],
    "PROJECT_MANAGER": [
        "bim:read", "bim:write",
        "cost_center:read", "cost_center:write",
        "hr:read", "documents:read", "documents:write",
        "registry:read",
    ],
    "TELECONSEILLERE": [
        "adv:read", "adv:write", "adv:sale:create",
        "crm:read", "crm:write",
        "documents:read",
    ],
    "ARCHIVISTE": [
        "documents:read", "documents:write",
        "imports:read", "imports:write",
    ],
    "SECURITE": [
        "admin:read", "documents:read",
    ],
    "MAGASINIER": [
        "cost_center:read",
        "documents:read",
    ],
    "ACHATS": [
        "cost_center:read", "cost_center:write",
        "documents:read", "documents:write",
    ],
    "OPERATIONS_TECH": [
        "bim:read", "bim:write",
        "cost_center:read",
        "documents:read",
    ],
    "ARCHITECTE": [
        "bim:read", "bim:write", "bim:import",
        "edd:read", "edd:generate",
        "re_unit:read", "re_unit:write",
        "documents:read",
    ],
    "CHEF_PROJET_EXT": [
        "bim:read",
        "cost_center:read",
        "documents:read",
    ],
}


def check_permission(user_role: str, permission: str) -> bool:
    """Check whether a role has the given permission (role-based only)."""
    role = _normalize_role(user_role)
    perms = PERMISSIONS.get(role, [])

    # Wildcard: SUPER_ADMIN has all permissions
    if "*" in perms:
        return True

    # Direct match
    if permission in perms:
        return True

    # Wildcard read: "*:read" matches any "xxx:read"
    if "*:read" in perms and permission.endswith(":read"):
        return True

    return False


def _extract_module(permission: str) -> str:
    """Extract module name from a permission string like 'finance:read'."""
    return permission.split(":")[0]


def _is_read_action(permission: str) -> bool:
    """Return True if the permission is a read action."""
    parts = permission.split(":")
    return parts[-1] == "read" if len(parts) >= 2 else False


async def check_user_permission(
    db: AsyncSession,
    user: User,
    permission: str,
) -> bool:
    """Check permission with per-user overrides, falling back to role defaults.

    Priority:
      1. SUPER_ADMIN role always passes.
      2. If UserPermission rows exist for this user, they are authoritative.
      3. Otherwise fall back to the role-based matrix.
    """
    role = _normalize_role(user.role)
    # SUPER_ADMIN bypasses everything
    if PERMISSIONS.get(role) == ["*"]:
        return True

    module = _extract_module(permission)
    is_read = _is_read_action(permission)

    # Check per-user override
    result = await db.execute(
        select(UserPermission).where(
            UserPermission.user_id == user.id,
            UserPermission.module == module,
        )
    )
    user_perm = result.scalar_one_or_none()

    if user_perm is not None:
        return user_perm.can_read if is_read else user_perm.can_write

    # Fallback to role-based
    return check_permission(user.role, permission)


def require_permission(permission: str):
    """FastAPI dependency factory: restrict access by permission.

    Uses per-user overrides when available, otherwise role-based defaults.
    """
    async def _permission_check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        allowed = await check_user_permission(db, user, permission)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        return user
    return _permission_check
