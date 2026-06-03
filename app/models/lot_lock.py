"""
GFI v7.0 — LotLock: pessimistic 15-minute lock on lots.

When a commercial agent selects a lot to present to a client, the lot
is locked for 900 seconds. During this time:
- Lot shows as VERROUILLE to all other agents
- Only the locking agent can proceed with reservation
- After TTL expires without reservation, lock auto-releases
- Failed reservation attempts are audit-logged

The lock is acquired atomically with the availability check in a single
transaction using SELECT ... FOR UPDATE SKIP LOCKED.

Uses GFIBase (company_id = the entity selling the lot).
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class LotLock(GFIBase, Base):
    __tablename__ = "lot_lock"

    lot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lot.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Who locked it ────────────────────────────────────────────────────
    locked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_name = Column(String(255), nullable=True)

    # ── Lock timing ──────────────────────────────────────────────────────
    locked_at = Column(
        DateTime(timezone=True), nullable=False
    )
    expires_at = Column(
        DateTime(timezone=True), nullable=False
    )
    ttl_seconds = Column(Integer, nullable=False, server_default="900")

    # ── Resolution ───────────────────────────────────────────────────────
    # ACTIVE, RESERVED (converted to reservation), EXPIRED, RELEASED
    status = Column(String(20), nullable=False, server_default="'ACTIVE'")
    released_at = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    lot = relationship("Lot")
    agent = relationship("AuthUser")

    def __repr__(self):
        return (
            f"<LotLock lot={self.lot_id} by={self.locked_by} "
            f"{self.status} expires={self.expires_at}>"
        )
