"""
GFI v7.0 — EDD (Etat Descriptif Detaille) Inventory Engine.

The EDD is the single source of truth for every lot across all projects.

Core operations:
  lock_lot()      — atomic availability check + 15-min pessimistic lock
  reserve_lot()   — convert lock to reservation (within TTL)
  release_lock()  — manual or auto-release expired locks
  transition()    — lot state machine transitions
  get_available() — list lots available for a project (CRM feed)

Race condition prevention (RES-001, EX-ADV-001):
  lock_lot() uses SELECT ... FOR UPDATE to atomically check status AND
  apply the lock in a single transaction. Two simultaneous agents ->
  only the first succeeds; the second gets HTTP 409 CONFLICT.

Lot state machine:
  DISPONIBLE -> VERROUILLE (lock_lot)
  VERROUILLE -> DISPONIBLE (lock expired / released)
  VERROUILLE -> RESERVE (reserve_lot within TTL)
  RESERVE -> PROMIS (contract signed)
  PROMIS -> VENDU (acte notarie)
  VENDU -> LIVRE (delivery)
  DISPONIBLE -> PRELEVEMENT (associate withdrawal)
  RESERVE -> ANNULE (cancellation)
  PROMIS -> ANNULE (cancellation -> lot returns to DISPONIBLE)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Lock TTL in seconds
LOCK_TTL_SECONDS = 900  # 15 minutes


class LotNotAvailable(Exception):
    """Raised when a lot is not in DISPONIBLE status."""

    pass


class LotAlreadyLocked(Exception):
    """Raised when another agent already holds the lock (HTTP 409)."""

    def __init__(
        self, message: str, locked_by: str, locked_at: datetime, expires_at: datetime
    ):
        super().__init__(message)
        self.locked_by = locked_by
        self.locked_at = locked_at
        self.expires_at = expires_at


class LotLockExpired(Exception):
    """Raised when attempting to reserve after lock TTL expired."""

    pass


class InvalidTransition(Exception):
    """Raised when a lot state transition is not allowed."""

    pass


# ── Valid state transitions ──────────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, set[str]] = {
    "DISPONIBLE": {"VERROUILLE", "PRELEVEMENT", "BLOQUE"},
    "VERROUILLE": {"DISPONIBLE", "RESERVE"},
    "RESERVE": {"PROMIS", "ANNULE", "DISPONIBLE"},
    "PROMIS": {"VENDU", "ANNULE"},
    "VENDU": {"LIVRE"},
    "ANNULE": {"DISPONIBLE"},
    "PRELEVEMENT": set(),
    "LIVRE": set(),
    "BLOQUE": {"DISPONIBLE"},
}


def _expire_stale_locks(session: Session, lot_id: UUID) -> None:
    """Auto-release any expired locks on a lot."""
    from app.models.lot_lock import LotLock
    from app.models.lot import Lot

    now = datetime.now(timezone.utc)

    expired_locks = (
        session.query(LotLock)
        .filter(
            LotLock.lot_id == lot_id,
            LotLock.status == "ACTIVE",
            LotLock.expires_at <= now,
            LotLock.is_deleted.is_(False),
        )
        .all()
    )

    for lock in expired_locks:
        lock.status = "EXPIRED"
        lock.released_at = now

    if expired_locks:
        # Reset lot to DISPONIBLE if it was VERROUILLE
        lot = session.get(Lot, lot_id)
        if lot and lot.status == "VERROUILLE":
            lot.status = "DISPONIBLE"

    session.flush()


def lock_lot(
    session: Session,
    *,
    lot_id: UUID,
    agent_id: UUID,
    agent_name: str | None = None,
    company_id: UUID | None = None,
) -> object:
    """
    Atomically check availability and lock a lot for 15 minutes.

    Uses SELECT ... FOR UPDATE to prevent race conditions (RES-001).
    If the lot is already locked by another agent -> raises LotAlreadyLocked.

    Returns the LotLock object.
    """
    from app.models.lot import Lot
    from app.models.lot_lock import LotLock

    # Auto-expire stale locks first
    _expire_stale_locks(session, lot_id)

    # Atomic: SELECT FOR UPDATE locks the row for this transaction
    lot = (
        session.query(Lot)
        .filter(Lot.id == lot_id, Lot.is_deleted.is_(False))
        .with_for_update(nowait=True)
        .first()
    )

    if lot is None:
        raise LotNotAvailable(f"Lot {lot_id} not found.")

    if lot.status == "VERROUILLE":
        # Check if there's an active lock by another agent
        active_lock = (
            session.query(LotLock)
            .filter(
                LotLock.lot_id == lot_id,
                LotLock.status == "ACTIVE",
                LotLock.is_deleted.is_(False),
            )
            .first()
        )
        if active_lock and active_lock.locked_by != agent_id:
            now = datetime.now(timezone.utc)
            remaining = (active_lock.expires_at - now).total_seconds()
            remaining_min = max(0, int(remaining / 60))
            raise LotAlreadyLocked(
                f"Lot {lot.lot_ref} verrouille par {active_lock.agent_name or active_lock.locked_by} "
                f"depuis {active_lock.locked_at.strftime('%H:%M')}. "
                f"Liberation dans {remaining_min} minutes.",
                locked_by=active_lock.agent_name or str(active_lock.locked_by),
                locked_at=active_lock.locked_at,
                expires_at=active_lock.expires_at,
            )
        # Same agent re-locking — extend (idempotent)
        if active_lock and active_lock.locked_by == agent_id:
            now = datetime.now(timezone.utc)
            active_lock.expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
            session.flush()
            return active_lock

    if lot.status != "DISPONIBLE":
        raise LotNotAvailable(
            f"Lot {lot.lot_ref} is {lot.status}, not DISPONIBLE."
        )

    # Apply lock
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=LOCK_TTL_SECONDS)

    lot.status = "VERROUILLE"

    lock = LotLock(
        company_id=company_id or lot.company_id,
        lot_id=lot_id,
        locked_by=agent_id,
        agent_name=agent_name,
        locked_at=now,
        expires_at=expires,
        ttl_seconds=LOCK_TTL_SECONDS,
        status="ACTIVE",
    )
    session.add(lock)
    session.flush()

    return lock


def reserve_lot(
    session: Session,
    *,
    lot_id: UUID,
    agent_id: UUID,
    client_name: str,
    client_id: UUID | None = None,
) -> object:
    """
    Convert a lock into a reservation. Must be called within the TTL
    by the agent who holds the lock.
    """
    from app.models.lot import Lot
    from app.models.lot_lock import LotLock

    lot = session.get(Lot, lot_id)
    if lot is None:
        raise LotNotAvailable(f"Lot {lot_id} not found.")

    if lot.status != "VERROUILLE":
        raise InvalidTransition(
            f"Lot {lot.lot_ref} is {lot.status}, not VERROUILLE."
        )

    # Find the active lock
    active_lock = (
        session.query(LotLock)
        .filter(
            LotLock.lot_id == lot_id,
            LotLock.status == "ACTIVE",
            LotLock.locked_by == agent_id,
            LotLock.is_deleted.is_(False),
        )
        .first()
    )

    if active_lock is None:
        raise LotNotAvailable(
            f"No active lock found for lot {lot.lot_ref} by this agent."
        )

    now = datetime.now(timezone.utc)
    if now > active_lock.expires_at:
        # Lock expired — release and fail
        active_lock.status = "EXPIRED"
        active_lock.released_at = now
        lot.status = "DISPONIBLE"
        session.flush()
        raise LotLockExpired(
            f"Lock on lot {lot.lot_ref} expired at "
            f"{active_lock.expires_at.strftime('%H:%M:%S')}. "
            f"Lot returned to DISPONIBLE."
        )

    # Convert lock to reservation
    active_lock.status = "RESERVED"
    active_lock.released_at = now

    lot.status = "RESERVE"
    lot.client_name = client_name
    lot.client_id = client_id

    session.flush()
    return lot


def release_lock(
    session: Session,
    *,
    lot_id: UUID,
    agent_id: UUID | None = None,
) -> None:
    """Manually release a lock (or release all expired locks on a lot)."""
    from app.models.lot import Lot
    from app.models.lot_lock import LotLock

    now = datetime.now(timezone.utc)

    query = session.query(LotLock).filter(
        LotLock.lot_id == lot_id,
        LotLock.status == "ACTIVE",
        LotLock.is_deleted.is_(False),
    )
    if agent_id:
        query = query.filter(LotLock.locked_by == agent_id)

    locks = query.all()
    for lock in locks:
        lock.status = "RELEASED"
        lock.released_at = now

    lot = session.get(Lot, lot_id)
    if lot and lot.status == "VERROUILLE":
        lot.status = "DISPONIBLE"

    session.flush()


def transition_lot(
    session: Session,
    *,
    lot_id: UUID,
    new_status: str,
) -> object:
    """
    Transition a lot to a new status following the state machine.
    Raises InvalidTransition if the transition is not allowed.
    """
    from app.models.lot import Lot

    lot = session.get(Lot, lot_id)
    if lot is None:
        raise LotNotAvailable(f"Lot {lot_id} not found.")

    allowed = VALID_TRANSITIONS.get(lot.status, set())
    if new_status not in allowed:
        raise InvalidTransition(
            f"Transition {lot.status} -> {new_status} not allowed for "
            f"lot {lot.lot_ref}. Allowed: {sorted(allowed)}"
        )

    # Special handling for ANNULE -> return to DISPONIBLE
    if new_status == "ANNULE":
        lot.status = "ANNULE"
        lot.client_name = None
        lot.client_id = None
    else:
        lot.status = new_status

    session.flush()
    return lot


def get_available_lots(
    session: Session,
    project_id: UUID,
    *,
    typology: str | None = None,
) -> list:
    """
    List all DISPONIBLE lots for a project (CRM feed).
    Only returns lots where RF1 price is set.
    Auto-expires stale locks first.
    """
    from app.models.lot import Lot

    # Auto-expire stale locks across the project
    _expire_project_locks(session, project_id)

    query = session.query(Lot).filter(
        Lot.project_id == project_id,
        Lot.status == "DISPONIBLE",
        Lot.rf1_price.isnot(None),
        Lot.is_deleted.is_(False),
    )
    if typology:
        query = query.filter(Lot.typology == typology)

    return query.order_by(Lot.lot_ref).all()


def _expire_project_locks(session: Session, project_id: UUID) -> None:
    """Batch-expire all stale locks across a project."""
    from app.models.lot import Lot
    from app.models.lot_lock import LotLock

    now = datetime.now(timezone.utc)

    expired = (
        session.query(LotLock)
        .join(Lot, LotLock.lot_id == Lot.id)
        .filter(
            Lot.project_id == project_id,
            LotLock.status == "ACTIVE",
            LotLock.expires_at <= now,
            LotLock.is_deleted.is_(False),
        )
        .all()
    )

    lot_ids = set()
    for lock in expired:
        lock.status = "EXPIRED"
        lock.released_at = now
        lot_ids.add(lock.lot_id)

    if lot_ids:
        (
            session.query(Lot)
            .filter(Lot.id.in_(lot_ids), Lot.status == "VERROUILLE")
            .update({"status": "DISPONIBLE"}, synchronize_session="fetch")
        )

    session.flush()


def set_lot_pricing(
    session: Session,
    *,
    lot_id: UUID,
    rf1_price: Decimal,
    rf2_price: Decimal | None = None,
) -> object:
    """Set or update lot pricing. Recomputes real_price = RF1 + RF2."""
    from app.models.lot import Lot

    lot = session.get(Lot, lot_id)
    if lot is None:
        raise LotNotAvailable(f"Lot {lot_id} not found.")

    lot.rf1_price = Decimal(str(rf1_price))
    if rf2_price is not None:
        lot.rf2_price = Decimal(str(rf2_price))
        lot.real_price = lot.rf1_price + lot.rf2_price
    else:
        lot.real_price = lot.rf1_price

    session.flush()
    return lot


def get_lot_summary(
    session: Session,
    project_id: UUID,
) -> dict:
    """Get inventory summary for a project: counts by status and typology."""
    from app.models.lot import Lot
    from sqlalchemy import func as sqfunc

    rows = (
        session.query(
            Lot.status,
            Lot.typology,
            sqfunc.count(Lot.id).label("count"),
        )
        .filter(
            Lot.project_id == project_id,
            Lot.is_deleted.is_(False),
        )
        .group_by(Lot.status, Lot.typology)
        .all()
    )

    by_status: dict[str, int] = {}
    by_typology: dict[str, int] = {}
    for status, typology, count in rows:
        by_status[status] = by_status.get(status, 0) + count
        by_typology[typology] = by_typology.get(typology, 0) + count

    return {
        "project_id": str(project_id),
        "total": sum(by_status.values()),
        "by_status": by_status,
        "by_typology": by_typology,
    }
