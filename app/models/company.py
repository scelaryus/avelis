"""
GFI v7.0 — Company (legal entity) model.

The company table is the root of the multi-tenant isolation.
It does NOT use company_id itself (it IS the company), so it inherits
from Base directly and carries its own system columns.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Company(Base):
    __tablename__ = "company"

    # ── PK ───────────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Identity ─────────────────────────────────────────────────────────
    code = Column(String(20), unique=True, nullable=False)
    legal_name = Column(String(255), nullable=False)
    legal_form = Column(String(10), nullable=False)  # ETS, SARL, EURL, SCI

    # ── Tax / registry ───────────────────────────────────────────────────
    nif = Column(String(30), nullable=True)   # NULL → triggers FC-002
    rc = Column(String(50), nullable=True)    # Commerce registry

    # ── Status & activity ────────────────────────────────────────────────
    status = Column(String(30), nullable=False)           # ACTIF, À FERMER, etc.
    activity = Column(String(255), nullable=True)

    # ── Fiscal ───────────────────────────────────────────────────────────
    fiscal_regime = Column(String(20), nullable=True)     # REEL or SIMPLIFIE
    ibs_rate = Column(Numeric(5, 2), nullable=True)       # 19 or 26; NULL → FC-005
    tap_rate = Column(Numeric(5, 2), nullable=True)       # 1 or 2;  NULL → FC-005

    # ── CNAS ─────────────────────────────────────────────────────────────
    cnas_regime = Column(String(10), nullable=True)       # GENERAL or BTPH
    # Derived rates stored for clarity — BTPH includes CACOBATPH surcharge.
    cnas_employee_rate = Column(Numeric(6, 3), nullable=True)  # 9.000 or 9.375
    cnas_employer_rate = Column(Numeric(6, 3), nullable=True)  # 25.000 or 25.375

    # ── System columns (company is self-referential root) ────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")
    version = Column(Integer, nullable=False, server_default="1")

    # ── Relationships ────────────────────────────────────────────────────
    associates = relationship(
        "Associate", back_populates="company", lazy="select"
    )

    def __repr__(self):
        return f"<Company {self.code} — {self.legal_name}>"
