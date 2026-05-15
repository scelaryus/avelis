"""GFI Platform - Admin API router."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, Tenant, AuditLog, UserPermission
from app.models.hr import Employee
from app.auth.dependencies import require_role
from app.schemas.api import SetUserPermissionsBody, UpdateUserRoleBody
from app.services.rbac import MODULE_REGISTRY, MODULE_CODES, _normalize_role

router = APIRouter(tags=["Administration"])


# ── Tenant Management ──────────────────────────────────────────────

@router.post("/tenants")
async def create_tenant(
    name: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant."""
    tenant = Tenant(name=name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return {"id": str(tenant.id), "name": tenant.name}


@router.get("/tenants")
async def list_tenants(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all tenants."""
    result = await db.execute(select(Tenant).order_by(Tenant.name))
    tenants = result.scalars().all()
    return [{"id": str(t.id), "name": t.name} for t in tenants]


# ── User Management ───────────────────────────────────────────────

@router.get("/users")
async def list_users(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List users in current tenant."""
    result = await db.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.full_name)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": _normalize_role(u.role),
            "is_active": u.is_active,
            "employee_id": str(u.employee_id) if u.employee_id else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UpdateUserRoleBody,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role."""
    from app.services.rbac import UserRole, ROLE_ALIASES
    role = body.role
    valid_roles = {r.value for r in UserRole} | set(ROLE_ALIASES.keys())
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Valid roles: {sorted(valid_roles)}",
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = target_user.role
    target_user.role = _normalize_role(role)
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user_role_change",
        entity_type="user",
        entity_id=str(user_id),
    ))
    await db.commit()
    return {"user_id": str(user_id), "role": _normalize_role(role)}


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Activate/deactivate a user."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_user.is_active = not target_user.is_active
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user_toggle_active",
        entity_type="user",
        entity_id=str(user_id),
    ))
    await db.commit()
    return {"user_id": str(user_id), "is_active": target_user.is_active}


# ── Policies ───────────────────────────────────────────────────────

@router.get("/policies")
async def get_policies(
    user: User = Depends(require_role("admin")),
):
    """Get current platform policies."""
    from app.config import get_settings
    settings = get_settings()
    return {
        "vat_rates_allowed": settings.VAT_RATES_ALLOWED,
        "rounding_tolerance": settings.ROUNDING_TOLERANCE,
        "confidence_gate_threshold": settings.CONFIDENCE_GATE_THRESHOLD,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "render_dpi": settings.RENDER_DPI,
        "ocr_engine": settings.OCR_ENGINE,
    }


# ── Audit Log ──────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action_filter: Optional[str] = Query(None),
    user_filter: Optional[uuid.UUID] = Query(None),
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries."""
    base = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    count_base = select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == user.tenant_id)

    if action_filter:
        base = base.where(AuditLog.action == action_filter)
        count_base = count_base.where(AuditLog.action == action_filter)
    if user_filter:
        base = base.where(AuditLog.user_id == user_filter)
        count_base = count_base.where(AuditLog.user_id == user_filter)

    total = (await db.execute(count_base)).scalar()
    result = await db.execute(
        base.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(l.id),
                "user_id": str(l.user_id) if l.user_id else None,
                "action": l.action,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── System Stats ───────────────────────────────────────────────────

@router.get("/stats")
async def get_system_stats(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get system-wide statistics for admin dashboard."""
    from app.models.core import Document, Workflow, WorkflowStatus, JournalEntry

    docs_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.tenant_id == user.tenant_id)
    )).scalar()

    workflows_total = (await db.execute(
        select(func.count()).select_from(Workflow).where(Workflow.tenant_id == user.tenant_id)
    )).scalar()

    workflows_committed = (await db.execute(
        select(func.count()).select_from(Workflow).where(
            Workflow.tenant_id == user.tenant_id,
            Workflow.status == WorkflowStatus.COMMITTED,
        )
    )).scalar()

    workflows_blocked = (await db.execute(
        select(func.count()).select_from(Workflow).where(
            Workflow.tenant_id == user.tenant_id,
            Workflow.status == WorkflowStatus.BLOCKED,
        )
    )).scalar()

    journal_entries = (await db.execute(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.tenant_id == user.tenant_id)
    )).scalar()

    users_count = (await db.execute(
        select(func.count()).select_from(User).where(User.tenant_id == user.tenant_id)
    )).scalar()

    return {
        "documents": docs_count,
        "workflows_total": workflows_total,
        "workflows_committed": workflows_committed,
        "workflows_blocked": workflows_blocked,
        "journal_entries": journal_entries,
        "users": users_count,
    }


# ── Module Registry ────────────────────────────────────────────────

@router.get("/modules")
async def list_modules(
    user: User = Depends(require_role("admin")),
):
    """List all application modules available for permission assignment."""
    return MODULE_REGISTRY


# ── User Detail with Permissions ───────────────────────────────────

@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get full user detail including employee link and permissions."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Load employee name if linked
    employee_name = None
    if target.employee_id:
        emp_result = await db.execute(
            select(Employee).where(Employee.id == target.employee_id)
        )
        emp = emp_result.scalar_one_or_none()
        if emp:
            employee_name = f"{emp.first_name} {emp.last_name}"

    # Load per-user permissions
    perm_result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = perm_result.scalars().all()

    return {
        "id": str(target.id),
        "tenant_id": str(target.tenant_id),
        "email": target.email,
        "full_name": target.full_name,
        "role": _normalize_role(target.role),
        "is_active": target.is_active,
        "employee_id": str(target.employee_id) if target.employee_id else None,
        "employee_name": employee_name,
        "permissions": [
            {"module": p.module, "can_read": p.can_read, "can_write": p.can_write}
            for p in perms
        ],
        "created_at": target.created_at.isoformat() if target.created_at else None,
    }


# ── User Permission CRUD ──────────────────────────────────────────

@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get all per-user module permissions for a user."""
    # Verify user exists in this tenant
    target = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    if target.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = result.scalars().all()
    return [
        {"module": p.module, "can_read": p.can_read, "can_write": p.can_write}
        for p in perms
    ]


@router.put("/users/{user_id}/permissions")
async def set_user_permissions(
    user_id: str,
    body: SetUserPermissionsBody,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Set per-user module permissions (replaces all existing).

    Pass a list of {module, can_read, can_write} items.
    Modules not included will have no per-user override (role defaults apply).
    """
    # Verify user exists in this tenant
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate module codes
    for item in body.permissions:
        if item.module not in MODULE_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown module: {item.module}. Valid: {sorted(MODULE_CODES)}",
            )

    # Delete existing permissions
    await db.execute(
        delete(UserPermission).where(UserPermission.user_id == user_id)
    )

    # Insert new permissions
    new_perms = []
    for item in body.permissions:
        perm = UserPermission(
            tenant_id=user.tenant_id,
            user_id=user_id,
            module=item.module,
            can_read=item.can_read,
            can_write=item.can_write,
        )
        db.add(perm)
        new_perms.append({"module": item.module, "can_read": item.can_read, "can_write": item.can_write})

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user_permissions_set",
        entity_type="user",
        entity_id=user_id,
        new_value=new_perms,
    ))
    await db.commit()

    return {"user_id": user_id, "permissions": new_perms}


@router.delete("/users/{user_id}/permissions")
async def clear_user_permissions(
    user_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Remove all per-user overrides — user reverts to role-based defaults."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        delete(UserPermission).where(UserPermission.user_id == user_id)
    )
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user_permissions_clear",
        entity_type="user",
        entity_id=user_id,
    ))
    await db.commit()
    return {"user_id": user_id, "permissions": []}
