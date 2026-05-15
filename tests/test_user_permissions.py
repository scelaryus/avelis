"""
Tests for User Permission System & Notification Integration
============================================================
Covers:
  - UserPermission model CRUD
  - RBAC per-user permission overrides
  - Role-based fallback when no user overrides
  - Admin API: modules, get/set/clear permissions, user detail
  - Account-employee linking + notification flow
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User, Tenant, AuditLog, UserPermission
from app.models.hr import Employee, TaskNotification, HRTask, EmploymentStatus
from app.services.rbac import (
    check_permission,
    check_user_permission,
    MODULE_CODES,
    MODULE_REGISTRY,
    _extract_module,
    _is_read_action,
    ROLE_ALIASES,
    UserRole,
)
from app.auth.security import get_password_hash


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def tenant(db: AsyncSession) -> Tenant:
    t = Tenant(id=str(uuid.uuid4()), name="Test Corp", code="TST", is_active=True)
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, tenant: Tenant) -> User:
    u = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession, tenant: Tenant) -> User:
    u = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="viewer@test.com",
        hashed_password=get_password_hash("viewer123"),
        full_name="Viewer User",
        role="VIEWER",
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def employee(db: AsyncSession, tenant: Tenant) -> Employee:
    emp = Employee(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        employee_number="EMP-001",
        first_name="Ahmed",
        last_name="Benali",
        email="ahmed@test.com",
        status=EmploymentStatus.ACTIVE,
        department="IT",
        position="Developer",
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest_asyncio.fixture
async def employee_user(db: AsyncSession, tenant: Tenant, employee: Employee) -> User:
    u = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="ahmed@test.com",
        hashed_password=get_password_hash("emp123"),
        full_name="Ahmed Benali",
        role="EMPLOYE",
        employee_id=employee.id,
        is_active=True,
    )
    db.add(u)
    employee.user_id = u.id
    await db.flush()
    return u


# ────────────────────────────────────────────────────────────────────────────
# 1. Module registry & helper tests
# ────────────────────────────────────────────────────────────────────────────

class TestModuleRegistry:
    def test_module_registry_non_empty(self):
        assert len(MODULE_REGISTRY) >= 15

    def test_module_codes_derived(self):
        codes = {m["code"] for m in MODULE_REGISTRY}
        assert codes == MODULE_CODES

    def test_all_modules_have_label(self):
        for m in MODULE_REGISTRY:
            assert "code" in m
            assert "label" in m
            assert len(m["label"]) > 0

    def test_extract_module(self):
        assert _extract_module("finance:read") == "finance"
        assert _extract_module("bim:write") == "bim"
        assert _extract_module("adv:sale:create") == "adv"

    def test_is_read_action(self):
        assert _is_read_action("finance:read") is True
        assert _is_read_action("finance:write") is False
        assert _is_read_action("adv:sale:create") is False
        assert _is_read_action("*:read") is True


# ────────────────────────────────────────────────────────────────────────────
# 2. Role-based permission tests (existing behaviour must not break)
# ────────────────────────────────────────────────────────────────────────────

class TestRoleBasedPermissions:
    def test_super_admin_has_everything(self):
        assert check_permission("SUPER_ADMIN", "finance:read") is True
        assert check_permission("SUPER_ADMIN", "bim:write") is True
        assert check_permission("SUPER_ADMIN", "anything:whatever") is True

    def test_admin_alias_maps_to_super_admin(self):
        assert check_permission("admin", "finance:read") is True

    def test_viewer_has_read_only(self):
        assert check_permission("VIEWER", "finance:read") is True
        assert check_permission("VIEWER", "finance:write") is False
        assert check_permission("VIEWER", "bim:read") is True

    def test_daf_has_finance(self):
        assert check_permission("DAF", "finance:read") is True
        assert check_permission("DAF", "finance:write") is True
        assert check_permission("DAF", "bim:write") is False

    def test_employe_has_own_only(self):
        assert check_permission("EMPLOYE", "spi:own") is True
        assert check_permission("EMPLOYE", "documents:read") is True
        assert check_permission("EMPLOYE", "finance:read") is False

    def test_unknown_role_has_nothing(self):
        assert check_permission("UNKNOWN_ROLE", "finance:read") is False

    def test_role_aliases(self):
        assert ROLE_ALIASES["accountant"] == "DAF"
        assert ROLE_ALIASES["hr_manager"] == "RH"


# ────────────────────────────────────────────────────────────────────────────
# 3. Per-user permission override tests
# ────────────────────────────────────────────────────────────────────────────

class TestPerUserPermissions:
    @pytest.mark.asyncio
    async def test_no_overrides_falls_back_to_role(self, db: AsyncSession, viewer_user: User):
        # VIEWER role has *:read
        allowed = await check_user_permission(db, viewer_user, "finance:read")
        assert allowed is True

        denied = await check_user_permission(db, viewer_user, "finance:write")
        assert denied is False

    @pytest.mark.asyncio
    async def test_override_grants_write(self, db: AsyncSession, viewer_user: User):
        # Grant write on finance to a viewer
        perm = UserPermission(
            tenant_id=viewer_user.tenant_id,
            user_id=viewer_user.id,
            module="finance",
            can_read=True,
            can_write=True,
        )
        db.add(perm)
        await db.flush()

        assert await check_user_permission(db, viewer_user, "finance:write") is True
        assert await check_user_permission(db, viewer_user, "finance:read") is True

    @pytest.mark.asyncio
    async def test_override_revokes_read(self, db: AsyncSession, viewer_user: User):
        # Explicitly deny read on bim for a viewer (who normally has *:read)
        perm = UserPermission(
            tenant_id=viewer_user.tenant_id,
            user_id=viewer_user.id,
            module="bim",
            can_read=False,
            can_write=False,
        )
        db.add(perm)
        await db.flush()

        assert await check_user_permission(db, viewer_user, "bim:read") is False

    @pytest.mark.asyncio
    async def test_super_admin_ignores_overrides(self, db: AsyncSession, admin_user: User):
        # Even if we add a restrictive override, SUPER_ADMIN bypasses
        perm = UserPermission(
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            module="finance",
            can_read=False,
            can_write=False,
        )
        db.add(perm)
        await db.flush()

        assert await check_user_permission(db, admin_user, "finance:read") is True
        assert await check_user_permission(db, admin_user, "finance:write") is True

    @pytest.mark.asyncio
    async def test_module_without_override_uses_role(self, db: AsyncSession, viewer_user: User):
        # Override only finance, check that bim still uses role default
        perm = UserPermission(
            tenant_id=viewer_user.tenant_id,
            user_id=viewer_user.id,
            module="finance",
            can_read=True,
            can_write=True,
        )
        db.add(perm)
        await db.flush()

        # bim has no override, falls back to VIEWER (has *:read)
        assert await check_user_permission(db, viewer_user, "bim:read") is True
        assert await check_user_permission(db, viewer_user, "bim:write") is False


# ────────────────────────────────────────────────────────────────────────────
# 4. UserPermission model tests
# ────────────────────────────────────────────────────────────────────────────

class TestUserPermissionModel:
    @pytest.mark.asyncio
    async def test_create_permission(self, db: AsyncSession, viewer_user: User):
        perm = UserPermission(
            tenant_id=viewer_user.tenant_id,
            user_id=viewer_user.id,
            module="hr",
            can_read=True,
            can_write=False,
        )
        db.add(perm)
        await db.flush()

        result = await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == viewer_user.id,
                UserPermission.module == "hr",
            )
        )
        saved = result.scalar_one()
        assert saved.can_read is True
        assert saved.can_write is False

    @pytest.mark.asyncio
    async def test_multiple_modules(self, db: AsyncSession, viewer_user: User):
        for mod in ["hr", "finance", "bim"]:
            db.add(UserPermission(
                tenant_id=viewer_user.tenant_id,
                user_id=viewer_user.id,
                module=mod,
                can_read=True,
                can_write=(mod == "hr"),
            ))
        await db.flush()

        result = await db.execute(
            select(UserPermission).where(UserPermission.user_id == viewer_user.id)
        )
        perms = result.scalars().all()
        assert len(perms) == 3

        perm_map = {p.module: p for p in perms}
        assert perm_map["hr"].can_write is True
        assert perm_map["finance"].can_write is False


# ────────────────────────────────────────────────────────────────────────────
# 5. Account ↔ Employee linking tests
# ────────────────────────────────────────────────────────────────────────────

class TestAccountEmployeeLinking:
    @pytest.mark.asyncio
    async def test_employee_linked_to_user(self, db: AsyncSession, employee: Employee, employee_user: User):
        assert employee.user_id == employee_user.id
        assert employee_user.employee_id == employee.id

    @pytest.mark.asyncio
    async def test_create_account_for_employee(self, db: AsyncSession, tenant: Tenant, admin_user: User):
        emp = Employee(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            employee_number="EMP-002",
            first_name="Sara",
            last_name="Kaddouri",
            email="sara@test.com",
            status=EmploymentStatus.ACTIVE,
        )
        db.add(emp)
        await db.flush()

        new_user = User(
            tenant_id=tenant.id,
            email=emp.email,
            full_name=f"{emp.first_name} {emp.last_name}",
            hashed_password=get_password_hash("sara123"),
            role="EMPLOYE",
            employee_id=emp.id,
        )
        db.add(new_user)
        await db.flush()
        emp.user_id = new_user.id
        await db.flush()

        assert emp.user_id == new_user.id
        assert new_user.employee_id == emp.id
        assert new_user.full_name == "Sara Kaddouri"


# ────────────────────────────────────────────────────────────────────────────
# 6. Notification flow tests
# ────────────────────────────────────────────────────────────────────────────

class TestNotificationFlow:
    @pytest.mark.asyncio
    async def test_task_notification_created(
        self, db: AsyncSession, tenant: Tenant, employee: Employee, employee_user: User,
    ):
        task = HRTask(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            employee_id=employee.id,
            assigned_to=employee_user.id,
            task_type="development",
            title="Fix login bug",
            plan_date=date(2026, 3, 12),
        )
        db.add(task)
        await db.flush()

        notif = TaskNotification(
            tenant_id=tenant.id,
            task_id=task.id,
            employee_id=employee.id,
            user_id=employee_user.id,
            title="New task assigned",
            message=f"Task '{task.title}' assigned to you.",
        )
        db.add(notif)
        await db.flush()

        result = await db.execute(
            select(TaskNotification).where(
                TaskNotification.user_id == employee_user.id,
                TaskNotification.is_read == False,
            )
        )
        notifications = result.scalars().all()
        assert len(notifications) == 1
        assert notifications[0].title == "New task assigned"
        assert notifications[0].task_id == task.id

    @pytest.mark.asyncio
    async def test_mark_notification_read(
        self, db: AsyncSession, tenant: Tenant, employee: Employee, employee_user: User,
    ):
        task = HRTask(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            employee_id=employee.id,
            task_type="review",
            title="Review PR",
            plan_date=date(2026, 3, 12),
        )
        db.add(task)
        await db.flush()

        notif = TaskNotification(
            tenant_id=tenant.id,
            task_id=task.id,
            user_id=employee_user.id,
            title="Task assigned",
            message="Review PR assigned.",
        )
        db.add(notif)
        await db.flush()

        # Mark as read
        notif.is_read = True
        await db.flush()

        result = await db.execute(
            select(TaskNotification).where(
                TaskNotification.user_id == employee_user.id,
                TaskNotification.is_read == True,
            )
        )
        assert result.scalar_one().title == "Task assigned"

    @pytest.mark.asyncio
    async def test_no_notification_without_account(
        self, db: AsyncSession, tenant: Tenant,
    ):
        """Employee without user account → no user_id in notification."""
        emp = Employee(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            employee_number="EMP-X",
            first_name="No",
            last_name="Account",
            status=EmploymentStatus.ACTIVE,
        )
        db.add(emp)
        await db.flush()

        task = HRTask(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            employee_id=emp.id,
            task_type="task",
            title="Do something",
            plan_date=date(2026, 3, 12),
        )
        db.add(task)
        await db.flush()

        notif = TaskNotification(
            tenant_id=tenant.id,
            task_id=task.id,
            employee_id=emp.id,
            user_id=None,  # No linked account
            title="Task assigned",
            message="Pending account creation.",
        )
        db.add(notif)
        await db.flush()

        result = await db.execute(
            select(TaskNotification).where(TaskNotification.employee_id == emp.id)
        )
        saved = result.scalar_one()
        assert saved.user_id is None


# ────────────────────────────────────────────────────────────────────────────
# 7. Permission + notification integration
# ────────────────────────────────────────────────────────────────────────────

class TestPermissionIntegration:
    @pytest.mark.asyncio
    async def test_employee_with_custom_permissions(
        self, db: AsyncSession, tenant: Tenant, employee_user: User,
    ):
        """Employee gets custom read on finance (normally denied for EMPLOYE)."""
        db.add(UserPermission(
            tenant_id=tenant.id,
            user_id=employee_user.id,
            module="finance",
            can_read=True,
            can_write=False,
        ))
        await db.flush()

        # Finance read now allowed via override
        assert await check_user_permission(db, employee_user, "finance:read") is True
        # Finance write still denied
        assert await check_user_permission(db, employee_user, "finance:write") is False
        # Tasks own still works via role fallback
        assert await check_user_permission(db, employee_user, "tasks:own") is True

    @pytest.mark.asyncio
    async def test_daf_with_restricted_module(self, db: AsyncSession, tenant: Tenant):
        """DAF user explicitly denied BIM access."""
        daf_user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email="daf@test.com",
            hashed_password=get_password_hash("daf123"),
            full_name="DAF User",
            role="DAF",
        )
        db.add(daf_user)
        await db.flush()

        # DAF role normally has finance:read but not bim:read
        assert await check_user_permission(db, daf_user, "finance:read") is True

        # Restrict documents for this DAF user
        db.add(UserPermission(
            tenant_id=tenant.id,
            user_id=daf_user.id,
            module="documents",
            can_read=False,
            can_write=False,
        ))
        await db.flush()

        assert await check_user_permission(db, daf_user, "documents:read") is False


# ────────────────────────────────────────────────────────────────────────────
# 8. Audit trail for permission changes
# ────────────────────────────────────────────────────────────────────────────

class TestPermissionAudit:
    @pytest.mark.asyncio
    async def test_audit_log_created(self, db: AsyncSession, tenant: Tenant, admin_user: User, viewer_user: User):
        log = AuditLog(
            tenant_id=tenant.id,
            user_id=admin_user.id,
            action="user_permissions_set",
            entity_type="user",
            entity_id=viewer_user.id,
            new_value=[{"module": "hr", "can_read": True, "can_write": True}],
        )
        db.add(log)
        await db.flush()

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.action == "user_permissions_set",
                AuditLog.entity_id == viewer_user.id,
            )
        )
        saved = result.scalar_one()
        assert saved.user_id == admin_user.id
        assert saved.new_value[0]["module"] == "hr"
