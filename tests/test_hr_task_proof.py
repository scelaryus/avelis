from __future__ import annotations

from datetime import date
from io import BytesIO
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers, UploadFile

from app.api.hr import upload_task_proof
from app.models.core import Document, Tenant, User
from app.models.hr import Employee, EmploymentStatus, HRTask, TaskApprovalStatus
from app.auth.security import get_password_hash
from app.api.hr import TaskRatingBody, rate_task


class DummyStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.uploads.append((key, data, content_type))
        return key


@pytest_asyncio.fixture
async def tenant(db: AsyncSession) -> Tenant:
    tenant = Tenant(id=str(uuid.uuid4()), name="Test Corp", code="TST", is_active=True)
    db.add(tenant)
    await db.flush()
    return tenant


@pytest_asyncio.fixture
async def employee_user(db: AsyncSession, tenant: Tenant) -> User:
    employee = Employee(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        employee_number="EMP-PRF-001",
        first_name="Aya",
        last_name="Test",
        email="aya@test.local",
        status=EmploymentStatus.ACTIVE,
        department="RH",
        position="Coordinator",
    )
    db.add(employee)
    await db.flush()

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="aya@test.local",
        hashed_password=get_password_hash("secret123"),
        full_name="Aya Test",
        role="RH",
        employee_id=employee.id,
        is_active=True,
    )
    db.add(user)
    employee.user_id = user.id
    await db.flush()
    return user


@pytest_asyncio.fixture
async def approved_task(db: AsyncSession, tenant: Tenant, employee_user: User) -> HRTask:
    task = HRTask(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        employee_id=employee_user.employee_id,
        task_type="hr",
        title="Upload proof",
        description="Submit completion proof",
        plan_date=date.today(),
        assigned_to=employee_user.id,
        approval_status=TaskApprovalStatus.APPROVED,
        status="in_progress",
    )
    db.add(task)
    await db.flush()
    return task


@pytest.mark.asyncio
async def test_upload_task_proof_uses_storage_service_and_creates_document(
    db: AsyncSession,
    employee_user: User,
    approved_task: HRTask,
    monkeypatch: pytest.MonkeyPatch,
):
    storage = DummyStorage()
    monkeypatch.setattr("app.storage.service.get_storage_service", lambda: storage)

    upload = UploadFile(
        file=BytesIO(b"proof payload"),
        filename="proof.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    result = await upload_task_proof(
        task_id=approved_task.id,
        file=upload,
        user=employee_user,
        db=db,
    )

    assert result["task_id"] == approved_task.id
    assert result["approval_status"] == TaskApprovalStatus.PROOF_SUBMITTED.value
    assert storage.uploads
    storage_key, content, content_type = storage.uploads[0]
    assert approved_task.id in storage_key
    assert content == b"proof payload"
    assert content_type == "text/plain"

    await db.refresh(approved_task)
    assert approved_task.approval_status == TaskApprovalStatus.PROOF_SUBMITTED
    assert approved_task.proof_document_id is not None

    document = await db.scalar(select(Document).where(Document.id == approved_task.proof_document_id))
    assert document is not None
    assert document.filename == "proof.txt"
    assert document.storage_key == storage_key
    assert document.uploaded_by == employee_user.id


@pytest.mark.asyncio
async def test_rate_task_closes_completed_task(
    db: AsyncSession,
    tenant: Tenant,
    employee_user: User,
):
    manager = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="manager@test.local",
        hashed_password=get_password_hash("secret123"),
        full_name="Manager",
        role="RH",
        is_active=True,
    )
    db.add(manager)
    await db.flush()

    task = HRTask(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        employee_id=employee_user.employee_id,
        task_type="hr",
        title="Completed task",
        description="Ready for rating",
        plan_date=date.today(),
        assigned_to=employee_user.id,
        approval_status=TaskApprovalStatus.APPROVED,
        status="completed",
        completed_by=employee_user.id,
    )
    db.add(task)
    await db.flush()

    result = await rate_task(
        task_id=task.id,
        body=TaskRatingBody(rating=4, feedback="Bien fait"),
        user=manager,
        db=db,
    )

    await db.refresh(task)
    assert result["status"] == "closed"
    assert result["approval_status"] == TaskApprovalStatus.VALIDATED.value
    assert task.status == "closed"
    assert task.approval_status == TaskApprovalStatus.VALIDATED
    assert task.manager_rating == 4