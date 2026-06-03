"""
GFI v7.0 — CcaFreeze: tracks CCA freezes due to unpaid capital calls (R-016).

When an associate has an outstanding unpaid capital call:
  1. CCA is frozen — no withdrawals
  2. Share transfers blocked
  3. DAF alerted

Freeze persists until the capital call is covered.
"""

from sqlalchemy import Column, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class CcaFreeze(GFIBase, Base):
    __tablename__ = "cca_freeze"

    # ── Which CCA is frozen ──────────────────────────────────────────────
    cca_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cca_account.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Freeze details ───────────────────────────────────────────────────
    freeze_date = Column(Date, nullable=False)
    reason = Column(String(40), nullable=False)  # CAPITAL_CALL_UNPAID
    description = Column(Text, nullable=True)

    # ── The unpaid capital call that triggered the freeze ─────────────────
    capital_call_amount = Column(Numeric(15, 2), nullable=True)
    capital_call_ref = Column(String(100), nullable=True)

    # ── Resolution ───────────────────────────────────────────────────────
    # ACTIVE, RESOLVED
    status = Column(String(20), nullable=False, server_default="'ACTIVE'")
    resolved_date = Column(Date, nullable=True)
    resolved_by_movement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cca_movement.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    cca_account = relationship("CcaAccount")

    def __repr__(self):
        return (
            f"<CcaFreeze {self.reason} {self.status} "
            f"on CCA {self.cca_account_id}>"
        )
