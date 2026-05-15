# GAP 7 — SPI AUTOMATISATION 24h — spi_scheduler.py
"""Daily SPI computation + threshold checks (alerts, freeze, rupture).

Called by APScheduler every day at 01:00 (Africa/Algiers).

Business rules:
  - SPI < 50  → HR alert
  - SPI < 50 for 2 consecutive months → auto-termination trigger ("rupture")
  - 5 consecutive inactive days → salary freeze + HR alert
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Tenant
from app.models.hr import Employee, EmploymentStatus
from app.models.spi import SPIScore, SPIScorePeriod

logger = structlog.get_logger(__name__)

# Thresholds
SPI_ALERT_THRESHOLD = Decimal("50")
SPI_RUPTURE_MONTHS = 2
INACTIVE_DAYS_FREEZE = 5


async def run_daily_spi_computation(db: AsyncSession) -> dict:
    """Compute SPI for all tenants, then run threshold checks.

    Returns summary dict with counts.
    """
    from app.services.spi_engine import compute_spi_batch

    today = date.today()
    tenants_result = await db.execute(select(Tenant))
    tenants = tenants_result.scalars().all()

    total_computed = 0
    total_alerts = 0
    total_freezes = 0
    total_ruptures = 0

    for tenant in tenants:
        scores = await compute_spi_batch(
            db,
            tenant_id=tenant.id,
            target_date=today,
            period_type=SPIScorePeriod.DAILY,
        )
        total_computed += len(scores)
        await db.flush()

        # Threshold checks for this tenant
        stats = await check_spi_thresholds(db, tenant.id, today)
        total_alerts += stats["alerts"]
        total_freezes += stats["freezes"]
        total_ruptures += stats["ruptures"]

    await db.flush()

    summary = {
        "date": str(today),
        "tenants": len(tenants),
        "scores_computed": total_computed,
        "alerts": total_alerts,
        "freezes": total_freezes,
        "ruptures": total_ruptures,
    }
    logger.info("daily_spi_complete", **summary)
    return summary


async def check_spi_thresholds(
    db: AsyncSession,
    tenant_id: str,
    ref_date: date,
) -> dict:
    """Check SPI thresholds for all active employees in a tenant.

    Actions:
      1. SPI < 50 today → log HR alert
      2. SPI < 50 for last `SPI_RUPTURE_MONTHS` months → log rupture trigger
      3. No SPI score for last `INACTIVE_DAYS_FREEZE` days → log salary freeze
    """
    alerts = 0
    freezes = 0
    ruptures = 0

    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()

    for emp in employees:
        # ── 1. Check today's SPI ────────────────────────────────────────
        score_result = await db.execute(
            select(SPIScore).where(
                SPIScore.employee_id == emp.id,
                SPIScore.period_date == ref_date,
            )
        )
        today_score = score_result.scalar_one_or_none()

        if today_score and Decimal(str(today_score.spi_total)) < SPI_ALERT_THRESHOLD:
            alerts += 1
            logger.warning(
                "spi_alert_low_score",
                employee_id=emp.id,
                score=float(today_score.spi_total),
                threshold=float(SPI_ALERT_THRESHOLD),
            )

        # ── 2. Check 2-month consecutive low SPI → rupture ────────────
        low_months = 0
        for months_back in range(1, SPI_RUPTURE_MONTHS + 1):
            # First day of N months ago
            month_date = (ref_date.replace(day=1) - timedelta(days=1))
            for _ in range(months_back - 1):
                month_date = (month_date.replace(day=1) - timedelta(days=1))
            month_start = month_date.replace(day=1)

            monthly_result = await db.execute(
                select(func.avg(SPIScore.spi_total)).where(
                    SPIScore.employee_id == emp.id,
                    SPIScore.period_date >= month_start,
                    SPIScore.period_date <= month_date,
                )
            )
            avg_score = monthly_result.scalar()
            if avg_score is not None and Decimal(str(avg_score)) < SPI_ALERT_THRESHOLD:
                low_months += 1

        if low_months >= SPI_RUPTURE_MONTHS:
            ruptures += 1
            logger.critical(
                "spi_rupture_trigger",
                employee_id=emp.id,
                consecutive_low_months=low_months,
            )

        # ── 3. Check inactivity → salary freeze ───────────────────────
        cutoff = ref_date - timedelta(days=INACTIVE_DAYS_FREEZE)
        recent_result = await db.execute(
            select(func.count(SPIScore.id)).where(
                SPIScore.employee_id == emp.id,
                SPIScore.period_date >= cutoff,
                SPIScore.period_date <= ref_date,
            )
        )
        recent_count = recent_result.scalar() or 0

        if recent_count == 0:
            freezes += 1
            logger.warning(
                "spi_salary_freeze",
                employee_id=emp.id,
                inactive_days=INACTIVE_DAYS_FREEZE,
            )

    return {"alerts": alerts, "freezes": freezes, "ruptures": ruptures}
