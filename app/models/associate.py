"""
GFI v7.0 — Associate model.

Associates are linked to companies via the company_id FK (standard GFIBase).
The same physical person may appear in multiple companies (one row per company).
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Associate(GFIBase, Base):
    __tablename__ = "associate"

    # ── Identity ─────────────────────────────────────────────────────────
    canonical_name = Column(String(255), nullable=False)
    is_founder = Column(Boolean, nullable=False, server_default="false")
    role = Column(String(100), nullable=True)

    # ── CCA (Compte Courant d'Associé) ───────────────────────────────────
    has_cca = Column(Boolean, nullable=False, server_default="false")

    # ── Relationships ────────────────────────────────────────────────────
    company = relationship("Company", back_populates="associates")

    def __repr__(self):
        return f"<Associate {self.canonical_name} @ company_id={self.company_id}>"
