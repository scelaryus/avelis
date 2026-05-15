"""GFI Platform - HR API router."""
import uuid
from typing import Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, AuditLog
from app.models.hr import Employee, PayrollProposal, HRTask, TaskNotification, EmploymentStatus, TaskApprovalStatus
from app.auth.dependencies import get_current_user, require_role
from app.schemas.api import (
    EmployeeCreate, EmployeeResponse, PayrollResponse,
    TaskEstimateBody, TaskApproveBody, TaskValidateBody,
    CreateEmployeeAccountBody,
)
from app.services.task_planner import plan_tasks_from_text, apply_salary_adjustment
from app.services.employee_import import normalize_import_employee_row, parse_tabular_employee_file
from app.services.seed_import import EMPLOYEES_DATA

router = APIRouter(tags=["HR"])


class DailyTaskPlanCreate(BaseModel):
    plan_date: date
    raw_text: str = Field(min_length=10)
    entreprise_id: Optional[str] = None


class TaskCompleteBody(BaseModel):
    status: str = "completed"


class TaskRatingBody(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: Optional[str] = None


def _employee_full_name(employee: Employee) -> str:
    return " ".join(part for part in [employee.first_name, employee.last_name] if part).strip()


def _normalize_employee_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = " ".join(value.strip().upper().split())
    return normalized or None


async def _load_employee_maps(db: AsyncSession, tenant_id: str) -> tuple[dict[str, Employee], dict[str, str]]:
    result = await db.execute(select(Employee).where(Employee.tenant_id == tenant_id))
    employees = result.scalars().all()
    employees_by_id = {employee.id: employee for employee in employees}
    employees_by_name: dict[str, str] = {}
    for employee in employees:
        direct = _normalize_employee_name(_employee_full_name(employee))
        reverse = _normalize_employee_name(f"{employee.last_name} {employee.first_name}")
        if direct and direct not in employees_by_name:
            employees_by_name[direct] = employee.id
        if reverse and reverse not in employees_by_name:
            employees_by_name[reverse] = employee.id
    return employees_by_id, employees_by_name


def _resolve_employee_reference(name: Optional[str], employees_by_name: dict[str, str]) -> Optional[str]:
    normalized = _normalize_employee_name(name)
    if not normalized:
        return None
    return employees_by_name.get(normalized)


def _coerce_employee_status(raw_status: Optional[str], is_active: bool = True) -> EmploymentStatus:
    normalized = (raw_status or "ACTIVE").strip().upper()
    if not is_active and normalized == "ACTIVE":
        normalized = "INACTIVE"
    try:
        return EmploymentStatus(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid employee status") from exc


def _build_employee_indexes(employees: list[Employee]) -> tuple[dict[str, Employee], dict[str, Employee], dict[str, Employee]]:
    by_email: dict[str, Employee] = {}
    by_number: dict[str, Employee] = {}
    by_name: dict[str, Employee] = {}
    for employee in employees:
        if employee.email:
            by_email[employee.email.strip().lower()] = employee
        if employee.employee_number:
            by_number[employee.employee_number.strip().upper()] = employee
        direct = _normalize_employee_name(_employee_full_name(employee))
        reverse = _normalize_employee_name(f"{employee.last_name} {employee.first_name}")
        if direct:
            by_name[direct] = employee
        if reverse:
            by_name[reverse] = employee
    return by_email, by_number, by_name


def _find_matching_employee(payload: dict, by_email: dict[str, Employee], by_number: dict[str, Employee], by_name: dict[str, Employee]) -> Optional[Employee]:
    email = (payload.get("email") or "").strip().lower()
    if email and email in by_email:
        return by_email[email]
    employee_number = (payload.get("employee_number") or "").strip().upper()
    if employee_number and employee_number in by_number:
        return by_number[employee_number]
    full_name = _normalize_employee_name(" ".join(part for part in [payload.get("first_name"), payload.get("last_name")] if part))
    if full_name and full_name in by_name:
        return by_name[full_name]
    source_name = _normalize_employee_name(payload.get("source_name"))
    if source_name and source_name in by_name:
        return by_name[source_name]
    return None


async def _next_employee_number(db: AsyncSession, tenant_id: str) -> str:
    result = await db.execute(select(Employee.employee_number).where(Employee.tenant_id == tenant_id))
    max_number = 0
    for value in result.scalars().all():
        if not value:
            continue
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            max_number = max(max_number, int(digits))
    return f"EMP-{max_number + 1:04d}"


def _apply_employee_payload(
    employee: Employee,
    payload: dict,
    employee_status: EmploymentStatus,
    *,
    overwrite_nulls: bool = True,
) -> None:
    def assign(attr_name: str, value):
        if value is None and not overwrite_nulls:
            return
        setattr(employee, attr_name, value)

    assign("employee_number", payload.get("employee_number") or employee.employee_number)
    assign("first_name", payload.get("first_name") or employee.first_name)
    assign("last_name", payload.get("last_name") or employee.last_name)
    assign("email", payload.get("email"))
    assign("phone", payload.get("phone"))
    assign("professional_address", payload.get("professional_address"))
    assign("activities", payload.get("activities"))
    assign("hire_date", payload.get("hire_date"))
    assign("upcoming_activity_due_date", payload.get("upcoming_activity_due_date"))
    assign("department", payload.get("department"))
    assign("position", payload.get("position"))
    assign("company", payload.get("company"))
    employee.status = employee_status
    employee.is_active = payload.get("is_active", True)
    assign("base_salary", payload.get("base_salary"))
    assign("social_security_number", payload.get("social_security_number"))


def _serialize_employee(emp: Employee, employees_by_id: Optional[dict[str, Employee]] = None) -> EmployeeResponse:
    manager = employees_by_id.get(emp.manager_id) if employees_by_id and emp.manager_id else None
    mentor = employees_by_id.get(emp.mentor_id) if employees_by_id and emp.mentor_id else None
    return EmployeeResponse(
        id=emp.id,
        employee_number=emp.employee_number,
        first_name=emp.first_name,
        last_name=emp.last_name,
        email=emp.email,
        phone=emp.phone,
        professional_address=emp.professional_address,
        activities=emp.activities,
        user_id=emp.user_id,
        is_active=bool(emp.is_active),
        department=emp.department,
        position=emp.position,
        manager_name=_employee_full_name(manager) if manager else None,
        mentor_name=_employee_full_name(mentor) if mentor else None,
        company=emp.company,
        hire_date=emp.hire_date,
        upcoming_activity_due_date=emp.upcoming_activity_due_date,
        base_salary=float(emp.base_salary) if emp.base_salary else None,
        social_security_number=emp.social_security_number,
        status=emp.status.value if emp.status else None,
        created_at=emp.created_at,
    )


def _serialize_task(task: HRTask, employee: Optional[Employee] = None) -> dict:
    full_name = None
    if employee:
        full_name = f"{employee.first_name} {employee.last_name}"
    return {
        "id": task.id,
        "employee_id": task.employee_id,
        "employee_name": full_name,
        "entreprise_id": task.entreprise_id,
        "task_type": task.task_type,
        "title": task.title,
        "description": task.description,
        "required_role": task.required_role,
        "plan_date": task.plan_date.isoformat() if task.plan_date else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        # Estimate & approval workflow
        "approval_status": task.approval_status.value if task.approval_status else None,
        "employee_estimated_time": task.employee_estimated_time,
        "employee_estimated_price": float(task.employee_estimated_price) if task.employee_estimated_price else None,
        "estimated_at": task.estimated_at.isoformat() if task.estimated_at else None,
        "manager_final_time": task.manager_final_time,
        "manager_final_price": float(task.manager_final_price) if task.manager_final_price else None,
        "manager_approved_at": task.manager_approved_at.isoformat() if task.manager_approved_at else None,
        # Proof & AI
        "proof_document_id": task.proof_document_id,
        "proof_uploaded_at": task.proof_uploaded_at.isoformat() if task.proof_uploaded_at else None,
        "ai_score": task.ai_score,
        "ai_note": task.ai_note,
        "ai_evaluated_at": task.ai_evaluated_at.isoformat() if task.ai_evaluated_at else None,
        "manager_validated": task.manager_validated,
        "manager_validated_at": task.manager_validated_at.isoformat() if task.manager_validated_at else None,
        # Rating
        "manager_rating": task.manager_rating,
        "manager_feedback": task.manager_feedback,
        "salary_adjustment_amount": float(task.salary_adjustment_amount or 0),
    }


def _serialize_notification(notification: TaskNotification, task: Optional[HRTask] = None) -> dict:
    return {
        "id": notification.id,
        "task_id": notification.task_id,
        "employee_id": notification.employee_id,
        "user_id": notification.user_id,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "task": _serialize_task(task) if task else None,
    }


# ── Employees ──────────────────────────────────────────────────────

@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreate,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Create an employee record."""
    employee_status = _coerce_employee_status(body.status, body.is_active)

    _, employees_by_name = await _load_employee_maps(db, user.tenant_id)
    emp = Employee(
        tenant_id=user.tenant_id,
        employee_number=body.employee_number,
        manager_id=_resolve_employee_reference(body.manager_name, employees_by_name),
        mentor_id=_resolve_employee_reference(body.mentor_name, employees_by_name),
        cost_center_code=body.cost_center_code,
        currency=body.currency,
    )
    _apply_employee_payload(emp, body.model_dump(), employee_status)
    db.add(emp)
    await db.flush()

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="employee_create",
        entity_type="employee",
        entity_id=str(emp.id),
    ))
    await db.commit()
    await db.refresh(emp)
    employees_by_id, _ = await _load_employee_maps(db, user.tenant_id)
    return _serialize_employee(emp, employees_by_id)


@router.get("/employees", response_model=list[EmployeeResponse])
async def list_employees(
    department: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List employees for tenant."""
    query = select(Employee).where(Employee.tenant_id == user.tenant_id)
    if department:
        query = query.where(Employee.department == department)
    query = query.order_by(Employee.last_name, Employee.first_name)
    result = await db.execute(query)
    employees = result.scalars().all()
    employees_by_id, _ = await _load_employee_maps(db, user.tenant_id)
    return [_serialize_employee(e, employees_by_id) for e in employees]


@router.get("/employees/{emp_id}", response_model=EmployeeResponse)
async def get_employee(
    emp_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get employee details."""
    result = await db.execute(
        select(Employee).where(Employee.id == emp_id, Employee.tenant_id == user.tenant_id)
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    employees_by_id, _ = await _load_employee_maps(db, user.tenant_id)
    return _serialize_employee(emp, employees_by_id)


@router.put("/employees/{emp_id}", response_model=EmployeeResponse)
async def update_employee(
    emp_id: str,
    body: EmployeeCreate,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Update employee record."""
    result = await db.execute(
        select(Employee).where(Employee.id == emp_id, Employee.tenant_id == user.tenant_id)
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    employee_status = _coerce_employee_status(body.status, body.is_active)

    _, employees_by_name = await _load_employee_maps(db, user.tenant_id)

    _apply_employee_payload(emp, body.model_dump(), employee_status)
    emp.cost_center_code = body.cost_center_code
    emp.currency = body.currency
    emp.manager_id = _resolve_employee_reference(body.manager_name, employees_by_name)
    emp.mentor_id = _resolve_employee_reference(body.mentor_name, employees_by_name)
    await db.commit()
    await db.refresh(emp)
    employees_by_id, _ = await _load_employee_maps(db, user.tenant_id)
    return _serialize_employee(emp, employees_by_id)


@router.post("/employees/import")
async def import_employees(
    file: UploadFile = File(...),
    user: User = Depends(require_role("admin", "hr_manager", "RH", "SUPER_ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Import employees from CSV or Excel and upsert matching records."""
    filename = file.filename or "employees.csv"
    content = await file.read()
    try:
        rows = parse_tabular_employee_file(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    payloads = [normalized for normalized in (normalize_import_employee_row(row) for row in rows) if normalized]
    if not payloads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune ligne employé exploitable dans le fichier.")

    existing_rows = (await db.execute(select(Employee).where(Employee.tenant_id == user.tenant_id))).scalars().all()
    by_email, by_number, by_name = _build_employee_indexes(existing_rows)

    created = 0
    updated = 0
    normalized_names = 0
    imported_records: list[tuple[Employee, dict]] = []

    for payload in payloads:
        employee = _find_matching_employee(payload, by_email, by_number, by_name)
        employee_status = _coerce_employee_status(payload.get("status"), payload.get("is_active", True))
        if employee is None:
            employee = Employee(
                tenant_id=user.tenant_id,
                employee_number=payload.get("employee_number") or await _next_employee_number(db, user.tenant_id),
                currency="DZD",
            )
            _apply_employee_payload(employee, payload, employee_status)
            db.add(employee)
            created += 1
        else:
            if employee.first_name != payload.get("first_name") or employee.last_name != payload.get("last_name"):
                normalized_names += 1
            _apply_employee_payload(employee, payload, employee_status, overwrite_nulls=False)
            if payload.get("employee_number"):
                employee.employee_number = payload["employee_number"]
            updated += 1

        imported_records.append((employee, payload))
        await db.flush()
        refreshed = (await db.execute(select(Employee).where(Employee.id == employee.id))).scalar_one()
        if refreshed.email:
            by_email[refreshed.email.strip().lower()] = refreshed
        if refreshed.employee_number:
            by_number[refreshed.employee_number.strip().upper()] = refreshed
        full_name = _normalize_employee_name(_employee_full_name(refreshed))
        reverse_name = _normalize_employee_name(f"{refreshed.last_name} {refreshed.first_name}")
        if full_name:
            by_name[full_name] = refreshed
        if reverse_name:
            by_name[reverse_name] = refreshed

    employees_by_id, employees_by_name = await _load_employee_maps(db, user.tenant_id)
    manager_links = 0
    mentor_links = 0
    for employee, payload in imported_records:
        manager_id = _resolve_employee_reference(payload.get("manager_name"), employees_by_name)
        mentor_id = _resolve_employee_reference(payload.get("mentor_name"), employees_by_name)
        if manager_id and manager_id != employee.id and employee.manager_id != manager_id:
            employee.manager_id = manager_id
            manager_links += 1
        if mentor_id and mentor_id != employee.id and employee.mentor_id != mentor_id:
            employee.mentor_id = mentor_id
            mentor_links += 1

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="employee_import",
        entity_type="employee",
        entity_id=str(len(imported_records)),
    ))
    await db.commit()
    return {
        "status": "ok",
        "summary": {
            "rows_read": len(rows),
            "employees_processed": len(payloads),
            "created": created,
            "updated": updated,
            "normalized_names": normalized_names,
            "manager_links": manager_links,
            "mentor_links": mentor_links,
        },
    }


# ── Payroll ────────────────────────────────────────────────────────

@router.post("/payroll/generate")
async def generate_payroll(
    period_label: str,
    employee_ids: Optional[list[uuid.UUID]] = None,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Generate payroll proposals for employees."""
    query = select(Employee).where(
        Employee.tenant_id == user.tenant_id,
        Employee.status == EmploymentStatus.ACTIVE,
    )
    if employee_ids:
        query = query.where(Employee.id.in_(employee_ids))
    result = await db.execute(query)
    employees = result.scalars().all()

    if not employees:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active employees found")

    # create payroll proposals
    proposals = []
    for emp in employees:
        gross = float(emp.base_salary) if emp.base_salary else 0.0
        # Moroccan deductions (simplified)
        cnss = round(gross * 0.0448, 2)
        amo = round(gross * 0.0226, 2)
        net = round(gross - cnss - amo, 2)
        proposal = PayrollProposal(
            tenant_id=user.tenant_id,
            employee_id=emp.id,
            period_label=period_label,
            gross_salary=gross,
            deductions={"cnss": cnss, "amo": amo},
            net_salary=net,
            created_by=user.id,
        )
        db.add(proposal)
        proposals.append(proposal)

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="payroll_generate",
        entity_type="payroll",
    ))
    await db.commit()

    return {"generated": len(proposals), "period": period_label}


@router.get("/payroll", response_model=list[PayrollResponse])
async def list_payroll(
    period_label: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List payroll proposals."""
    query = select(PayrollProposal).where(PayrollProposal.tenant_id == user.tenant_id)
    if period_label:
        query = query.where(PayrollProposal.period_label == period_label)
    result = await db.execute(query.order_by(PayrollProposal.created_at.desc()))
    proposals = result.scalars().all()
    return [
        PayrollResponse(
            id=p.id,
            employee_id=p.employee_id,
            period_label=p.period_label,
            gross_salary=float(p.gross_salary) if p.gross_salary else None,
            net_salary=float(p.net_salary) if p.net_salary else None,
            deductions=p.deductions or {},
            status=p.status.value if p.status else None,
            created_at=p.created_at,
        )
        for p in proposals
    ]


# ── Daily Task Management ─────────────────────────────────────────

@router.post("/tasks/plan", status_code=status.HTTP_201_CREATED)
async def create_daily_task_plan(
    body: DailyTaskPlanCreate,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    if body.plan_date < today or body.plan_date > today + timedelta(days=7):
        raise HTTPException(status_code=400, detail="Task planning must target today or the coming 7 days")

    employees_result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == user.tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        ).order_by(Employee.department, Employee.position, Employee.last_name)
    )
    employees = employees_result.scalars().all()
    if not employees:
        raise HTTPException(status_code=404, detail="No active employees found")

    user_result = await db.execute(select(User).where(User.tenant_id == user.tenant_id, User.is_active == True))
    users = user_result.scalars().all()
    user_by_email = {u.email.lower(): u for u in users if u.email}
    user_by_employee_id = {u.employee_id: u for u in users if u.employee_id}

    planned = await plan_tasks_from_text(body.raw_text, employees, body.plan_date)
    created_tasks = []
    for item in planned:
        employee = item["employee"]
        matched_user = None
        if employee and employee.user_id:
            matched_user = next((u for u in users if u.id == employee.user_id), None)
        if matched_user is None and employee:
            matched_user = user_by_employee_id.get(employee.id)
        if matched_user is None and employee and employee.email:
            matched_user = user_by_email.get(employee.email.lower())
        task = HRTask(
            tenant_id=user.tenant_id,
            entreprise_id=body.entreprise_id,
            employee_id=employee.id if employee else None,
            task_type="daily_plan",
            title=item["title"],
            description=item["description"],
            plan_date=body.plan_date,
            due_date=body.plan_date,
            required_role=item["required_role"],
            source_text=body.raw_text,
            status="pending",
            assigned_to=matched_user.id if matched_user else None,
            created_by=user.id,
            metadata_={
                "planner": "ai_task_planner_llm",
                "ai_reasoning": item.get("ai_reasoning", ""),
                "employee_position": employee.position if employee else None,
                "employee_department": employee.department if employee else None,
            },
        )
        db.add(task)
        await db.flush()

        notification = TaskNotification(
            tenant_id=user.tenant_id,
            task_id=task.id,
            employee_id=employee.id if employee else None,
            user_id=matched_user.id if matched_user else None,
            title=f"Tâche du {body.plan_date.isoformat()} - {task.title}",
            message=task.description,
        )
        db.add(notification)
        created_tasks.append(task)

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="daily_task_plan_create",
        entity_type="hr_tasks",
        entity_id=created_tasks[0].id if created_tasks else None,
    ))
    await db.commit()

    employee_map = {e.id: e for e in employees}
    return {
        "created": len(created_tasks),
        "tasks": [_serialize_task(task, employee_map.get(task.employee_id)) for task in created_tasks],
    }


@router.get("/tasks")
async def list_tasks(
    plan_date: Optional[date] = Query(None),
    employee_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    mine: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(HRTask).where(HRTask.tenant_id == user.tenant_id)
    if plan_date:
        query = query.where(HRTask.plan_date == plan_date)
    if employee_id:
        query = query.where(HRTask.employee_id == employee_id)
    if status_filter:
        query = query.where(HRTask.status == status_filter)
    if mine and user.role not in {"admin", "SUPER_ADMIN"}:
        if user.employee_id:
            query = query.where(
                or_(HRTask.assigned_to == user.id, HRTask.employee_id == user.employee_id)
            )
        else:
            query = query.where(HRTask.assigned_to == user.id)
    query = query.order_by(HRTask.plan_date.asc(), HRTask.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()
    employee_ids = [task.employee_id for task in tasks if task.employee_id]
    employees_result = await db.execute(select(Employee).where(Employee.id.in_(employee_ids))) if employee_ids else None
    employees = {e.id: e for e in employees_result.scalars().all()} if employees_result else {}
    return [_serialize_task(task, employees.get(task.employee_id)) for task in tasks]


@router.get("/tasks/notifications")
async def list_task_notifications(
    unread_only: bool = Query(False),
    mine: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TaskNotification).where(TaskNotification.tenant_id == user.tenant_id)
    if unread_only:
        query = query.where(TaskNotification.is_read == False)
    if mine and user.role not in {"admin", "SUPER_ADMIN"}:
        if user.employee_id:
            query = query.where(
                or_(TaskNotification.user_id == user.id, TaskNotification.employee_id == user.employee_id)
            )
        else:
            query = query.where(TaskNotification.user_id == user.id)
    query = query.order_by(TaskNotification.created_at.desc())
    result = await db.execute(query)
    notifications = result.scalars().all()

    task_ids = [notification.task_id for notification in notifications]
    task_result = await db.execute(select(HRTask).where(HRTask.id.in_(task_ids))) if task_ids else None
    task_map = {task.id: task for task in task_result.scalars().all()} if task_result else {}
    return [_serialize_notification(notification, task_map.get(notification.task_id)) for notification in notifications]


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    body: TaskCompleteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.status not in {"completed", "in_progress", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid task status")

    task.status = body.status
    if body.status == "completed":
        task.completed_at = datetime.utcnow()
        task.completed_by = user.id

    await db.commit()
    return {"id": task.id, "status": task.status}


@router.post("/tasks/{task_id}/rate")
async def rate_task(
    task_id: str,
    body: TaskRatingBody,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task must be completed before rating")
    if not task.employee_id:
        raise HTTPException(status_code=400, detail="Task has no assigned employee")

    employee_result = await db.execute(select(Employee).where(Employee.id == task.employee_id, Employee.tenant_id == user.tenant_id))
    employee = employee_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Assigned employee not found")

    adjustment = apply_salary_adjustment(employee, task, body.rating)
    task.manager_rating = body.rating
    task.manager_feedback = body.feedback
    task.rated_at = datetime.utcnow()
    task.status = "closed"
    if task.approval_status in {
        TaskApprovalStatus.APPROVED,
        TaskApprovalStatus.IN_PROGRESS,
        TaskApprovalStatus.PROOF_SUBMITTED,
        TaskApprovalStatus.AI_EVALUATED,
    }:
        task.approval_status = TaskApprovalStatus.VALIDATED

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="task_rate",
        entity_type="hr_task",
        entity_id=task.id,
    ))
    await db.commit()

    return {
        "task_id": task.id,
        "status": task.status,
        "approval_status": task.approval_status.value if task.approval_status else None,
        "rating": task.manager_rating,
        "salary_adjustment_amount": float(adjustment),
        "new_base_salary": float(Decimal(str(employee.base_salary or 0))),
    }


@router.post("/tasks/notifications/{notification_id}/read")
async def read_task_notification(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TaskNotification).where(
            TaskNotification.id == notification_id,
            TaskNotification.tenant_id == user.tenant_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    await db.commit()
    return {"id": notification.id, "is_read": notification.is_read}


# ── Employee Account Generation ───────────────────────────────────

@router.post("/employees/create-account", status_code=status.HTTP_201_CREATED)
async def create_employee_account(
    body: CreateEmployeeAccountBody,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Create a user account for an employee, linking them together."""
    from app.auth.security import get_password_hash

    # Verify employee exists in this tenant
    emp_result = await db.execute(
        select(Employee).where(Employee.id == body.employee_id, Employee.tenant_id == user.tenant_id)
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Check if employee already has an account
    if employee.user_id:
        raise HTTPException(status_code=409, detail="Employee already has a user account")

    email = body.email or employee.email
    if not email:
        raise HTTPException(status_code=400, detail="Email required (employee has no email on file)")

    # Check unique email within this tenant
    existing = await db.execute(
        select(User).where(User.email == email, User.tenant_id == user.tenant_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered in this company")

    new_user = User(
        tenant_id=user.tenant_id,
        email=email,
        full_name=f"{employee.first_name} {employee.last_name}",
        hashed_password=get_password_hash(body.password),
        role=body.role or "EMPLOYE",
        employee_id=employee.id,
    )
    db.add(new_user)
    await db.flush()

    # Link back
    employee.user_id = new_user.id

    # Notify
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="employee_account_create",
        entity_type="user",
        entity_id=str(new_user.id),
    ))
    await db.commit()
    await db.refresh(new_user)

    return {
        "user_id": new_user.id,
        "employee_id": employee.id,
        "email": new_user.email,
        "role": new_user.role,
        "full_name": new_user.full_name,
    }


# ── Task Estimate (employee submits estimate) ─────────────────────

@router.post("/tasks/{task_id}/estimate")
async def submit_task_estimate(
    task_id: str,
    body: TaskEstimateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee submits time and price estimate for assigned task."""
    result = await db.execute(
        select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only assigned user can estimate
    if task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned user can submit estimates")

    if task.approval_status not in (TaskApprovalStatus.PENDING_ESTIMATE, TaskApprovalStatus.REJECTED):
        raise HTTPException(status_code=400, detail=f"Cannot estimate in status {task.approval_status.value}")

    task.employee_estimated_time = body.estimated_time
    task.employee_estimated_price = body.estimated_price
    task.estimated_at = datetime.utcnow()
    task.approval_status = TaskApprovalStatus.ESTIMATED

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="task_estimate", entity_type="hr_task", entity_id=task.id,
    ))
    await db.commit()

    return {"task_id": task.id, "approval_status": task.approval_status.value}


# ── Task Approve/Override (manager) ───────────────────────────────

@router.post("/tasks/{task_id}/approve")
async def approve_task_estimate(
    task_id: str,
    body: TaskApproveBody,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Manager approves or rejects employee estimate, optionally overriding time/price."""
    result = await db.execute(
        select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.approval_status != TaskApprovalStatus.ESTIMATED:
        raise HTTPException(status_code=400, detail=f"Task not in ESTIMATED status (current: {task.approval_status.value})")

    if not body.approved:
        task.approval_status = TaskApprovalStatus.REJECTED
        task.manager_feedback = body.feedback
        task.manager_approved_at = datetime.utcnow()
        task.manager_approved_by = user.id

        # Notify employee
        if task.assigned_to:
            db.add(TaskNotification(
                tenant_id=user.tenant_id,
                task_id=task.id,
                employee_id=task.employee_id,
                user_id=task.assigned_to,
                title=f"Estimation rejetée: {task.title}",
                message=body.feedback or "Veuillez soumettre une nouvelle estimation.",
            ))
    else:
        task.approval_status = TaskApprovalStatus.APPROVED
        task.manager_final_time = body.final_time if body.final_time else task.employee_estimated_time
        task.manager_final_price = body.final_price if body.final_price else task.employee_estimated_price
        task.manager_approved_at = datetime.utcnow()
        task.manager_approved_by = user.id
        task.manager_feedback = body.feedback
        task.status = "in_progress"

        # Notify employee
        if task.assigned_to:
            db.add(TaskNotification(
                tenant_id=user.tenant_id,
                task_id=task.id,
                employee_id=task.employee_id,
                user_id=task.assigned_to,
                title=f"Tâche approuvée: {task.title}",
                message=f"Temps: {task.manager_final_time}h, Valeur: {task.manager_final_price} DA",
            ))

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="task_approve" if body.approved else "task_reject",
        entity_type="hr_task", entity_id=task.id,
    ))
    await db.commit()

    return {"task_id": task.id, "approval_status": task.approval_status.value}


# ── Task Proof Upload ─────────────────────────────────────────────

@router.post("/tasks/{task_id}/proof")
async def upload_task_proof(
    task_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee uploads proof that task is completed."""
    import hashlib
    from app.models.core import Document
    from app.storage.service import get_storage_service

    result = await db.execute(
        select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned user can upload proof")

    if task.approval_status not in (TaskApprovalStatus.APPROVED, TaskApprovalStatus.IN_PROGRESS, TaskApprovalStatus.REJECTED):
        raise HTTPException(status_code=400, detail=f"Cannot upload proof in status {task.approval_status.value}")

    # Read and store file
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()
    storage = get_storage_service()
    storage_key = f"documents/{user.tenant_id}/proof_{task_id}_{file.filename}"
    await storage.upload(storage_key, content, file.content_type or "application/octet-stream")

    # Create document record
    doc = Document(
        tenant_id=user.tenant_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        sha256=sha256,
        storage_key=storage_key,
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()

    # Link proof to task
    task.proof_document_id = doc.id
    task.proof_uploaded_at = datetime.utcnow()
    task.approval_status = TaskApprovalStatus.PROOF_SUBMITTED
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    task.completed_by = user.id

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="task_proof_upload", entity_type="hr_task", entity_id=task.id,
    ))
    await db.commit()

    return {
        "task_id": task.id,
        "proof_document_id": doc.id,
        "approval_status": task.approval_status.value,
    }


# ── AI Proof Evaluation ───────────────────────────────────────────

@router.post("/tasks/{task_id}/ai-evaluate")
async def ai_evaluate_task_proof(
    task_id: str,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI evaluation of the proof submitted for a task."""
    result = await db.execute(
        select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.approval_status != TaskApprovalStatus.PROOF_SUBMITTED:
        raise HTTPException(status_code=400, detail=f"Task not in PROOF_SUBMITTED status")

    if not task.proof_document_id:
        raise HTTPException(status_code=400, detail="No proof document uploaded")

    # AI evaluation
    from app.services.proof_evaluator import evaluate_task_proof
    score, note = await evaluate_task_proof(task, db)

    task.ai_score = score
    task.ai_note = note
    task.ai_evaluated_at = datetime.utcnow()
    task.approval_status = TaskApprovalStatus.AI_EVALUATED

    # Notify manager
    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="task_ai_evaluate", entity_type="hr_task", entity_id=task.id,
    ))
    await db.commit()

    return {
        "task_id": task.id,
        "ai_score": task.ai_score,
        "ai_note": task.ai_note,
        "approval_status": task.approval_status.value,
    }


# ── Manager Validate AI Score ─────────────────────────────────────

@router.post("/tasks/{task_id}/validate")
async def validate_task_score(
    task_id: str,
    body: TaskValidateBody,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Manager validates (or rejects) the AI-generated score. On validation, the score feeds into bonus/malus."""
    result = await db.execute(
        select(HRTask).where(HRTask.id == task_id, HRTask.tenant_id == user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.approval_status != TaskApprovalStatus.AI_EVALUATED:
        raise HTTPException(status_code=400, detail=f"Task not in AI_EVALUATED status")

    task.manager_validated = body.validated
    task.manager_validated_at = datetime.utcnow()

    if body.validated:
        task.approval_status = TaskApprovalStatus.VALIDATED

        # Convert AI score to 1-5 rating for payroll impact
        if task.ai_score is not None:
            if task.ai_score >= 90:
                rating = 5
            elif task.ai_score >= 75:
                rating = 4
            elif task.ai_score >= 50:
                rating = 3
            elif task.ai_score >= 25:
                rating = 2
            else:
                rating = 1
            task.manager_rating = rating

            # Apply salary adjustment if employee exists
            if task.employee_id:
                emp_result = await db.execute(
                    select(Employee).where(Employee.id == task.employee_id, Employee.tenant_id == user.tenant_id)
                )
                employee = emp_result.scalar_one_or_none()
                if employee:
                    adjustment = apply_salary_adjustment(employee, task, rating)

        # Notify employee
        if task.assigned_to:
            db.add(TaskNotification(
                tenant_id=user.tenant_id,
                task_id=task.id,
                employee_id=task.employee_id,
                user_id=task.assigned_to,
                title=f"Score validé: {task.title}",
                message=f"Score AI: {task.ai_score}/100 — Note: {task.ai_note}",
            ))
    else:
        task.approval_status = TaskApprovalStatus.REJECTED
        # Notify employee to redo
        if task.assigned_to:
            db.add(TaskNotification(
                tenant_id=user.tenant_id,
                task_id=task.id,
                employee_id=task.employee_id,
                user_id=task.assigned_to,
                title=f"Preuve rejetée: {task.title}",
                message="Le manager a rejeté votre preuve. Veuillez soumettre une nouvelle preuve.",
            ))

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="task_validate" if body.validated else "task_reject_proof",
        entity_type="hr_task", entity_id=task.id,
    ))
    await db.commit()

    return {
        "task_id": task.id,
        "validated": task.manager_validated,
        "approval_status": task.approval_status.value,
        "manager_rating": task.manager_rating,
    }
