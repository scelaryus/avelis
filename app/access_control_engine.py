"""
GFI v7.0 — Access Control Engine.

Badge lifecycle, middleware communication, event processing.
Offline resilience with queued commands and exponential backoff.

Core API:
  create_badge(employee_id, zones) -> BadgeRecord + queue CREATE to middleware
  deactivate_badge(badge_number, reason) -> immediate deactivation + queue DELETE
  deactivate_all_for_employee(employee_id) -> offboarding full revocation
  process_badge_event(event_data) -> idempotent event processing
  check_expired_badges(today) -> CDD expired badge cleanup
  process_command_queue(middleware_id) -> retry pending commands
  detect_anomalies(events) -> fraud / security alerts
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class BadgeDeactivationFailed(Exception):
    """Badge could not be deactivated on all controllers."""
    pass


def create_badge(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    employee_name: str,
    access_zones: list[dict],
    valid_from: date,
    valid_until: date | None = None,
    created_by: UUID | None = None,
) -> object:
    """Create badge record and queue CREATE command to all site middlewares."""
    from app.models.access_control import BadgeRecord, MiddlewareCommand, SiteMiddleware

    badge_number = f"RFID-{uuid4().hex[:12].upper()}"

    record = BadgeRecord(
        company_id=company_id,
        employee_id=employee_id,
        badge_number=badge_number,
        employee_name=employee_name,
        access_zones=access_zones,
        valid_from=valid_from,
        valid_until=valid_until,
        status="PENDING_SYNC",
        created_by=created_by,
    )
    session.add(record)
    session.flush()

    # Update employee badge number
    from app.models.hr import Employee
    emp = session.get(Employee, employee_id)
    if emp:
        emp.badge_rfid_number = badge_number

    # Queue CREATE commands to relevant middlewares
    middlewares = (
        session.query(SiteMiddleware)
        .filter(
            SiteMiddleware.company_id == company_id,
            SiteMiddleware.is_deleted.is_(False),
        )
        .all()
    )

    for mw in middlewares:
        cmd = MiddlewareCommand(
            company_id=company_id,
            middleware_id=mw.id,
            command_type="CREATE_BADGE",
            payload={
                "badge_number": badge_number,
                "employee_name": employee_name,
                "access_zones": access_zones,
                "valid_from": str(valid_from),
                "valid_until": str(valid_until) if valid_until else None,
            },
            status="QUEUED",
            next_retry_at=datetime.now(timezone.utc),
            created_by=created_by,
        )
        session.add(cmd)

    session.flush()
    return record


def deactivate_badge(
    session: Session,
    *,
    badge_number: str,
    reason: str,
    company_id: UUID | None = None,
) -> object:
    """Immediately deactivate a badge and queue DELETE to all controllers."""
    from app.models.access_control import BadgeRecord, MiddlewareCommand, SiteMiddleware

    record = (
        session.query(BadgeRecord)
        .filter(BadgeRecord.badge_number == badge_number,
                BadgeRecord.is_deleted.is_(False))
        .first()
    )
    if record is None:
        raise ValueError(f"Badge {badge_number} not found.")

    now = datetime.now(timezone.utc)
    record.status = "DEACTIVATED"
    record.deactivated_at = now
    record.deactivation_reason = reason
    cid = company_id or record.company_id

    # Queue DELETE to ALL middlewares
    middlewares = (
        session.query(SiteMiddleware)
        .filter(SiteMiddleware.company_id == cid,
                SiteMiddleware.is_deleted.is_(False))
        .all()
    )

    for mw in middlewares:
        cmd = MiddlewareCommand(
            company_id=cid,
            middleware_id=mw.id,
            command_type="DELETE_BADGE",
            payload={"badge_number": badge_number},
            priority=1,  # highest priority for deactivation
            status="QUEUED",
            next_retry_at=now,
        )
        session.add(cmd)

    session.flush()
    return record


def deactivate_all_for_employee(
    session: Session,
    employee_id: UUID,
    reason: str = "OFFBOARDING",
) -> list:
    """Offboarding: deactivate ALL badges across ALL sites. No exception."""
    from app.models.access_control import BadgeRecord

    active_badges = (
        session.query(BadgeRecord)
        .filter(
            BadgeRecord.employee_id == employee_id,
            BadgeRecord.status.in_(["ACTIVE", "PENDING_SYNC"]),
            BadgeRecord.is_deleted.is_(False),
        )
        .all()
    )

    results = []
    for badge in active_badges:
        r = deactivate_badge(session, badge_number=badge.badge_number, reason=reason)
        results.append(r)

    return results


def process_badge_event(
    session: Session,
    *,
    company_id: UUID,
    badge_number: str,
    controller_id: str,
    door_id: int,
    direction: str,
    event_timestamp: datetime,
    result: str,
    middleware_id: UUID | None = None,
) -> object | None:
    """
    Idempotent event processing. Dedup via SHA-256 hash.
    Returns the event if new, None if duplicate.
    """
    from app.models.access_control import BadgeEvent, BadgeRecord

    # Compute dedup hash
    hash_input = f"{badge_number}:{controller_id}:{door_id}:{event_timestamp.isoformat()}"
    event_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # Check for duplicate
    existing = (
        session.query(BadgeEvent.id)
        .filter(BadgeEvent.event_hash == event_hash)
        .first()
    )
    if existing:
        return None  # idempotent: already processed

    # Look up employee
    badge = (
        session.query(BadgeRecord)
        .filter(BadgeRecord.badge_number == badge_number,
                BadgeRecord.is_deleted.is_(False))
        .first()
    )
    employee_id = badge.employee_id if badge else None

    event = BadgeEvent(
        company_id=company_id,
        badge_number=badge_number,
        controller_id=controller_id,
        door_id=door_id,
        direction=direction,
        event_timestamp=event_timestamp,
        result=result,
        employee_id=employee_id,
        event_hash=event_hash,
        middleware_id=middleware_id,
    )
    session.add(event)
    session.flush()
    return event


def check_expired_badges(
    session: Session,
    today: date | None = None,
) -> list:
    """CDD requalification rule: deactivate badges past valid_until."""
    from app.models.access_control import BadgeRecord

    if today is None:
        today = date.today()

    expired = (
        session.query(BadgeRecord)
        .filter(
            BadgeRecord.status == "ACTIVE",
            BadgeRecord.valid_until.isnot(None),
            BadgeRecord.valid_until < today,
            BadgeRecord.is_deleted.is_(False),
        )
        .all()
    )

    deactivated = []
    for badge in expired:
        deactivate_badge(session, badge_number=badge.badge_number,
                         reason="CDD_EXPIRED")
        deactivated.append(badge.badge_number)

    return deactivated


def detect_anomalies(
    session: Session,
    company_id: UUID,
    since_hours: int = 24,
) -> list[dict]:
    """Detect security anomalies in recent badge events."""
    from app.models.access_control import BadgeEvent
    from sqlalchemy import func as sqfunc

    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    alerts = []

    # Repeated denials from same badge
    denials = (
        session.query(
            BadgeEvent.badge_number,
            sqfunc.count(BadgeEvent.id).label("cnt"),
        )
        .filter(
            BadgeEvent.company_id == company_id,
            BadgeEvent.result == "DENIED",
            BadgeEvent.event_timestamp >= since,
            BadgeEvent.is_deleted.is_(False),
        )
        .group_by(BadgeEvent.badge_number)
        .having(sqfunc.count(BadgeEvent.id) >= 3)
        .all()
    )

    for badge_num, count in denials:
        alerts.append({
            "type": "DENIED_REPEATED",
            "badge_number": badge_num,
            "count": count,
            "message": f"Badge {badge_num}: {count} acces refuses en {since_hours}h",
        })

    return alerts
