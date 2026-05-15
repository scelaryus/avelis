# GAP 1 + GAP 5 + GAP 7 — SCHEDULER — scheduler.py
"""APScheduler setup for periodic jobs (SPI daily, Clôture monthly)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import structlog

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="Africa/Algiers")


def register_jobs(sched: AsyncIOScheduler) -> None:
    """Register all scheduled jobs."""

    # SPI: every day at 01:00
    sched.add_job(
        _run_daily_spi,
        trigger=CronTrigger(hour=1, minute=0),
        id="daily_spi",
        replace_existing=True,
        name="Daily SPI Computation",
    )

    # Clôture mensuelle: 1st of each month at 02:00
    sched.add_job(
        _run_monthly_clotures,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="monthly_cloture",
        replace_existing=True,
        name="Monthly Clôture",
    )

    logger.info("scheduler_jobs_registered", jobs=["daily_spi", "monthly_cloture"])


async def _run_daily_spi():
    """Execute daily SPI computation for all tenants."""
    from app.services.spi_scheduler import run_daily_spi_computation
    from app.database import AsyncSessionLocal

    logger.info("scheduler_spi_start")
    try:
        async with AsyncSessionLocal() as db:
            await run_daily_spi_computation(db)
            await db.commit()
        logger.info("scheduler_spi_done")
    except Exception as exc:
        logger.error("scheduler_spi_error", error=str(exc))


async def _run_monthly_clotures():
    """Execute monthly clôture for all active projects."""
    from app.services.cloture_service import run_monthly_clotures_all
    from app.database import AsyncSessionLocal

    logger.info("scheduler_cloture_start")
    try:
        async with AsyncSessionLocal() as db:
            await run_monthly_clotures_all(db)
            await db.commit()
        logger.info("scheduler_cloture_done")
    except Exception as exc:
        logger.error("scheduler_cloture_error", error=str(exc))
