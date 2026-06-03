"""
GFI v7.0 — ClosedPeriod: permanent period lock registry.

Once a period is closed, it is PERMANENTLY locked. A database trigger
checks this table before allowing any INSERT/UPDATE/DELETE on financial
records dated within a closed period.

This table itself is append-only (no UPDATE, no DELETE allowed).
company_id scopes the lock per entity.
"""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class ClosedPeriod(Base):
    __tablename__ = "closed_period"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # ── Seal ─────────────────────────────────────────────────────────────
    sha256_hash = Column(String(64), nullable=False)
    closing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("treasury_closing.id", ondelete="RESTRICT"),
        nullable=False,
    )

    locked_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self):
        return (
            f"<ClosedPeriod {self.period_year}-{self.period_month:02d} "
            f"@ {self.company_id}>"
        )
