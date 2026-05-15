"""GAP 7 — Integration tests for SPI scheduler service."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.core import Tenant, User
from app.models.hr import Employee, EmploymentStatus, HRTask
from app.models.spi import SPIScore, SPIScorePeriod
from app.services.spi_engine import compute_spi_for_employee
from app.services.task_planner import apply_salary_adjustment
from app.api.spi import spi_dashboard


async def _setup_spi_tenant(db, tenant_id):
    """Create tenant + active employee."""
    tenant = Tenant(
        id=tenant_id, name="TST", code="TST", description="Test", settings={}
    )
    db.add(tenant)
    await db.flush()

    emp = Employee(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_number="E001",
        first_name="Test",
        last_name="Worker",
        email="test@test.com",
        status=EmploymentStatus.ACTIVE,
        base_salary=Decimal("50000"),
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.mark.asyncio
async def test_check_thresholds_no_scores(db, tenant_id):
    """Employee with no scores for 5+ days → salary freeze alert."""
    from app.services.spi_scheduler import check_spi_thresholds

    emp = await _setup_spi_tenant(db, tenant_id)
    today = date.today()

    stats = await check_spi_thresholds(db, tenant_id, today)
    # No scores at all for last 5 days → freeze
    assert stats["freezes"] >= 1
    assert stats["alerts"] == 0  # no score today → no low-score alert


@pytest.mark.asyncio
async def test_check_thresholds_low_score_alert(db, tenant_id):
    """Employee with SPI < 50 → alert."""
    from app.services.spi_scheduler import check_spi_thresholds

    emp = await _setup_spi_tenant(db, tenant_id)
    today = date.today()

    # Add a low score for today
    score = SPIScore(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_id=emp.id,
        period_type=SPIScorePeriod.DAILY,
        period_date=today,
        score_planification=Decimal("10"),
        score_qualite=Decimal("10"),
        score_comportement=Decimal("10"),
        score_performance=Decimal("10"),
        spi_total=Decimal("40"),
    )
    db.add(score)
    await db.flush()

    stats = await check_spi_thresholds(db, tenant_id, today)
    assert stats["alerts"] >= 1


@pytest.mark.asyncio
async def test_check_thresholds_good_score_no_alert(db, tenant_id):
    """Employee with SPI > 50 → no alert."""
    from app.services.spi_scheduler import check_spi_thresholds

    emp = await _setup_spi_tenant(db, tenant_id)
    today = date.today()

    # Add scores for today and recent days (no freeze)
    for i in range(6):
        d = today - timedelta(days=i)
        score = SPIScore(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_id=emp.id,
            period_type=SPIScorePeriod.DAILY,
            period_date=d,
            score_planification=Decimal("20"),
            score_qualite=Decimal("20"),
            score_comportement=Decimal("20"),
            score_performance=Decimal("20"),
            spi_total=Decimal("80"),
        )
        db.add(score)

    await db.flush()

    stats = await check_spi_thresholds(db, tenant_id, today)
    assert stats["alerts"] == 0
    assert stats["freezes"] == 0


@pytest.mark.asyncio
async def test_rbac_check_permission():
    """RBAC permission checks."""
    from app.services.rbac import check_permission

    # SUPER_ADMIN has wildcard
    assert check_permission("SUPER_ADMIN", "anything:write") is True
    assert check_permission("admin", "anything:write") is True  # alias

    # DAF can do finance
    assert check_permission("DAF", "finance:read") is True
    assert check_permission("DAF", "bim:import") is False

    # BIM can import
    assert check_permission("BIM", "bim:import") is True
    assert check_permission("BIM", "finance:write") is False

    # VIEWER has *:read
    assert check_permission("VIEWER", "finance:read") is True
    assert check_permission("VIEWER", "finance:write") is False

    # EMPLOYE has limited
    assert check_permission("EMPLOYE", "spi:own") is True
    assert check_permission("EMPLOYE", "finance:read") is False


@pytest.mark.asyncio
async def test_task_rating_adjustment_does_not_mutate_employee_base_salary(db, tenant_id):
    emp = await _setup_spi_tenant(db, tenant_id)
    task = HRTask(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_id=emp.id,
        task_type="hr",
        title="Rated task",
        description="Test task",
        plan_date=date.today(),
        status="completed",
    )
    db.add(task)
    await db.flush()

    before_salary = Decimal(str(emp.base_salary))
    adjustment = apply_salary_adjustment(emp, task, 1)

    assert adjustment < 0
    assert Decimal(str(emp.base_salary)) == before_salary
    assert task.salary_adjustment_applied is True


@pytest.mark.asyncio
async def test_compute_spi_without_assigned_tasks_has_no_malus(db, tenant_id):
    emp = await _setup_spi_tenant(db, tenant_id)

    score = await compute_spi_for_employee(db, emp, date.today())

    assert score.tasks_planned == 0
    assert score.jours_inactifs == 0
    assert Decimal(str(score.malus_amount or 0)) == Decimal("0")
    assert Decimal(str(score.malus_pct or 0)) == Decimal("0")


@pytest.mark.asyncio
async def test_closed_task_counts_as_completed_for_spi(db, tenant_id):
    emp = await _setup_spi_tenant(db, tenant_id)
    today = date.today()

    task = HRTask(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_id=emp.id,
        task_type="hr",
        title="Closed task",
        description="Should count as completed",
        plan_date=today,
        due_date=today,
        status="closed",
        manager_rating=4,
        completed_at=datetime.combine(today, datetime.min.time()),
    )
    db.add(task)
    await db.flush()

    score = await compute_spi_for_employee(db, emp, today)

    assert score.tasks_planned == 1
    assert score.tasks_completed == 1
    assert score.score_planification > 0
    assert score.score_performance > 0


@pytest.mark.asyncio
async def test_spi_dashboard_filters_top_and_low_performers_by_threshold(db, tenant_id):
    tenant = Tenant(
        id=tenant_id, name="TST", code="TST", description="Test", settings={}
    )
    db.add(tenant)
    await db.flush()

    manager = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email="manager@test.com",
        hashed_password="hash",
        full_name="Manager",
        role="SUPER_ADMIN",
        is_active=True,
    )
    db.add(manager)

    emp_good = Employee(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_number="E001",
        first_name="Good",
        last_name="Performer",
        status=EmploymentStatus.ACTIVE,
        base_salary=Decimal("50000"),
    )
    emp_low = Employee(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        employee_number="E002",
        first_name="Low",
        last_name="Performer",
        status=EmploymentStatus.ACTIVE,
        base_salary=Decimal("50000"),
    )
    db.add_all([emp_good, emp_low])
    await db.flush()

    today = date.today()
    db.add_all([
        SPIScore(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_id=emp_good.id,
            period_type=SPIScorePeriod.DAILY,
            period_date=today,
            spi_total=Decimal("95"),
            tasks_planned=2,
            tasks_completed=2,
        ),
        SPIScore(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_id=emp_low.id,
            period_type=SPIScorePeriod.DAILY,
            period_date=today,
            spi_total=Decimal("27.5"),
            tasks_planned=2,
            tasks_completed=0,
            malus_amount=Decimal("15000"),
            malus_pct=Decimal("30"),
        ),
    ])
    await db.flush()

    dashboard = await spi_dashboard(target_date=today, user=manager, db=db)

    assert [item["employee_name"] for item in dashboard["top_performers"]] == ["Good Performer"]
    assert [item["employee_name"] for item in dashboard["low_performers"]] == ["Low Performer"]
