"""
GFI v7.0 — BaremeTimbre: stamp duty schedule (parameterizable by DAF).

The cap/rate for stamp duty changes when the loi de finances is updated.
This table stores the schedule indexed by effective date.
The CFF engine looks up the schedule in effect at the invoice date.
If no schedule exists for the date -> BLOCK, generate FC-011.

System reference data (no company_id — applies to all entities).
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class BaremeTimbre(Base):
    __tablename__ = "bareme_timbre"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Effective period ─────────────────────────────────────────────────
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True)  # NULL = still in effect

    # ── Stamp duty parameters ────────────────────────────────────────────
    # Invoices with TTC <= exemption_threshold -> 0 stamp duty
    exemption_threshold = Column(
        Numeric(15, 2), nullable=False, server_default="20000"
    )
    # Rate applied to TTC when above threshold
    rate_percent = Column(
        Numeric(5, 2), nullable=False, server_default="2.50"
    )
    # Regulatory cap (plafonné). NULL = no cap.
    cap_amount = Column(Numeric(15, 2), nullable=True)

    # ── Reference ────────────────────────────────────────────────────────
    loi_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<BaremeTimbre from={self.effective_from} rate={self.rate_percent}%>"
