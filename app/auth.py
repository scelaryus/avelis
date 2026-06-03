"""
GFI v7.0 — Authorization enforcement and audit logging.

This module provides the application-level enforcement for:
- Permission checks (has_permission)
- Separation of Duties (check_sod)
- RF2 access control (with mandatory audit tagging)
- Audit trail logging (log_audit)
- KT-06: Agent Commercial discount > 5% auto-escalation

Every module that performs authorization MUST use these functions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PermissionDenied(Exception):
    """Raised when a user lacks the required permission."""

    pass


class SoDViolation(Exception):
    """Raised when a Separation of Duties rule is triggered."""

    def __init__(self, message: str, sod_code: str, escalate_to: str | None):
        super().__init__(message)
        self.sod_code = sod_code
        self.escalate_to = escalate_to


class RF2AccessDenied(Exception):
    """Raised when a user without RF2 permission attempts RF2 access."""

    pass


def has_permission(
    session: Session,
    user_id: UUID,
    company_id: UUID,
    permission_code: str,
) -> bool:
    """Check if user has a specific permission in a specific company."""
    from app.models.user_role import UserRole
    from app.models.role_permission import RolePermission
    from app.models.permission import Permission

    result = (
        session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(
            UserRole.user_id == user_id,
            UserRole.company_id == company_id,
            UserRole.is_deleted.is_(False),
            Permission.code == permission_code,
            Permission.is_deleted.is_(False),
        )
        .first()
    )
    return result is not None


def require_permission(
    session: Session,
    user_id: UUID,
    company_id: UUID,
    permission_code: str,
) -> None:
    """Raise PermissionDenied if user lacks the permission."""
    if not has_permission(session, user_id, company_id, permission_code):
        raise PermissionDenied(
            f"User {user_id} lacks permission '{permission_code}' "
            f"in company {company_id}."
        )


def get_user_role_code(
    session: Session,
    user_id: UUID,
    company_id: UUID,
) -> str | None:
    """Return the first active role code for audit snapshot."""
    from app.models.user_role import UserRole
    from app.models.role import Role

    result = (
        session.query(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == user_id,
            UserRole.company_id == company_id,
            UserRole.is_deleted.is_(False),
        )
        .first()
    )
    return result[0] if result else None


def check_sod(
    session: Session,
    user_id: UUID,
    company_id: UUID,
    permission_code: str,
    resource_type: str,
    resource_id: UUID,
) -> None:
    """
    Check Separation of Duties rules.

    Looks up active SoD rules where action_a or action_b matches the
    permission_code. Then checks if the same user already performed the
    conflicting action on the same resource (via audit_trail).

    Raises SoDViolation with auto-escalation target if violated.
    """
    from app.models.sod_rule import SodRule
    from app.models.audit_trail import AuditTrail

    rules = (
        session.query(SodRule)
        .filter(
            SodRule.is_active.is_(True),
            (SodRule.action_a == permission_code)
            | (SodRule.action_b == permission_code),
        )
        .all()
    )

    for rule in rules:
        # Determine the conflicting action
        if rule.action_a == permission_code:
            conflicting = rule.action_b
        else:
            conflicting = rule.action_a

        # Check if this user already did the conflicting action on this resource
        if rule.scope == "SAME_RECORD":
            conflict = (
                session.query(AuditTrail.id)
                .filter(
                    AuditTrail.user_id == user_id,
                    AuditTrail.company_id == company_id,
                    AuditTrail.resource_type == resource_type,
                    AuditTrail.resource_id == resource_id,
                    AuditTrail.action.in_(["CREATE", "WRITE", "APPROVE"]),
                )
                .first()
            )
        else:
            conflict = (
                session.query(AuditTrail.id)
                .filter(
                    AuditTrail.user_id == user_id,
                    AuditTrail.company_id == company_id,
                    AuditTrail.resource_type == resource_type,
                )
                .first()
            )

        if conflict:
            raise SoDViolation(
                f"SoD rule {rule.code}: {rule.description}. "
                f"User {user_id} already performed the conflicting action "
                f"on {resource_type}/{resource_id}. "
                f"Escalating to {rule.escalate_to_role}.",
                sod_code=rule.code,
                escalate_to=rule.escalate_to_role,
            )


def require_rf2_access(
    session: Session,
    user_id: UUID,
    company_id: UUID,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    resource_id: UUID | None = None,
    action: str = "READ",
) -> None:
    """
    Gate RF2 access: check permission AND log the access (mandatory).

    Even a READ generates an audit entry tagged rf2_access=true.
    Agent Commercial role must NEVER reach this — the UI strips RF2 entirely.
    """
    perm = "rf2.read" if action == "READ" else "rf2.write"
    if not has_permission(session, user_id, company_id, perm):
        raise RF2AccessDenied(
            f"User {user_id} has no RF2 access in company {company_id}."
        )

    # Mandatory audit entry for every RF2 access
    log_audit(
        session,
        user_id=user_id,
        company_id=company_id,
        action=action,
        resource_type="rf2_transaction",
        resource_id=resource_id,
        module="RF2",
        rf2_access=True,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_audit(
    session: Session,
    *,
    user_id: UUID,
    company_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    data_before: dict | None = None,
    data_after: dict | None = None,
    module: str | None = None,
    workflow_step: str | None = None,
    verification_level: int | None = None,
    event_id: UUID | None = None,
    rf2_access: bool = False,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Write an immutable audit trail entry.

    The role_code is snapshotted at the time of the action.
    created_at is server-side (UTC) — never trust client time.
    """
    from app.models.audit_trail import AuditTrail

    role_code = get_user_role_code(session, user_id, company_id)

    entry = AuditTrail(
        company_id=company_id,
        user_id=user_id,
        role_code=role_code,
        ip_address=ip_address,
        user_agent=user_agent,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        data_before=data_before,
        data_after=data_after,
        module=module,
        workflow_step=workflow_step,
        verification_level=verification_level,
        event_id=event_id,
        rf2_access=rf2_access,
    )
    session.add(entry)
    session.flush()
